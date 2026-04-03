#!/usr/bin/env python3
"""
One Pace for Jellyfin - NFO Setup Script

Automatically places NFO metadata files and season posters alongside
your One Pace video files so Jellyfin displays proper arc names,
episode titles, and artwork.

Usage:
    python setup.py "/path/to/your/One Pace/"

See README.md for full instructions.
"""

import os
import re
import json
import shutil
import argparse
import unicodedata
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
METADATA_DIR = SCRIPT_DIR / "metadata"

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".m4v"}

# Matches standard and legacy One Pace filenames:
#   [One Pace][218-220] Jaya 01 [1080p][2BBCD106].mkv
#   [One Pace][302-303] Skypiea 25 Alternate (G-8) [1080p][90C45C25].mkv
#   [One Pace][303] Long Ring Long Land 00 [1080p][En Sub][7582DAC2].mp4
ORIGINAL_FILENAME_PATTERN = re.compile(
    r"^\[One Pace\]\[([^\]]+)\]\s+(.+?)\s+(\d+)"
    r"(\s+Alternate[^\[]*?)?"
    r"(?:\s+-\s+(.+?))?"
    r"(?:\s+\[|$)",
    re.IGNORECASE,
)
SEASON_EPISODE_TITLE_PATTERN = re.compile(
    r"^\[One Pace\]\s+S(\d+)E(\d+)\s+\[(.+?)\]",
    re.IGNORECASE,
)
TITLE_PATTERN = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)
CHAPTER_NUMBER_PATTERN = re.compile(r"(\d+)")

ARC_ALIASES = {
    "onigashima": "Wano",
    "end of wano": "Wano",
}


def load_seasons():
    with open(METADATA_DIR / "seasons.json") as f:
        return json.load(f)


NUMBER_WORDS = {
    "1": "one", "2": "two", "3": "three", "4": "four", "5": "five",
    "6": "six", "7": "seven", "8": "eight", "9": "nine",
}
NUMBER_WORDS_INV = {v: k for k, v in NUMBER_WORDS.items()}


def normalize(name):
    """Lowercase and replace digit↔word numbers for fuzzy matching."""
    n = name.lower().strip()
    for digit, word in NUMBER_WORDS.items():
        n = re.sub(rf"\b{digit}\b", word, n)
    return n


def find_season_number(arc_name, seasons):
    """Match arc name from filename to season number, with fuzzy fallback."""
    alias_name = ARC_ALIASES.get(arc_name.lower())
    if alias_name:
        arc_name = alias_name

    if arc_name in seasons:
        return seasons[arc_name]
    arc_lower = arc_name.lower()
    for k, v in seasons.items():
        if k.lower() == arc_lower:
            return v
    # Normalize numbers (e.g. "Water 7" → "Water Seven")
    arc_norm = normalize(arc_name)
    for k, v in seasons.items():
        if normalize(k) == arc_norm:
            return v
    # Partial match
    for k, v in seasons.items():
        if arc_lower in k.lower() or k.lower() in arc_lower:
            return v
    return None


def resolve_season_from_folder(folder_name, seasons):
    """Resolve a season number and canonical arc name from a folder name."""
    arc_match = re.search(r"\]\s+(.+?)(?:\s+\[|$)", folder_name)
    if not arc_match:
        arc_match = re.search(r"[-–]\s*(.+)$", folder_name)

    if arc_match:
        arc_name = arc_match.group(1).strip()
        season_num = find_season_number(arc_name, seasons)
        return season_num, arc_name

    season_num = find_season_number(folder_name, seasons)
    if season_num is not None:
        return season_num, folder_name.strip()

    season_match = re.fullmatch(r"season\s+(\d+)", folder_name.strip(), re.IGNORECASE)
    if not season_match:
        return None, None

    season_num = int(season_match.group(1))
    for arc_name, num in seasons.items():
        if num == season_num:
            return season_num, arc_name

    return None, None


def normalize_title(title):
    """Normalize an episode title for matching."""
    normalized = unicodedata.normalize("NFKD", title)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower().replace("&", "and")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def extract_nfo_title(nfo_path):
    """Read an episode title from an NFO file."""
    match = TITLE_PATTERN.search(nfo_path.read_text(encoding="utf-8"))
    if not match:
        return None
    return match.group(1).strip()


def build_episode_nfo_path(season_meta, episode_number, is_alternate=False):
    suffix = "_alternate" if is_alternate else ""
    return season_meta / f"S{int(season_meta.name):02d}E{episode_number:02d}{suffix}.nfo"


def find_nfo_by_title(season_meta, title):
    normalized_title = normalize_title(title)
    for nfo_path in sorted(season_meta.glob("S*.nfo")):
        nfo_title = extract_nfo_title(nfo_path)
        if nfo_title and normalize_title(nfo_title) == normalized_title:
            return nfo_path
    return None


def parse_chapter_number(chapter_token):
    match = CHAPTER_NUMBER_PATTERN.search(chapter_token)
    if not match:
        return None
    return int(match.group(1))


def resolve_episode_nfo(video_name, season_meta, seasons):
    """Resolve the source NFO file for a video filename within a season."""
    match = ORIGINAL_FILENAME_PATTERN.match(video_name)
    if match:
        chapter_token = match.group(1)
        arc_name = match.group(2).strip()
        ep_num = int(match.group(3))
        is_alternate = bool(match.group(4))
        title = match.group(5).strip() if match.group(5) else None
        if title:
            title = re.sub(r"\.[^.]+$", "", title)
        chapter_num = parse_chapter_number(chapter_token)

        candidate_seasons = [season_meta]
        arc_season_num = find_season_number(arc_name, seasons)
        if arc_season_num is not None:
            arc_season_meta = METADATA_DIR / "seasons" / str(arc_season_num)
            if arc_season_meta.is_dir() and arc_season_meta != season_meta:
                candidate_seasons.append(arc_season_meta)

        numbered_nfo = build_episode_nfo_path(season_meta, ep_num, is_alternate)
        if numbered_nfo.exists():
            if not title:
                return numbered_nfo
            nfo_title = extract_nfo_title(numbered_nfo)
            if nfo_title and normalize_title(nfo_title) == normalize_title(title):
                return numbered_nfo

        if title:
            for candidate in candidate_seasons:
                title_nfo = find_nfo_by_title(candidate, title)
                if title_nfo is not None:
                    return title_nfo

        if chapter_num is not None:
            for candidate in candidate_seasons:
                chapter_nfo = build_episode_nfo_path(candidate, chapter_num)
                if chapter_nfo.exists():
                    return chapter_nfo

        return None

    match = SEASON_EPISODE_TITLE_PATTERN.match(video_name)
    if not match:
        return None

    ep_num = int(match.group(2))
    title = normalize_title(match.group(3))

    numbered_nfo = build_episode_nfo_path(season_meta, ep_num)
    if numbered_nfo.exists():
        return numbered_nfo

    return find_nfo_by_title(season_meta, match.group(3))


def place_file(src, dst, force):
    if dst.exists() and not force:
        return False
    shutil.copy2(src, dst)
    return True


def process(media_path, force=False):
    seasons = load_seasons()
    series_dir = Path(media_path)

    if not series_dir.is_dir():
        print(f"Error: '{media_path}' is not a valid directory.")
        return

    # Place tvshow.nfo at series root
    tvshow_src = METADATA_DIR / "tvshow.nfo"
    tvshow_dst = series_dir / "tvshow.nfo"
    if place_file(tvshow_src, tvshow_dst, force):
        print("✓ tvshow.nfo placed at series root")

    placed = 0
    skipped = 0
    unmatched = []

    for arc_dir in sorted(series_dir.iterdir()):
        if not arc_dir.is_dir():
            continue

        season_num, arc_name = resolve_season_from_folder(arc_dir.name, seasons)
        if season_num is None:
            continue

        season_meta = METADATA_DIR / "seasons" / str(season_num)
        if not season_meta.is_dir():
            print(f"\n⚠  No metadata available for season {season_num} ({arc_name})")
            continue

        print(f"\n📁 {arc_dir.name}  →  Season {season_num} ({arc_name})")

        # Place season.nfo
        if place_file(season_meta / "season.nfo", arc_dir / "season.nfo", force):
            print("   ✓ season.nfo")

        # Place poster
        if place_file(season_meta / "poster.png", arc_dir / "poster.png", force):
            print("   ✓ poster.png")

        # Match each video file to an episode NFO
        for video in sorted(arc_dir.iterdir()):
            if video.suffix.lower() not in VIDEO_EXTENSIONS:
                continue

            nfo_src = resolve_episode_nfo(video.name, season_meta, seasons)
            nfo_dst = video.with_suffix(".nfo")

            if nfo_src is None:
                print(f"   ✗ No matching NFO found — {video.name}")
                unmatched.append(str(video))
                continue

            if place_file(nfo_src, nfo_dst, force):
                print(f"   ✓ {video.name}")
                placed += 1
            else:
                print(f"   · {video.name}  (skipped, already exists — use --force to overwrite)")
                skipped += 1

    print(f"\n{'='*60}")
    print(f"Done!  {placed} NFOs placed, {skipped} skipped.")
    if unmatched:
        print(f"\n⚠  {len(unmatched)} file(s) could not be matched:")
        for f in unmatched:
            print(f"   {f}")
    print(
        "\nNext step: in Jellyfin, go to your library and run "
        "Scan All Libraries (or right-click the series → Refresh Metadata)."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Place One Pace NFO metadata files for Jellyfin.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python setup.py "/Volumes/MyDrive/Jellyfin/media/Anime/One Pace"
  python setup.py ~/media/One\\ Pace --force
        """,
    )
    parser.add_argument("path", help="Path to your One Pace series folder")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing NFO/poster files",
    )
    args = parser.parse_args()
    process(args.path, force=args.force)
