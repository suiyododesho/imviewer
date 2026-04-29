"""Release tool for separated system/data version management.

Usage
-----
    python tools/release.py system
    python tools/release.py system --major
    python tools/release.py system --dry-run

    python tools/release.py data
    python tools/release.py data --dry-run
    python tools/release.py data --rollback
    python tools/release.py data --rollback --version v1.2

For backward compatibility, omitting the mode defaults to ``data``.
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from history_manager import parse_history, write_history  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SITE_DIR = os.path.join(ROOT, "site")
CONTENTS_DIR = os.path.join(SITE_DIR, "contents")
PHOTO_ROOT = os.path.join(CONTENTS_DIR, "photo")
THUMBNAIL_DIR = os.path.join(SITE_DIR, "thumbnail")
BANNER_DIR = os.path.join(SITE_DIR, "banner")
HISTORY_PATH = os.path.join(SITE_DIR, "history.txt")
STRUCTURE_JSON_PATH = os.path.join(SITE_DIR, "structure.json")
VERSION_DATA_PATH = os.path.join(SITE_DIR, "version_data.txt")
LEGACY_VERSION_DATA_PATH = os.path.join(SITE_DIR, "version.txt")
VERSION_SYS_PATH = os.path.join(SITE_DIR, "version_sys.txt")
RELEASES_DIR = os.path.join(ROOT, "releases")

DATA_FIXED_TARGETS = [
    ("structure.json", os.path.join(SITE_DIR, "structure.json")),
    ("js/structure.js", os.path.join(SITE_DIR, "js", "structure.js")),
    ("js/gallery-pages.js", os.path.join(SITE_DIR, "js", "gallery-pages.js")),
    ("history.txt", HISTORY_PATH),
    ("version_data.txt", VERSION_DATA_PATH),
    ("★データの追加方法.png", os.path.join(SITE_DIR, "★データの追加方法.png")),
]

SYSTEM_EXCLUDED_TOP_LEVEL = {"contents", "thumbnail"}


# ---------------------------------------------------------------------------
# Version helpers
# ---------------------------------------------------------------------------

def _clean_version(version_str: str) -> str:
    cleaned = (version_str or "").strip().lstrip("v")
    return cleaned or "1.0"


def _parse_version(version_str: str) -> tuple[int, int]:
    cleaned = _clean_version(version_str)
    parts = cleaned.split(".")
    try:
        major = int(parts[0])
    except (ValueError, IndexError):
        major = 1
    try:
        minor = int(parts[1])
    except (ValueError, IndexError):
        minor = 0
    return major, minor


def _read_version(path: str, default: str = "1.0") -> str:
    if not os.path.isfile(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        value = f.read().strip()
    return value or default


def _write_version(path: str, version_str: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(_clean_version(version_str) + "\n")


def _ensure_data_version_file() -> None:
    if os.path.isfile(VERSION_DATA_PATH):
        return
    if os.path.isfile(LEGACY_VERSION_DATA_PATH):
        legacy_version = _read_version(LEGACY_VERSION_DATA_PATH, default="1.0")
        _write_version(VERSION_DATA_PATH, legacy_version)
        return
    _write_version(VERSION_DATA_PATH, "1.0")


def _bump_minor(version_str: str) -> str:
    major, minor = _parse_version(version_str)
    return f"{major}.{minor + 1}"


def _bump_major(version_str: str) -> str:
    major, _minor = _parse_version(version_str)
    return f"{major + 1}.0"


def _decrement_minor(version_str: str) -> str:
    major, minor = _parse_version(version_str)
    return f"{major}.{max(0, minor - 1)}"


# ---------------------------------------------------------------------------
# Structure.json-based filtering helpers
# ---------------------------------------------------------------------------


def _normalize_release_rel_path(path: str) -> str:
    normalized = str(path or "").strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.lstrip("/")


def _is_same_or_child_path(path: str, parent: str) -> bool:
    return path == parent or path.startswith(parent + "/")


def _collapse_directory_paths(paths: list[str]) -> list[str]:
    collapsed: list[str] = []
    for raw_path in sorted(set(paths)):
        normalized = _normalize_release_rel_path(raw_path).rstrip("/")
        if not normalized:
            continue
        if any(_is_same_or_child_path(normalized, existing) for existing in collapsed):
            continue
        collapsed = [existing for existing in collapsed if not _is_same_or_child_path(existing, normalized)]
        collapsed.append(normalized)
    return collapsed


def _load_structure_json() -> dict:
    if not os.path.isfile(STRUCTURE_JSON_PATH):
        return {}
    with open(STRUCTURE_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _collect_structure_release_targets() -> tuple[set[str], set[str], set[str]]:
    structure = _load_structure_json()
    photo_dirs: set[str] = set()
    thumbnail_paths: set[str] = set()
    banner_paths: set[str] = set()

    def add_photo_target(raw_path: str) -> None:
        normalized = _normalize_release_rel_path(raw_path)
        if not normalized or "://" in normalized or normalized.startswith(("#", "mailto:", "javascript:")):
            return
        if normalized.startswith("contents/photo/"):
            normalized = normalized[len("contents/"):]
        if not normalized.startswith("photo/"):
            return

        if normalized == "photo":
            return

        ext = os.path.splitext(normalized)[1].lower()
        if ext:
            parent = os.path.dirname(normalized).replace("\\", "/").rstrip("/")
            if parent:
                photo_dirs.add(parent)
            return

        photo_dirs.add(normalized.rstrip("/"))

    def visit(node) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, str):
                    normalized = _normalize_release_rel_path(value)
                    if key in {"path", "url"}:
                        add_photo_target(normalized)
                    elif key == "thumbnail" and normalized.startswith("thumbnail/"):
                        thumbnail_paths.add(normalized)
                    elif key == "banner" and normalized.startswith("banner/"):
                        banner_paths.add(normalized)
                visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(structure)
    return photo_dirs, thumbnail_paths, banner_paths


def _is_referenced_photo_dir(photo_path: str, referenced_dirs: set[str]) -> bool:
    normalized = _normalize_release_rel_path(photo_path)
    if normalized.startswith("contents/"):
        normalized = normalized[len("contents/"):]
    normalized = normalized.rstrip("/")

    if not normalized.startswith("photo/"):
        return False

    return any(
        ref == normalized
        or ref.startswith(normalized + "/")
        or normalized.startswith(ref + "/")
        for ref in referenced_dirs
    )


def _split_releasable_photo_dirs(photo_paths: list[str], force_dirs: list[str] | None = None) -> tuple[list[str], list[str]]:
    referenced_dirs, _thumbnail_paths, _banner_paths = _collect_structure_release_targets()
    releasable: list[str] = []
    skipped: list[str] = []
    normalized_force_dirs = _collapse_directory_paths(force_dirs or [])

    for raw_path in sorted(set(photo_paths)):
        normalized = _normalize_release_rel_path(raw_path)
        if normalized.startswith("contents/"):
            normalized = normalized[len("contents/"):]
        normalized = normalized.rstrip("/")

        if _is_referenced_photo_dir(normalized, referenced_dirs):
            releasable.append(normalized)
        else:
            skipped.append(normalized)

    releasable = _collapse_directory_paths(releasable + normalized_force_dirs)
    skipped = [
        path for path in _collapse_directory_paths(skipped)
        if not any(_is_same_or_child_path(path, forced) for forced in normalized_force_dirs)
    ]
    return releasable, skipped


# ---------------------------------------------------------------------------
# Zip helpers
# ---------------------------------------------------------------------------

def _add_path_to_zip(zf: zipfile.ZipFile, abs_path: str, arc_path: str) -> None:
    arc_path = arc_path.replace("\\", "/")
    if os.path.isfile(abs_path):
        zf.write(abs_path, arc_path)
        return
    if not os.path.isdir(abs_path):
        print(f"  警告: パスが見つからないためスキップします: {abs_path}")
        return

    for root, dirs, files in os.walk(abs_path):
        dirs.sort(key=str.lower)
        files.sort(key=str.lower)
        for fname in files:
            file_abs = os.path.join(root, fname)
            rel = os.path.relpath(file_abs, abs_path).replace("\\", "/")
            zf.write(file_abs, f"{arc_path}/{rel}")


def _iter_system_targets() -> list[tuple[str, str]]:
    targets = []
    for name in sorted(os.listdir(SITE_DIR), key=str.lower):
        if name in SYSTEM_EXCLUDED_TOP_LEVEL:
            continue
        targets.append((name, os.path.join(SITE_DIR, name)))
    return targets


def _create_system_zip(tag_name: str, dry_run: bool = False) -> str:
    date_str = datetime.datetime.now().strftime("%Y%m%d")
    zip_name = f"xcity-photobook_{tag_name}_{date_str}.zip"
    zip_path = os.path.join(RELEASES_DIR, zip_name)
    targets = _iter_system_targets()

    if dry_run:
        print(f"\n[DRY RUN] 作成予定のシステムパッケージ: {zip_path}")
        print("[DRY RUN] site/ 直下の同梱対象:")
        for arc_name, _ in targets:
            print(f"  {arc_name}")
        print("[DRY RUN] 除外対象:")
        print("  contents/")
        print("  thumbnail/")
        return zip_path

    os.makedirs(RELEASES_DIR, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for arc_name, abs_path in targets:
            _add_path_to_zip(zf, abs_path, arc_name)
    return zip_path


def _create_data_zip(version_tag: str, photo_paths: list[str], dry_run: bool = False) -> str:
    date_str = datetime.datetime.now().strftime("%Y%m%d")
    zip_name = f"xcity-photodata_{version_tag}_{date_str}.zip"
    zip_path = os.path.join(RELEASES_DIR, zip_name)
    unique_photo_paths = sorted(set(photo_paths))
    _referenced_dirs, thumbnail_paths, banner_paths = _collect_structure_release_targets()

    if dry_run:
        print(f"\n[DRY RUN] 作成予定のデータパッケージ: {zip_path}")
        print("[DRY RUN] 変更対象の photo ディレクトリ:")
        for p in unique_photo_paths:
            print(f"  contents/{p}")
        print("[DRY RUN] structure.json に含まれる同梱対象:")
        if thumbnail_paths:
            print(f"  thumbnail/ ({len(thumbnail_paths)} files)")
        if banner_paths:
            print(f"  banner/ ({len(banner_paths)} files)")
        for arc_name, _ in DATA_FIXED_TARGETS:
            print(f"  {arc_name}")
        return zip_path

    os.makedirs(RELEASES_DIR, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for photo_path in unique_photo_paths:
            abs_dir = os.path.join(CONTENTS_DIR, photo_path)
            arc_name = f"contents/{photo_path}"
            _add_path_to_zip(zf, abs_dir, arc_name)

        for thumb_path in sorted(thumbnail_paths):
            _add_path_to_zip(zf, os.path.join(SITE_DIR, thumb_path), thumb_path)
        for banner_path in sorted(banner_paths):
            _add_path_to_zip(zf, os.path.join(SITE_DIR, banner_path), banner_path)

        for arc_name, abs_path in DATA_FIXED_TARGETS:
            _add_path_to_zip(zf, abs_path, arc_name)
    return zip_path


# ---------------------------------------------------------------------------
# Git helpers (system release only)
# ---------------------------------------------------------------------------

def _run_git(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _ensure_git_tag_available(tag_name: str) -> None:
    probe = _run_git(["rev-parse", "--is-inside-work-tree"])
    if probe.returncode != 0:
        raise RuntimeError("Git リポジトリとして認識できません。system リリースタグを作成できません。")

    existing = _run_git(["tag", "--list", tag_name])
    if existing.returncode == 0 and existing.stdout.strip():
        raise RuntimeError(f"Git tag '{tag_name}' は既に存在します。")


def _create_git_tag(tag_name: str) -> None:
    result = _run_git(["tag", tag_name])
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"Git tag の作成に失敗しました: {detail}")


# ---------------------------------------------------------------------------
# Commands: system release
# ---------------------------------------------------------------------------

def cmd_system_release(args) -> None:
    current_version = _read_version(VERSION_SYS_PATH, default="1.0")
    new_version = _bump_major(current_version) if args.major else _bump_minor(current_version)
    tag_name = f"release_ver_{new_version}"

    print(f"現在のシステム版 : {current_version}")
    print(f"新しいシステム版 : {new_version}")
    print(f"Git tag          : {tag_name}")

    if args.dry_run:
        _create_system_zip(tag_name, dry_run=True)
        print(f"[DRY RUN] 作成予定の Git tag: {tag_name}")
        print("\n[DRY RUN] ファイルは変更していません。")
        return

    _ensure_git_tag_available(tag_name)
    _write_version(VERSION_SYS_PATH, new_version)
    zip_path = _create_system_zip(tag_name)
    _create_git_tag(tag_name)

    print(f"\nシステムパッケージを作成しました: {zip_path}")
    print(f"version_sys.txt         : {current_version} -> {new_version}")
    print(f"Git tag を作成しました    : {tag_name}")


# ---------------------------------------------------------------------------
# Commands: data release / rollback
# ---------------------------------------------------------------------------

def cmd_data_release(args) -> None:
    _ensure_data_version_file()
    data = parse_history(HISTORY_PATH)

    if not data.next_dirs and not getattr(data, "next_force_dirs", []):
        print("history.txt の next: ブロックに未リリースのデータ差分がありません。")
        return

    current_version = _read_version(VERSION_DATA_PATH, default="1.0")
    new_version = _bump_minor(current_version)
    version_tag = f"v{new_version}"
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    unique_dirs = sorted(set(data.next_dirs))
    force_dirs = _collapse_directory_paths(list(getattr(data, "next_force_dirs", [])))
    releasable_dirs, skipped_dirs = _split_releasable_photo_dirs(unique_dirs, force_dirs)

    print(f"現在のデータ版           : {current_version}")
    print(f"新しいデータ版           : {new_version}")
    print(f"リリース対象ディレクトリ数 : {len(releasable_dirs)}")
    for d in releasable_dirs:
        print(f"  {d}")

    if force_dirs:
        print("手動指定で同梱するディレクトリ:")
        for d in force_dirs:
            print(f"  {d}")

    if skipped_dirs:
        print("structure.json 未掲載のため今回除外するディレクトリ:")
        for d in skipped_dirs:
            print(f"  {d}")

    if not releasable_dirs:
        print("structure.json に含まれる未リリースデータがなく、force_dirs も空のためパッケージは作成しません。")
        print("history.txt / version_data.txt は変更していません。")
        return

    if args.dry_run:
        _create_data_zip(version_tag, releasable_dirs, dry_run=True)
        print("\n[DRY RUN] ファイルは変更していません。")
        return

    data.versions.insert(0, {
        "key": version_tag,
        "released": now_str,
        "force_dirs": force_dirs,
        "dirs": [d for d in releasable_dirs if not any(_is_same_or_child_path(d, forced) for forced in force_dirs)],
    })
    data.next_dirs = skipped_dirs
    data.next_force_dirs = []
    write_history(HISTORY_PATH, data)
    _write_version(VERSION_DATA_PATH, new_version)
    zip_path = _create_data_zip(version_tag, releasable_dirs)

    print(f"\nデータパッケージを作成しました: {zip_path}")
    print(f"version_data.txt        : {current_version} -> {new_version}")
    if skipped_dirs:
        print("history.txt             : structure.json 未掲載分は next: に残しました")
    else:
        print(f"history.txt             : next: を {version_tag} として確定しました")


def cmd_data_rollback(args) -> None:
    _ensure_data_version_file()
    data = parse_history(HISTORY_PATH)

    target_key = args.version or data.latest_version_key()
    if target_key is None:
        print("history.txt にロールバック対象のデータ版がありません。")
        return

    idx = next((i for i, v in enumerate(data.versions) if v["key"] == target_key), None)
    if idx is None:
        available = [v["key"] for v in data.versions]
        print(f"history.txt に指定版 '{target_key}' が見つかりません。")
        print(f"利用可能な版: {available or '(none)'}")
        return

    rollback_dirs = data.versions[idx].get("dirs", [])
    rollback_force_dirs = data.versions[idx].get("force_dirs", [])
    if idx + 1 < len(data.versions):
        restore_version = data.versions[idx + 1]["key"].lstrip("v")
    else:
        restore_version = _decrement_minor(target_key)

    print(f"ロールバック対象データ版 : {target_key}")
    print(f"復元するデータ版         : {restore_version}")
    print(f"next: に戻すディレクトリ数 : {len(rollback_dirs)}")
    for d in rollback_dirs:
        print(f"  {d}")
    if rollback_force_dirs:
        print(f"next: に戻す force_dirs 数 : {len(rollback_force_dirs)}")
        for d in rollback_force_dirs:
            print(f"  {d}")
    if data.next_dirs or getattr(data, "next_force_dirs", []):
        print(
            f"  (plus {len(data.next_dirs)} already-pending dirs"
            f" / {len(getattr(data, 'next_force_dirs', []))} force_dirs)"
        )

    if args.dry_run:
        print("\n[DRY RUN] ファイルは変更していません。")
        return

    data.versions.pop(idx)
    data.next_dirs = rollback_dirs + data.next_dirs
    data.next_force_dirs = rollback_force_dirs + list(getattr(data, "next_force_dirs", []))
    write_history(HISTORY_PATH, data)
    _write_version(VERSION_DATA_PATH, restore_version)

    print("\nデータのロールバックが完了しました。")
    print(f"version_data.txt -> {restore_version}")
    print("history.txt -> 対象版を削除し、dirs / force_dirs を next: に戻しました")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Separated release tool for system/data packages.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python tools/release.py system
  python tools/release.py system --major
  python tools/release.py system --dry-run
  python tools/release.py data
  python tools/release.py data --dry-run
  python tools/release.py data --rollback
  python tools/release.py data --rollback --version v1.2
  python tools/release.py --dry-run  # defaults to data mode
""",
    )
    parser.add_argument(
        "mode",
        nargs="?",
        choices=["data", "system"],
        default="data",
        help="Which release target to operate on. Default: data",
    )
    parser.add_argument(
        "--major",
        action="store_true",
        help="For system mode only: bump major version (x.y -> x+1.0).",
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="For data mode only: roll back the last (or --version specified) data release.",
    )
    parser.add_argument(
        "--version",
        metavar="VERSION",
        default=None,
        help="Version key for data rollback, e.g. v1.2",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview actions without modifying any files.",
    )
    args = parser.parse_args()

    if args.mode == "system":
        if args.rollback:
            parser.error("--rollback is only available in data mode.")
        if args.version:
            parser.error("--version is only available with data --rollback.")
        cmd_system_release(args)
        return

    if args.major:
        parser.error("--major is only available in system mode.")

    if args.rollback:
        cmd_data_rollback(args)
    else:
        cmd_data_release(args)


if __name__ == "__main__":
    main()

