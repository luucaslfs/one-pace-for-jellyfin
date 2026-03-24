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
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
METADATA_DIR = SCRIPT_DIR / "metadata"

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".m4v"}

# Matches standard One Pace filenames:
#   [One Pace][218-220] Jaya 01 [1080p][2BBCD106].mkv
#   [One Pace][302-303] Skypiea 25 Alternate (G-8) [1080p][90C45C25].mkv
#   [One Pace][303] Long Ring Long Land 00 [1080p][En Sub][7582DAC2].mp4
FILENAME_PATTERN = re.compile(
    r"^\[One Pace\]\[[^\]]+\]\s+(.+?)\s+(\d+)"
    r"(\s+Alternate[^\[]*?)?"
    r"\s+\[",
    re.IGNORECASE,
)


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

    # Place main poster at series root
    poster_src = METADATA_DIR / "poster.png"
    poster_dst = series_dir / "poster.png"
    if place_file(poster_src, poster_dst, force):
        print("✓ main poster placed at series root")

    placed = 0
    skipped = 0
    unmatched = []

    for arc_dir in sorted(series_dir.iterdir()):
        if not arc_dir.is_dir():
            continue

        # Extract arc name from folder — supports both formats:
        #   [One Pace][218-236] Jaya [1080p]   (plugin format)
        #   Arco 13 - Jaya                      (custom format)
        arc_match = re.search(r"\]\s+(.+?)(?:\s+\[|$)", arc_dir.name)
        if not arc_match:
            arc_match = re.search(r"[-–]\s*(.+)$", arc_dir.name)
        if not arc_match:
            continue

        arc_name = arc_match.group(1).strip()
        season_num = find_season_number(arc_name, seasons)

        if season_num is None:
            print(f"\n⚠  Could not match arc: '{arc_name}' (folder: {arc_dir.name})")
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

            m = FILENAME_PATTERN.match(video.name)
            if not m:
                unmatched.append(str(video))
                continue

            ep_num = int(m.group(2))
            is_alternate = bool(m.group(3))

            if is_alternate:
                nfo_name = f"S{season_num:02d}E{ep_num:02d}_alternate.nfo"
            else:
                nfo_name = f"S{season_num:02d}E{ep_num:02d}.nfo"

            nfo_src = season_meta / nfo_name
            nfo_dst = video.with_suffix(".nfo")

            if not nfo_src.exists():
                print(f"   ✗ No NFO found for ep {ep_num:02d} {'(alternate) ' if is_alternate else ''}— {video.name}")
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
