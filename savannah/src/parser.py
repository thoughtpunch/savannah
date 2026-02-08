"""Robust action parsing from LLM output. Falls back to rest on failure."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Strip markdown backticks and surrounding whitespace from action text
_BACKTICK_RE = re.compile(r"`+")

# Supported actions and their argument patterns
# Order matters: more specific patterns first to avoid partial matches
ACTION_PATTERNS = [
    ("move", re.compile(r"move\s*\(\s*(n|s|e|w)\s*\)", re.IGNORECASE)),
    ("flee", re.compile(r"flee\s*\(\s*(n|s|e|w)\s*\)", re.IGNORECASE)),
    ("eat", re.compile(r"\beat\b", re.IGNORECASE)),
    ("recall", re.compile(r"""recall\s*\(\s*["']([^"']+)["']\s*\)""", re.IGNORECASE)),
    ("remember", re.compile(r"""remember\s*\(\s*["']([^"']+)["']\s*\)""", re.IGNORECASE)),
    ("signal", re.compile(r"""signal\s*\(\s*["']([^"']+)["']\s*\)""", re.IGNORECASE)),
    ("attack", re.compile(r"attack\s*\(\s*([a-zA-Z][\w-]*)\s*\)", re.IGNORECASE)),
    ("compact", re.compile(r"\bcompact\b", re.IGNORECASE)),
    ("observe", re.compile(r"\bobserve\b", re.IGNORECASE)),
    ("rest", re.compile(r"\brest\b", re.IGNORECASE)),
]

# Section extraction: match label then capture to next label or end
_SECTION_RE = re.compile(
    r"^(ACTION|WORKING|REASONING)\s*:\s*",
    re.IGNORECASE | re.MULTILINE,
)


def parse_action(raw_response: str) -> dict:
    """Parse an LLM response into a structured action dict.

    Returns:
        {
            "action": str,         # action name
            "args": str | None,    # action argument if any
            "working": str,        # updated working notes
            "reasoning": str,      # agent's reasoning
            "parse_failed": bool,  # True if we fell back to rest
        }
    """
    if not raw_response or not isinstance(raw_response, str):
        logger.warning("Empty or non-string response, defaulting to rest")
        return _default_rest("Empty response")

    # Split into labeled sections
    sections = _extract_sections(raw_response)

    action_text = sections.get("action", "").strip()
    working = sections.get("working", "").strip()
    reasoning = sections.get("reasoning", "").strip()

    if not action_text:
        logger.warning("No ACTION: line found, defaulting to rest")
        return _default_rest(raw_response)

    # Strip markdown backticks that LLMs sometimes add
    action_text = _BACKTICK_RE.sub("", action_text).strip()

    # Try to match an action pattern
    for action_name, pattern in ACTION_PATTERNS:
        match = pattern.search(action_text)
        if match:
            args = match.group(1).strip() if match.lastindex else None
            return {
                "action": action_name,
                "args": args,
                "working": working,
                "reasoning": reasoning,
                "parse_failed": False,
            }

    logger.warning("Unparseable action: %s", action_text[:100])
    return {
        "action": "rest",
        "args": None,
        "working": working,
        "reasoning": reasoning,
        "parse_failed": True,
    }


def _extract_sections(text: str) -> dict[str, str]:
    """Split response into ACTION/WORKING/REASONING sections.

    Handles multi-line WORKING blocks correctly by splitting at
    section labels rather than just taking the first line.
    """
    sections: dict[str, str] = {}
    matches = list(_SECTION_RE.finditer(text))

    for i, m in enumerate(matches):
        label = m.group(1).lower()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[label] = text[start:end].strip()

    return sections


def _default_rest(context: str) -> dict:
    return {
        "action": "rest",
        "args": None,
        "working": "",
        "reasoning": f"(parse failure: {context[:100]})",
        "parse_failed": True,
    }
