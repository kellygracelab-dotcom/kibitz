"""Turning raw engine output into something a coach can talk about.

A list of centipawn losses is not teaching material. These helpers pull out
the two things that actually generalise between games: which mistakes were
worst, and whether the player was even looking when they made them.
"""

from __future__ import annotations

import statistics

# A move played this fast was not chosen — it was reflex.
INSTANT_SECONDS = 3.0

# Worth flagging in the habit check; below this it is noise.
HABIT_LOSS_CP = 100


def my_side(game: dict, username: str) -> str:
    """Which colour the configured player had in this game."""
    if game["white"].lower() == username.lower():
        return "white"
    if game["black"].lower() == username.lower():
        return "black"
    return "white"


def time_stats(game: dict, side: str) -> dict | None:
    """Time budget and, more usefully, whether hard moves got more of it."""
    moves = [m for m in game["moves"] if m["side"] == side and m.get("seconds") is not None]
    if not moves:
        return None

    base, _, increment = game.get("time_control", "").partition("+")
    try:
        budget = float(base) + float(increment or 0) * len(moves)
    except ValueError:
        budget = 0.0

    used = sum(m["seconds"] for m in moves)
    clean = [m["seconds"] for m in moves if m["verdict"] == "ok"]
    errors = [m["seconds"] for m in moves if m["verdict"] != "ok"]

    return {
        "moves": len(moves),
        "used": round(used),
        "budget": round(budget),
        "share": round(used / budget * 100) if budget else None,
        "avg": round(used / len(moves), 1),
        "long_thinks": sum(1 for m in moves if m["seconds"] >= 8),
        "instant": sum(1 for m in moves if m["seconds"] < INSTANT_SECONDS),
        "median_clean": round(statistics.median(clean), 1) if clean else None,
        "median_error": round(statistics.median(errors), 1) if errors else None,
    }


def habit_check(game: dict, side: str) -> dict:
    """Moves played immediately after the opponent changed the material count.

    This is where reflex costs the most: the board just changed, and the
    natural reply gets played before the position is re-read.
    """
    replies = [m for m in game["moves"] if m["side"] == side and m["after_capture"]]
    failures = [m for m in replies if m["loss_cp"] >= HABIT_LOSS_CP]
    return {
        "total": len(replies),
        "failures": failures,
        "clean": not failures,
        "worst": max((m["loss_cp"] for m in replies), default=0),
    }


def worst_moves(game: dict, side: str, limit: int = 3) -> list[dict]:
    moves = [m for m in game["moves"] if m["side"] == side and m["verdict"] != "ok"]
    return sorted(moves, key=lambda m: -m["loss_cp"])[:limit]


def _fmt_seconds(move: dict) -> str:
    return f"{move['seconds']:.0f}s" if move.get("seconds") is not None else "-"


def render(game: dict, username: str) -> str:
    side = my_side(game, username)
    opponent = game["black"] if side == "white" else game["white"]
    lines: list[str] = []

    lines.append(f"# {game['date']} — vs {opponent} ({side})")
    lines.append("")
    header = " ".join(filter(None, (game["eco"], game["opening"])))
    if header:
        lines.append(f"- Opening: {header}")
    lines.append(f"- Result: {game['result']}   Time control: {game['time_control'] or 'n/a'}")
    lines.append(f"- ACPL: **you {game['acpl'][side]}**, opponent {game['acpl']['white' if side == 'black' else 'black']}")
    if game["site"]:
        lines.append(f"- Game: {game['site']}")
    lines.append("")

    flagged = [m for m in game["moves"] if m["side"] == side and m["verdict"] != "ok"]
    lines.append("## Your mistakes")
    lines.append("")
    if not flagged:
        lines.append("None above the inaccuracy threshold.")
    else:
        lines.append("| Move | Played | Better | Loss | Verdict | Time |")
        lines.append("|---|---|---|---|---|---|")
        for move in flagged:
            lines.append(
                f"| {move['move_number']} | {move['san']} | {move['best_san']} | "
                f"-{move['loss_cp']} | {move['verdict']} | {_fmt_seconds(move)} |"
            )
    lines.append("")

    stats = time_stats(game, side)
    if stats:
        lines.append("## Time")
        lines.append("")
        share = f" ({stats['share']}%)" if stats["share"] is not None else ""
        lines.append(f"- Used {stats['used']}s of {stats['budget']}s{share}, {stats['avg']}s per move")
        lines.append(f"- Long thinks (8s+): {stats['long_thinks']} | instant moves (<3s): {stats['instant']} of {stats['moves']}")
        if stats["median_clean"] is not None and stats["median_error"] is not None:
            lines.append(
                f"- Median time: {stats['median_clean']}s on sound moves, "
                f"{stats['median_error']}s on mistakes"
            )
            if stats["median_error"] <= stats["median_clean"]:
                lines.append(
                    "  - Mistakes got no more thought than routine moves — "
                    "hard positions are not being recognised as hard."
                )
        lines.append("")

    habit = habit_check(game, side)
    lines.append("## Habit check — replies to captures")
    lines.append("")
    if habit["total"] == 0:
        lines.append("No captures to reply to in this game.")
    elif habit["clean"]:
        lines.append(
            f"Clean. {habit['total']} replies after a capture, worst loss {habit['worst']}."
        )
    else:
        lines.append(f"{len(habit['failures'])} of {habit['total']} replies cost 100+ centipawns:")
        lines.append("")
        for move in habit["failures"]:
            lines.append(
                f"- Move {move['move_number']}: `{move['san']}` "
                f"({_fmt_seconds(move)}, -{move['loss_cp']}) — better was `{move['best_san']}`"
            )
    lines.append("")
    return "\n".join(lines)


def render_many(games: list[dict], username: str) -> str:
    parts = [render(game, username) for game in games]
    if len(games) > 1:
        summary = ["# Summary", ""]
        summary.append("| Date | Opening | Result | Your ACPL |")
        summary.append("|---|---|---|---|")
        for game in games:
            side = my_side(game, username)
            summary.append(
                f"| {game['date']} | {game['opening'] or game['eco'] or '?'} | "
                f"{game['result']} | {game['acpl'][side]} |"
            )
        summary.append("")
        parts.insert(0, "\n".join(summary))
    return "\n---\n\n".join(parts)
