#!/usr/bin/env python3
# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "fonttools>=4.63,<5.0",
#     "regex>=2025.9,<2027",
# ]
# ///
"""Normalize project emoji in source files and rebuild the web emoji font."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import tempfile
import urllib.request

import regex
from fontTools import subset
from fontTools.ttLib import TTFont

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_FONT = REPO_ROOT / "web" / "static" / "fonts" / "HomeDashboardEmoji.ttf"
CACHE_DIR = Path.home() / ".cache" / "home-dashboard-emoji"
SOURCE_FONT_NAME = "NotoColorEmoji-v2.051.ttf"
SOURCE_URL = (
    "https://raw.githubusercontent.com/googlefonts/noto-emoji/"
    "v2.051/fonts/NotoColorEmoji.ttf"
)
SOURCE_SHA256 = "72a635cb3d2f3524c51620cdde406b217204e8a6a06c6a096ff8ed4b5fd6e27b"

SOURCE_DIRS = ("src", "web", "config")
TEXT_EXTENSIONS = {
    ".css",
    ".html",
    ".jinja",
    ".jinja2",
    ".js",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}

GRAPHEME_RE = regex.compile(r"\X")
EMOJI_RE = regex.compile(r"\p{Emoji}")
EMOJI_CLUSTER_RE = regex.compile(r"\p{Emoji_Presentation}|\p{Extended_Pictographic}|\uFE0F|\u200D")


def _is_standalone_emoji(cluster: str) -> bool:
    """Return whether a single code point should be forced to emoji presentation."""
    if len(cluster) != 1:
        return False
    codepoint = ord(cluster)
    if codepoint in {0x23, 0x2A} or 0x30 <= codepoint <= 0x39:
        return False
    if 0x1F1E6 <= codepoint <= 0x1F1FF:
        return False
    return bool(EMOJI_RE.fullmatch(cluster))


def normalize_emoji(text: str) -> str:
    """Force emoji presentation for standalone emoji-capable characters."""
    normalized: list[str] = []
    for cluster in GRAPHEME_RE.findall(text):
        if _is_standalone_emoji(cluster):
            cluster += "\ufe0f"
        elif (
            len(cluster) == 2
            and cluster[1] == "\ufe0e"
            and _is_standalone_emoji(cluster[0])
        ):
            cluster = f"{cluster[0]}\ufe0f"
        normalized.append(cluster)
    return "".join(normalized)


def extract_emoji(text: str) -> set[str]:
    """Return emoji grapheme clusters that the generated font must cover."""
    return {
        cluster
        for cluster in GRAPHEME_RE.findall(text)
        if EMOJI_CLUSTER_RE.search(cluster)
    }


def iter_source_files() -> list[Path]:
    files: list[Path] = []
    for directory_name in SOURCE_DIRS:
        directory = REPO_ROOT / directory_name
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS:
                files.append(path)
    return sorted(files)


def read_and_normalize_sources() -> tuple[dict[Path, str], set[str]]:
    normalized_sources: dict[Path, str] = {}
    emoji_clusters: set[str] = set()
    for path in iter_source_files():
        original = path.read_text(encoding="utf-8")
        normalized = normalize_emoji(original)
        normalized_sources[path] = normalized
        emoji_clusters.update(extract_emoji(normalized))

    changed_files = sum(
        normalized_sources[path] != path.read_text(encoding="utf-8")
        for path in normalized_sources
    )
    print(f"Scanned {len(normalized_sources)} source files; {changed_files} file(s) need normalization.")
    return normalized_sources, emoji_clusters


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_source_font() -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached = CACHE_DIR / SOURCE_FONT_NAME
    if cached.exists() and sha256(cached) == SOURCE_SHA256:
        return cached

    print(f"Downloading {SOURCE_FONT_NAME} ...")
    temporary = cached.with_suffix(cached.suffix + ".tmp")
    request = urllib.request.Request(
        SOURCE_URL,
        headers={"User-Agent": "HomeDashboardServer emoji-font-builder"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as file:
            while chunk := response.read(1024 * 1024):
                file.write(chunk)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

    actual = sha256(temporary)
    if actual != SOURCE_SHA256:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(
            "Downloaded Noto Color Emoji has an unexpected SHA-256: "
            f"{actual} (expected {SOURCE_SHA256})."
        )
    temporary.replace(cached)
    return cached


def build_font(emoji_clusters: set[str], source_font: Path) -> bytes:
    if not emoji_clusters:
        raise RuntimeError("No emoji were found in the project source files.")

    emoji_text = "".join(sorted(emoji_clusters))
    font = TTFont(source_font)
    options = subset.Options()
    options.layout_features = "*"
    options.name_IDs = "*"
    options.name_languages = "*"
    options.glyph_names = False

    subsetter = subset.Subsetter(options=options)
    subsetter.populate(text=emoji_text)
    subsetter.subset(font)
    font.flavor = None

    with tempfile.NamedTemporaryFile(suffix=".ttf", delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        font.save(temporary_path)
        return temporary_path.read_bytes()
    finally:
        temporary_path.unlink(missing_ok=True)


def write_outputs(normalized_sources: dict[Path, str], font_bytes: bytes) -> None:
    OUTPUT_FONT.parent.mkdir(parents=True, exist_ok=True)
    for path, normalized in normalized_sources.items():
        original = path.read_text(encoding="utf-8")
        if normalized != original:
            path.write_text(normalized, encoding="utf-8")

    with tempfile.NamedTemporaryFile(
        dir=OUTPUT_FONT.parent,
        prefix=OUTPUT_FONT.name + ".",
        suffix=".tmp",
        delete=False,
    ) as temporary:
        temporary.write(font_bytes)
        temporary_path = Path(temporary.name)
    try:
        temporary_path.chmod(0o644)
        temporary_path.replace(OUTPUT_FONT)
    finally:
        temporary_path.unlink(missing_ok=True)

    print(f"Built {OUTPUT_FONT.relative_to(REPO_ROOT)} ({len(font_bytes):,} bytes).")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normalize project emoji and rebuild HomeDashboardEmoji.ttf."
    )
    parser.add_argument(
        "--source-font",
        type=Path,
        help="Use a local full Noto Color Emoji TTF instead of downloading the pinned source.",
    )
    args = parser.parse_args()

    normalized_sources, emoji_clusters = read_and_normalize_sources()
    source_font = args.source_font.expanduser() if args.source_font else download_source_font()
    if not source_font.is_file():
        raise SystemExit(f"Source font not found: {source_font}")
    font_bytes = build_font(emoji_clusters, source_font)
    write_outputs(normalized_sources, font_bytes)
    print(f"Emoji clusters: {len(emoji_clusters)}; {' '.join(emoji_clusters)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())