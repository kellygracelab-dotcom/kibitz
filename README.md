# Kibitz

**A kibitzer is the person who watches your game and tells you what you missed.**
This one runs Stockfish first, so it never makes anything up.

You play. The engine says where you went wrong. Your AI coding agent explains
why, and keeps a running file of the mistakes you actually repeat — not the ones
you made once.

## Why it is split this way

Ask a language model to analyse a chess position and it will confidently tell
you things that are not true. It loses track of the board after a few moves and
invents variations that do not survive checking. That is not a prompt problem;
it is what these models are.

But a language model is genuinely good at the thing an engine cannot do at all:
telling you *why* a move was bad, what you were probably thinking, and which of
your mistakes are the same mistake wearing different clothes.

So the roles are split, strictly:

| Question | Answered by |
|---|---|
| Evaluation, best move, where exactly the error is | **Stockfish** |
| Why it is an error, what the plan is, what keeps repeating | **The agent** |

The agent is instructed never to overrule the engine and never to present its
own evaluation as fact. Everything else follows from that.

## What you get

After each game, a report like this:

```markdown
# 2026.08.08 — vs opponent (white)

- Opening: B50 Sicilian Defense
- Result: 1-0   Time control: 180+2
- ACPL: you 48, opponent 76

## Your mistakes

| Move | Played | Better | Loss | Verdict | Time |
|---|---|---|---|---|---|
| 9  | b3    | Nd5  | -307 | blunder  | 2s |
| 13 | Bc6   | Nxc8 | -242 | mistake  | 6s |

## Time

- Used 93s of 240s (39%), 3.1s per move
- Long thinks (8s+): 3 | instant moves (<3s): 18 of 30
- Median time: 2.0s on sound moves, 2.0s on mistakes
  - Mistakes got no more thought than routine moves — hard positions are
    not being recognised as hard.

## Habit check — replies to captures

Clean. 9 replies after a capture, worst loss 42.
```

Three things there are not in a normal engine report:

- **Time per move**, parsed from the PGN clock comments. A move played in one
  second was not chosen, it was reflex — and that changes the diagnosis.
- **The median comparison.** If your mistakes got no more thought than your
  routine moves, you are not failing to calculate; you are failing to notice
  that a position is critical.
- **The habit check.** Replies made immediately after the opponent changed the
  material count, which is where reflex is most expensive.

## Requirements

- Python 3.10 or newer
- [Stockfish](https://stockfishchess.org/download/)
- A Lichess or Chess.com account
- An AI coding agent for the coaching half — Claude Code, Codex, Cursor, or
  anything else that can read a folder and talk to you about it

## Install

```bash
git clone https://github.com/kellygracelab-dotcom/kibitz
cd kibitz
pip install -r requirements.txt
```

Then Stockfish, if you do not already have it:

```bash
winget install --id Stockfish.Stockfish
```

```bash
brew install stockfish
```

```bash
sudo apt install stockfish
```

## Setup

```bash
python coach.py setup
```

The wizard asks which platform you play on and your username, checks that the
account really exists, finds Stockfish, and creates your local files. It writes
`config.json` and a `data/` folder — both stay on your machine and are
git-ignored.

If Stockfish sits somewhere unusual, point at it directly:

```bash
python coach.py setup --engine /path/to/stockfish
```

## Your first session

Play a game. A slow one — see *Honest limits* below. Then:

```bash
python coach.py sync
python coach.py analyze
```

You now have a report in `data/reports/`. **Open this folder in your AI agent**
and say something like:

> Read AGENTS.md and my latest report, then take me through the game.

The agent will show you the position before your worst mistake and ask what is
wrong with it — **without naming the move**. Try to find it. If you cannot, ask
for a hint; it gives them in steps rather than handing over the answer. Once you
see it, it will ask you to say in your own words why the move was bad.

That last step is the point. A position you looked at and understood in the
moment is not learned. A position you can explain is.

## The everyday loop

```bash
python coach.py sync -n 3
python coach.py analyze --last 3
```

Then ask the agent to review them. It will take the two or three worst errors
rather than every inaccuracy, because twenty remarks per game do not stick.

## Commands

| Command | What it does |
|---|---|
| `python coach.py setup` | First-run wizard |
| `python coach.py sync` | Download your most recent game |
| `python coach.py sync -n 5` | Download the last 5 |
| `python coach.py analyze` | Analyse the most recent game |
| `python coach.py analyze --last 3` | Analyse the 3 most recent |
| `python coach.py analyze --game FILE.pgn` | Analyse one file from `data/games/` |
| `python coach.py analyze --depth 14` | Faster, shallower analysis |
| `python coach.py status` | What is on disk right now |

## The three files that make it a coach

Anything can print an engine report. What makes this a study loop is that the
agent keeps notes between sessions, in `data/`:

| File | Holds |
|---|---|
| `player-state.md` | Your level, where your effort goes, the current focus |
| `repertoire.md` | Your openings and the plan behind each |
| `mistake-patterns.md` | Errors confirmed across three separate games |

The three-game rule is the important one. A bad move in one game is chance. A
pattern is written down only after it shows up in three different games, and it
is closed only after three consecutive games without it. That is the difference
between a review that feels productive and one that changes your results.

You can read and edit these files yourself. They are yours, they are plain
markdown, and nothing is hidden in a database.

## Troubleshooting

**"Stockfish was not found."** Install it with one of the commands above, pass
`--engine` with the full path, or set the `STOCKFISH_PATH` environment variable.
On Windows, winget adds Stockfish to `PATH` only after you restart the shell —
setup looks inside the winget package directory anyway.

**Analysis is slow.** Every position in the game is evaluated, at depth 18 by
default. A long game takes a few minutes. Use `--depth 14` for a quick look and
keep the default when you actually intend to study the game.

**No time section in the report.** That PGN has no clock data. Lichess always
includes it; on Chess.com it depends on the game, and daily games have no usable
clock times at all.

**Chess.com returns an error.** Their API is public but rate-limited. Wait a
minute and try again; if it persists, that month's archive may simply be empty.

**The agent starts inventing variations.** Point it back at `AGENTS.md`. The
rule it is breaking is the first one in the file.

## Privacy

Everything stays on your machine. `data/` and `config.json` are git-ignored, so
a fork of this repository never carries anyone's games, ratings, or notes. The
only network calls are read-only requests to the public Lichess and Chess.com
APIs, for your own games.

## Honest limits

- This will not make you a strong player on its own. It makes your practice
  legible, which is a different and smaller claim.
- Fast time controls produce reports full of "did not look" errors. Those are
  real, but they are not interesting to review. Play slower games.
- The starter repertoire in `templates/repertoire.md` is aimed at roughly
  1000–1600 and is a starting point, not advice for every player.
- Evaluations in the templates should be re-checked with your own engine. Do not
  trust a number written in a markdown file, including these.

## How it works inside

Four small modules under `chesscoach/`:

- `platforms.py` — downloads your games from Lichess or Chess.com, using only
  the standard library so the single dependency stays `python-chess`.
- `engine.py` — finds Stockfish and analyses a game. Each position is evaluated
  once and a move's cost is the gap it opens, which halves the engine work.
  Evaluations are clamped at ten pawns, so sliding from +12 to +6 in a won
  position is not reported as a blunder.
- `report.py` — turns the numbers into something worth discussing: worst moves,
  the time comparison, the habit check.
- `config.py` — paths, settings, and the first-run file layout.

The coaching half is not code at all. It lives in `AGENTS.md`, which every agent
reads: what it may claim, what it must defer to the engine on, how to teach, and
when a mistake becomes a pattern.

## How this was built

The design is mine: the split between engine and model, the rule that the agent may never
present its own evaluation as fact, the three-game threshold for writing down a pattern, and
the decision to treat time per move as evidence rather than trivia.

A significant part of the code was written by coding agents against those specifications —
which is also why `AGENTS.md` and `CLAUDE.md` sit in the repository root. They are not
leftovers; they are the interface the tool is built around.

## License

MIT
