"""Configuration and on-disk layout.

Everything the user generates lives under `data/` and is git-ignored, so a
fork of this repository never carries someone else's games or progress.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
GAMES = DATA / "games"
REPORTS = DATA / "reports"
TEMPLATES = ROOT / "templates"
CONFIG_PATH = ROOT / "config.json"

# State files copied out of templates/ on first run. The agent reads and
# rewrites these; they are the memory of the coaching relationship.
STATE_FILES = ("player-state.md", "repertoire.md", "mistake-patterns.md")

# Instructions live in AGENTS.md so every agent reads one source. Claude Code
# looks for CLAUDE.md, so setup drops a pointer file next to it.
AGENT_INSTRUCTIONS = ROOT / "AGENTS.md"
CLAUDE_ALIAS = ROOT / "CLAUDE.md"
CLAUDE_ALIAS_BODY = """# Kibitz

@AGENTS.md

This file exists only so Claude Code picks up the instructions, which live in
`AGENTS.md` so that Codex, Cursor and other agents read the same source. Edit
`AGENTS.md`, not this file.
"""


def ensure_claude_alias() -> bool:
    """Create CLAUDE.md if it is missing. Returns True when it was created."""
    if CLAUDE_ALIAS.exists() or not AGENT_INSTRUCTIONS.exists():
        return False
    CLAUDE_ALIAS.write_text(CLAUDE_ALIAS_BODY, encoding="utf-8")
    return True


@dataclass
class Config:
    platform: str          # "lichess" or "chesscom"
    username: str
    engine_path: str = ""  # empty means "discover it each run"
    depth: int = 18
    threads: int = 2
    hash_mb: int = 256

    @classmethod
    def load(cls) -> "Config":
        if not CONFIG_PATH.exists():
            raise FileNotFoundError(
                "No config.json found. Run `python coach.py setup` first."
            )
        return cls(**json.loads(CONFIG_PATH.read_text(encoding="utf-8")))

    def save(self) -> None:
        CONFIG_PATH.write_text(
            json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8"
        )


def ensure_dirs() -> None:
    for path in (DATA, GAMES, REPORTS):
        path.mkdir(parents=True, exist_ok=True)
