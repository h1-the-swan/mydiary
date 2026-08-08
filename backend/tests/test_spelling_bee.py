# -*- coding: utf-8 -*-

from datetime import date

import pytest

from mydiary.spelling_bee import (
    HIVE_SIZE,
    VOWELS,
    check_consistency,
    derive_hive,
    is_pangram,
    normalize_word,
    parse_words,
    split_by_puzzle,
    validate_words,
)

# the two puzzles that actually got filed under one date
M_PUZZLE = ["DENIM", "DIME", "DIMMED", "EMEND", "GIMME", "MIDGE", "IMPEND"]
B_PUZZLE = ["ABROAD", "BAOBAB", "BURBOT", "DARTBOARD", "TABOO", "DOUBT"]

DT = date(2026, 8, 7)


class TestParsing:
    def test_normalize_word(self):
        assert normalize_word("  candid ") == "CANDID"
        assert normalize_word("Dyadic,") == "DYADIC"
        assert normalize_word("") == ""

    def test_parse_words_newlines(self):
        # the shape the NYT answer list actually pastes in
        blob = "CANDID\nCADDY\nDYADIC\n"
        assert parse_words(blob) == ["CANDID", "CADDY", "DYADIC"]

    def test_parse_words_mixed_separators_and_case(self):
        blob = "candid, caddy; DYADIC  indicia"
        assert parse_words(blob) == ["CANDID", "CADDY", "DYADIC", "INDICIA"]

    def test_parse_words_dedupes_preserving_order(self):
        assert parse_words("CADDY CANDID caddy") == ["CADDY", "CANDID"]

    def test_is_pangram(self):
        assert is_pangram("INDICACY") is False  # 6 distinct letters
        assert is_pangram("CANDIDLY") is True  # C,A,N,D,I,L,Y
        assert is_pangram("CADDY") is False

    def test_validate_words_rejects_short(self):
        valid, invalid = validate_words(["CANDID", "CAD", "DYADIC"])
        assert valid == ["CANDID", "DYADIC"]
        assert invalid == ["CAD"]

    def test_validate_words_strips_punctuation_rather_than_rejecting(self):
        valid, invalid = validate_words(["candid,", " dyadic "])
        assert valid == ["CANDID", "DYADIC"]
        assert invalid == []


class TestDeriveHive:
    def test_stored_letters_are_used_verbatim(self):
        hive = derive_hive(
            DT, ["CANDID", "CADDY"], center_letter="D", outer_letters="CANIYL"
        )
        assert hive.exact is True
        assert hive.center_letter == "D"
        assert hive.letters == set("DCANIYL")

    def test_pangram_pins_the_letter_set_exactly(self):
        # CANDIDLY has 7 distinct letters, so those ARE the puzzle's seven
        hive = derive_hive(DT, ["CANDIDLY", "CANDID", "CADDY"])
        assert hive.letters == set("CANDILY")
        assert "CANDIDLY" in hive.pangrams
        # inferred, not recorded -- the UI says so
        assert hive.exact is False

    def test_short_letter_set_is_padded_to_seven(self):
        hive = derive_hive(DT, ["CANDID", "CADDY"])
        assert len(hive.letters) == HIVE_SIZE
        assert len(hive.outer_letters) == HIVE_SIZE - 1
        # the words' own letters all survive
        assert set("CANDIDCADDY") <= hive.letters

    def test_padding_never_introduces_s(self):
        # S is vanishingly rare in real puzzles, so it's never a good guess
        hive = derive_hive(DT, ["CANDID", "CADDY"])
        assert "S" not in hive.letters

    def test_a_word_containing_s_keeps_its_s(self):
        # the rare real S puzzle: filtering S out of the words would be wrong
        hive = derive_hive(DT, ["SANDIER", "RAIDERS", "ARIDNESS"])
        assert "S" in hive.letters
        assert "SANDIER" in hive.words

    def test_padded_board_has_a_vowel(self):
        hive = derive_hive(DT, ["TRYST", "CRYPT"])
        assert any(c in VOWELS for c in hive.letters)

    def test_derivation_is_deterministic(self):
        # hash() is PYTHONHASHSEED-salted; a reshuffling board would be a bug
        first = derive_hive(DT, ["CANDID", "CADDY"])
        second = derive_hive(DT, ["CANDID", "CADDY"])
        assert first.center_letter == second.center_letter
        assert first.outer_letters == second.outer_letters

    def test_center_letter_appears_in_every_playable_word(self):
        # the property the whole game depends on
        hive = derive_hive(DT, ["CANDID", "CADDY", "DYADIC", "INDICIA"])
        assert all(hive.center_letter in word for word in hive.words)

    def test_single_word_warns_that_the_center_is_a_guess(self):
        hive = derive_hive(DT, ["CANDID"])
        assert hive.warnings
        assert hive.center_letter in "CANDID"

    def test_too_many_distinct_letters_warns_and_still_returns_a_board(self):
        # nine distinct letters across these -- a data entry error
        hive = derive_hive(DT, ["CANDID", "MURKY", "FLIGHT"])
        assert len(hive.letters) == HIVE_SIZE
        assert any("distinct letters" in w for w in hive.warnings)

    def test_words_sharing_no_letter_warn_but_do_not_crash(self):
        hive = derive_hive(DT, ["CANDID", "ROOFS"])
        assert hive.center_letter
        assert len(hive.letters) == HIVE_SIZE
        assert any("every word" in w for w in hive.warnings)

    def test_unplayable_words_are_dropped_from_the_game(self):
        # stored letters that can't spell CADDY -- it must not be a target
        hive = derive_hive(
            DT, ["MOUTHER", "CADDY"], center_letter="T", outer_letters="MOUHER"
        )
        assert "CADDY" not in hive.words
        assert "MOUTHER" in hive.words
        assert any("can't be made" in w for w in hive.warnings)

    def test_outer_letters_never_contain_the_center(self):
        hive = derive_hive(DT, ["CANDID", "CADDY", "DYADIC"])
        assert hive.center_letter not in hive.outer_letters
        assert len(set(hive.outer_letters)) == HIVE_SIZE - 1


class TestConsistency:
    def test_one_puzzle_is_consistent(self):
        result = check_consistency(M_PUZZLE)
        assert result.ok
        assert result.problems == ()
        assert "M" in result.center_candidates

    def test_empty_is_consistent(self):
        assert check_consistency([]).ok

    def test_two_puzzles_under_one_date_is_caught(self):
        # the real mistake: two days' answers filed under one date
        result = check_consistency(M_PUZZLE + B_PUZZLE)
        assert not result.ok
        assert any("different letters" in p for p in result.problems)
        assert any("centre letter" in p for p in result.problems)

    def test_too_many_letters_alone_is_caught(self):
        result = check_consistency(["CANDID", "MURKY", "FLIGHT"])
        assert not result.ok
        assert any("different letters" in p for p in result.problems)

    def test_no_common_letter_alone_is_caught(self):
        # few enough letters to pass the count rule, but nothing shared
        result = check_consistency(["MEND", "ROTS"])
        assert not result.ok
        assert any("centre letter" in p for p in result.problems)

    def test_word_outside_recorded_letters_is_caught(self):
        result = check_consistency(
            ["CANDID", "MUFFIN"], center_letter="D", outer_letters="CANIYL"
        )
        assert not result.ok
        assert any("not among the letters" in p for p in result.problems)

    def test_word_missing_recorded_center_is_caught(self):
        result = check_consistency(
            ["CANDID", "CLAY"], center_letter="D", outer_letters="CANIYL"
        )
        assert not result.ok
        assert any("centre letter D" in p for p in result.problems)

    def test_consistent_with_recorded_letters(self):
        result = check_consistency(
            ["CANDID", "CANDY"], center_letter="D", outer_letters="CANIYL"
        )
        assert result.ok

    def test_split_separates_the_two_puzzles(self):
        groups = split_by_puzzle(M_PUZZLE + B_PUZZLE)
        assert len(groups) == 2
        assert set(groups[0]) == set(M_PUZZLE)
        assert set(groups[1]) == set(B_PUZZLE)

    def test_split_leaves_one_puzzle_whole(self):
        assert split_by_puzzle(M_PUZZLE) == [M_PUZZLE]
