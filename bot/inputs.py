"""Inputs that place a piece where the bot chose, found and played with this
game's own code.

The bot plans with TETR.IO's movement (SRS+ kicks, spawn, soft drop). This
game is close but not identical (its I piece kicks are plain SRS, and pieces
do not fall on their own), so the bot's own key list is not replayed here.
Instead a breadth-first search runs over the game's own moves (`Piece.collide`
for shifts and kicks, `Game.drop` for drops) to find the fewest inputs that
lock the piece on the bot's four cells, preferring a path whose lock gives the
spin the bot counted on; the inputs are then sent through `Game.handle_event`
and `MovementHandler`, as a player's keys would be.
"""

from collections import deque
from math import sqrt
from typing import Dict, Optional, Tuple

import pygame

from piece import Piece

HEIGHT = 40
MOVES = ('left', 'right', 'cw', 'ccw', '180', 'sd')
ROTATIONS = ('cw', 'ccw', '180')
SHAPES = {}
# (x, y, rotation, spun, force); see _step.
State = Tuple[int, int, int, bool, bool]


def _shape(ptype, rotation):
    """Filled cells of a piece's box as (dx, dy), dy growing downwards."""
    key = (ptype, rotation)
    if key not in SHAPES:
        grid = Piece.MINO_MAPS[ptype][rotation]
        size = int(sqrt(len(grid)))
        SHAPES[key] = tuple((i % size, i // size) for i, filled in enumerate(grid) if filled)
    return SHAPES[key]


def cells(ptype, rotation, x, y):
    """The piece's cells in the bot's frame: (column, row counted from the bottom)."""
    return frozenset((x + dx, HEIGHT - 1 - (y + dy)) for dx, dy in _shape(ptype, rotation % 4))


def _blocked(matrix, ptype, rotation, x, y):
    # Piece.collide's test, cell for cell.
    for dx, dy in _shape(ptype, rotation):
        cx, cy = x + dx, y + dy
        if cx < 0 or cx > 9 or cy > 39 or matrix[cy][cx]:
            return True
    return False


def _rest_row(matrix, ptype, rotation, x, y):
    """Where Game.drop leaves the piece."""
    while not _blocked(matrix, ptype, rotation, x, y + 1):
        y += 1
    return y


def spin_kind(spin):
    """The game's spin text as the bot counts spins: 0 none, 1 mini, 2 full."""
    if not spin:
        return 0
    return 1 if spin.startswith('Mini') else 2


def _piece(ptype, x, y, rotation):
    piece = Piece(ptype, rotation=rotation)
    piece.x, piece.y = x, y
    return piece


def _step(matrix, ptype, state, move):
    """The state after one input, as the game's handlers apply it; None when nothing changes.

    A state is (x, y, rotation, spun, force): `spun` is whether the last input
    that changed the piece was a rotation (the game's `last_input`), `force`
    the game's `force_spin` (a T rotation that took its last kick).
    """
    x, y, rotation, spun, force = state
    if move == 'sd':
        rest = _rest_row(matrix, ptype, rotation, x, y)
        return None if rest == y else (x, rest, rotation, False, force)
    piece = _piece(ptype, x, y, rotation)
    if move in ('left', 'right'):
        piece.x += -1 if move == 'left' else 1
        if not piece.collide(matrix, move):
            return None
        return (piece.x, piece.y, rotation, False, force)
    if move == 'cw':
        piece.rotation -= 1
        force, failed = piece.collide(matrix, 'cw')
    elif move == 'ccw':
        piece.rotation += 1
        force, failed = piece.collide(matrix, 'ccw')
    else:
        piece.rotation += 2
        failed = piece.collide(matrix, '180')
    if failed:
        return None
    return (piece.x, piece.y, piece.rotation % 4, True, force)


def _lock(matrix, ptype, state):
    """Cells and spin kind of a hard drop from `state`, as the game scores it."""
    x, y, rotation, spun, force = state
    rest = _rest_row(matrix, ptype, rotation, x, y)
    placed = cells(ptype, rotation, x, rest)
    # Game.drop marks any fall as the last input, which rules a spin out.
    if rest != y or not spun:
        return placed, 0
    _, spin = _piece(ptype, x, y, rotation).lock_piece([row[:] for row in matrix])
    if force and spin[:4] == 'Mini':
        spin = spin[4:]
    return placed, spin_kind(spin)


def _path(parents, state):
    moves = []
    while parents[state] is not None:
        state, move = parents[state]
        moves.append(move)
    return moves[::-1]


def find_inputs(matrix, ptype, start, target, spin):
    """Fewest inputs from `start` to a lock on `target` (a frozenset of cells).

    Returns (inputs, placed cells, spin kind). A lock with the bot's `spin` is
    preferred over one that only matches the cells. When no input sequence
    reaches `target`, the reachable lock sharing the most cells with it (the
    lowest of those) is returned instead.
    """
    parents: Dict[State, Optional[Tuple[State, str]]] = {start: None}
    frontier = deque([start])
    cells_only = None
    outcomes = {}
    while frontier:
        state = frontier.popleft()
        placed, kind = _lock(matrix, ptype, state)
        if placed == target:
            if kind == spin:
                return _path(parents, state), placed, kind
            if cells_only is None:
                cells_only = (state, kind)
        if placed not in outcomes:
            outcomes[placed] = (state, kind)
        for move in MOVES:
            after = _step(matrix, ptype, state, move)
            if after is not None and after not in parents:
                parents[after] = (state, move)
                frontier.append(after)
    if cells_only is not None:
        state, kind = cells_only
        return _path(parents, state), target, kind
    nearest = max(outcomes, key=lambda placed: (len(placed & target), -max(y for _, y in placed)))
    state, kind = outcomes[nearest]
    return _path(parents, state), nearest, kind


def start_state(game):
    current = game.current
    return (current.x, current.y, current.rotation % 4,
            game.last_input in ROTATIONS, game.force_spin)


def _key(game, kind, name):
    return pygame.event.Event(kind, key=game.KEYBINDS[name])


def press(game, handler, name):
    """One input through the game's own handlers, as a key press and release."""
    if name in ('left', 'right'):
        handler.handle_event(_key(game, pygame.KEYDOWN, name), game)
        handler.handle_event(_key(game, pygame.KEYUP, name), game)
    elif name == 'sd':
        game.handle_event(_key(game, pygame.KEYDOWN, 'sd'))
        handler.update(game)
        handler.handle_event(_key(game, pygame.KEYUP, 'sd'), game)
    else:
        game.handle_event(_key(game, pygame.KEYDOWN, name))


def play_move(game, handler, move):
    """Places the current piece where the adapter's `move` says, through the game's handlers.

    Returns what happened: the inputs, the target and placed cells, whether
    they match, and the spin the game scored.
    """
    data = move.get('data')
    if not data:
        # The adapter found no placement it could reach: it hard-drops.
        press(game, handler, 'hd')
        return {'inputs': ['hd'], 'target': None, 'placed': None, 'exact': False, 'spin': None}
    inputs = []
    if data['hold']:
        press(game, handler, 'hold')
        inputs.append('hold')
    target = frozenset(tuple(cell) for cell in data['cells'])
    current = game.current
    path, expected, kind = find_inputs(
        game.board.matrix, current.type, start_state(game), target, data['spin'])
    for name in path:
        press(game, handler, name)
    rest = _rest_row(game.board.matrix, current.type, current.rotation % 4, current.x, current.y)
    placed = cells(current.type, current.rotation, current.x, rest)
    press(game, handler, 'hd')
    inputs += path + ['hd']
    return {
        'inputs': inputs,
        'target': target,
        'placed': placed,
        'exact': placed == target,
        'expected': expected,
        'spin': kind,
        'botSpin': data['spin'],
        'gameSpin': game.spin_type,
    }
