"""Robust action parsing from LLM output. Falls back to rest on failure."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Supported actions and their argument patterns
ACTION_PATTERNS = {
    "move": re.compile(r"move\s*\(\s*(n|s|e|w)\s*\)", re.IGNORECASE),
    "eat": re.compile(r"eat\b", re.IGNORECASE),
    "recall": re.compile(r'recall\s*\(\s*"([^"]+)"\s*\)', re.IGNORECASE),
    "remember": re.compile(r'remember\s*\(\s*"([^"]+)"\s*\)', re.IGNORECASE),
    "compact": re.compile(r"compact\b", re.IGNORECASE),
    "signal": re.compile(r'signal\s*\(\s*"([^"]+)"\s*\)', re.IGNORECASE),
    "observe": re.compile(r"observe\b", re.IGNORECASE),
    "attack": re.compile(r"attack\s*\(\s*([a-zA-Z][\w-]*)\s*\)", re.IGNORECASE),
    "flee": re.compile(r"flee\s*\(\s*(n|s|e|w)\s*\)", re.IGNORECASE),
    "rest": re.compile(r"rest\b", re.IGNORECASE),
}

# Extract the three response fields
ACTION_LINE = re.compile(r"ACTION:\s*(.+)", re.IGNORECASE)
WORKING_LINE = re.compile(r"WORKING:\s*(.+)", re.IGNORECASE | re.DOTALL)
REASONING_LINE = re.compile(r"REASONING:\s*(.+)", re.IGNORECASE | re.DOTALL)


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

    # Extract ACTION line
    action_match = ACTION_LINE.search(raw_response)
    if not action_match:
        logger.warning("No ACTION: line found, defaulting to rest")
        return _default_rest(raw_response)

    action_text = action_match.group(1).strip()

    # Extract WORKING and REASONING
    working = ""
    working_match = WORKING_LINE.search(raw_response)
    if working_match:
        working = working_match.group(1).strip()
        # Trim at REASONING if it bleeds in
        if "REASONING:" in working:
            working = working[: working.index("REASONING:")].strip()

    reasoning = ""
    reasoning_match = REASONING_LINE.search(raw_response)
    if reasoning_match:
        reasoning = reasoning_match.group(1).strip()

    # Parse the action
    for action_name, pattern in ACTION_PATTERNS.items():
        match = pattern.search(action_text)
        if match:
            args = match.group(1) if match.lastindex else None
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


def _default_rest(context: str) -> dict:
    return {
        "action": "rest",
        "args": None,
        "working": "",
        "reasoning": f"(parse failure: {context[:100]})",
        "parse_failed": True,
    }
