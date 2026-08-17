# Player state

> Your agent maintains this file. Edit it freely; it is your memory, not the
> tool's. Nothing here is uploaded anywhere.

## Level

- Platform account: `not set yet`
- Ratings: fill in after setup, and note how many games each rating is based on.
  A provisional rating with a high deviation is a range, not a measurement.
- Games analysed in this system: 0

## Where effort goes

Below roughly 1600, this split holds for almost everyone:

| Area | Share | Why |
|---|---|---|
| Tactics and not hanging pieces | ~60% | Games at this level are decided by one-move oversights, not by theory |
| Reviewing your own games | ~20% | The only way to find your personal recurring errors |
| Opening repertoire | ~20% | Goal is a playable position by move 10, not an advantage |

Revisit this split when your rating is stable above 1600.

## Time control

Play a control that leaves you time to think. In very fast games an error of
inattention is indistinguishable from an error of understanding, and the
review degenerates into "look more carefully" - which you already know.

## Checks to run during a game

Two questions, both cheap:

1. The opponent moved a piece. **What does it attack now?**
2. Material just changed on the board. **Before replying, is there a capture,
   check, or threat that is stronger than the obvious recapture?**

## Current focus

Nothing yet. After three or four analysed games the agent should replace this
with one specific, measurable thing.

## Next step

1. Run `python coach.py setup`.
2. Play one game.
3. Run `python coach.py sync` then `python coach.py analyze`.
4. Open this folder in your agent and ask it to review the report with you.
