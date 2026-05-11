import json
from pathlib import Path

from immich_alben.state import State, load, save


def test_load_missing_returns_empty(tmp_path: Path):
    state = load(tmp_path / "missing.json")
    assert state.albums == {}


def test_round_trip(tmp_path: Path):
    state = State.empty()
    state.set("2026", "Geburtstagsfeier", "uuid-1")
    state.set("2025", "Urlaub", "uuid-2")

    path = tmp_path / "state.json"
    save(path, state)
    loaded = load(path)

    assert loaded.albums == {
        ("2026", "Geburtstagsfeier"): "uuid-1",
        ("2025", "Urlaub"): "uuid-2",
    }


def test_save_is_atomic(tmp_path: Path):
    """No partial state file is visible: replace happens atomically."""
    path = tmp_path / "state.json"
    state = State.empty()
    state.set("2026", "X", "uuid-1")
    save(path, state)

    # No .tmp leftovers
    leftovers = list(tmp_path.glob(".state-*.tmp"))
    assert leftovers == []

    # File contains valid JSON
    raw = json.loads(path.read_text("utf-8"))
    assert raw["version"] == 1
    assert raw["albums"] == [{"year": "2026", "album": "X", "uuid": "uuid-1"}]


def test_remove(tmp_path: Path):
    state = State.empty()
    state.set("2026", "A", "uuid-a")
    state.remove("2026", "A")
    assert state.get("2026", "A") is None
    # remove of non-existing is a no-op
    state.remove("2099", "B")


def test_get(tmp_path: Path):
    state = State.empty()
    state.set("2026", "A", "uuid-a")
    assert state.get("2026", "A") == "uuid-a"
    assert state.get("2026", "B") is None
    assert state.get("2025", "A") is None
