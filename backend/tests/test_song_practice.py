# -*- coding: utf-8 -*-

from datetime import datetime, timedelta

import pytest

from mydiary.song_practice import (
    CLEAN_RUNS_TO_LEVEL_UP,
    LEVELS,
    LevelOverride,
    RunSummary,
    SectionResult,
    practice_markdown,
    run_line,
    section_level,
    song_ref,
    validate_level,
)

T0 = datetime(2026, 9, 1, 12, 0)


def results(pattern: str, start: datetime = T0):
    """'ccs' -> clean, clean, stumbled, one day apart."""
    return [
        SectionResult(practiced_at=start + timedelta(days=i), stumbled=(ch == "s"))
        for i, ch in enumerate(pattern)
    ]


class TestSectionLevel:
    def test_no_runs_is_full(self):
        lvl = section_level([])
        assert lvl.level == "full"
        assert lvl.num_runs == 0
        assert lvl.last_practiced_at is None
        assert lvl.overridden is False

    def test_threshold_is_three(self):
        assert CLEAN_RUNS_TO_LEVEL_UP == 3
        assert LEVELS == ("full", "letters", "cues", "memorized")

    def test_two_clean_runs_stay_full(self):
        lvl = section_level(results("cc"))
        assert (lvl.level, lvl.clean_streak) == ("full", 2)

    def test_three_clean_runs_move_up_and_reset_streak(self):
        lvl = section_level(results("ccc"))
        assert (lvl.level, lvl.clean_streak) == ("letters", 0)

    def test_nine_clean_runs_reach_memorized(self):
        assert section_level(results("c" * 9)).level == "memorized"

    def test_memorized_is_the_ceiling(self):
        lvl = section_level(results("c" * 12))
        assert lvl.level == "memorized"
        assert lvl.clean_streak == 3

    def test_stumble_moves_down_one_and_resets(self):
        lvl = section_level(results("cccccc" + "s"))  # cues, then a stumble
        assert (lvl.level, lvl.clean_streak) == ("letters", 0)

    def test_stumble_at_full_stays_full(self):
        assert section_level(results("s")).level == "full"

    def test_stumble_breaks_a_streak(self):
        # two clean, a stumble, two clean: never three in a row
        assert section_level(results("ccscc")).level == "full"

    def test_results_are_sorted_by_time(self):
        rs = results("ccc")
        assert section_level(list(reversed(rs))).level == "letters"
        assert section_level(rs).last_practiced_at == rs[-1].practiced_at

    def test_override_sets_level_and_ignores_earlier_runs(self):
        rs = results("sss")
        ov = LevelOverride(level="cues", set_at=rs[-1].practiced_at)
        lvl = section_level(rs, ov)
        assert lvl.level == "cues"
        assert lvl.overridden is True
        assert lvl.num_runs == 3

    def test_rules_continue_after_override(self):
        rs = results("ccc")
        ov = LevelOverride(level="memorized", set_at=T0 - timedelta(days=1))
        assert section_level(rs + results("s", start=T0 + timedelta(days=5)), ov).level == "cues"

    def test_validate_level(self):
        assert validate_level("cues") == "cues"
        with pytest.raises(ValueError):
            validate_level("mostly")


class TestDiaryLines:
    def test_song_ref_is_a_song_tag(self):
        assert song_ref("Paper Lanterns") == "#song:paper-lanterns"

    def test_song_ref_falls_back_to_name(self):
        assert song_ref("!!!") == "!!!"

    def test_clean_run(self):
        run = RunSummary("Paper Lanterns", "ukulele", [], T0)
        assert run_line(run) == "- #song:paper-lanterns, ukulele: clean run"

    def test_stumbles_listed_in_order(self):
        run = RunSummary("Paper Lanterns", "guitar", ["Verse 2", "Bridge"], T0)
        assert run_line(run) == "- #song:paper-lanterns, guitar: stumbled on Verse 2, Bridge"

    def test_lyrics_only(self):
        run = RunSummary("Paper Lanterns", None, [], T0)
        assert run_line(run) == "- #song:paper-lanterns, lyrics only: clean run"

    def test_markdown_sorted_by_time_and_none_when_empty(self):
        late = RunSummary("B Song", "guitar", [], T0 + timedelta(hours=2))
        early = RunSummary("A Song", "guitar", [], T0)
        assert practice_markdown([late, early]).splitlines() == [
            "- #song:a-song, guitar: clean run",
            "- #song:b-song, guitar: clean run",
        ]
        assert practice_markdown([]) == "None"
