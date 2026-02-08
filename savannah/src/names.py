"""Human-readable name generator for agents.

Produces nature-themed compound names like "Bright-Creek" or "Swift-Stone".
No personality implications — names are arbitrary labels.
"""

from __future__ import annotations

import random

ADJECTIVES = [
    "Bright", "Swift", "Broad", "Dark", "Deep", "Dry", "Far", "Fast",
    "Flat", "Gold", "Gray", "Half", "Hard", "High", "Dense", "Last",
    "Late", "Lean", "Long", "Blank", "Low", "Near", "New", "Old",
    "Pale", "Red", "Round", "Rough", "Sharp", "Slow", "Small", "Soft",
    "Still", "Tall", "Thin", "Steep", "Warm", "West", "Wide", "North",
]

NOUNS = [
    "Ash", "Bank", "Bark", "Bay", "Birch", "Bluff", "Brook", "Clay",
    "Cliff", "Cloud", "Cove", "Creek", "Crest", "Dale", "Dawn", "Dell",
    "Dew", "Drift", "Dune", "Dust", "Elm", "Fern", "Field", "Flint",
    "Fog", "Ford", "Frost", "Glen", "Grove", "Hawk", "Heath", "Hill",
    "Holt", "Ivy", "Lake", "Leaf", "Marsh", "Mist", "Moss", "Oak",
    "Path", "Peak", "Pine", "Pond", "Rain", "Reed", "Ridge", "Rock",
    "Root", "Rush", "Sand", "Shade", "Shore", "Sky", "Slate", "Snow",
    "Spring", "Star", "Stone", "Storm", "Thorn", "Tide", "Vale", "Wind",
]


def generate_names(count: int, seed: int = 42) -> list[str]:
    """Generate unique compound names. Returns exactly `count` names."""
    rng = random.Random(seed)
    names = set()

    # Shuffle to get variety
    adjs = ADJECTIVES.copy()
    nouns = NOUNS.copy()
    rng.shuffle(adjs)
    rng.shuffle(nouns)

    for adj in adjs:
        for noun in nouns:
            name = f"{adj}-{noun}"
            names.add(name)
            if len(names) >= count:
                return sorted(names)[:count]

    # Should never reach here with 40×64 = 2560 combinations
    raise ValueError(f"Cannot generate {count} unique names")
