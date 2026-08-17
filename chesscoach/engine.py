"""Stockfish discovery and game analysis.

The engine is the only source of truth about positions in this project. The
language model explains; it never evaluates. Everything in this module exists
to make the engine's verdict cheap enough to run after every game.
"""

from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass, asdict
from pathlib import Path

import chess
import chess.engine
import chess.pgn

# Once a position is winning, dropping from +12 to +6 is not a mistake.
# Clamping keeps those swings out of the report.
EVAL_CLAMP_CP = 1000

# Centipawn loss thresholds. Same spirit as Lichess's classification.
THRESHOLDS = ((300, "blunder"), (100, "mistake"), (50, "inaccuracy"))

COMMON_PATHS = (
    r"C:\Program Files\Stockfish\stockfish.exe",
    r"C:\Program Files (x86)\Stockfish\stockfish.exe",
    "/usr/games/stockfish",
    "/usr/local/bin/stockfish",
    "/opt/homebrew/bin/stockfish",
)

# winget adds its shim to PATH only after a shell restart, so look inside the
# package directory directly.
WINGET_GLOB = r"Microsoft\WinGet\Packages\Stockfish.Stockfish_*\**\stockfish*.exe"

INSTALL_HINTS = {
    "Windows": "winget install --id Stockfish.Stockfish",
    "Darwin": "brew install stockfish",
    "Linux": "sudo apt install stockfish   (or your distro's package manager)",
}


class EngineNotFound(RuntimeError):
    def __init__(self) -> None:
        hint = INSTALL_HINTS.get(platform.system(), "install Stockfish")
        super().__init__(
            "Stockfish was not found.\n"
            f"  Install it:  {hint}\n"
            "  Or download from https://stockfishchess.org/download/\n"
            "  Then re-run setup, or set STOCKFISH_PATH to the executable."
        )


@dataclass
class MoveReport:
    ply: int
    move_number: int
    side: str
    san: str
    best_san: str
    eval_before_cp: int
    eval_after_cp: int
    loss_cp: int
    verdict: str
    seconds: float | None = None
    after_capture: bool = False


def find_engine(explicit: str | None = None) -> str:
    """Argument, then env var, then PATH, then the usual install locations."""
    for candidate in (explicit, os.environ.get("STOCKFISH_PATH")):
        if candidate and Path(candidate).is_file():
            return candidate

    found = shutil.which("stockfish")
    if found:
        return found

    for path in COMMON_PATHS:
        if Path(path).is_file():
            return path

    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        for path in sorted(Path(local_appdata).glob(WINGET_GLOB)):
            if path.is_file():
                return str(path)

    raise EngineNotFound()


def open_engine(path: str, threads: int, hash_mb: int) -> chess.engine.SimpleEngine:
    engine = chess.engine.SimpleEngine.popen_uci(path)
    engine.configure({"Threads": threads, "Hash": hash_mb})
    return engine


def _clamp(value: int) -> int:
    return max(-EVAL_CLAMP_CP, min(EVAL_CLAMP_CP, value))


def _classify(loss_cp: int) -> str:
    for threshold, verdict in THRESHOLDS:
        if loss_cp >= threshold:
            return verdict
    return "ok"


def _parse_time_control(header: str) -> tuple[float, float] | None:
    try:
        base, _, increment = header.partition("+")
        return float(base), float(increment or 0)
    except ValueError:
        return None


def move_times(game: chess.pgn.Game) -> list[float | None]:
    """Seconds spent on each half-move, derived from PGN clock comments.

    Clocks record time remaining *after* a move, so a move's cost is the drop
    from that side's previous reading, plus the increment it just earned.
    """
    control = _parse_time_control(game.headers.get("TimeControl", ""))
    if not control:
        return []
    base, increment = control

    remaining = {chess.WHITE: base, chess.BLACK: base}
    spent: list[float | None] = []
    for node in game.mainline():
        mover = not node.board().turn  # the move is already played
        clock = node.clock()
        if clock is None:
            spent.append(None)
            continue
        spent.append(round(remaining[mover] - clock + increment, 1))
        remaining[mover] = clock
    return spent


def analyse_game(
    game: chess.pgn.Game, engine: chess.engine.SimpleEngine, depth: int
) -> dict:
    """Evaluate every position once; a move's cost is the gap it opens.

    Analysing each position a single time (rather than before and after every
    move) halves the engine work for an identical result.
    """
    moves = list(game.mainline_moves())
    limit = chess.engine.Limit(depth=depth)

    scores: list[int] = []
    best_moves: list[chess.Move | None] = []
    positions: list[chess.Board] = []

    probe = game.board()
    for move in moves + [None]:
        info = engine.analyse(probe, limit)
        scores.append(_clamp(info["score"].white().score(mate_score=10000)))
        pv = info.get("pv") or []
        best_moves.append(pv[0] if pv else None)
        positions.append(probe.copy())
        if move is None:
            break
        probe.push(move)

    times = move_times(game)
    reports: list[MoveReport] = []
    for index, move in enumerate(moves):
        position = positions[index]
        white_to_move = position.turn == chess.WHITE
        sign = 1 if white_to_move else -1

        before = sign * scores[index]
        after = sign * scores[index + 1]
        loss = max(0, before - after)
        best = best_moves[index]

        reports.append(
            MoveReport(
                ply=index + 1,
                move_number=position.fullmove_number,
                side="white" if white_to_move else "black",
                san=position.san(move),
                best_san=position.san(best) if best else "",
                eval_before_cp=before,
                eval_after_cp=after,
                loss_cp=loss,
                verdict=_classify(loss),
                seconds=times[index] if index < len(times) else None,
                after_capture=index > 0 and positions[index - 1].is_capture(moves[index - 1]),
            )
        )

    return {
        "site": game.headers.get("Site", ""),
        "date": game.headers.get("Date", "?"),
        "white": game.headers.get("White", "?"),
        "black": game.headers.get("Black", "?"),
        "result": game.headers.get("Result", "*"),
        "eco": game.headers.get("ECO", ""),
        "opening": game.headers.get("Opening", ""),
        "time_control": game.headers.get("TimeControl", ""),
        "acpl": _acpl(reports),
        "moves": [asdict(report) for report in reports],
    }


def _acpl(reports: list[MoveReport]) -> dict:
    """Average centipawn loss — the standard one-number summary of accuracy."""
    result = {}
    for side in ("white", "black"):
        losses = [report.loss_cp for report in reports if report.side == side]
        result[side] = round(sum(losses) / len(losses)) if losses else 0
    return result
