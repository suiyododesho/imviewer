"""Compatibility wrapper for the full maintenance pipeline."""

from __future__ import annotations

import argparse
import os

try:
    from .build_site_config import main as build_site_config_main
    from .maint_metrics import RunMetrics
    from .maint_build_gallery_pages import main as build_gallery_pages_main
    from .maint_build_gallery_thumbnails import main as build_gallery_thumbnails_main
    from .maint_build_structure import main as build_structure_main
    from .maint_build_structure_js import main as build_structure_js_main
    from .maint_extract_archives import main as extract_archives_main
    from .maint_refresh_covers import main as refresh_covers_main
    from .maint_sync_history import main as sync_history_main
    from .maint_structure_lib import SITE_DIR
except ImportError:
    from build_site_config import main as build_site_config_main
    from maint_metrics import RunMetrics
    from maint_build_gallery_pages import main as build_gallery_pages_main
    from maint_build_gallery_thumbnails import main as build_gallery_thumbnails_main
    from maint_build_structure import main as build_structure_main
    from maint_build_structure_js import main as build_structure_js_main
    from maint_extract_archives import main as extract_archives_main
    from maint_refresh_covers import main as refresh_covers_main
    from maint_sync_history import main as sync_history_main
    from maint_structure_lib import SITE_DIR


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='Run the full maintenance pipeline')
    parser.add_argument('--diff', action='store_true', help='Run diff mode for gallery thumbnails and gallery-pages')
    parser.add_argument('--plan', action='store_true', help='Show execution plan only (no writes)')
    parser.add_argument('--dry-run', action='store_true', help='Alias of --plan')
    parser.add_argument('--metrics-log', default='', help='Optional JSONL output path for metrics log')
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    plan_mode = args.plan or args.dry_run
    diff_args = ['--diff'] if args.diff else []
    monitor_paths = [
        os.path.join(SITE_DIR, 'structure.json'),
        os.path.join(SITE_DIR, 'history.txt'),
        os.path.join(SITE_DIR, 'contents'),
        os.path.join(SITE_DIR, 'thumbnail'),
        os.path.join(SITE_DIR, 'js'),
    ]
    metrics = RunMetrics(
        pipeline='uc1-maintenance',
        mode='plan' if plan_mode else 'apply',
        log_path=args.metrics_log or None,
    )

    steps = [
        ('maint_build_structure', build_structure_main, ['--sync']),
        ('maint_extract_archives', extract_archives_main, []),
        ('maint_build_gallery_thumbnails', build_gallery_thumbnails_main, diff_args),
        ('maint_refresh_covers', refresh_covers_main, []),
        ('maint_build_structure_js', build_structure_js_main, []),
        ('maint_build_gallery_pages', build_gallery_pages_main, diff_args),
        ('build_site_config', build_site_config_main, []),
        ('maint_sync_history', sync_history_main, []),
    ]

    if plan_mode:
        print('Pipeline plan (no write):')
        for name, _func, step_args in steps:
            print(f"  - {name} {' '.join(step_args)}".rstrip())
            metrics.plan_stage(name, {'args': step_args})
        payload = metrics.finalize(success=True)
        print(f"Metrics log: {metrics.log_path}")
        if payload.get('compare'):
            compare = payload['compare']
            print(
                'Compare(previous): '
                f"duration_ms={compare['delta_duration_ms']}, "
                f"generated={compare['delta_generated_count']}, "
                f"transfer_files={compare['delta_transfer_files']}, "
                f"transfer_bytes={compare['delta_transfer_bytes']}"
            )
        return 0

    for name, func, step_args in steps:
        token = metrics.begin_stage(name, monitor_paths, {'args': step_args})
        rc = func(step_args) if step_args else func()
        if rc:
            metrics.end_stage(token, status='failed', details={'exit_code': rc})
            metrics.finalize(success=False)
            print(f'Metrics log: {metrics.log_path}')
            return rc
        metrics.end_stage(token, status='ok')

    payload = metrics.finalize(success=True)
    print(f'Metrics log: {metrics.log_path}')
    if payload.get('compare'):
        compare = payload['compare']
        print(
            'Compare(previous): '
            f"duration_ms={compare['delta_duration_ms']}, "
            f"generated={compare['delta_generated_count']}, "
            f"transfer_files={compare['delta_transfer_files']}, "
            f"transfer_bytes={compare['delta_transfer_bytes']}"
        )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
