from __future__ import annotations

import logging
import sys


def setup(level: str = "INFO") -> logging.Logger:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%dT%H:%M:%S")
    )
    root.addHandler(handler)
    root.setLevel(getattr(logging, level, logging.INFO))
    return logging.getLogger("immich_alben")


def section(title: str) -> None:
    print()
    print(f"=== {title} ===")
