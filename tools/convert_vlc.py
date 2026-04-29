"""VLC-based converter for legacy videos to MP4/H.264 with deinterlace.

Usage examples:
    python tools/convert_vlc.py "path/to/movie.wmv"
    python tools/convert_vlc.py "path/to/folder"
    python tools/convert_vlc.py --config tools/convert_config.json --dry-run "path/to/movie.wmv"
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
from typing import Any

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOOLS_DIR = os.path.join(ROOT, "tools")
DEFAULT_CONFIG_PATH = os.path.join(TOOLS_DIR, "convert_config.json")
ERROR_LOG_PATH = os.path.join(ROOT, "convert.error")
TARGET_EXTENSIONS = (".avi", ".mpg", ".mpeg", ".mkv", ".wmv", ".mov")
DEFAULT_CONFIG = {
    "vlc_path": "",
    "ffmpeg_path": "",
    "upscale": False,
}


def now_text() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(message: str) -> None:
    print(f"[{now_text()}] {message}")


def display_path(path: str) -> str:
    try:
        return os.path.relpath(path, ROOT)
    except ValueError:
        return os.path.abspath(path)


def parse_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "on", "y"}:
        return True
    if text in {"0", "false", "no", "off", "n"}:
        return False
    return default


def load_config(path: str | None) -> dict[str, Any]:
    config = dict(DEFAULT_CONFIG)
    config_path = path or DEFAULT_CONFIG_PATH
    if not os.path.isfile(config_path):
        return sanitize_config(config)

    try:
        with open(config_path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        log(f"failed to read config, defaults will be used: {exc}")
        return sanitize_config(config)

    if isinstance(raw, dict):
        config.update(raw)
    return sanitize_config(config)


def sanitize_config(config: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(DEFAULT_CONFIG)

    vlc_path = str(config.get("vlc_path", "") or "").strip()
    if vlc_path:
        sanitized["vlc_path"] = vlc_path

    ffmpeg_path = str(config.get("ffmpeg_path", "") or "").strip()
    if ffmpeg_path:
        sanitized["ffmpeg_path"] = ffmpeg_path

    sanitized["upscale"] = parse_bool(config.get("upscale", DEFAULT_CONFIG["upscale"]), DEFAULT_CONFIG["upscale"])
    return sanitized


def resolve_vlc_bin(cli_vlc: str, config: dict[str, Any]) -> str:
    cli_value = str(cli_vlc or "").strip()
    config_value = str(config.get("vlc_path", "") or "").strip()
    if cli_value and cli_value.lower() not in {"vlc", "vlc.exe"}:
        return cli_value
    if config_value:
        return config_value
    return cli_value or "vlc"


def ensure_vlc_available(vlc_bin: str) -> None:
    if os.path.isabs(vlc_bin) and os.path.isfile(vlc_bin):
        return
    if shutil.which(vlc_bin):
        return
    raise FileNotFoundError(f"vlc was not found: {vlc_bin}")


def iter_video_files(root_dir: str) -> list[str]:
    files: list[str] = []
    for root, dirs, names in os.walk(root_dir):
        dirs.sort(key=str.lower)
        names.sort(key=str.lower)
        for name in names:
            if os.path.splitext(name)[1].lower() in TARGET_EXTENSIONS:
                files.append(os.path.join(root, name))
    return files


def collect_targets(inputs: list[str]) -> tuple[list[str], list[str]]:
    found: list[str] = []
    missing: list[str] = []
    seen: set[str] = set()

    for raw in inputs:
        candidate = os.path.abspath(os.path.expanduser(str(raw).strip().strip('"')))
        if not candidate:
            continue
        if os.path.isdir(candidate):
            for path in iter_video_files(candidate):
                if path not in seen:
                    found.append(path)
                    seen.add(path)
            continue
        if os.path.isfile(candidate):
            if candidate not in seen:
                found.append(candidate)
                seen.add(candidate)
            continue
        missing.append(candidate)

    return found, missing


def build_output_path(source_path: str) -> str:
    base, _ext = os.path.splitext(source_path)
    return base + ".mp4"


def resolve_ffprobe_bin(config: dict[str, Any]) -> str:
    ffmpeg_path = str(config.get("ffmpeg_path", "") or "").strip()
    if ffmpeg_path:
        if os.path.isdir(ffmpeg_path):
            candidate = os.path.join(ffmpeg_path, "ffprobe.exe")
        else:
            candidate = os.path.join(os.path.dirname(ffmpeg_path), "ffprobe.exe")
        if os.path.isfile(candidate):
            return candidate
    return "ffprobe"


def probe_video_size(source_path: str, config: dict[str, Any]) -> tuple[int, int] | None:
    ffprobe_bin = resolve_ffprobe_bin(config)
    try:
        completed = subprocess.run(
            [
                ffprobe_bin,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "csv=p=0:s=x",
                source_path,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        return None

    if completed.returncode != 0:
        return None

    text = completed.stdout.strip()
    if "x" not in text:
        return None

    width_str, height_str = text.split("x", 1)
    try:
        return int(width_str), int(height_str)
    except ValueError:
        return None


def get_upscale_size(source_path: str, config: dict[str, Any], min_height: int = 480) -> tuple[int, int] | None:
    if not config.get("upscale"):
        return None

    size = probe_video_size(source_path, config)
    if not size:
        return None

    width, height = size
    if width <= 0 or height <= 0 or height >= min_height:
        return None

    new_width = max(2, int(round(width * min_height / height)))
    if new_width % 2 != 0:
        new_width += 1
    return new_width, min_height


def build_vlc_command(
    source_path: str,
    output_path: str,
    vlc_bin: str,
    upscale_size: tuple[int, int] | None = None,
) -> list[str]:
    dst_path = output_path.replace("\\", "/")
    transcode_parts = ["vcodec=h264", "acodec=mp3"]
    if upscale_size:
        width, height = upscale_size
        transcode_parts.append(f"width={width}")
        transcode_parts.append(f"height={height}")
    sout = (
        f"#transcode{{{','.join(transcode_parts)}}}:"
        f"standard{{access=file,mux=mp4,dst={dst_path}}}"
    )
    return [
        vlc_bin,
        "--intf",
        "dummy",
        "--video-filter=deinterlace",
        "--deinterlace-mode=yadif",
        "--no-video-title-show",
        source_path,
        "--sout",
        sout,
        "vlc://quit",
    ]


def convert_file(
    source_path: str,
    vlc_bin: str,
    overwrite: bool,
    dry_run: bool,
    config: dict[str, Any] | None = None,
) -> tuple[str, str | None]:
    output_path = build_output_path(source_path)
    relative_source = display_path(source_path)
    relative_output = display_path(output_path)

    if os.path.abspath(source_path) == os.path.abspath(output_path):
        log(f"SKIP  {relative_source} (source is already .mp4)")
        return "skipped", None

    if os.path.exists(output_path):
        if not overwrite:
            log(f"SKIP  {relative_source} -> {relative_output} (mp4 already exists)")
            return "skipped", None
        os.remove(output_path)

    effective_config = config or DEFAULT_CONFIG
    upscale_size = get_upscale_size(source_path, effective_config)
    command = build_vlc_command(source_path, output_path, vlc_bin, upscale_size)

    log(f"START {relative_source}")
    if upscale_size:
        log(f"UPSCALE {relative_source} -> {upscale_size[0]}x{upscale_size[1]}")
    if dry_run:
        print(f"        {subprocess.list2cmdline(command)}")
        log(f"DONE  {relative_output} (dry-run)")
        return "converted", None

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if completed.returncode == 0 and os.path.isfile(output_path):
        log(f"DONE  {relative_output}")
        return "converted", None

    detail = (completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else "")
    detail = detail.strip() or f"vlc exited with code {completed.returncode}"
    if os.path.isfile(output_path) and os.path.getsize(output_path) == 0:
        os.remove(output_path)
    return "failed", detail


def write_error_log(errors: list[tuple[str, str]]) -> None:
    if not errors:
        if os.path.exists(ERROR_LOG_PATH):
            os.remove(ERROR_LOG_PATH)
        return

    with open(ERROR_LOG_PATH, "w", encoding="utf-8", newline="\n") as fh:
        for path, detail in errors:
            fh.write(f"[{now_text()}]\n")
            fh.write(f"file: {path}\n")
            fh.write("error:\n")
            fh.write(detail.rstrip() + "\n")
            fh.write("-" * 72 + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert videos with VLC deinterlace to MP4/H.264."
    )
    parser.add_argument("paths", nargs="*", help="Video files or folders to convert.")
    parser.add_argument("--config", default=None, help="Optional JSON config path.")
    parser.add_argument("--vlc", default="vlc", help="vlc executable path or command name.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing MP4 files.")
    parser.add_argument("--dry-run", action="store_true", help="Preview commands without conversion.")
    args = parser.parse_args()

    if not args.paths:
        print("no input path was provided.")
        return 1

    config = load_config(args.config)
    vlc_bin = resolve_vlc_bin(args.vlc, config)
    targets, missing = collect_targets(args.paths)

    for item in missing:
        print(f"path not found: {item}")

    if not targets:
        print("no convertible video files were found.")
        return 1 if missing else 0

    if not args.dry_run:
        try:
            ensure_vlc_available(vlc_bin)
        except FileNotFoundError as exc:
            print(str(exc))
            write_error_log([("vlc", str(exc))])
            return 1

    print("=== VLC Video Convert Tool ===")
    print(f"vlc      : {vlc_bin}")
    print(f"targets  : {len(targets)} files")
    print(f"mode     : deinterlace=yadif, output=mp4/h264, upscale={config['upscale']}")
    print()

    converted = 0
    skipped = 0
    errors: list[tuple[str, str]] = []

    for source_path in targets:
        status, detail = convert_file(source_path, vlc_bin, args.overwrite, args.dry_run, config)
        if status == "converted":
            converted += 1
        elif status == "skipped":
            skipped += 1
        else:
            errors.append((display_path(source_path), detail or "unknown error"))
            print(detail)

    write_error_log(errors)

    print()
    print("=== Summary ===")
    print(f"converted : {converted}")
    print(f"skipped   : {skipped}")
    print(f"failed    : {len(errors)}")
    if errors:
        print(f"error log : {ERROR_LOG_PATH}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
