#!/usr/bin/env python3
"""Generate site/js/site-config.js from site/sitedesign.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parents[2]
else:
    ROOT = Path(__file__).resolve().parent.parent
SITE_DIR = ROOT / "site"
CONFIG_JSON_PATH = SITE_DIR / "sitedesign.json"
CONFIG_JS_PATH = SITE_DIR / "js" / "site-config.js"


def main() -> int:
    with CONFIG_JSON_PATH.open("r", encoding="utf-8") as handle:
        config = json.load(handle)

    CONFIG_JS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_JS_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("/**\n")
        handle.write(" * Auto-generated from site/sitedesign.json.\n")
        handle.write(" * Do not edit manually. Rebuild using tools/build_site_config.py\n")
        handle.write(" */\n\n")
        handle.write("window.siteConfig = ")
        json.dump(config, handle, ensure_ascii=False, indent=2)
        handle.write(";\n")

    print(f"Generated {CONFIG_JS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
