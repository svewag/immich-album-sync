from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from . import __version__
from .config import load_config
from .immich import ImmichClient
from . import log as log_module
from . import preflight
from . import sync


log = logging.getLogger("immich_alben")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="immich-alben",
        description="Sync NAS folder structure to Immich albums.",
    )
    p.add_argument(
        "--config",
        type=Path,
        default=Path(os.environ.get("IMMICH_ALBEN_CONFIG", "/config/config.yaml")),
        help="Path to config.yaml (default: /config/config.yaml or $IMMICH_ALBEN_CONFIG)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without writing to Immich.",
    )
    p.add_argument(
        "--only-path",
        type=str,
        default=None,
        help="Only process assets whose originalPath contains this substring.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    if not args.config.exists():
        print(f"error: config file not found: {args.config}", file=sys.stderr)
        return 2

    cfg = load_config(args.config)
    log_module.setup(cfg.logging.level)

    api_key = os.environ.get("IMMICH_API_KEY", "").strip()
    if not api_key:
        print("error: IMMICH_API_KEY env var is empty", file=sys.stderr)
        return 2

    if args.dry_run:
        print(f"=== DRY-RUN against {cfg.immich.base_url} ===")
    else:
        print(f"=== RUN against {cfg.immich.base_url} ===")
    if args.only_path:
        print(f"  only-path filter: {args.only_path!r}")

    with ImmichClient(cfg.immich.base_url, api_key, dry_run=args.dry_run) as client:
        print()
        print("=== Pre-flight ===")
        pre = preflight.run(client, cfg)
        if not pre.ok:
            print("pre-flight failed — aborting.", file=sys.stderr)
            return 1

        print()
        print("=== Planned actions ===" if args.dry_run else "=== Actions ===")
        sync.run(client, cfg, dry_run=args.dry_run, only_path=args.only_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
