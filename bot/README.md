# Bot player

Lets the Fusion league bot play this game, as either player or both.

## Running

You need Python 3.9 or later with `pygame`, a `league_adapter` binary and a bot
package JSON (both from Fusion). Pass them as flags or set `FUSION_ADAPTER` and
`FUSION_PACKAGE`.

```sh
# you against the bot
python main.py --mode versus --p1 human --p2 bot --adapter PATH --package PATH
# bot against bot
python main.py --mode versus --p1 bot --p2 bot --adapter PATH --package PATH
# bot 40-line sprint
python main.py --mode sprint --p1 bot --adapter PATH --package PATH
```

`--pps` sets the bot's speed (default 2.5 pieces a second). A bot player
ignores the keyboard except `R`, which restarts the round as usual.

The bot can think on another machine while the game runs here: `--remote`
(or `FUSION_REMOTE`) is an ssh command, and `--adapter` and `--package` are
paths on that machine. A Windows machine needs PowerShell as its OpenSSH
default shell.

```sh
python main.py --mode versus --p2 bot --remote 'ssh pc' \
  --adapter 'C:\fusion\league_adapter.exe' --package 'C:\fusion\league-best.json'
```

Without a window, as fast as the bot answers (one JSON line per game):

```sh
python -m bot.run --adapter PATH --package PATH --mode sprint --games 5
python -m bot.run --adapter PATH --package PATH --mode versus --games 5
```

Tests: `python -m pytest tests`. The test that plays the real bot runs only
when `FUSION_ADAPTER` and `FUSION_PACKAGE` are set.

## How it works

- `position.py` turns a player's state into the adapter's position JSON
  (bottom-up board rows, piece ids, B2B and combo counted from -1, queued
  garbage, and the opponent's side in versus).
- `adapter.py` runs the adapter process and exchanges one JSON line per
  piece: a `play` with the position, a `move` back with the four cells the
  bot chose.
- `inputs.py` finds the inputs that lock the piece on those cells with this
  game's own movement and kicks (`Piece.collide`, `Game.drop`), preferring a
  path whose last input gives the spin the bot planned, then presses them
  through `Game.handle_event` and `MovementHandler`. The game's own code moves
  and scores every piece.
- `seat.py` asks for each move on a worker thread so the window keeps
  drawing, and places pieces at the set speed.

## Rule differences

The bot plans for TETR.IO Tetra League (season 2); this game scores with its
own tables, so the bot's attack plans are approximate here:

- No surge, opener phase or garbage-clear bonus; a different combo table and
  perfect-clear value.
- Some J/L/S/Z placements the bot counts as mini spins are not spins here.
- I pieces kick with plain SRS here, SRS+ for the bot. If the bot ever picks a
  cell set this game cannot reach, the closest reachable placement is played.
