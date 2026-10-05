"""Game state -> the adapter's position JSON (`play.data`).

The adapter's board is bottom-up: row 0 is the bottom row and bit x of a row
is column x. This game's matrix is top-down (matrix[0] is the top of the
40-row buffer, matrix[39] the bottom row).
"""

PIECE_IDS = {'i': 0, 'o': 1, 't': 2, 's': 3, 'z': 4, 'j': 5, 'l': 6}
NO_PIECE = 7
PREVIEWS = 5
HEIGHT = 40
FPS = 60
# Incoming rows in this game enter on the receiver's next lock that clears no
# lines, so every entry is dated well before the decision: ready now.
READY_FRAMES = 60
# The opponent's pace is a guess until they have placed this many pieces.
PACE_PIECES = 4


def board_rows(matrix):
    """Bottom-up row masks (trailing empty rows dropped) and the garbage-row bits."""
    rows = []
    garbage = 0
    for y in range(HEIGHT):
        row = matrix[HEIGHT - 1 - y]
        mask = 0
        for x, cell in enumerate(row):
            if cell is not None:
                mask |= 1 << x
        if 'g' in row:
            garbage |= 1 << y
        rows.append(mask)
    while rows and rows[-1] == 0:
        rows.pop()
    return rows, garbage


def side(game, frame, frames_per_piece, next_lock_frame):
    """One player's side. This game counts B2B and combo from 0 (Triangle from -1)."""
    rows, garbage = board_rows(game.board.matrix)
    pieces = game.queue.pieces
    return {
        'rows': rows,
        'garbageRows': garbage,
        'current': PIECE_IDS[game.current.type],
        'hold': PIECE_IDS[game.hold.type] if game.hold else NO_PIECE,
        'queue': [PIECE_IDS[p] for p in pieces[game.queue_pos:game.queue_pos + PREVIEWS]],
        'b2b': game.b2b - 1,
        'combo': game.combo - 1,
        'pieces': game.pieces,
        'lines': game.lines_cleared,
        # The game keeps no count of rows sent after cancelling.
        'sent': game.attack,
        'attack': game.attack,
        'incoming': [{'frame': frame - READY_FRAMES, 'amount': amount}
                     for amount in game.garbage if amount > 0],
        'nextLockFrame': next_lock_frame,
        'framesPerPiece': frames_per_piece,
    }


def empty_side(frame, frames_per_piece):
    return {
        'rows': [], 'hold': NO_PIECE, 'b2b': -1, 'combo': -1, 'pieces': 0,
        'incoming': [], 'nextLockFrame': frame, 'framesPerPiece': frames_per_piece,
    }


def position(game, frame, pps):
    """The bot's view before it places its next piece, `frame` frames into the round."""
    fpp = FPS / pps
    me = side(game, frame, fpp, frame)
    opponent = game.opponent if game.mode == 'versus' else None
    if opponent is None:
        them = empty_side(frame, fpp)
    else:
        their_fpp = fpp
        if opponent.pieces >= PACE_PIECES and frame > 0:
            their_fpp = frame / opponent.pieces
        them = side(opponent, frame, their_fpp, frame + their_fpp)
    return {'frame': frame, 'me': me, 'opponent': them}
