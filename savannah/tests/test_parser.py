"""Comprehensive tests for the action parser."""

from savannah.src.parser import parse_action


class TestParseActionHappyPath:
    """All 10 action types parse correctly."""

    def test_move_north(self):
        r = parse_action("ACTION: move(n)\nWORKING: heading north\nREASONING: food north")
        assert r["action"] == "move"
        assert r["args"] == "n"
        assert r["parse_failed"] is False

    def test_move_south(self):
        r = parse_action("ACTION: move(s)\nWORKING: x\nREASONING: y")
        assert r["action"] == "move"
        assert r["args"] == "s"

    def test_move_east(self):
        r = parse_action("ACTION: move(e)\nWORKING: x\nREASONING: y")
        assert r["action"] == "move"
        assert r["args"] == "e"

    def test_move_west(self):
        r = parse_action("ACTION: move(w)\nWORKING: x\nREASONING: y")
        assert r["action"] == "move"
        assert r["args"] == "w"

    def test_eat(self):
        r = parse_action("ACTION: eat\nWORKING: eating food\nREASONING: food here")
        assert r["action"] == "eat"
        assert r["args"] is None
        assert r["parse_failed"] is False

    def test_recall(self):
        r = parse_action('ACTION: recall("food locations")\nWORKING: checking\nREASONING: need food')
        assert r["action"] == "recall"
        assert r["args"] == "food locations"

    def test_remember(self):
        r = parse_action('ACTION: remember("Found food at (3,5)")\nWORKING: noted\nREASONING: recording')
        assert r["action"] == "remember"
        assert r["args"] == "Found food at (3,5)"

    def test_compact(self):
        r = parse_action("ACTION: compact\nWORKING: consolidating\nREASONING: memory full")
        assert r["action"] == "compact"
        assert r["args"] is None

    def test_signal(self):
        r = parse_action('ACTION: signal("food at (5,3)")\nWORKING: sharing\nREASONING: helping')
        assert r["action"] == "signal"
        assert r["args"] == "food at (5,3)"

    def test_observe(self):
        r = parse_action("ACTION: observe\nWORKING: looking around\nREASONING: need info")
        assert r["action"] == "observe"
        assert r["args"] is None

    def test_attack(self):
        r = parse_action("ACTION: attack(Bright-Creek)\nWORKING: fighting\nREASONING: desperate")
        assert r["action"] == "attack"
        assert r["args"] == "Bright-Creek"

    def test_flee_north(self):
        r = parse_action("ACTION: flee(n)\nWORKING: running\nREASONING: danger")
        assert r["action"] == "flee"
        assert r["args"] == "n"

    def test_rest(self):
        r = parse_action("ACTION: rest\nWORKING: nothing\nREASONING: no options")
        assert r["action"] == "rest"
        assert r["args"] is None
        assert r["parse_failed"] is False


class TestParseActionFormattingQuirks:
    """LLMs produce weird formatting. Parser must handle it."""

    def test_uppercase_action(self):
        r = parse_action("ACTION: MOVE(N)\nWORKING: x\nREASONING: y")
        assert r["action"] == "move"
        assert r["args"].lower() == "n"

    def test_mixed_case(self):
        r = parse_action("ACTION: Move(n)\nWORKING: x\nREASONING: y")
        assert r["action"] == "move"

    def test_backtick_wrapped(self):
        r = parse_action("ACTION: `move(n)`\nWORKING: x\nREASONING: y")
        assert r["action"] == "move"
        assert r["args"] == "n"

    def test_triple_backtick_wrapped(self):
        r = parse_action("ACTION: ```move(n)```\nWORKING: x\nREASONING: y")
        assert r["action"] == "move"

    def test_extra_spaces_in_parens(self):
        r = parse_action("ACTION: move(  n  )\nWORKING: x\nREASONING: y")
        assert r["action"] == "move"
        assert r["args"] == "n"

    def test_action_with_trailing_explanation(self):
        """LLMs sometimes explain after the action."""
        r = parse_action("ACTION: move(n) - heading north to find food\nWORKING: x\nREASONING: y")
        assert r["action"] == "move"
        assert r["args"] == "n"

    def test_single_quotes_in_recall(self):
        r = parse_action("ACTION: recall('food locations')\nWORKING: x\nREASONING: y")
        assert r["action"] == "recall"
        assert r["args"] == "food locations"

    def test_single_quotes_in_remember(self):
        r = parse_action("ACTION: remember('important event')\nWORKING: x\nREASONING: y")
        assert r["action"] == "remember"
        assert r["args"] == "important event"

    def test_single_quotes_in_signal(self):
        r = parse_action("ACTION: signal('food nearby')\nWORKING: x\nREASONING: y")
        assert r["action"] == "signal"
        assert r["args"] == "food nearby"

    def test_attack_hyphenated_name(self):
        r = parse_action("ACTION: attack(Swift-Stone)\nWORKING: x\nREASONING: y")
        assert r["action"] == "attack"
        assert r["args"] == "Swift-Stone"


class TestParseActionMultilineWorking:
    """WORKING blocks can span multiple lines."""

    def test_multiline_working(self):
        response = (
            "ACTION: move(n)\n"
            "WORKING: I'm heading north because:\n"
            "- Food spotted at (3,5)\n"
            "- Energy running low\n"
            "- Need to eat soon\n"
            "REASONING: Following food signal"
        )
        r = parse_action(response)
        assert r["action"] == "move"
        assert "Food spotted" in r["working"]
        assert "Need to eat" in r["working"]
        assert "Following food" in r["reasoning"]

    def test_working_with_colons(self):
        """WORKING may contain colons — don't confuse with section labels."""
        response = (
            "ACTION: rest\n"
            "WORKING: status: resting, energy: 45.0, plan: find food\n"
            "REASONING: conserving energy"
        )
        r = parse_action(response)
        assert "status: resting" in r["working"]
        assert r["reasoning"] == "conserving energy"

    def test_multiline_reasoning(self):
        response = (
            "ACTION: eat\n"
            "WORKING: eating\n"
            "REASONING: I found food at my position.\n"
            "This is good because my energy was getting low.\n"
            "I should remember this location."
        )
        r = parse_action(response)
        assert "found food" in r["reasoning"]
        assert "remember this location" in r["reasoning"]


class TestParseActionFailures:
    """Failures must fallback to rest gracefully."""

    def test_empty_string(self):
        r = parse_action("")
        assert r["action"] == "rest"
        assert r["parse_failed"] is True

    def test_none_input(self):
        r = parse_action(None)
        assert r["action"] == "rest"
        assert r["parse_failed"] is True

    def test_integer_input(self):
        r = parse_action(42)
        assert r["action"] == "rest"
        assert r["parse_failed"] is True

    def test_no_action_line(self):
        r = parse_action("I think I should move north")
        assert r["action"] == "rest"
        assert r["parse_failed"] is True

    def test_unrecognized_action(self):
        r = parse_action("ACTION: dance(wildly)\nWORKING: x\nREASONING: y")
        assert r["action"] == "rest"
        assert r["parse_failed"] is True

    def test_malformed_move_no_direction(self):
        r = parse_action("ACTION: move()\nWORKING: x\nREASONING: y")
        assert r["action"] == "rest"
        assert r["parse_failed"] is True

    def test_malformed_move_invalid_direction(self):
        r = parse_action("ACTION: move(x)\nWORKING: x\nREASONING: y")
        assert r["action"] == "rest"
        assert r["parse_failed"] is True

    def test_garbage_input(self):
        r = parse_action("asdf8923jklasdf\n\nrandom garbage")
        assert r["action"] == "rest"
        assert r["parse_failed"] is True

    def test_only_action_no_other_fields(self):
        """Action line exists but no WORKING or REASONING."""
        r = parse_action("ACTION: eat")
        assert r["action"] == "eat"
        assert r["working"] == ""
        assert r["reasoning"] == ""
        assert r["parse_failed"] is False

    def test_working_and_reasoning_preserved_on_action_failure(self):
        """Even if action is unparseable, keep the working/reasoning text."""
        r = parse_action("ACTION: fly(up)\nWORKING: notes\nREASONING: reasons")
        assert r["action"] == "rest"
        assert r["parse_failed"] is True
        assert r["working"] == "notes"
        assert r["reasoning"] == "reasons"


class TestParseActionEdgeCases:
    """Edge cases from real LLM outputs."""

    def test_multiple_action_lines_uses_last(self):
        """When LLM outputs multiple ACTION lines, the last one wins
        (it's their final decision after deliberation)."""
        response = (
            "ACTION: move(n)\n"
            "ACTION: eat\n"
            "WORKING: confused\n"
            "REASONING: can't decide"
        )
        r = parse_action(response)
        assert r["action"] == "eat"

    def test_eat_doesnt_match_in_reasoning(self):
        """'eat' in reasoning shouldn't be confused with ACTION: eat."""
        response = (
            "ACTION: move(n)\n"
            "WORKING: heading to eat\n"
            "REASONING: I want to eat food"
        )
        r = parse_action(response)
        assert r["action"] == "move"

    def test_recall_with_special_chars_in_query(self):
        r = parse_action('ACTION: recall("food at (3,5) tick 100")\nWORKING: x\nREASONING: y')
        assert r["action"] == "recall"
        assert "(3,5)" in r["args"]

    def test_response_with_preamble(self):
        """LLM sometimes adds text before the ACTION line."""
        response = (
            "Let me think about this...\n"
            "Based on my energy level, I should:\n"
            "ACTION: rest\n"
            "WORKING: conserving energy\n"
            "REASONING: low energy, no food visible"
        )
        r = parse_action(response)
        assert r["action"] == "rest"
        assert r["parse_failed"] is False
