#!/usr/bin/env python3
"""Kibitz - command line entry point.

    python coach.py setup      first-run wizard
    python coach.py sync       download recent games
    python coach.py analyze    run Stockfish over them
    python coach.py status     what is on disk right now
"""

from __future__ import annotations

import argparse
import io
import json
import re
import shutil
import sys
from pathlib import Path

import chess.pgn

from chesscoach import config as cfg
from chesscoach import engine as eng
from chesscoach import platforms, report

BANNER = "Kibitz"

HOW_IT_WORKS = """
Setup complete.

How this works
--------------
  1. You play games on {platform}. Play slow ones - the engine cannot tell
     "did not see it" apart from "did not understand it".
  2. `python coach.py sync` pulls them into data/games/.
  3. `python coach.py analyze` runs Stockfish and writes a report into
     data/reports/: mistakes, time spent per move, and a habit check.
  4. You open this folder in your AI coding agent and ask it to coach you.
     It reads AGENTS.md, the latest report, and your three state files:

       data/player-state.md       where you are and what you are working on
       data/repertoire.md         your openings and the plan behind each
       data/mistake-patterns.md   errors confirmed across three games

     Codex and Cursor read AGENTS.md directly; Claude Code reads the CLAUDE.md
     pointer created above. Both end up at the same instructions.

The division of labour is the point. The engine owns evaluation; the agent
owns explanation and never overrules the numbers. That is what keeps the
coaching honest instead of confidently wrong.

Next: play a game, then run

    python coach.py sync
    python coach.py analyze
"""


def _ask(prompt: str, valid: tuple[str, ...] | None = None) -> str:
    while True:
        answer = input(prompt).strip()
        if not answer:
            continue
        if valid and answer.lower() not in valid:
            print("  Pick one of: " + ", ".join(valid))
            continue
        return answer


def _outcome(headers: dict, username: str) -> tuple[str, str]:
    """Colour played and result, from the configured player's point of view."""
    side = "white" if headers.get("White", "").lower() == username.lower() else "black"
    result = headers.get("Result", "*")
    if result == "1/2-1/2":
        return side, "draw"
    if result == "*":
        return side, "unfinished"
    winner = "white" if result == "1-0" else "black"
    return side, "win" if winner == side else "loss"


def _safe_stem(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", text).strip("-") or "game"


# --------------------------------------------------------------------------
# setup
# --------------------------------------------------------------------------

def cmd_setup(args: argparse.Namespace) -> int:
    print("\n" + BANNER + " - setup\n")
    print("This tool pairs a chess engine with an AI coding agent.")
    print("Stockfish decides what is true about a position; the agent explains")
    print("why, and tracks which mistakes you keep repeating.\n")

    print("Step 1 of 3 - your account\n")
    print("  1) Lichess")
    print("  2) Chess.com")
    choice = _ask(
        "Which platform do you play on? [1/2]: ",
        ("1", "2", "lichess", "chess.com", "chesscom"),
    ).lower()
    platform = "lichess" if choice in ("1", "lichess") else "chesscom"
    label = platforms.PLATFORM_LABELS[platform]

    while True:
        username = _ask("Your " + label + " username: ")
        print("  checking...", end=" ", flush=True)
        try:
            profile = platforms.verify(platform, username)
        except platforms.PlatformError as error:
            print("failed (" + str(error) + "). Try again.")
            continue
        print("found.")
        username = profile["username"]
        if profile["ratings"]:
            ratings = ", ".join(
                k + " " + str(v) for k, v in sorted(profile["ratings"].items())
            )
            print("  Ratings: " + ratings)
        break

    print("\nStep 2 of 3 - the engine\n")
    if args.engine and not Path(args.engine).is_file():
        print("  No Stockfish executable at: " + args.engine)
        print()
        print("Setup stopped. Check the path passed to --engine.")
        return 1

    try:
        engine_path = eng.find_engine(args.engine)
    except eng.EngineNotFound as error:
        print("  " + str(error) + "\n")
        print("Setup stopped. Install Stockfish, then run setup again.")
        return 1
    print("  Stockfish found: " + engine_path)

    print("\nStep 3 of 3 - your files\n")
    cfg.ensure_dirs()
    created = []
    for name in cfg.STATE_FILES:
        target = cfg.DATA / name
        if target.exists():
            continue
        shutil.copyfile(cfg.TEMPLATES / name, target)
        created.append(name)
    if created:
        print("  data/ ready, created: " + ", ".join(created))
    else:
        print("  data/ ready (state files already existed)")

    if cfg.ensure_claude_alias():
        print("  CLAUDE.md created (points at AGENTS.md, for Claude Code)")
    else:
        print("  CLAUDE.md already present")

    cfg.Config(
        platform=platform,
        username=username,
        engine_path=engine_path,
        depth=args.depth,
    ).save()
    print("  config.json written (git-ignored, stays on your machine)")

    print(HOW_IT_WORKS.format(platform=label))
    return 0


# --------------------------------------------------------------------------
# sync
# --------------------------------------------------------------------------

def cmd_sync(args: argparse.Namespace) -> int:
    configuration = cfg.Config.load()
    cfg.ensure_dirs()
    print("Fetching up to " + str(args.count) + " game(s) for " + configuration.username + "...")
    try:
        pgns = platforms.fetch_games(
            configuration.platform, configuration.username, args.count
        )
    except platforms.PlatformError as error:
        print("Failed: " + str(error))
        return 1

    if not pgns:
        print("No games found.")
        return 0

    saved = []
    for text in pgns:
        game = chess.pgn.read_game(io.StringIO(text))
        if game is None:
            continue
        headers = dict(game.headers)
        side, outcome = _outcome(headers, configuration.username)
        date = headers.get("UTCDate") or headers.get("Date", "0000.00.00")
        stem = _safe_stem(date.replace(".", "-") + "-" + side + "-" + outcome)
        target = cfg.GAMES / (stem + ".pgn")
        index = 2
        while target.exists():
            target = cfg.GAMES / (stem + "-" + str(index) + ".pgn")
            index += 1
        target.write_text(text.strip() + "\n", encoding="utf-8")
        saved.append(target.name)

    print("Saved " + str(len(saved)) + " game(s) to data/games/:")
    for name in saved:
        print("  " + name)
    print("\nNext: python coach.py analyze")
    return 0


# --------------------------------------------------------------------------
# analyze
# --------------------------------------------------------------------------

def cmd_analyze(args: argparse.Namespace) -> int:
    configuration = cfg.Config.load()
    cfg.ensure_dirs()

    if args.game:
        target = cfg.GAMES / args.game
        if not target.exists():
            print("No such game: " + str(target))
            return 1
        targets = [target]
    else:
        found = sorted(cfg.GAMES.glob("*.pgn"), key=lambda p: p.stat().st_mtime)
        targets = found[-args.last:]

    if not targets:
        print("No games on disk. Run `python coach.py sync` first.")
        return 1

    try:
        engine_path = eng.find_engine(configuration.engine_path or None)
    except eng.EngineNotFound as error:
        print(error)
        return 1

    depth = args.depth or configuration.depth
    engine = eng.open_engine(engine_path, configuration.threads, configuration.hash_mb)
    analysed: list[dict] = []
    try:
        for path in targets:
            print("Analysing " + path.name + " at depth " + str(depth) + "...", file=sys.stderr)
            with path.open(encoding="utf-8") as handle:
                while True:
                    game = chess.pgn.read_game(handle)
                    if game is None:
                        break
                    result = eng.analyse_game(game, engine, depth)
                    result["source"] = path.name
                    analysed.append(result)
    finally:
        engine.quit()

    if not analysed:
        print("Nothing to analyse - the PGN files contained no games.")
        return 1

    markdown = report.render_many(analysed, configuration.username)
    print("\n" + markdown)

    stem = targets[0].stem if len(targets) == 1 else "latest"
    (cfg.REPORTS / (stem + ".md")).write_text(markdown, encoding="utf-8")
    (cfg.REPORTS / (stem + ".json")).write_text(
        json.dumps(analysed, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\nWritten: data/reports/" + stem + ".md and .json", file=sys.stderr)
    print("Now open this folder in your AI agent and ask it to go through the report.", file=sys.stderr)
    return 0


# --------------------------------------------------------------------------
# status
# --------------------------------------------------------------------------

def cmd_status(_: argparse.Namespace) -> int:
    configuration = cfg.Config.load()
    games = sorted(cfg.GAMES.glob("*.pgn"))
    reports = sorted(cfg.REPORTS.glob("*.md"))
    print(BANNER)
    print("  Platform : " + platforms.PLATFORM_LABELS[configuration.platform])
    print("  Username : " + configuration.username)
    print("  Depth    : " + str(configuration.depth))
    print("  Games    : " + str(len(games)) + " in data/games/")
    print("  Reports  : " + str(len(reports)) + " in data/reports/")
    for name in cfg.STATE_FILES:
        mark = "ok" if (cfg.DATA / name).exists() else "MISSING"
        print("  " + name.ljust(24) + " " + mark)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="coach", description="Kibitz - engine-grounded chess study")
    sub = parser.add_subparsers(dest="command", required=True)

    setup = sub.add_parser("setup", help="first-run wizard")
    setup.add_argument("--engine", help="path to the Stockfish executable")
    setup.add_argument("--depth", type=int, default=18, help="analysis depth (default 18)")
    setup.set_defaults(func=cmd_setup)

    sync = sub.add_parser("sync", help="download recent games")
    sync.add_argument("-n", "--count", type=int, default=1, help="how many games (default 1)")
    sync.set_defaults(func=cmd_sync)

    analyze = sub.add_parser("analyze", help="run Stockfish over saved games")
    analyze.add_argument("--game", help="a single file name inside data/games/")
    analyze.add_argument("--last", type=int, default=1, help="analyse the N most recent (default 1)")
    analyze.add_argument("--depth", type=int, help="override the configured depth")
    analyze.set_defaults(func=cmd_analyze)

    status = sub.add_parser("status", help="show what is on disk")
    status.set_defaults(func=cmd_status)

    args = parser.parse_args()
    try:
        return args.func(args)
    except FileNotFoundError as error:
        print(error)
        return 1
    except KeyboardInterrupt:
        print("\nCancelled.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
