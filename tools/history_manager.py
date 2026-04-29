"""
Manage site/history.txt in YAML-based format.

Format
------
Released versions are recorded as named blocks; unreleased (pending) changes
live under the special ``next:`` block.

Example::

    v1.1:
      released: 2026-03-31 18:00:00
      dirs:
        - photo/aneone-p01/桜ここみ
        - photo/aneone-p01/南乃花

    next:
      dirs:
        - photo/aneone-p03/三津谷真希

Migration
---------
The parser automatically converts two legacy formats:

* **Old plain format** – bare ``TIMESTAMP ADD path`` lines, with optional
  ``RELEASE vX.Y TIMESTAMP`` markers.
* **Intermediate format** – ``next:`` header followed by
  ``- TIMESTAMP ADD path`` list items (user hand-edited transition state).
"""

import os
import re


def _version_sort_key(version_key: str) -> tuple[int, int]:
    """Return a comparable sort key for version labels like 'v1.4'."""
    cleaned = (version_key or '').strip().lstrip('v')
    parts = cleaned.split('.')
    try:
        major = int(parts[0])
    except (ValueError, IndexError):
        major = 0
    try:
        minor = int(parts[1])
    except (ValueError, IndexError):
        minor = 0
    return major, minor


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class HistoryData:
    def __init__(self):
        # [{'key': 'v1.1', 'released': '2026-03-31 18:00:00', 'dirs': [...], 'force_dirs': [...]}, ...]
        self.versions: list[dict] = []
        # Paths pending release (next: block)
        self.next_dirs: list[str] = []
        # Manually forced-in paths pending release (next: force_dirs block)
        self.next_force_dirs: list[str] = []

    def sort_versions(self) -> None:
        """Normalize released versions to newest-first order."""
        self.versions.sort(key=lambda v: _version_sort_key(v.get('key', '')), reverse=True)

    def all_known_dirs(self) -> set:
        """Return set of every path already recorded (released + pending)."""
        result: set[str] = set()
        for v in self.versions:
            result.update(v.get('dirs', []))
            result.update(v.get('force_dirs', []))
        result.update(self.next_dirs)
        result.update(self.next_force_dirs)
        return result

    def latest_version_key(self) -> str | None:
        """Return the key of the most recent released version, e.g. 'v1.4'."""
        self.sort_versions()
        return self.versions[0]['key'] if self.versions else None

    def previous_version_key(self) -> str | None:
        """Return the key before the latest version, or None."""
        self.sort_versions()
        return self.versions[1]['key'] if len(self.versions) >= 2 else None


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

_OLD_PLAIN_RE   = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} ADD ')
_OLD_RELEASE_RE = re.compile(r'^RELEASE (v[\d.]+) (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})')
_INTER_RE       = re.compile(r'^-\s+\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} ADD ')
_NEW_VER_RE     = re.compile(r'^v[\d.]+:\s*$')
_LIST_HDR_RE    = re.compile(r'^\s{2,}(dirs|force_dirs):\s*$')


def _detect_format(lines: list[str]) -> str:
    """Return 'new', 'old', 'intermediate', or 'empty'."""
    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        if _NEW_VER_RE.match(s):
            return 'new'
        if _LIST_HDR_RE.match(raw):   # indented 'dirs:' / 'force_dirs:' only appear in new format
            return 'new'
        if _OLD_PLAIN_RE.match(s) or _OLD_RELEASE_RE.match(s):
            return 'old'
        if _INTER_RE.match(s):
            return 'intermediate'
    return 'empty'


# ---------------------------------------------------------------------------
# Migration: old plain format
# ---------------------------------------------------------------------------

def _migrate_old(lines: list[str]) -> HistoryData:
    data = HistoryData()
    pending: list[str] = []
    for raw in lines:
        s = raw.rstrip()
        m = _OLD_PLAIN_RE.match(s)
        if m:
            pending.append(s.split(' ADD ', 1)[1])
            continue
        m = _OLD_RELEASE_RE.match(s)
        if m:
            data.versions.append({
                'key': m.group(1),
                'released': m.group(2),
                'dirs': list(pending),
            })
            pending = []
    data.next_dirs = list(pending)
    return data


# ---------------------------------------------------------------------------
# Migration: intermediate format  (next: header + "- TIMESTAMP ADD path" items)
# ---------------------------------------------------------------------------

_INTER_ITEM_RE  = re.compile(r'^-\s+\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} ADD (.+)$')
_PLAIN_ITEM_RE  = re.compile(r'^-\s+(.+)$')


def _extract_path_from_inter_item(s: str) -> str | None:
    m = _INTER_ITEM_RE.match(s)
    if m:
        return m.group(1).strip()
    m = _PLAIN_ITEM_RE.match(s)
    if m:
        return m.group(1).strip()
    return None


def _migrate_intermediate(lines: list[str]) -> HistoryData:
    """Convert hand-edited 'next: / - TIMESTAMP ADD path' format."""
    data = HistoryData()
    in_next_block = False
    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        # A versioned block (e.g. v1.1:) that might also appear
        if _NEW_VER_RE.match(s):
            in_next_block = False
            continue
        if s == 'next:' or s.startswith('next:'):
            in_next_block = True
            continue
        if in_next_block:
            path = _extract_path_from_inter_item(s)
            if path:
                data.next_dirs.append(path)
    return data


# ---------------------------------------------------------------------------
# New YAML-like format parser
# ---------------------------------------------------------------------------

_KEY_RE      = re.compile(r'^(v[\d.]+|next):\s*$')
_RELEASE_RE  = re.compile(r'^\s{2}released:\s*(.+)$')
_ITEM_RE     = re.compile(r'^\s{4,}-\s+(.+)$')


def _parse_new(lines: list[str]) -> HistoryData:
    data = HistoryData()
    current_key: str | None = None
    current_released: str = ''
    current_dirs: list[str] = []
    current_force_dirs: list[str] = []
    current_list_name: str | None = None

    def flush():
        nonlocal current_key, current_released, current_dirs, current_force_dirs, current_list_name
        if current_key is None:
            return
        if current_key == 'next':
            data.next_dirs = list(current_dirs)
            data.next_force_dirs = list(current_force_dirs)
        else:
            data.versions.append({
                'key': current_key,
                'released': current_released,
                'dirs': list(current_dirs),
                'force_dirs': list(current_force_dirs),
            })
        current_key = None
        current_released = ''
        current_dirs = []
        current_force_dirs = []
        current_list_name = None

    for raw in lines:
        line = raw.rstrip('\n\r')
        if not line.strip():
            continue

        m = _KEY_RE.match(line)
        if m:
            flush()
            current_key = m.group(1)
            continue

        if current_key is None:
            continue

        m = _RELEASE_RE.match(line)
        if m:
            current_released = m.group(1).strip()
            continue

        m = _LIST_HDR_RE.match(line)
        if m:
            current_list_name = m.group(1)
            continue

        if current_list_name:
            m = _ITEM_RE.match(line)
            if m:
                value = m.group(1).strip()
                if current_list_name == 'force_dirs':
                    current_force_dirs.append(value)
                else:
                    current_dirs.append(value)

    flush()
    return data


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_history(path: str) -> HistoryData:
    """Parse history.txt and return HistoryData.

    Automatically handles three legacy formats (old-plain, intermediate,
    new-YAML) as well as an empty / missing file.
    """
    if not os.path.isfile(path):
        return HistoryData()
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    if not lines:
        return HistoryData()

    fmt = _detect_format(lines)
    if fmt == 'old':
        data = _migrate_old(lines)
    elif fmt == 'intermediate':
        data = _migrate_intermediate(lines)
    elif fmt == 'new':
        data = _parse_new(lines)
    else:
        data = HistoryData()

    data.sort_versions()
    return data


def write_history(path: str, data: HistoryData) -> None:
    """Write HistoryData back to history.txt in the standard YAML-based format."""
    lines: list[str] = []
    data.sort_versions()

    lines.append('next:\n')
    lines.append('  force_dirs:\n')
    for d in data.next_force_dirs:
        lines.append(f"    - {d}\n")
    lines.append('  dirs:\n')
    for d in data.next_dirs:
        lines.append(f"    - {d}\n")
    lines.append('\n')

    for v in data.versions:
        lines.append(f"{v['key']}:\n")
        lines.append(f"  released: {v['released']}\n")
        lines.append('  force_dirs:\n')
        for d in v.get('force_dirs', []):
            lines.append(f"    - {d}\n")
        lines.append('  dirs:\n')
        for d in v.get('dirs', []):
            lines.append(f"    - {d}\n")
        lines.append('\n')

    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.writelines(lines)
