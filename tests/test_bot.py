import json
import os
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from game import Game, MovementHandler, SharedQueue  # noqa: E402
from piece import Piece  # noqa: E402

from bot import inputs, position  # noqa: E402
from bot.run import new_game  # noqa: E402

PIECES = 'iotszjl'


Matrix = List[List[Optional[str]]]


def empty() -> Matrix:
    return [[None] * 10 for _ in range(40)]


def game_with(matrix, ptype, hold=None):
    queue = SharedQueue()
    queue.pieces = [ptype] + list('iotszjl') * 3
    game = Game(1366, 768, 0, 1, 'sprint', queue)
    game.resetting = False
    game.reset_animation_done = True
    game.current = Piece(ptype, current=True)
    game.hold = Piece(hold) if hold else None
    game.board.matrix = [row[:] for row in matrix]
    return game


def random_board(rng):
    """A ragged stack with holes and a few overhangs, never a full row."""
    matrix = empty()
    for x in range(10):
        height = rng.randint(0, 7)
        for y in range(40 - height, 40):
            if rng.random() < 0.85:
                matrix[y][x] = 'g'
    for y in range(40):
        if all(matrix[y]):
            matrix[y][rng.randrange(10)] = None
    return matrix


def slot_board(rng):
    """Filled rows with a T-shaped cavity, a shaft above it and an overhang or two."""
    while True:
        matrix = empty()
        top = 39 - rng.randint(2, 5)
        for y in range(top + 1, 40):
            matrix[y] = list('g' * 10)
        rotation = rng.randrange(4)
        x0, y0 = rng.randint(-1, 8), rng.randint(top, 37)
        cells = [(x0 + dx, y0 + dy) for dx, dy in inputs._shape('t', rotation)]
        if any(not 0 <= x <= 9 for x, _ in cells):
            continue
        for x, y in cells:
            matrix[y][x] = None
        for _ in range(rng.randint(1, 4)):
            x = rng.choice(cells)[0] + rng.choice((-1, 0, 1))
            y = rng.randint(top - 2, max(y for _, y in cells) - 1)
            if 0 <= x <= 9:
                matrix[y][x] = None
        for _ in range(rng.randint(0, 3)):
            matrix[rng.randint(top - 1, top)][rng.randrange(10)] = 'g'
        if not any(all(row) for row in matrix):
            return matrix


def reachable_locks(matrix, ptype, start):
    """Every distinct (cells, spin) lock the search can reach, with its path."""
    found = {}
    parents: Dict[tuple, Optional[tuple]] = {start: None}
    frontier = [start]
    while frontier:
        state = frontier.pop()
        placed, kind = inputs._lock(matrix, ptype, state)
        found.setdefault((placed, kind), state)
        for move in inputs.MOVES:
            after = inputs._step(matrix, ptype, state, move)
            if after is not None and after not in parents:
                parents[after] = (state, move)
                frontier.append(after)
    return {key: inputs._path(parents, state) for key, state in found.items()}


def check_every_lock(matrix, pieces=PIECES):
    kinds = set()
    for ptype in pieces:
        game = game_with(matrix, ptype)
        locks = reachable_locks(matrix, ptype, inputs.start_state(game))
        assert locks
        for (cells, kind), path in locks.items():
            game = game_with(matrix, ptype)
            handler = MovementHandler()
            for name in path:
                inputs.press(game, handler, name)
            current = game.current
            rest = inputs._rest_row(game.board.matrix, ptype, current.rotation % 4, current.x, current.y)
            assert inputs.cells(ptype, current.rotation, current.x, rest) == cells, (ptype, path)
            inputs.press(game, handler, 'hd')
            assert inputs.spin_kind(game.spin_type) == kind, (ptype, path, game.spin_type)
            assert game.pieces == 1
            kinds.add(kind)
    return kinds


@pytest.mark.parametrize('seed', range(40))
def test_every_searched_lock_is_what_the_game_locks(seed):
    rng = random.Random(seed)
    check_every_lock(random_board(rng) if seed % 2 else slot_board(rng))


def tsd_board():
    """A T-spin double slot reached only by a rotation that takes the last kick."""
    rows = [
        '..........',
        '....#.....',
        '#.........',
        '####.#####',
        '####..####',
        '####..####',
        '#####.####',
    ]
    matrix = empty()
    for i, row in enumerate(rows):
        for x, c in enumerate(row):
            if c == '#':
                matrix[40 - len(rows) + i][x] = 'g'
    return matrix


def test_every_lock_on_a_last_kick_tsd_board():
    assert check_every_lock(tsd_board(), 't') == {0, 1, 2}


def test_finds_a_spin_path_and_the_game_scores_it():
    matrix = tsd_board()
    target = frozenset({(4, 3), (4, 2), (5, 2), (4, 1)})
    game = game_with(matrix, 't')
    path, placed, kind = inputs.find_inputs(matrix, 't', inputs.start_state(game), target, 2)
    assert placed == target and kind == 2
    handler = MovementHandler()
    for name in path:
        inputs.press(game, handler, name)
    inputs.press(game, handler, 'hd')
    assert game.last_lines_cleared == 2
    assert inputs.spin_kind(game.spin_type) == 2


def test_play_move_holds_then_places():
    game = game_with(empty(), 't', hold='i')
    move = {'data': {'hold': True, 'cells': [[0, 0], [1, 0], [2, 0], [3, 0]], 'spin': 0}}
    outcome = inputs.play_move(game, MovementHandler(), move)
    assert outcome['inputs'][0] == 'hold' and outcome['exact']
    assert game.hold is not None and game.hold.type == 't'
    assert [c is not None for c in game.board.matrix[39][:5]] == [True] * 4 + [False]


def test_position_is_bottom_up_with_triangle_counters():
    game = game_with(empty(), 't', hold='o')
    game.board.matrix[39][0] = 'g'
    game.board.matrix[39][9] = 'j'
    game.board.matrix[38][3] = 'l'
    game.b2b, game.combo = 0, 2
    game.garbage = [3, 0]
    side = position.position(game, 120, 2.5)['me']
    assert side['rows'] == [1 | 1 << 9, 1 << 3]
    assert side['garbageRows'] == 1
    assert side['current'] == 2 and side['hold'] == 1
    assert side['queue'] == [position.PIECE_IDS[p] for p in game.queue.pieces[1:6]]
    assert side['b2b'] == -1 and side['combo'] == 1
    assert side['incoming'] == [{'frame': 120 - position.READY_FRAMES, 'amount': 3}]


def test_new_games_start_without_the_countdown():
    p1, p2 = new_game('versus')
    assert p1.opponent is p2 and p2.opponent is p1
    assert not p1.resetting and not p2.resetting


ADAPTER = os.environ.get('FUSION_ADAPTER')
PACKAGE = os.environ.get('FUSION_PACKAGE')


@pytest.mark.skipif(not (ADAPTER and PACKAGE), reason='set FUSION_ADAPTER and FUSION_PACKAGE')
def test_bot_plays_sprint_pieces_where_it_chose(tmp_path):
    from bot.run import sprint
    from bot.adapter import Adapter

    # A narrow search keeps the test quick; the placements are still the bot's.
    package = json.loads(Path(PACKAGE).read_text())
    package['width'] = 32
    narrow = tmp_path / 'narrow.json'
    narrow.write_text(json.dumps(package))
    random.seed(1)
    adapter = Adapter([ADAPTER, '--package', str(narrow), '--parallel', 'off'])
    try:
        result = sprint(adapter, 2.5, 60)
    finally:
        adapter.close()
    assert result['pieces'] == 60 and result['lines'] > 0
    assert result['dropped'] == 0
    assert result['offTarget'] <= 2
