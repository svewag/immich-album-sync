from __future__ import annotations

import logging
from dataclasses import dataclass

from .config import Config
from .immich import ImmichClient, ImmichError
from .patterns import match_path


log = logging.getLogger("immich_alben.preflight")


@dataclass
class PreflightResult:
    ok: bool
    immich_reachable: bool
    auth_valid: bool
    user_email: str | None
    sample_total: int
    sample_matched: int
    sample_unmatched_examples: list[str]


def run(client: ImmichClient, cfg: Config, sample_size: int = 50) -> PreflightResult:
    immich_reachable = client.ping()
    print(f"  Immich reachable: {'YES' if immich_reachable else 'NO'}")

    auth_valid = False
    user_email: str | None = None
    if immich_reachable:
        try:
            me = client.me()
            auth_valid = True
            user_email = me.get("email")
            print(f"  API key valid: YES (user: {user_email})")
        except ImmichError as e:
            print(f"  API key valid: NO ({e})")

    matched = 0
    total = 0
    unmatched_examples: list[str] = []
    if auth_valid:
        try:
            for asset in client.iter_assets(page_size=sample_size):
                total += 1
                m = match_path(asset.original_path, cfg.patterns, cfg.library_roots)
                if m:
                    matched += 1
                elif len(unmatched_examples) < 5:
                    unmatched_examples.append(asset.original_path)
                if total >= sample_size:
                    break
            print(f"  Pattern sample: {matched}/{total} matched")
            for ex in unmatched_examples:
                print(f"    unmatched example: {ex}")
        except ImmichError as e:
            print(f"  Pattern sample: FAILED ({e})")

    ok = immich_reachable and auth_valid
    return PreflightResult(
        ok=ok,
        immich_reachable=immich_reachable,
        auth_valid=auth_valid,
        user_email=user_email,
        sample_total=total,
        sample_matched=matched,
        sample_unmatched_examples=unmatched_examples,
    )
