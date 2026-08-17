"""Fetching games from Lichess and Chess.com.

Only the standard library is used here so the single external dependency of
this project stays `python-chess`.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Iterable

USER_AGENT = "kibitz/1.0 (https://github.com/kellygracelab-dotcom/kibitz)"
TIMEOUT = 30

PLATFORMS = ("lichess", "chesscom")
PLATFORM_LABELS = {"lichess": "Lichess", "chesscom": "Chess.com"}


class PlatformError(RuntimeError):
    pass


def _get(url: str, accept: str = "application/json") -> bytes:
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": accept}
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise PlatformError("not found") from error
        raise PlatformError(f"HTTP {error.code} from {url}") from error
    except urllib.error.URLError as error:
        raise PlatformError(f"network error: {error.reason}") from error


def split_pgn(text: str) -> list[str]:
    """Split a multi-game PGN blob into individual games."""
    chunks = re.split(r"(?m)^(?=\[Event )", text.strip())
    return [chunk.strip() for chunk in chunks if chunk.strip()]


# --------------------------------------------------------------------------
# Lichess
# --------------------------------------------------------------------------

def lichess_verify(username: str) -> dict:
    data = json.loads(_get(f"https://lichess.org/api/user/{username}"))
    perfs = {
        name: perf.get("rating")
        for name, perf in (data.get("perfs") or {}).items()
        if perf.get("games")
    }
    return {
        "username": data.get("username", username),
        "games": (data.get("count") or {}).get("all", 0),
        "ratings": perfs,
    }


def lichess_games(username: str, count: int) -> list[str]:
    url = (
        f"https://lichess.org/api/games/user/{username}"
        f"?max={count}&clocks=true&opening=true&evals=false"
    )
    raw = _get(url, accept="application/x-chess-pgn").decode("utf-8", "replace")
    return split_pgn(raw)


# --------------------------------------------------------------------------
# Chess.com
# --------------------------------------------------------------------------

def chesscom_verify(username: str) -> dict:
    data = json.loads(_get(f"https://api.chess.com/pub/player/{username}"))
    ratings = {}
    try:
        stats = json.loads(
            _get(f"https://api.chess.com/pub/player/{username}/stats")
        )
        for key, value in stats.items():
            if key.startswith("chess_") and isinstance(value, dict):
                rating = (value.get("last") or {}).get("rating")
                if rating:
                    ratings[key.replace("chess_", "")] = rating
    except PlatformError:
        pass
    return {
        "username": data.get("username", username),
        "games": 0,  # Chess.com exposes no cheap total; archives cover it
        "ratings": ratings,
    }


def chesscom_games(username: str, count: int) -> list[str]:
    """Walk monthly archives backwards until `count` games are collected."""
    archives = json.loads(
        _get(f"https://api.chess.com/pub/player/{username}/games/archives")
    ).get("archives", [])

    collected: list[str] = []
    for archive_url in reversed(archives):
        month = json.loads(_get(archive_url))
        for game in reversed(month.get("games", [])):
            pgn = game.get("pgn")
            if pgn:
                collected.append(pgn.strip())
            if len(collected) >= count:
                return collected
    return collected


# --------------------------------------------------------------------------
# Dispatch
# --------------------------------------------------------------------------

def verify(platform: str, username: str) -> dict:
    if platform == "lichess":
        return lichess_verify(username)
    if platform == "chesscom":
        return chesscom_verify(username)
    raise PlatformError(f"unknown platform: {platform}")


def fetch_games(platform: str, username: str, count: int) -> list[str]:
    if platform == "lichess":
        return lichess_games(username, count)
    if platform == "chesscom":
        return chesscom_games(username, count)
    raise PlatformError(f"unknown platform: {platform}")
