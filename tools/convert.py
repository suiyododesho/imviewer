"""Convert legacy gallery videos to browser-friendly MP4/H.264.

Usage examples:
    python tools/convert.py
    python tools/convert.py --config tools/convert_config.json
    python tools/convert.py --dry-run
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from typing import Any

import convert_vlc

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOOLS_DIR = os.path.join(ROOT, "tools")
DEFAULT_PHOTO_DIR = os.path.join(ROOT, "site", "contents", "photo")
DEFAULT_CONFIG_PATH = os.path.join(TOOLS_DIR, "convert_config.json")
ERROR_LOG_PATH = os.path.join(ROOT, "convert.error")
TARGET_EXTENSIONS = (".avi", ".mpg", ".mpeg", ".mkv", ".wmv", ".mov")
DEFAULT_CONFIG = {
    "ffmpeg_path": "",
    "vlc_path": "",
    "upscale": False,
    "resolution": "",
    "frame_rate": "",
    "bit_rate": "",
    "quality": 24,
    "ffmpeg_options": "",
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
    if not path:
        return sanitize_config(config)
    if not os.path.isfile(path):
        log(f"config not found, defaults will be used: {path}")
        return sanitize_config(config)

    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        log(f"failed to read config, defaults will be used: {exc}")
        return sanitize_config(config)

    if isinstance(raw, dict):
        config.update(raw)
    return sanitize_config(config)


def sanitize_config(config: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(DEFAULT_CONFIG)

    ffmpeg_path = str(config.get("ffmpeg_path", "") or "").strip()
    if ffmpeg_path:
        sanitized["ffmpeg_path"] = ffmpeg_path

    vlc_path = str(config.get("vlc_path", "") or "").strip()
    if vlc_path:
        sanitized["vlc_path"] = vlc_path

    sanitized["upscale"] = parse_bool(config.get("upscale", DEFAULT_CONFIG["upscale"]), DEFAULT_CONFIG["upscale"])

    resolution = str(config.get("resolution", "") or "").strip().lower()
    if re.fullmatch(r"\d{2,5}x\d{2,5}", resolution):
        sanitized["resolution"] = resolution

    frame_rate = str(config.get("frame_rate", "") or "").strip()
    if frame_rate:
        try:
            frame_rate_value = float(frame_rate)
            if frame_rate_value > 0:
                if frame_rate_value.is_integer():
                    sanitized["frame_rate"] = str(int(frame_rate_value))
                else:
                    sanitized["frame_rate"] = str(frame_rate_value)
        except ValueError:
            pass

    bit_rate = str(config.get("bit_rate", "") or "").strip()
    if re.fullmatch(r"\d+(?:\.\d+)?[kKmM]?", bit_rate):
        sanitized["bit_rate"] = bit_rate

    try:
        quality = int(config.get("quality", DEFAULT_CONFIG["quality"]))
        if 0 <= quality <= 51:
            sanitized["quality"] = quality
    except (TypeError, ValueError):
        pass

    ffmpeg_options = config.get("ffmpeg_options", "")
    if isinstance(ffmpeg_options, str):
        sanitized["ffmpeg_options"] = ffmpeg_options.strip()

    return sanitized


def iter_source_files(photo_dir: str) -> list[str]:
    if not os.path.isdir(photo_dir):
        return []

    files: list[str] = []
    for root, dirs, names in os.walk(photo_dir):
        dirs.sort(key=str.lower)
        names.sort(key=str.lower)
        for name in names:
            if os.path.splitext(name)[1].lower() in TARGET_EXTENSIONS:
                files.append(os.path.join(root, name))
    return files


def build_output_path(source_path: str) -> str:
    base, _ext = os.path.splitext(source_path)
    return base + ".mp4"


def build_ffmpeg_command(
    source_path: str,
    output_path: str,
    config: dict[str, Any],
    ffmpeg_bin: str,
    overwrite: bool,
) -> list[str]:
    command = [
        ffmpeg_bin,
        "-hide_banner",
        "-y" if overwrite else "-n",
        "-i",
        source_path,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        str(config["quality"]),
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
    ]

    filters: list[str] = []

    if config.get("resolution"):
        width, height = str(config["resolution"]).split("x", 1)
        filters.append(
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
        )
    elif config.get("upscale"):
        filters.append("scale='if(lt(ih,480),-2,iw)':'if(lt(ih,480),480,ih)'")

    if filters:
        command.extend(["-vf", ",".join(filters)])

    if config.get("frame_rate"):
        command.extend(["-r", str(config["frame_rate"])])

    if config.get("bit_rate"):
        command.extend(["-b:v", str(config["bit_rate"])])

    extra_options = str(config.get("ffmpeg_options", "") or "").strip()
    if extra_options:
        command.extend(shlex.split(extra_options, posix=False))

    command.extend(["-progress", "pipe:1", "-nostats", output_path])
    return command


def resolve_ffmpeg_bin(cli_ffmpeg: str, config: dict[str, Any]) -> str:
    cli_value = str(cli_ffmpeg or "").strip()
    config_value = str(config.get("ffmpeg_path", "") or "").strip()

    if cli_value and cli_value != "ffmpeg":
        return cli_value
    if config_value:
        return config_value
    return cli_value or "ffmpeg"


def ensure_ffmpeg_available(ffmpeg_bin: str) -> None:
    if os.path.isabs(ffmpeg_bin) and os.path.isfile(ffmpeg_bin):
        return
    if shutil.which(ffmpeg_bin):
        return
    raise FileNotFoundError(f"ffmpeg was not found: {ffmpeg_bin}")


def convert_file(
    source_path: str,
    output_path: str,
    config: dict[str, Any],
    ffmpeg_bin: str,
    overwrite: bool,
    dry_run: bool,
) -> tuple[str, str | None]:
    relative_source = display_path(source_path)
    relative_output = display_path(output_path)

    if os.path.exists(output_path) and not overwrite:
        log(f"SKIP  {relative_source} -> {relative_output} (mp4 already exists)")
        return "skipped", None

    command = build_ffmpeg_command(source_path, output_path, config, ffmpeg_bin, overwrite)

    log(f"START {relative_source}")
    if dry_run:
        print(f"        {subprocess.list2cmdline(command)}")
        log(f"DONE  {relative_output} (dry-run)")
        return "converted", None

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    combined_output: list[str] = []
    if process.stdout is not None:
        for line in process.stdout:
            combined_output.append(line)
            stripped = line.strip()
            if stripped.startswith("out_time="):
                print(f"        progress {stripped.split('=', 1)[1]}")

    return_code = process.wait()
    if return_code == 0:
        log(f"DONE  {relative_output}")
        return "converted", None

    error_text = "".join(combined_output).strip() or f"ffmpeg exited with code {return_code}"
    if os.path.isfile(output_path) and os.path.getsize(output_path) == 0:
        os.remove(output_path)
    return "failed", error_text


def try_vlc_fallback(
    source_path: str,
    config: dict[str, Any],
    vlc_bin: str,
    overwrite: bool,
    dry_run: bool,
) -> tuple[str, str | None]:
    log(f"FALLBACK {display_path(source_path)} -> VLC")
    try:
        if not dry_run:
            convert_vlc.ensure_vlc_available(vlc_bin)
    except FileNotFoundError as exc:
        return "failed", str(exc)
    return convert_vlc.convert_file(source_path, vlc_bin, overwrite, dry_run, config)


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
        description="Convert AVI/MPG/MPEG/MKV/WMV files under site/contents/photo to MP4/H.264."
    )
    parser.add_argument(
        "--config",
        default=None,
        help=f"Optional JSON config path. Example: {DEFAULT_CONFIG_PATH}",
    )
    parser.add_argument(
        "--photo-dir",
        default=DEFAULT_PHOTO_DIR,
        help="Directory to scan for source video files.",
    )
    parser.add_argument(
        "--ffmpeg",
        default="ffmpeg",
        help="ffmpeg executable path or command name.",
    )
    parser.add_argument(
        "--vlc",
        default="vlc",
        help="vlc executable path or command name for fallback conversion.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing MP4 files if they already exist.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be converted without running ffmpeg.",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    ffmpeg_bin = resolve_ffmpeg_bin(args.ffmpeg, config)
    vlc_bin = convert_vlc.resolve_vlc_bin(args.vlc, config)
    source_files = iter_source_files(args.photo_dir)

    if not os.path.isdir(args.photo_dir):
        print(f"photo directory not found: {args.photo_dir}")
        return 1

    if not source_files:
        print("no convertible video files were found.")
        return 0

    ffmpeg_available = True
    if not args.dry_run:
        try:
            ensure_ffmpeg_available(ffmpeg_bin)
        except FileNotFoundError as exc:
            print(str(exc))
            print("FFmpeg is unavailable. VLC fallback will be used for all targets.")
            ffmpeg_available = False

    print("=== Video Convert Tool ===")
    print(f"photo dir : {args.photo_dir}")
    print(f"ffmpeg    : {ffmpeg_bin}")
    print(f"vlc       : {vlc_bin}")
    print(f"targets   : {len(source_files)} files")
    print(f"config    : resolution={config['resolution'] or '(same as source)'}, "
          f"frame_rate={config['frame_rate'] or '(same as source)'}, "
          f"bit_rate={config['bit_rate'] or '(auto)'}, quality={config['quality']}, "
          f"upscale={config['upscale']}")
    if config.get("ffmpeg_options"):
        print(f"options   : {config['ffmpeg_options']}")
    print()

    converted = 0
    skipped = 0
    errors: list[tuple[str, str]] = []

    for source_path in source_files:
        output_path = build_output_path(source_path)

        if ffmpeg_available:
            status, detail = convert_file(
                source_path,
                output_path,
                config,
                ffmpeg_bin,
                args.overwrite,
                args.dry_run,
            )
        else:
            status = "failed"
            detail = f"ffmpeg was not found: {ffmpeg_bin}"

        if status == "converted":
            converted += 1
            continue
        if status == "skipped":
            skipped += 1
            continue

        if detail:
            print(detail)

        fallback_status, fallback_detail = try_vlc_fallback(
            source_path,
            config,
            vlc_bin,
            args.overwrite,
            args.dry_run,
        )
        if fallback_status == "converted":
            converted += 1
        elif fallback_status == "skipped":
            skipped += 1
        else:
            combined_detail = (
                f"FFmpeg error:\n{detail or 'unknown error'}\n\n"
                f"VLC error:\n{fallback_detail or 'unknown error'}"
            )
            errors.append((display_path(source_path), combined_detail))
            print(fallback_detail)

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
