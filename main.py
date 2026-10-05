import argparse
import os
import pygame
from render import Renderer
from game import Game, MovementHandler, SharedQueue

parser = argparse.ArgumentParser(description='Tetris. Either player can be the bot (see bot/README.md).')
parser.add_argument('--mode', choices=('sprint', 'versus'), default='versus')
parser.add_argument('--p1', choices=('human', 'bot'), default='human')
parser.add_argument('--p2', choices=('human', 'bot'), default='human')
parser.add_argument('--adapter', default=os.environ.get('FUSION_ADAPTER'), help='league_adapter binary')
parser.add_argument('--package', default=os.environ.get('FUSION_PACKAGE'), help='bot package JSON')
parser.add_argument('--pps', type=float, default=2.5, help="the bot's pieces per second")
args = parser.parse_args()
kinds = [args.p1] if args.mode == 'sprint' else [args.p1, args.p2]
if 'bot' in kinds and not (args.adapter and args.package):
    parser.error('a bot player needs --adapter and --package (or FUSION_ADAPTER and FUSION_PACKAGE)')

pygame.init()
WINDOW_W = 1366
WINDOW_H = 768
screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
clock = pygame.time.Clock()
running = True
mode = args.mode
queue = SharedQueue()
if mode == 'versus':
    tetris_p1 = Game(WINDOW_W, WINDOW_H, WINDOW_W / 5.95, 1, mode, queue)
    tetris_p2 = Game(WINDOW_W, WINDOW_H, WINDOW_W / 1.55, 2, mode, queue)
    tetris_p1.opponent = tetris_p2
    tetris_p2.opponent = tetris_p1
    games = [tetris_p1, tetris_p2]
else:
    games = [Game(WINDOW_W, WINDOW_H, WINDOW_W / 2.5, 1, mode, queue)]
renderers = [Renderer(screen, WINDOW_W, WINDOW_H) for _ in games]
input_handlers = [MovementHandler() for _ in games]

seats = [None for _ in games]
if 'bot' in kinds:
    from bot.adapter import Adapter
    from bot.seat import BotSeat
    command = [args.adapter, '--package', args.package, '--pps', str(args.pps)]
    for i, kind in enumerate(kinds):
        if kind == 'bot':
            seats[i] = BotSeat(games[i], Adapter(command), args.pps, pygame.time.get_ticks)

try:
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            for game, input_handler, seat in zip(games, input_handlers, seats):
                if seat is None:
                    game.handle_event(event)
                    input_handler.handle_event(event, game)
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                    # The bot plays its own keys; it only takes the restart.
                    game.handle_event(event)
        renderers[0].draw_bg()
        for game, input_handler, renderer, seat in zip(games, input_handlers, renderers, seats):
            if seat is None:
                input_handler.update(game)
            else:
                seat.update()
            renderer.draw_game(game)
        pygame.display.flip()
        clock.tick(240)
finally:
    for seat in seats:
        if seat is not None:
            seat.close()
    pygame.quit()
