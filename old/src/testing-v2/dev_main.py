"""Main runner for the bot."""

import asyncio
import math

import chess
import chess.engine

import bobbot

# import bobbot.activities.chess_engine.dev_sunfish


async def get_engine_move(engine, board, limit, game_id):
    with await engine.analysis(board, limit, game=game_id, info=chess.engine.INFO_ALL, multipv=None) as analysis:
        async for _ in analysis:  # Partial results
            pass
        info = analysis.info
        print(analysis.info)
        score = info["score"].relative
        score = math.tanh(score.score() / 600) if score.score() is not None else score.mate()
        print(math.tanh(analysis.info["score"].relative.score() / 600))
        return analysis.info["pv"][0]


async def test_engine():
    async def load_engine_from_cmd(cmd, debug=True):
        _, engine = await chess.engine.popen_uci(cmd.split())
        if hasattr(engine, "debug"):
            engine.debug(debug)
        return engine

    engine = await load_engine_from_cmd("python src/bobbot/activities/chess_engine/dev_sunfish.py")
    # await engine.quit()

    board = chess.Board()
    print(board)
    # chess.engine.Limit(nodes=10),
    move = await get_engine_move(engine, board, chess.engine.Limit(time=0.1), "test")
    print(move)
    print(isinstance(engine, chess.engine.XBoardProtocol))
    print(engine.options)


async def main() -> None:
    """Run the bot."""
    await test_engine()
    # bobbot.run_bot()
    # bobbot.get_logger("bobbot").info("Stopping...")


if __name__ == "__main__":
    asyncio.run(main())
