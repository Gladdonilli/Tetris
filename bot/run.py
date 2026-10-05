"""Plays the bot in this game without a window, as fast as it answers.

    python -m bot.run --adapter PATH --package PATH [--mode sprint|versus]
                      [--games N] [--seed S] [--pps P] [--max-pieces N]

Sprint: one bot clears 40 lines. Versus: two bots play each other, taking
turns in lock order at the same speed. Each game prints one summary line;
time is the bot's game time at `--pps`, not the time the run took.
"""

import argparse
import json
import random
import sys

from game import Game, MovementHandler, SharedQueue

from .adapter import Adapter
from .inputs import play_move
from .position import FPS, position

WINDOW_W, WINDOW_H = 1366, 768


def new_game(mode):
    queue = SharedQueue()
    players = [Game(WINDOW_W, WINDOW_H, 0, 1, mode, queue)]
    if mode == 'versus':
        players.append(Game(WINDOW_W, WINDOW_H, 0, 2, mode, queue))
        players[0].opponent, players[1].opponent = players[1], players[0]
    for game in players:
        # Skip the renderer's countdown, which is what starts a round.
        game.resetting = False
        game.reset_animation_done = True
    return players


def turn(game, handler, adapter, pps, frame):
    move = adapter.play(position(game, frame, pps))
    outcome = play_move(game, handler, move)
    outcome['ms'] = (move.get('data') or {}).get('ms')
    return outcome


def summary(moves):
    placed = [m for m in moves if m['target'] is not None]
    times = sorted(m['ms'] for m in moves if m['ms'] is not None)
    return {
        'moves': len(moves),
        'offTarget': sum(not m['exact'] for m in placed),
        'dropped': len(moves) - len(placed),
        'spinDiffers': sum(m['exact'] and m['spin'] != m['botSpin'] for m in placed),
        'medianMs': times[len(times) // 2] if times else None,
    }


def sprint(adapter, pps, max_pieces):
    (game,) = new_game('sprint')
    handler, moves = MovementHandler(), []
    while not game.locked_out and game.pieces < max_pieces:
        moves.append(turn(game, handler, adapter, pps, game.pieces * FPS / pps))
    return {
        'mode': 'sprint',
        'lines': game.lines_cleared,
        'pieces': game.pieces,
        'finished': game.lines_cleared >= 40,
        'seconds': round(game.pieces / pps, 2),
        'attack': game.attack,
        **summary(moves),
    }


def versus(adapters, pps, max_pieces):
    players = new_game('versus')
    handlers = [MovementHandler(), MovementHandler()]
    moves = [[], []]
    while not any(g.locked_out for g in players) and min(g.pieces for g in players) < max_pieces:
        # Same speed for both: the side with fewer locks goes next, player 1 on ties.
        i = 0 if players[0].pieces <= players[1].pieces else 1
        game = players[i]
        moves[i].append(turn(game, handlers[i], adapters[i], pps, game.pieces * FPS / pps))
    out = [g.locked_out for g in players]
    return {
        'mode': 'versus',
        'winner': None if out[0] == out[1] else (2 if out[0] else 1),
        'pieces': [g.pieces for g in players],
        'attack': [g.attack for g in players],
        'lines': [g.lines_cleared for g in players],
        'players': [summary(m) for m in moves],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description='Plays the bot in this game without a window.')
    parser.add_argument('--adapter', required=True, help='league_adapter binary')
    parser.add_argument('--package', required=True, help='bot package JSON')
    parser.add_argument('--mode', choices=('sprint', 'versus'), default='sprint')
    parser.add_argument('--games', type=int, default=1)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--pps', type=float, default=2.5)
    parser.add_argument('--max-pieces', type=int, default=400)
    parser.add_argument('--adapter-arg', action='append', default=[],
                        help='extra adapter argument (repeatable), e.g. --adapter-arg=--parallel --adapter-arg=off')
    args = parser.parse_args(argv)
    command = [args.adapter, '--package', args.package, '--pps', str(args.pps)] + args.adapter_arg
    adapters = [Adapter(command) for _ in range(2 if args.mode == 'versus' else 1)]
    try:
        for game_index in range(args.games):
            random.seed(args.seed + game_index)
            if args.mode == 'sprint':
                result = sprint(adapters[0], args.pps, args.max_pieces)
            else:
                result = versus(adapters, args.pps, args.max_pieces)
            print(json.dumps({'game': game_index, 'seed': args.seed + game_index, **result}), flush=True)
    finally:
        for adapter in adapters:
            adapter.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
