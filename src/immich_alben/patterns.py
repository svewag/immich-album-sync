from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


PLACEHOLDER_RE = re.compile(r"\{(root|year|album|\*)\}")


@dataclass(frozen=True)
class Match:
    year: str
    album: str
    root: str
    pattern: str


@dataclass(frozen=True)
class CompiledPattern:
    raw: str
    regex: re.Pattern[str]


def compile_pattern(pattern: str, roots: Iterable[str]) -> list[CompiledPattern]:
    """Compile a template pattern into one regex per root.

    Placeholders:
      {root}  -> literal root path (one per configured root)
      {year}  -> (?P<year>\\d{4})
      {album} -> (?P<album>[^/]+)
      {*}     -> (?:[^/]+/)* — zero or more path segments, ignored
    """
    if "{root}" not in pattern:
        raise ValueError(f"Pattern must contain {{root}}: {pattern!r}")
    if "{year}" not in pattern:
        raise ValueError(f"Pattern must contain {{year}}: {pattern!r}")
    if "{album}" not in pattern:
        raise ValueError(f"Pattern must contain {{album}}: {pattern!r}")

    compiled: list[CompiledPattern] = []
    for root in roots:
        normalized_root = root.rstrip("/")
        regex_str = _build_regex(pattern, normalized_root)
        compiled.append(CompiledPattern(raw=pattern, regex=re.compile(regex_str)))
    return compiled


def _build_regex(pattern: str, root: str) -> str:
    """Build a regex that matches a FILE path against the directory pattern.

    {album} is always a directory segment, so the regex always expects at
    least one filename segment at the end. If the pattern already ends with
    {*} (which itself consumes 1+ path segments), no extra filename suffix
    is appended.
    """
    parts: list[str] = ["^"]
    pos = 0
    last_token: str | None = None
    for m in PLACEHOLDER_RE.finditer(pattern):
        literal = pattern[pos:m.start()]
        parts.append(re.escape(literal))
        token = m.group(1)
        last_token = token
        if token == "root":
            parts.append(re.escape(root))
        elif token == "year":
            parts.append(r"(?P<year>\d{4})")
        elif token == "album":
            parts.append(r"(?P<album>[^/]+)")
        elif token == "*":
            parts.append(r"(?:[^/]+/)*[^/]+")
        pos = m.end()
    trailing_literal = pattern[pos:]
    parts.append(re.escape(trailing_literal))

    if last_token != "*" and not trailing_literal:
        parts.append(r"/[^/]+")
    parts.append("$")
    return "".join(parts)


def match_path(
    path: str,
    patterns: list[str],
    roots: list[str],
) -> Match | None:
    """Try each (pattern, root) combination. Return first match or None."""
    for pattern in patterns:
        for root in roots:
            compiled = compile_pattern(pattern, [root])[0]
            m = compiled.regex.match(path)
            if m:
                return Match(
                    year=m.group("year"),
                    album=m.group("album"),
                    root=root.rstrip("/"),
                    pattern=pattern,
                )
    return None
