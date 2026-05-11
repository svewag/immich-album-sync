from immich_alben.patterns import match_path


ROOTS = ["/mnt/photos", "/volume1/scans"]
PATTERNS = ["{root}/{year}/{album}", "{root}/{year}/{album}/{*}"]


def test_simple_match():
    m = match_path("/mnt/photos/2026/Geburtstagsfeier/IMG_001.jpg", PATTERNS, ROOTS)
    assert m is not None
    assert m.year == "2026"
    assert m.album == "Geburtstagsfeier"
    assert m.root == "/mnt/photos"


def test_match_second_root():
    m = match_path("/volume1/scans/1998/Diashow/scan001.tif", PATTERNS, ROOTS)
    assert m is not None
    assert m.year == "1998"
    assert m.album == "Diashow"
    assert m.root == "/volume1/scans"


def test_match_nested_with_star():
    m = match_path(
        "/mnt/photos/2026/Urlaub/Tag1/morning/IMG_042.jpg", PATTERNS, ROOTS
    )
    assert m is not None
    assert m.album == "Urlaub"
    assert m.year == "2026"


def test_no_match_outside_root():
    m = match_path("/upload/library/admin/IMG.heic", PATTERNS, ROOTS)
    assert m is None


def test_no_match_no_album_segment():
    # File directly under year, no album sub-folder
    m = match_path("/mnt/photos/2026/loose.jpg", PATTERNS, ROOTS)
    assert m is None


def test_no_match_year_not_4_digits():
    m = match_path("/mnt/photos/26/Urlaub/foo.jpg", PATTERNS, ROOTS)
    assert m is None


def test_first_pattern_wins():
    # Both patterns would match the simple case, but {root}/{year}/{album}
    # comes first and matches the bare 3-segment path.
    m = match_path("/mnt/photos/2024/Wandern/foo.jpg", PATTERNS, ROOTS)
    assert m is not None
    assert m.pattern == "{root}/{year}/{album}"


def test_album_with_special_chars():
    m = match_path("/mnt/photos/2026/Müllers Hochzeit/foo.jpg", PATTERNS, ROOTS)
    assert m is not None
    assert m.album == "Müllers Hochzeit"


def test_trailing_slash_in_root_normalized():
    roots_with_slash = ["/mnt/photos/"]
    m = match_path("/mnt/photos/2026/Urlaub/foo.jpg", PATTERNS, roots_with_slash)
    assert m is not None
    assert m.root == "/mnt/photos"
