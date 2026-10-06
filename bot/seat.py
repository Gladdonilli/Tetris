"""A player driven by the bot.

The live game keeps drawing while the bot thinks: each piece's position is
taken on the game's thread, the adapter answers on a worker thread, and the
move is played on the game's thread once it is in and the pace allows.
"""

from concurrent.futures import ThreadPoolExecutor

from game import MovementHandler

from .inputs import play_move
from .position import FPS, position


class BotSeat:
    def __init__(self, game, adapter, pps, clock):
        """`clock()` gives milliseconds on the same clock as `game.start_time`."""
        self.game = game
        self.adapter = adapter
        self.slot_ms = 1000 / pps
        self.pps = pps
        self.clock = clock
        self.handler = MovementHandler()
        self.worker = ThreadPoolExecutor(max_workers=1)
        self.pending = None
        self.next_ms = None
        self.moves = []

    def frame(self):
        return max(0.0, (self.clock() - self.game.start_time) * FPS / 1000)

    def update(self):
        game = self.game
        if game.locked_out or game.resetting:
            self.next_ms = None
            return
        now = self.clock()
        if self.next_ms is None:
            self.next_ms = now + self.slot_ms
        if self.pending is None:
            asked = position(game, self.frame(), self.pps)
            self.pending = (self.worker.submit(self.adapter.play, asked), game.current, game.pieces)
            return
        answer, piece, pieces = self.pending
        if not answer.done():
            return
        if game.current is not piece or game.pieces != pieces:
            # The round restarted while the bot was thinking.
            self.pending = None
            return
        if now < self.next_ms:
            return
        self.pending = None
        move = answer.result()
        outcome = play_move(game, self.handler, move)
        outcome['ms'] = (move.get('data') or {}).get('ms')
        self.moves.append(outcome)
        # The next slot follows this slot, not the frame the move landed on,
        # so frame lateness does not add up; a bot more than a slot behind
        # starts over from now instead of catching up in a burst.
        self.next_ms += self.slot_ms
        if self.next_ms < now:
            self.next_ms = now + self.slot_ms

    def close(self):
        self.worker.shutdown(wait=False, cancel_futures=True)
        self.adapter.close()
