"""Thin Immich API client with a hard whitelist of allowed operations.

SECURITY: This client is intentionally restrictive. The only Immich endpoints
it will EVER call are listed in _READ_OPS / _WRITE_OPS below. Any other
request raises ImmichError before hitting the network.

Allowed writes are strictly:
  - POST /api/albums          (create album)
  - PUT  /api/albums/{id}/assets  (add assets to an existing album)

No deletes, no updates, no asset modifications. DO NOT add other write
operations without explicit review.

NOTE: Immich's API paths change between versions. The constants below were
chosen for Immich >= v1.106 (current path scheme). If the API moves, adjust
the constants at the top of this module.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Iterator

import httpx


log = logging.getLogger("immich_alben.immich")


PATH_PING_PRIMARY = "/api/server/ping"
PATH_PING_LEGACY = "/api/server-info/ping"
PATH_ME = "/api/users/me"
PATH_SEARCH = "/api/search/metadata"
PATH_ALBUMS = "/api/albums"

_UUID_SEG = r"[A-Za-z0-9_\-]+"

_READ_OPS: list[tuple[str, re.Pattern[str]]] = [
    ("GET",  re.compile(r"^/api/server/ping$")),
    ("GET",  re.compile(r"^/api/server-info/ping$")),
    ("GET",  re.compile(r"^/api/users/me$")),
    ("POST", re.compile(r"^/api/search/metadata$")),  # search, not a mutation
    ("GET",  re.compile(r"^/api/albums$")),
    ("GET",  re.compile(rf"^/api/albums/{_UUID_SEG}$")),
]

_WRITE_OPS: list[tuple[str, re.Pattern[str]]] = [
    ("POST", re.compile(r"^/api/albums$")),
    ("PUT",  re.compile(rf"^/api/albums/{_UUID_SEG}/assets$")),
]


@dataclass
class Asset:
    id: str
    original_path: str
    type: str
    latitude: float | None = None
    longitude: float | None = None
    file_created_at: str | None = None

    @classmethod
    def from_api(cls, raw: dict) -> "Asset":
        exif = raw.get("exifInfo") or {}
        return cls(
            id=raw["id"],
            original_path=raw.get("originalPath") or "",
            type=raw.get("type", ""),
            latitude=_to_float_or_none(exif.get("latitude")),
            longitude=_to_float_or_none(exif.get("longitude")),
            file_created_at=raw.get("fileCreatedAt") or raw.get("localDateTime"),
        )


def _to_float_or_none(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


@dataclass
class Album:
    id: str
    name: str
    asset_ids: set[str]

    @classmethod
    def from_api(cls, raw: dict) -> "Album":
        assets = raw.get("assets") or []
        return cls(
            id=raw["id"],
            name=raw.get("albumName", ""),
            asset_ids={a["id"] for a in assets if "id" in a},
        )


class ImmichError(RuntimeError):
    pass


def _match(method: str, path: str, ops: list[tuple[str, re.Pattern[str]]]) -> bool:
    for op_method, op_regex in ops:
        if op_method == method and op_regex.match(path):
            return True
    return False


class ImmichClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        dry_run: bool = False,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.dry_run = dry_run
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"x-api-key": api_key, "Accept": "application/json"},
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "ImmichClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # --- Whitelist enforcement ---

    def _check_allowed(self, method: str, path: str) -> None:
        method = method.upper()
        if _match(method, path, _READ_OPS):
            return
        if _match(method, path, _WRITE_OPS):
            if self.dry_run:
                raise ImmichError(
                    f"dry-run: refusing write {method} {path}"
                )
            return
        raise ImmichError(
            f"client whitelist: refusing {method} {path} — not on allow list"
        )

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        self._check_allowed(method, path)
        return self._client.request(method, path, **kwargs)

    # --- Health / Auth ---

    def ping(self) -> bool:
        for path in (PATH_PING_PRIMARY, PATH_PING_LEGACY):
            try:
                r = self._request("GET", path)
                if r.status_code == 200:
                    return True
            except httpx.HTTPError as e:
                log.debug("ping via %s failed: %s", path, e)
        return False

    def me(self) -> dict:
        r = self._request("GET", PATH_ME)
        if r.status_code != 200:
            raise ImmichError(f"GET {PATH_ME} -> {r.status_code}: {r.text[:200]}")
        return r.json()

    # --- Assets ---

    def iter_assets(self, page_size: int = 1000) -> Iterator[Asset]:
        """Yield all assets via paginated /search/metadata."""
        page: str | int | None = 1
        while page is not None:
            body = {"size": page_size, "page": str(page)}
            r = self._request("POST", PATH_SEARCH, json=body)
            if r.status_code != 200:
                raise ImmichError(
                    f"POST {PATH_SEARCH} (page={page}) -> {r.status_code}: {r.text[:200]}"
                )
            data = r.json()
            assets_block = data.get("assets") or {}
            items = assets_block.get("items") or []
            for item in items:
                yield Asset.from_api(item)
            next_page = assets_block.get("nextPage")
            page = next_page if next_page else None

    # --- Albums ---

    def list_albums(self) -> list[dict]:
        r = self._request("GET", PATH_ALBUMS)
        if r.status_code != 200:
            raise ImmichError(f"GET {PATH_ALBUMS} -> {r.status_code}: {r.text[:200]}")
        return r.json()

    def get_album(self, album_id: str) -> Album | None:
        r = self._request("GET", f"{PATH_ALBUMS}/{album_id}")
        if r.status_code == 404:
            return None
        if r.status_code != 200:
            raise ImmichError(
                f"GET {PATH_ALBUMS}/{album_id} -> {r.status_code}: {r.text[:200]}"
            )
        return Album.from_api(r.json())

    def create_album(self, name: str, asset_ids: list[str] | None = None) -> str:
        body: dict = {"albumName": name}
        if asset_ids:
            body["assetIds"] = asset_ids
        r = self._request("POST", PATH_ALBUMS, json=body)
        if r.status_code not in (200, 201):
            raise ImmichError(
                f"POST {PATH_ALBUMS} -> {r.status_code}: {r.text[:200]}"
            )
        return r.json()["id"]

    def add_assets_to_album(self, album_id: str, asset_ids: list[str]) -> dict:
        """Returns the Immich response: list of {id, success, error?} per asset."""
        if not asset_ids:
            return {"results": []}
        r = self._request(
            "PUT", f"{PATH_ALBUMS}/{album_id}/assets", json={"ids": asset_ids}
        )
        if r.status_code not in (200, 201):
            raise ImmichError(
                f"PUT {PATH_ALBUMS}/{album_id}/assets -> {r.status_code}: {r.text[:200]}"
            )
        return {"results": r.json()}
