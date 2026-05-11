from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field

from .config import Config
from .immich import ImmichClient, ImmichError
from .patterns import Match, match_path
from .state import State, load as load_state, save as save_state


log = logging.getLogger("immich_alben.sync")


@dataclass
class Bucket:
    year: str
    album: str
    asset_ids: list[str] = field(default_factory=list)


@dataclass
class SyncStats:
    albums_created: int = 0
    albums_updated: int = 0
    assets_added: int = 0
    unmatched_total: int = 0
    unmatched_examples: list[str] = field(default_factory=list)
    only_path_filter: str | None = None


def run(
    client: ImmichClient,
    cfg: Config,
    *,
    dry_run: bool,
    only_path: str | None = None,
) -> SyncStats:
    stats = SyncStats(only_path_filter=only_path)

    state = load_state(cfg.state_file)
    log.info("loaded state with %d album entries", len(state.albums))

    buckets, stats.unmatched_total, stats.unmatched_examples = _build_buckets(
        client, cfg, only_path
    )
    log.info("collected %d buckets across %d total matched assets",
             len(buckets), sum(len(b.asset_ids) for b in buckets.values()))

    for (year, album_name), bucket in sorted(buckets.items()):
        _process_bucket(client, state, bucket, stats, dry_run=dry_run)

    if not dry_run:
        save_state(cfg.state_file, state)
        log.info("saved state to %s", cfg.state_file)
    else:
        log.info("dry-run: state file NOT saved")

    _print_summary(stats, dry_run=dry_run)
    return stats


def _build_buckets(
    client: ImmichClient, cfg: Config, only_path: str | None
) -> tuple[dict[tuple[str, str], Bucket], int, list[str]]:
    buckets: dict[tuple[str, str], Bucket] = defaultdict(lambda: Bucket(year="", album=""))
    unmatched_total = 0
    unmatched_examples: list[str] = []

    for asset in client.iter_assets():
        if only_path and only_path not in asset.original_path:
            continue
        m: Match | None = match_path(asset.original_path, cfg.patterns, cfg.library_roots)
        if m is None:
            unmatched_total += 1
            if len(unmatched_examples) < 10:
                unmatched_examples.append(asset.original_path)
            continue
        key = (m.year, m.album)
        if not buckets[key].year:
            buckets[key] = Bucket(year=m.year, album=m.album)
        buckets[key].asset_ids.append(asset.id)

    return dict(buckets), unmatched_total, unmatched_examples


def _process_bucket(
    client: ImmichClient,
    state: State,
    bucket: Bucket,
    stats: SyncStats,
    *,
    dry_run: bool,
) -> None:
    label = f'"{bucket.album}" (year={bucket.year}, {len(bucket.asset_ids)} assets)'
    album_uuid = state.get(bucket.year, bucket.album)

    album = None
    if album_uuid:
        try:
            album = client.get_album(album_uuid)
        except ImmichError as e:
            log.warning("could not fetch album %s: %s", album_uuid, e)
        if album is None:
            log.warning("stale state: album %s missing, will recreate", album_uuid)
            if not dry_run:
                state.remove(bucket.year, bucket.album)
            album_uuid = None

    if album_uuid is None:
        if dry_run:
            print(f"  NEW ALBUM: {label}  [+{len(bucket.asset_ids)} assets]")
            stats.albums_created += 1
            stats.assets_added += len(bucket.asset_ids)
            return
        try:
            new_id = client.create_album(bucket.album, asset_ids=bucket.asset_ids)
        except ImmichError as e:
            log.error("failed to create album %s: %s", label, e)
            return
        state.set(bucket.year, bucket.album, new_id)
        stats.albums_created += 1
        stats.assets_added += len(bucket.asset_ids)
        log.info("created album %s -> uuid=%s", label, new_id)
        return

    # Existing album: diff
    existing_ids = album.asset_ids if album else set()
    if dry_run:
        new_ids = [aid for aid in bucket.asset_ids if aid not in existing_ids]
        if new_ids:
            print(
                f"  UPDATE ALBUM: {label} uuid={album_uuid}  "
                f"[+{len(new_ids)} new, {len(existing_ids)} already in]"
            )
            stats.albums_updated += 1
            stats.assets_added += len(new_ids)
        else:
            print(f"  UP-TO-DATE: {label} uuid={album_uuid}")
        return
    new_ids = [aid for aid in bucket.asset_ids if aid not in existing_ids]
    if not new_ids:
        log.info("album %s already up to date", label)
        return
    try:
        client.add_assets_to_album(album_uuid, new_ids)
    except ImmichError as e:
        log.error("failed to add assets to album %s: %s", label, e)
        return
    stats.albums_updated += 1
    stats.assets_added += len(new_ids)
    log.info("added %d assets to album %s", len(new_ids), label)


def _print_summary(stats: SyncStats, *, dry_run: bool) -> None:
    print()
    print("=== Summary ===")
    if dry_run:
        print("  (dry-run mode — nothing was written to Immich)")
    if stats.only_path_filter:
        print(f"  only-path filter: {stats.only_path_filter!r}")
    print(f"  Albums to create / created : {stats.albums_created}")
    print(f"  Albums to update / updated : {stats.albums_updated}")
    print(f"  Assets to add / added      : {stats.assets_added}")
    print(f"  Unmatched assets           : {stats.unmatched_total}")
    if stats.unmatched_examples:
        print("  Unmatched examples:")
        for ex in stats.unmatched_examples[:10]:
            print(f"    {ex}")
