"""Tests for the name generator module."""

from __future__ import annotations

import re

import pytest

from savannah.src.names import ADJECTIVES, NOUNS, generate_names


# --- Anti-contamination: no personality-implying adjectives ---

# Words that imply personality, cognitive style, or emotional state.
# These MUST NOT appear in the ADJECTIVES list per IMPLEMENTATION_GUIDE.md
# section 12 (Anti-Contamination Protocols).
PERSONALITY_WORDS = {
    # Emotional states
    "Calm", "Happy", "Sad", "Angry", "Fearful", "Anxious", "Joyful",
    "Gentle", "Fierce",
    # Personality traits
    "Kind", "Cruel", "Brave", "Shy", "Bold", "Meek", "Proud", "Humble",
    "Noble", "Vain", "Loyal", "Sly",
    # Cognitive/moral attributes
    "Wise", "Clever", "Dull", "Smart", "Foolish", "Cunning",
    # Moral/character judgments
    "True", "False", "Good", "Evil", "Pure", "Wicked", "Just", "Fair",
    # Emotional/temperament descriptors
    "Wild", "Tame", "Mad", "Keen", "Deft",
    # Wealth/status implications
    "Rich", "Poor",
    # State-of-mind
    "Lost", "Free",
}


class TestAntiContamination:
    """Verify that the word lists contain no personality-implying terms."""

    def test_no_personality_adjectives(self):
        """ADJECTIVES list must not contain words implying personality,
        cognitive style, or emotional state."""
        found = set(ADJECTIVES) & PERSONALITY_WORDS
        assert found == set(), (
            f"Personality-implying adjectives found in word list: {found}. "
            f"Remove these to comply with anti-contamination protocols."
        )

    def test_kind_specifically_removed(self):
        """IMPLEMENTATION_GUIDE.md explicitly calls out 'Kind' for removal."""
        assert "Kind" not in ADJECTIVES

    def test_adjectives_are_all_alpha(self):
        """Every adjective should be a single alphabetic word (title-cased)."""
        for adj in ADJECTIVES:
            assert adj.isalpha(), f"Adjective {adj!r} contains non-alpha chars"
            assert adj == adj.capitalize(), (
                f"Adjective {adj!r} is not title-cased"
            )

    def test_nouns_are_all_alpha(self):
        """Every noun should be a single alphabetic word (title-cased)."""
        for noun in NOUNS:
            assert noun.isalpha(), f"Noun {noun!r} contains non-alpha chars"
            assert noun == noun.capitalize(), (
                f"Noun {noun!r} is not title-cased"
            )


# --- Determinism and correctness ---


class TestGenerateNames:
    """Core behavior of generate_names()."""

    def test_returns_exact_count_12(self):
        """generate_names(12, seed=42) returns exactly 12 names."""
        names = generate_names(12, seed=42)
        assert len(names) == 12

    def test_returns_exact_count_1(self):
        """generate_names(1, seed=42) returns exactly 1 name."""
        names = generate_names(1, seed=42)
        assert len(names) == 1

    def test_returns_empty_list_for_zero(self):
        """generate_names(0, seed=42) returns an empty list."""
        names = generate_names(0, seed=42)
        assert names == []

    def test_all_names_unique(self):
        """All returned names must be unique."""
        names = generate_names(12, seed=42)
        assert len(names) == len(set(names))

    def test_determinism_same_seed(self):
        """Same seed always produces the same names."""
        names_a = generate_names(12, seed=42)
        names_b = generate_names(12, seed=42)
        assert names_a == names_b

    def test_determinism_same_seed_large(self):
        """Determinism holds for large counts too."""
        names_a = generate_names(200, seed=99)
        names_b = generate_names(200, seed=99)
        assert names_a == names_b

    def test_different_seeds_produce_different_names(self):
        """Different seeds should produce different name orderings."""
        names_a = generate_names(12, seed=42)
        names_b = generate_names(12, seed=99)
        # It's theoretically possible for two seeds to produce identical
        # sorted output, but astronomically unlikely with 2560 combinations.
        assert names_a != names_b

    def test_different_seeds_distinct_sets(self):
        """With different seeds, the actual name sets should differ
        (not just ordering, since output is sorted)."""
        names_a = set(generate_names(12, seed=1))
        names_b = set(generate_names(12, seed=2))
        # At least some names should differ between seeds
        assert names_a != names_b


# --- Name format validation ---


class TestNameFormat:
    """All generated names must follow the Adjective-Noun pattern
    and be valid filesystem directory names."""

    NAME_PATTERN = re.compile(r"^[A-Z][a-z]+-[A-Z][a-z]+$")

    def test_all_names_match_pattern(self):
        """Every name matches 'Adjective-Noun' (alpha-hyphen-alpha)."""
        names = generate_names(50, seed=42)
        for name in names:
            assert self.NAME_PATTERN.match(name), (
                f"Name {name!r} does not match pattern Adjective-Noun"
            )

    def test_names_are_valid_directory_names(self):
        """Names must be safe as filesystem directory names:
        no spaces, no special characters besides hyphen."""
        names = generate_names(50, seed=42)
        for name in names:
            # Only alphanumeric and hyphens allowed
            assert re.match(r"^[A-Za-z-]+$", name), (
                f"Name {name!r} contains invalid filesystem characters"
            )
            # No leading/trailing hyphens
            assert not name.startswith("-"), f"Name {name!r} starts with hyphen"
            assert not name.endswith("-"), f"Name {name!r} ends with hyphen"
            # No consecutive hyphens
            assert "--" not in name, f"Name {name!r} has consecutive hyphens"
            # No spaces
            assert " " not in name, f"Name {name!r} contains spaces"

    def test_name_components_from_word_lists(self):
        """Each name's adjective and noun parts come from the defined lists."""
        names = generate_names(50, seed=42)
        adj_set = set(ADJECTIVES)
        noun_set = set(NOUNS)
        for name in names:
            adj, noun = name.split("-")
            assert adj in adj_set, f"Adjective {adj!r} not in ADJECTIVES list"
            assert noun in noun_set, f"Noun {noun!r} not in NOUNS list"


# --- Capacity and edge cases ---


class TestCapacity:
    """The generator must handle large counts up to the combination limit."""

    def test_can_generate_2500_unique_names(self):
        """Must generate at least 2500 unique names without error."""
        names = generate_names(2500, seed=42)
        assert len(names) == 2500
        assert len(set(names)) == 2500

    def test_maximum_capacity(self):
        """Total capacity is len(ADJECTIVES) * len(NOUNS)."""
        max_count = len(ADJECTIVES) * len(NOUNS)
        names = generate_names(max_count, seed=42)
        assert len(names) == max_count
        assert len(set(names)) == max_count

    def test_exceeding_capacity_raises_error(self):
        """Requesting more names than possible raises ValueError."""
        max_count = len(ADJECTIVES) * len(NOUNS)
        with pytest.raises(ValueError, match="Cannot generate"):
            generate_names(max_count + 1, seed=42)

    def test_word_list_sizes(self):
        """Word lists must be large enough for 2500+ combinations."""
        total = len(ADJECTIVES) * len(NOUNS)
        assert total >= 2500, (
            f"Only {total} combinations available "
            f"({len(ADJECTIVES)} adj x {len(NOUNS)} nouns). Need >= 2500."
        )

    def test_no_duplicate_adjectives(self):
        """ADJECTIVES list must have no duplicates."""
        assert len(ADJECTIVES) == len(set(ADJECTIVES))

    def test_no_duplicate_nouns(self):
        """NOUNS list must have no duplicates."""
        assert len(NOUNS) == len(set(NOUNS))
