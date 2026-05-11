"""Security tests: ensure the ImmichClient only allows whitelisted ops."""
from __future__ import annotations

import pytest

from immich_alben.immich import ImmichClient, ImmichError


@pytest.fixture
def client() -> ImmichClient:
    c = ImmichClient("http://example.invalid", "fake-key")
    yield c
    c.close()


@pytest.fixture
def dry_client() -> ImmichClient:
    c = ImmichClient("http://example.invalid", "fake-key", dry_run=True)
    yield c
    c.close()


# --- Allowed reads ---

@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/server/ping"),
        ("GET", "/api/server-info/ping"),
        ("GET", "/api/users/me"),
        ("POST", "/api/search/metadata"),
        ("GET", "/api/albums"),
        ("GET", "/api/albums/abc-123-def"),
    ],
)
def test_read_ops_pass_check(client: ImmichClient, method: str, path: str):
    client._check_allowed(method, path)  # must not raise


def test_read_ops_pass_in_dry_run(dry_client: ImmichClient):
    dry_client._check_allowed("GET", "/api/users/me")
    dry_client._check_allowed("POST", "/api/search/metadata")
    dry_client._check_allowed("GET", "/api/albums/abc-123")


# --- Allowed writes ---

def test_write_ops_pass_when_not_dry_run(client: ImmichClient):
    client._check_allowed("POST", "/api/albums")
    client._check_allowed("PUT", "/api/albums/abc-123/assets")


# --- Dry-run blocks writes ---

def test_dry_run_blocks_create_album(dry_client: ImmichClient):
    with pytest.raises(ImmichError, match="dry-run: refusing write"):
        dry_client._check_allowed("POST", "/api/albums")


def test_dry_run_blocks_add_assets(dry_client: ImmichClient):
    with pytest.raises(ImmichError, match="dry-run: refusing write"):
        dry_client._check_allowed("PUT", "/api/albums/abc-123/assets")


# --- Forbidden ops (any mode) ---

@pytest.mark.parametrize(
    "method,path",
    [
        ("DELETE", "/api/albums/abc-123"),
        ("DELETE", "/api/albums/abc-123/assets"),
        ("DELETE", "/api/assets/abc-123"),
        ("DELETE", "/api/assets"),
        ("PATCH", "/api/albums/abc-123"),
        ("PUT", "/api/albums/abc-123"),
        ("POST", "/api/assets/trash"),
        ("PUT", "/api/users/me"),
        ("GET", "/api/some/random/path"),
        ("POST", "/api/albums/abc-123/share"),
    ],
)
def test_forbidden_ops_rejected(client: ImmichClient, method: str, path: str):
    with pytest.raises(ImmichError, match="not on allow list"):
        client._check_allowed(method, path)


def test_forbidden_ops_rejected_in_dry_run_too(dry_client: ImmichClient):
    with pytest.raises(ImmichError, match="not on allow list"):
        dry_client._check_allowed("DELETE", "/api/albums/abc-123")


# --- Live methods route through whitelist (no network access in unit test) ---

def test_create_album_in_dry_run_raises_before_network(dry_client: ImmichClient):
    """If we ever call create_album() in dry-run, it must fail before HTTP."""
    with pytest.raises(ImmichError, match="dry-run: refusing write"):
        dry_client.create_album("MyAlbum", asset_ids=["a", "b"])


def test_add_assets_in_dry_run_raises_before_network(dry_client: ImmichClient):
    with pytest.raises(ImmichError, match="dry-run: refusing write"):
        dry_client.add_assets_to_album("abc-123", ["a", "b"])
