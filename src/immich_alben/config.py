from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class ImmichConfig:
    base_url: str


@dataclass
class LoggingConfig:
    level: str


@dataclass
class Config:
    immich: ImmichConfig
    library_roots: list[str]
    patterns: list[str]
    state_file: Path
    logging: LoggingConfig


def load_config(path: Path) -> Config:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    immich = data.get("immich") or {}
    base_url = immich.get("base_url")
    if not base_url:
        raise ValueError("config: immich.base_url is required")

    library_roots = data.get("library_roots") or []
    if not isinstance(library_roots, list) or not library_roots:
        raise ValueError("config: library_roots must be a non-empty list")

    patterns = data.get("patterns") or []
    if not isinstance(patterns, list) or not patterns:
        raise ValueError("config: patterns must be a non-empty list")

    state_file = data.get("state_file")
    if not state_file:
        raise ValueError("config: state_file is required")

    logging_cfg = data.get("logging") or {}
    level = (logging_cfg.get("level") or "INFO").upper()

    return Config(
        immich=ImmichConfig(base_url=base_url.rstrip("/")),
        library_roots=[str(r) for r in library_roots],
        patterns=[str(p) for p in patterns],
        state_file=Path(state_file),
        logging=LoggingConfig(level=level),
    )
