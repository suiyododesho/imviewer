"""Generate site/js/structure.js from site/structure.json."""

from __future__ import annotations

try:
    from .maint_structure_lib import load_structure, write_structure_js
except ImportError:
    from maint_structure_lib import load_structure, write_structure_js


def main() -> int:
    structure = load_structure()
    write_structure_js(structure)
    print("Generated site/js/structure.js")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())