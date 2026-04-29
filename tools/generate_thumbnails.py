#!/usr/bin/env python3
from __future__ import annotations
import os
import sys
import json
from collections import OrderedDict, defaultdict
from pathlib import Path
from PIL import Image

SITE_DIR = Path("site")
CONTENTS = SITE_DIR / "contents"
PHOTO_DIR = CONTENTS / "photo"
THUMB_DIR = SITE_DIR / "thumbnail"


def sanitize_filename(s: str) -> str:
    return s.replace(" ", "_")


def find_gallery_dir(gallery_path: str) -> Path:
    # gallery_path is like "photo/honey2/Name 01/index_...html"
    full = CONTENTS / gallery_path
    return full.parent


def find_candidate_image(gdir: Path) -> Path | None:
    patterns = [
        "*.jpg",
        "*.jpeg",
        "*.png",
        "*.gif",
        "*.webp",
        "src/*.jpg",
        "src/*.jpeg",
        "src/*.png",
        "src/*.webp",
    ]
    candidates = []
    for pat in patterns:
        for p in sorted(gdir.glob(pat)):
            candidates.append(p)
    if not candidates:
        return None
    # prefer files with 001 or 01 in name
    for p in candidates:
        if "001" in p.name or "01" in p.name:
            return p
    return candidates[0]


def ensure_thumb_dir() -> None:
    THUMB_DIR.mkdir(parents=True, exist_ok=True)


def make_thumbnail(src: Path, dst: Path, max_size=(320, 240)) -> None:
    with Image.open(src) as im:
        im.thumbnail(max_size)
        rgb = im.convert("RGB")
        rgb.save(dst, format="JPEG", quality=85)


def load_structure(path: Path) -> OrderedDict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f, object_pairs_hook=OrderedDict)


def write_structure(path: Path, data: OrderedDict) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main() -> int:
    struct_path = SITE_DIR / "structure.json"
    if not struct_path.exists():
        print("structure.json not found", file=sys.stderr)
        return 2
    data = load_structure(struct_path)

    ensure_thumb_dir()

    person_counters = defaultdict(int)
    updated = 0
    created_files = []
    failed = []

    for project, proj_val in list(data.items()):
        if not isinstance(proj_val, dict):
            continue
        for key, person_val in list(proj_val.items()):
            # skip project-level metadata
            if key in ("label", "banner", "series"):
                continue
            if not isinstance(person_val, dict):
                continue
            person = key
            galleries = person_val.get("galleries", [])
            for g in galleries:
                thumb = g.get("thumbnail", "")
                gpath = g.get("path")
                if not gpath:
                    continue
                # check existing thumbnail file exists
                if thumb:
                    tpath = SITE_DIR / thumb
                    if tpath.exists():
                        continue
                gdir = find_gallery_dir(gpath)
                img = find_candidate_image(gdir)
                if img is None:
                    failed.append((project, person, gpath, "no image found"))
                    continue
                person_counters[(project, person)] += 1
                seq = person_counters[(project, person)]
                fname = f"{sanitize_filename(project)}_{sanitize_filename(person)}_{seq:03d}.jpg"
                dst = THUMB_DIR / fname
                # avoid overwrite
                dup = 1
                base = dst
                while dst.exists():
                    dst = THUMB_DIR / f"{base.stem}_dup{dup}{base.suffix}"
                    dup += 1
                try:
                    make_thumbnail(img, dst)
                    g["thumbnail"] = f"thumbnail/{dst.name}"
                    updated += 1
                    created_files.append(str(dst))
                except Exception as e:
                    failed.append((project, person, gpath, str(e)))

    if updated:
        write_structure(struct_path, data)

    # report
    print(f"projects scanned: {len(data)}")
    print(f"thumbnails created: {updated}")
    if created_files:
        print("created files:")
        for p in created_files[:50]:
            print(" -", p)
    if failed:
        print("failures:")
        for f in failed:
            print(" -", f)

    return 0


if __name__ == '__main__':
    sys.exit(main())
