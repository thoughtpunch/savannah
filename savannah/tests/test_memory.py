"""Tests for the memory system: recall, remember, compaction helpers."""

import pytest

from savannah.src.memory import (
    recall,
    remember,
    get_episodic_entries,
    read_memory_file,
    write_memory_file,
    build_compaction_prompt,
    parse_compaction_response,
    apply_compaction,
    _tokenize,
    _bm25_score,
    _load_all_chunks,
)


@pytest.fixture
def memory_dir(tmp_path):
    """Create a memory directory with sample content."""
    mem = tmp_path / "memory"
    mem.mkdir()

    (mem / "episodic.md").write_text(
        "Tick 100: Found food at (5,3). Gathered 50 energy.\n"
        "Tick 110: Moved north to (5,2). No food visible.\n"
        "Tick 120: Found food at (8,7). Gathered 30 energy.\n"
        "Tick 130: Received signal from Swift-Stone: food at (12,4).\n"
        "Tick 140: Area around (12,4) was empty. No food found.\n"
    )
    (mem / "semantic.md").write_text(
        "I am Test-Creek. I need food to maintain energy.\n\n"
        "Food is plentiful in the south area around (5,3).\n\n"
        "The north area is usually empty.\n"
    )
    (mem / "self.md").write_text("I am Test-Creek.")
    (mem / "social.md").write_text(
        "Swift-Stone: reported food at (12,4) but it was not there. Unreliable."
    )
    return mem


@pytest.fixture
def empty_memory_dir(tmp_path):
    mem = tmp_path / "memory"
    mem.mkdir()
    (mem / "episodic.md").write_text("")
    (mem / "semantic.md").write_text("")
    (mem / "self.md").write_text("")
    (mem / "social.md").write_text("")
    return mem


class TestTokenize:
    def test_basic(self):
        assert _tokenize("Hello World") == ["hello", "world"]

    def test_punctuation_stripped(self):
        assert _tokenize("food at (3,5).") == ["food", "at", "3", "5"]

    def test_empty(self):
        assert _tokenize("") == []

    def test_numbers(self):
        assert "100" in _tokenize("Tick 100: found food")


class TestRecall:
    def test_finds_food_memories(self, memory_dir):
        results = recall(memory_dir, "food", max_results=3)
        assert len(results) > 0
        assert any("food" in r.lower() for r in results)

    def test_finds_specific_location(self, memory_dir):
        results = recall(memory_dir, "food south", max_results=3)
        assert len(results) > 0
        # Should rank the semantic memory about south higher
        assert any("south" in r.lower() for r in results)

    def test_no_results_for_irrelevant_query(self, memory_dir):
        results = recall(memory_dir, "zzzxyzzz nonexistent", max_results=3)
        assert results == ["No relevant memories found."]

    def test_empty_query(self, memory_dir):
        results = recall(memory_dir, "", max_results=3)
        assert results == ["No relevant memories found."]

    def test_empty_memory(self, empty_memory_dir):
        results = recall(empty_memory_dir, "food", max_results=3)
        assert results == ["No relevant memories found."]

    def test_max_results_respected(self, memory_dir):
        results = recall(memory_dir, "food", max_results=1)
        assert len(results) <= 1

    def test_nonexistent_directory(self, tmp_path):
        results = recall(tmp_path / "nonexistent", "food")
        assert results == ["No relevant memories found."]

    def test_social_memory_searchable(self, memory_dir):
        results = recall(memory_dir, "Swift-Stone unreliable", max_results=3)
        assert len(results) > 0
        assert any("swift" in r.lower() or "unreliable" in r.lower() for r in results)


class TestRemember:
    def test_append_to_existing(self, memory_dir):
        remember(memory_dir, "Tick 200: Found something new.")
        content = (memory_dir / "episodic.md").read_text()
        assert "Tick 200: Found something new." in content
        # Original content preserved
        assert "Tick 100" in content

    def test_append_to_empty(self, empty_memory_dir):
        remember(empty_memory_dir, "First memory entry")
        content = (empty_memory_dir / "episodic.md").read_text()
        assert "First memory entry" in content

    def test_whitespace_stripped(self, memory_dir):
        remember(memory_dir, "  spaced text  ")
        content = (memory_dir / "episodic.md").read_text()
        assert "spaced text" in content

    def test_multiple_appends(self, empty_memory_dir):
        remember(empty_memory_dir, "Entry 1")
        remember(empty_memory_dir, "Entry 2")
        remember(empty_memory_dir, "Entry 3")
        content = (empty_memory_dir / "episodic.md").read_text()
        assert "Entry 1" in content
        assert "Entry 2" in content
        assert "Entry 3" in content


class TestGetEpisodicEntries:
    def test_get_last_n(self, memory_dir):
        entries = get_episodic_entries(memory_dir, last_n=3)
        assert len(entries) == 3
        assert "Tick 140" in entries[-1]

    def test_get_all(self, memory_dir):
        entries = get_episodic_entries(memory_dir, last_n=100)
        assert len(entries) == 5

    def test_empty(self, empty_memory_dir):
        entries = get_episodic_entries(empty_memory_dir)
        assert entries == []


class TestReadWriteMemoryFile:
    def test_read_existing(self, memory_dir):
        content = read_memory_file(memory_dir, "self.md")
        assert "Test-Creek" in content

    def test_read_missing(self, tmp_path):
        content = read_memory_file(tmp_path, "nonexistent.md")
        assert content == ""

    def test_write_and_read(self, memory_dir):
        write_memory_file(memory_dir, "self.md", "I am updated.")
        content = read_memory_file(memory_dir, "self.md")
        assert content == "I am updated."

    def test_write_overwrites(self, memory_dir):
        write_memory_file(memory_dir, "semantic.md", "New knowledge only.")
        content = read_memory_file(memory_dir, "semantic.md")
        assert content == "New knowledge only."
        assert "plentiful" not in content


class TestBM25Score:
    def test_relevant_scores_higher(self):
        chunks = [
            "Food found at location north",
            "Nothing happened today",
            "Large food source discovered nearby",
        ]
        scored = _bm25_score(chunks, "food")
        food_scores = [(c, s) for c, s in scored if "food" in c.lower()]
        other_scores = [(c, s) for c, s in scored if "food" not in c.lower()]
        assert all(fs[1] > os[1] for fs in food_scores for os in other_scores)

    def test_empty_query_zero_scores(self):
        chunks = ["some text", "more text"]
        scored = _bm25_score(chunks, "")
        assert all(s == 0.0 for _, s in scored)

    def test_single_chunk(self):
        scored = _bm25_score(["only chunk here"], "chunk")
        assert len(scored) == 1
        assert scored[0][1] > 0


class TestLoadAllChunks:
    def test_loads_paragraphs(self, memory_dir):
        chunks = _load_all_chunks(memory_dir)
        assert len(chunks) > 0
        # Should split on double newlines
        assert any("plentiful" in c.lower() for c in chunks)

    def test_empty_dir(self, empty_memory_dir):
        chunks = _load_all_chunks(empty_memory_dir)
        assert chunks == []


class TestBuildCompactionPrompt:
    def test_contains_agent_name(self, memory_dir):
        prompt = build_compaction_prompt("Test-Creek", memory_dir, tick=150)
        assert "Test-Creek" in prompt

    def test_contains_episodic_entries(self, memory_dir):
        prompt = build_compaction_prompt("Test-Creek", memory_dir, tick=150)
        assert "Tick 100" in prompt
        assert "Tick 140" in prompt

    def test_contains_semantic_content(self, memory_dir):
        prompt = build_compaction_prompt("Test-Creek", memory_dir, tick=150)
        assert "plentiful" in prompt.lower() or "food" in prompt.lower()

    def test_no_contamination_words(self, memory_dir):
        prompt = build_compaction_prompt("Test-Creek", memory_dir, tick=150)
        contamination = ["conscious", "alive", "feel", "experience", "survive", "sentient"]
        prompt_lower = prompt.lower()
        for word in contamination:
            assert word not in prompt_lower, f"Contamination word found: {word}"

    def test_contains_format_instructions(self, memory_dir):
        prompt = build_compaction_prompt("Test-Creek", memory_dir, tick=150)
        assert "EPISODIC:" in prompt
        assert "SEMANTIC:" in prompt
        assert "SELF:" in prompt
        assert "SOCIAL:" in prompt

    def test_contains_tick(self, memory_dir):
        prompt = build_compaction_prompt("Test-Creek", memory_dir, tick=999)
        assert "999" in prompt


class TestParseCompactionResponse:
    def test_valid_response(self):
        text = (
            "EPISODIC:\n"
            "Tick 100: Found food.\n"
            "Tick 120: Found more food.\n"
            "SEMANTIC:\n"
            "Food is common in the south.\n"
            "SELF:\n"
            "I am a capable forager.\n"
            "SOCIAL:\n"
            "Swift-Stone is unreliable."
        )
        result = parse_compaction_response(text)
        assert result is not None
        assert "episodic" in result
        assert "semantic" in result
        assert "self" in result
        assert "social" in result
        assert "Found food" in result["episodic"]
        assert "south" in result["semantic"]
        assert "forager" in result["self"]
        assert "unreliable" in result["social"]

    def test_missing_section_returns_none(self):
        text = (
            "EPISODIC:\nSome episodes.\n"
            "SEMANTIC:\nSome knowledge.\n"
            "SELF:\nSome assessment.\n"
            # SOCIAL section missing
        )
        result = parse_compaction_response(text)
        assert result is None

    def test_empty_input_returns_none(self):
        assert parse_compaction_response("") is None
        assert parse_compaction_response(None) is None

    def test_extra_text_before_sections(self):
        text = (
            "Here is my compacted memory:\n\n"
            "EPISODIC:\nTick 100: Found food.\n"
            "SEMANTIC:\nFood in south.\n"
            "SELF:\nI am Test-Creek.\n"
            "SOCIAL:\nSwift-Stone is unreliable."
        )
        result = parse_compaction_response(text)
        assert result is not None
        assert "Found food" in result["episodic"]


class TestApplyCompaction:
    def test_writes_all_files(self, memory_dir):
        sections = {
            "episodic": "Compacted episode 1.\nCompacted episode 2.",
            "semantic": "New general knowledge.",
            "self": "Updated self.",
            "social": "Updated social.",
        }
        apply_compaction(memory_dir, sections)

        assert (memory_dir / "episodic.md").read_text() == sections["episodic"]
        assert (memory_dir / "semantic.md").read_text() == sections["semantic"]
        assert (memory_dir / "self.md").read_text() == sections["self"]
        assert (memory_dir / "social.md").read_text() == sections["social"]

    def test_logs_to_compaction_jsonl(self, memory_dir, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        sections = {
            "episodic": "New episodes.",
            "semantic": "New knowledge.",
            "self": "New self.",
            "social": "New social.",
        }
        apply_compaction(memory_dir, sections, data_dir=data_dir)

        log_path = data_dir / "logs" / "compaction.jsonl"
        assert log_path.exists()
        import json
        record = json.loads(log_path.read_text().strip())
        assert "episodic" in record
        assert "before" in record["episodic"]
        assert "after" in record["episodic"]
        assert record["episodic"]["after"] == "New episodes."

    def test_before_state_captured(self, memory_dir, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        # Read the original content before compaction
        original_self = (memory_dir / "self.md").read_text().strip()
        original_social = (memory_dir / "social.md").read_text().strip()

        sections = {
            "episodic": "Compacted.",
            "semantic": "Compacted.",
            "self": "Compacted.",
            "social": "Compacted.",
        }
        result = apply_compaction(memory_dir, sections, data_dir=data_dir)

        assert result["self"]["before"] == original_self
        assert result["social"]["before"] == original_social
        assert result["self"]["after"] == "Compacted."
