# Thumbnail Extraction Tool

Reusable CLI tool:

- `tools/extract_thumbnails.py`

## What It Does

- Accepts one or more start HTML files.
- Finds linked non-index HTML pages from each start file.
- On each linked page, extracts thumbnail images tied to numbered HTML targets (for example `mai1.htm`, `maria02.html`).
- Saves images to `site/thumbnail/` by default.
- Uses filename format: `project_person_001.ext`.

## Usage

From the workspace root:

```powershell
python tools/extract_thumbnails.py "D:\Tool\_mytool\_bulk\xcity\webcrawler\output\juicyhoney_2\src\aja_archives_free_juicyhoney_honey2.html"
```

Multiple start files:

```powershell
python tools/extract_thumbnails.py "path\to\start1.html" "path\to\start2.html"
```

Optional flags:

- `--output-dir <path>`
- `--project-name <name>`
- `--encoding <encoding>`
- `--dry-run`

Example with options:

```powershell
python tools/extract_thumbnails.py "path\to\start.html" --output-dir "site\thumbnail" --dry-run
```

