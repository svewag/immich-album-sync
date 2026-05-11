from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class State:
    """In-memory representation of the state file.

    Maps (year, album_name) -> Immich album UUID.
    """
    albums: dict[tuple[str, str], str]

    @classmethod
    def empty(cls) -> "State":
        return cls(albums={})

    def get(self, year: str, album: str) -> str | None:
        return self.albums.get((year, album))

    def set(self, year: str, album: str, album_uuid: str) -> None:
        self.albums[(year, album)] = album_uuid

    def remove(self, year: str, album: str) -> None:
        self.albums.pop((year, album), None)


def load(path: Path) -> State:
    if not path.exists():
        return State.empty()
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    entries = data.get("albums", [])
    albums: dict[tuple[str, str], str] = {}
    for entry in entries:
        albums[(entry["year"], entry["album"])] = entry["uuid"]
    return State(albums=albums)


def save(path: Path, state: State) -> None:
    """Write state atomically: temp file then rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = [
        {"year": year, "album": album, "uuid": uuid}
        for (year, album), uuid in sorted(state.albums.items())
    ]
    payload = {"version": 1, "albums": entries}

    fd, tmp_path_str = tempfile.mkstemp(
        prefix=".state-", suffix=".json.tmp", dir=str(path.parent)
    )
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
