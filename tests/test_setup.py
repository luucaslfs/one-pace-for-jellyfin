import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETUP_PATH = ROOT / "setup.py"


spec = importlib.util.spec_from_file_location("onepace_setup", SETUP_PATH)
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class ResolveSeasonFromFolderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seasons = setup.load_seasons()

    def test_plugin_format_folder_still_maps_by_arc_name(self):
        season_num, arc_name = setup.resolve_season_from_folder(
            "[One Pace][218-236] Jaya [1080p]",
            self.seasons,
        )
        self.assertEqual(season_num, 15)
        self.assertEqual(arc_name, "Jaya")

    def test_dash_format_folder_still_maps_by_arc_name(self):
        season_num, arc_name = setup.resolve_season_from_folder(
            "Arco 13 - Jaya",
            self.seasons,
        )
        self.assertEqual(season_num, 15)
        self.assertEqual(arc_name, "Jaya")

    def test_specials_folder_maps_directly(self):
        season_num, arc_name = setup.resolve_season_from_folder(
            "Specials",
            self.seasons,
        )
        self.assertEqual(season_num, 0)
        self.assertEqual(arc_name, "Specials")

    def test_season_number_folder_maps_to_canonical_arc(self):
        season_num, arc_name = setup.resolve_season_from_folder(
            "Season 18",
            self.seasons,
        )
        self.assertEqual(season_num, 18)
        self.assertEqual(arc_name, "Water Seven")


class ResolveEpisodeNfoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seasons = setup.load_seasons()

    def test_original_filename_format_still_maps_by_episode_number(self):
        season_meta = ROOT / "metadata" / "seasons" / "15"
        nfo_path = setup.resolve_episode_nfo(
            "[One Pace][218-220] Jaya 01 [1080p][2BBCD106].mkv",
            season_meta,
            self.seasons,
        )
        self.assertEqual(nfo_path.name, "S15E01.nfo")

    def test_season_episode_title_format_maps_by_title(self):
        season_meta = ROOT / "metadata" / "seasons" / "1"
        nfo_path = setup.resolve_episode_nfo(
            "[One Pace] S01E03 [The Pirate King and the Master Swordsman].mkv",
            season_meta,
            self.seasons,
        )
        self.assertEqual(nfo_path.name, "S01E03.nfo")

    def test_title_fallback_wins_when_embedded_episode_number_is_wrong(self):
        season_meta = ROOT / "metadata" / "seasons" / "1"
        nfo_path = setup.resolve_episode_nfo(
            "[One Pace] S01E99 [The Pirate King and the Master Swordsman].mkv",
            season_meta,
            self.seasons,
        )
        self.assertEqual(nfo_path.name, "S01E03.nfo")

    def test_old_wano_filename_can_resolve_by_title_via_arc_alias(self):
        season_meta = ROOT / "metadata" / "seasons" / "36"
        nfo_path = setup.resolve_episode_nfo(
            "[One Pace][1005-1006] Onigashima 23 - The Honorable Hyogoro The Flower.mkv",
            season_meta,
            self.seasons,
        )
        self.assertEqual(nfo_path.name, "S35E58.nfo")

    def test_old_wano_filename_can_resolve_by_chapter_number(self):
        season_meta = ROOT / "metadata" / "seasons" / "36"
        nfo_path = setup.resolve_episode_nfo(
            "[One Pace][1023-1024] Onigashima 34 - So-and-So.mp4",
            season_meta,
            self.seasons,
        )
        self.assertEqual(nfo_path.name, "S35E1023.nfo")


if __name__ == "__main__":
    unittest.main()
