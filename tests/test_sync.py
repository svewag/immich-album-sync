"""Security/behavior tests for sync logic.

These tests use a fake ImmichClient and verify the central invariant:
in dry-run mode, no write methods are ever called.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from immich_alben.config import Config, ImmichConfig, LoggingConfig
from immich_alben.immich import Album, Asset
from immich_alben.sync import run as run_sync


@dataclass
class FakeImmichClient:
    """Minimal stand-in for ImmichClient. Records calls."""
    assets: list[Asset]
    existing_albums: dict[str, Album] = field(default_factory=dict)
    created_albums: list[tuple[str, list[str]]] = field(default_factory=list)
    add_calls: list[tuple[str, list[str]]] = field(default_factory=list)
    get_album_calls: list[str] = field(default_factory=list)

    def iter_assets(self, page_size: int = 1000):
        for a in self.assets:
            yield a

    def get_album(self, album_id: str) -> Album | None:
        self.get_album_calls.append(album_id)
        return self.existing_albums.get(album_id)

    def create_album(self, name: str, asset_ids: list[str] | None = None) -> str:
        new_id = f"created-uuid-{len(self.created_albums) + 1}"
        self.created_albums.append((name, list(asset_ids or [])))
        self.existing_albums[new_id] = Album(
            id=new_id, name=name, asset_ids=set(asset_ids or [])
        )
        return new_id

    def add_assets_to_album(self, album_id: str, asset_ids: list[str]) -> dict:
        self.add_calls.append((album_id, list(asset_ids)))
        if album_id in self.existing_albums:
            self.existing_albums[album_id].asset_ids.update(asset_ids)
        return {"results": []}


def _cfg(tmp_path: Path) -> Config:
    return Config(
        immich=ImmichConfig(base_url="http://x"),
        library_roots=["/mnt/photos"],
        patterns=["{root}/{year}/{album}", "{root}/{year}/{album}/{*}"],
        state_file=tmp_path / "state.json",
        logging=LoggingConfig(level="WARN"),
    )


def _asset(id_: str, path: str, type_: str = "IMAGE") -> Asset:
    return Asset(id=id_, original_path=path, type=type_)


# ============================================================
# Critical invariant: dry-run never writes
# ============================================================

def test_dry_run_does_not_create_any_album(tmp_path: Path):
    assets = [
        _asset("a1", "/mnt/photos/2026/Geburtstagsfeier/01.jpg"),
        _asset("a2", "/mnt/photos/2026/Geburtstagsfeier/02.jpg"),
        _asset("a3", "/mnt/photos/2025/Urlaub/03.jpg"),
    ]
    client = FakeImmichClient(assets=assets)
    run_sync(client, _cfg(tmp_path), dry_run=True)

    assert client.created_albums == []
    assert client.add_calls == []


def test_dry_run_does_not_add_to_existing_album(tmp_path: Path):
    assets = [_asset("a1", "/mnt/photos/2026/Urlaub/01.jpg")]
    client = FakeImmichClient(
        assets=assets,
        existing_albums={
            "existing-uuid": Album(id="existing-uuid", name="Urlaub", asset_ids=set())
        },
    )
    # pre-seed state file so the bucket maps to existing-uuid
    state_file = tmp_path / "state.json"
    state_file.write_text(
        '{"version":1,"albums":[{"year":"2026","album":"Urlaub","uuid":"existing-uuid"}]}'
    )
    cfg = _cfg(tmp_path)
    run_sync(client, cfg, dry_run=True)

    assert client.add_calls == []
    assert client.created_albums == []


def test_dry_run_does_not_write_state_file(tmp_path: Path):
    assets = [_asset("a1", "/mnt/photos/2026/Urlaub/01.jpg")]
    client = FakeImmichClient(assets=assets)
    cfg = _cfg(tmp_path)

    run_sync(client, cfg, dry_run=True)
    assert not cfg.state_file.exists()


# ============================================================
# Real-run behavior (also checks we only call allowed ops)
# ============================================================

def test_real_run_creates_album_for_new_bucket(tmp_path: Path):
    assets = [
        _asset("a1", "/mnt/photos/2026/Geburtstag/01.jpg"),
        _asset("a2", "/mnt/photos/2026/Geburtstag/02.jpg"),
    ]
    client = FakeImmichClient(assets=assets)
    run_sync(client, _cfg(tmp_path), dry_run=False)

    assert len(client.created_albums) == 1
    name, ids = client.created_albums[0]
    assert name == "Geburtstag"
    assert sorted(ids) == ["a1", "a2"]
    assert client.add_calls == []  # no separate add — all in initial create


def test_real_run_adds_only_missing_assets_to_existing_album(tmp_path: Path):
    """Idempotency: assets already in the album are NOT re-added."""
    assets = [
        _asset("a1", "/mnt/photos/2026/Urlaub/01.jpg"),
        _asset("a2", "/mnt/photos/2026/Urlaub/02.jpg"),
        _asset("a3", "/mnt/photos/2026/Urlaub/03.jpg"),
    ]
    client = FakeImmichClient(
        assets=assets,
        existing_albums={
            "u-uuid": Album(id="u-uuid", name="Urlaub", asset_ids={"a1"})
        },
    )
    (tmp_path / "state.json").write_text(
        '{"version":1,"albums":[{"year":"2026","album":"Urlaub","uuid":"u-uuid"}]}'
    )
    run_sync(client, _cfg(tmp_path), dry_run=False)

    assert client.created_albums == []
    assert len(client.add_calls) == 1
    album_id, added_ids = client.add_calls[0]
    assert album_id == "u-uuid"
    assert sorted(added_ids) == ["a2", "a3"]


def test_real_run_skips_album_already_up_to_date(tmp_path: Path):
    assets = [
        _asset("a1", "/mnt/photos/2026/Urlaub/01.jpg"),
        _asset("a2", "/mnt/photos/2026/Urlaub/02.jpg"),
    ]
    client = FakeImmichClient(
        assets=assets,
        existing_albums={
            "u-uuid": Album(id="u-uuid", name="Urlaub", asset_ids={"a1", "a2"})
        },
    )
    (tmp_path / "state.json").write_text(
        '{"version":1,"albums":[{"year":"2026","album":"Urlaub","uuid":"u-uuid"}]}'
    )
    run_sync(client, _cfg(tmp_path), dry_run=False)

    assert client.created_albums == []
    assert client.add_calls == []


def test_real_run_recreates_album_when_state_stale(tmp_path: Path):
    """State references an album that no longer exists -> recreate."""
    assets = [_asset("a1", "/mnt/photos/2026/Urlaub/01.jpg")]
    client = FakeImmichClient(
        assets=assets,
        existing_albums={},  # the uuid in state does NOT exist in Immich
    )
    (tmp_path / "state.json").write_text(
        '{"version":1,"albums":[{"year":"2026","album":"Urlaub","uuid":"vanished"}]}'
    )
    run_sync(client, _cfg(tmp_path), dry_run=False)

    assert len(client.created_albums) == 1


def test_real_run_writes_state_file(tmp_path: Path):
    assets = [_asset("a1", "/mnt/photos/2026/Urlaub/01.jpg")]
    client = FakeImmichClient(assets=assets)
    cfg = _cfg(tmp_path)
    run_sync(client, cfg, dry_run=False)
    assert cfg.state_file.exists()


# ============================================================
# Filter behavior
# ============================================================

def test_only_path_filter_restricts_to_one_bucket(tmp_path: Path):
    assets = [
        _asset("a1", "/mnt/photos/2026/Geburtstag/01.jpg"),
        _asset("a2", "/mnt/photos/2026/Urlaub/01.jpg"),
        _asset("a3", "/mnt/photos/2025/Hochzeit/01.jpg"),
    ]
    client = FakeImmichClient(assets=assets)
    run_sync(client, _cfg(tmp_path), dry_run=False, only_path="Urlaub")

    assert len(client.created_albums) == 1
    name, ids = client.created_albums[0]
    assert name == "Urlaub"
    assert ids == ["a2"]


def test_only_path_filter_in_dry_run_still_writes_nothing(tmp_path: Path):
    assets = [_asset("a1", "/mnt/photos/2026/Geburtstag/01.jpg")]
    client = FakeImmichClient(assets=assets)
    run_sync(client, _cfg(tmp_path), dry_run=True, only_path="Geburtstag")
    assert client.created_albums == []
    assert client.add_calls == []


# ============================================================
# Unmatched handling: no fallback writes
# ============================================================

def test_unmatched_assets_are_not_written_anywhere(tmp_path: Path):
    """Assets outside library_roots / not matching any pattern must be ignored."""
    assets = [
        _asset("a1", "/upload/library/admin/IMG.heic"),
        _asset("a2", "/mnt/photos/screenshot.png"),  # no year/album segments
        _asset("a3", "/mnt/photos/2026/loose.jpg"),  # year but no album dir
    ]
    client = FakeImmichClient(assets=assets)
    run_sync(client, _cfg(tmp_path), dry_run=False)

    assert client.created_albums == []
    assert client.add_calls == []
