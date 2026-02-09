"""Memory system — recall (BM25 keyword search), remember, compact."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path


def recall(memory_dir: Path, query: str, max_results: int = 3) -> list[str]:
    """Search all memory files for chunks matching query using BM25 scoring.

    Returns the top K most relevant chunks (paragraph-level).
    """
    chunks = _load_all_chunks(memory_dir)
    if not chunks:
        return ["No relevant memories found."]

    scored = _bm25_score(chunks, query)
    top = sorted(scored, key=lambda x: x[1], reverse=True)[:max_results]

    # Filter out zero-score results
    results = [chunk for chunk, score in top if score > 0]
    return results if results else ["No relevant memories found."]


def remember(memory_dir: Path, text: str) -> None:
    """Append an entry to episodic memory."""
    episodic = memory_dir / "episodic.md"
    current = episodic.read_text() if episodic.exists() else ""
    episodic.write_text(current + "\n" + text.strip() + "\n")


def get_episodic_entries(memory_dir: Path, last_n: int = 30) -> list[str]:
    """Get the last N entries from episodic memory."""
    episodic = memory_dir / "episodic.md"
    if not episodic.exists():
        return []
    lines = [line.strip() for line in episodic.read_text().split("\n") if line.strip()]
    return lines[-last_n:]


def read_memory_file(memory_dir: Path, filename: str) -> str:
    """Read a memory file, returning empty string if missing."""
    path = memory_dir / filename
    return path.read_text().strip() if path.exists() else ""


def write_memory_file(memory_dir: Path, filename: str, content: str) -> None:
    """Overwrite a memory file."""
    (memory_dir / filename).write_text(content)


# ── Compaction ─────────────────────────────────────────────────────


# Regex to split compaction response into labeled sections
_COMPACTION_SECTION_RE = re.compile(
    r"^(EPISODIC|SEMANTIC|SELF|SOCIAL)\s*:\s*",
    re.IGNORECASE | re.MULTILINE,
)


def build_compaction_prompt(name: str, memory_dir: Path, tick: int) -> str:
    """Build the LLM prompt for memory compaction.

    Reads the last 30 episodic entries and all memory files, then asks
    the LLM to rewrite them in a more compact form.
    """
    episodes = get_episodic_entries(memory_dir, last_n=30)
    episodes_text = "\n".join(episodes) if episodes else "(none)"
    semantic = read_memory_file(memory_dir, "semantic.md")
    self_text = read_memory_file(memory_dir, "self.md")
    social = read_memory_file(memory_dir, "social.md")

    return (
        f"[COMPACTION MODE - Tick {tick}] You are {name}.\n"
        f"\n"
        f"Recent episodes (last 30):\n"
        f"{episodes_text}\n"
        f"\n"
        f"Current general knowledge:\n"
        f"{semantic}\n"
        f"\n"
        f"Current self-assessment:\n"
        f"{self_text}\n"
        f"\n"
        f"Current social knowledge:\n"
        f"{social}\n"
        f"\n"
        f"Rewrite each file. Summarize episodes into general knowledge. "
        f"Remove redundant episodes. Update your self-assessment and social "
        f"knowledge. Be concise — storage is limited.\n"
        f"\n"
        f"Respond in this exact format:\n"
        f"EPISODIC:\n"
        f"(summarized recent episodes, keep only unique events)\n"
        f"SEMANTIC:\n"
        f"(updated general knowledge)\n"
        f"SELF:\n"
        f"(updated self-assessment)\n"
        f"SOCIAL:\n"
        f"(updated social knowledge)"
    )


def parse_compaction_response(text: str) -> dict | None:
    """Parse a compaction LLM response into its four sections.

    Returns a dict with keys 'episodic', 'semantic', 'self', 'social',
    or None if any section is missing (parse failure).
    """
    if not text or not isinstance(text, str):
        return None

    sections: dict[str, str] = {}
    matches = list(_COMPACTION_SECTION_RE.finditer(text))

    for i, m in enumerate(matches):
        label = m.group(1).lower()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[label] = text[start:end].strip()

    required = {"episodic", "semantic", "self", "social"}
    if not required.issubset(sections.keys()):
        return None

    return sections


def apply_compaction(
    memory_dir: Path, sections: dict, data_dir: Path | None = None
) -> dict:
    """Write compacted sections to memory files and optionally log.

    Reads the BEFORE state of all four files, writes the new content,
    and if data_dir is provided, appends a before/after record to
    data_dir/logs/compaction.jsonl.

    Returns a dict with before/after for each file.
    """
    file_map = {
        "episodic": "episodic.md",
        "semantic": "semantic.md",
        "self": "self.md",
        "social": "social.md",
    }

    result: dict[str, dict[str, str]] = {}
    for key, filename in file_map.items():
        before = read_memory_file(memory_dir, filename)
        write_memory_file(memory_dir, filename, sections[key])
        result[key] = {"before": before, "after": sections[key]}

    if data_dir is not None:
        log_dir = data_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "compaction.jsonl"
        with open(log_path, "a") as f:
            f.write(json.dumps(result) + "\n")

    return result


# ── BM25 implementation ────────────────────────────────────────────


def _load_all_chunks(memory_dir: Path) -> list[str]:
    """Load all memory files and split into paragraph-level chunks."""
    chunks = []
    for md_file in memory_dir.glob("*.md"):
        text = md_file.read_text()
        # Split on double newlines (paragraphs) or single entries
        paragraphs = re.split(r"\n\n+", text)
        for p in paragraphs:
            p = p.strip()
            if p:
                chunks.append(p)
    return chunks


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenization, lowercased."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _bm25_score(
    chunks: list[str], query: str, k1: float = 1.5, b: float = 0.75
) -> list[tuple[str, float]]:
    """Score chunks against query using BM25."""
    query_tokens = _tokenize(query)
    if not query_tokens:
        return [(c, 0.0) for c in chunks]

    # Document frequencies
    n = len(chunks)
    chunk_tokens = [_tokenize(c) for c in chunks]
    avg_dl = sum(len(t) for t in chunk_tokens) / max(n, 1)

    # IDF for query terms
    df = Counter()
    for tokens in chunk_tokens:
        unique = set(tokens)
        for qt in query_tokens:
            if qt in unique:
                df[qt] += 1

    results = []
    for chunk, tokens in zip(chunks, chunk_tokens, strict=True):
        tf = Counter(tokens)
        dl = len(tokens)
        score = 0.0
        for qt in query_tokens:
            if df[qt] == 0:
                continue
            idf = math.log((n - df[qt] + 0.5) / (df[qt] + 0.5) + 1)
            tf_norm = (tf[qt] * (k1 + 1)) / (
                tf[qt] + k1 * (1 - b + b * dl / max(avg_dl, 1))
            )
            score += idf * tf_norm
        results.append((chunk, score))

    return results
