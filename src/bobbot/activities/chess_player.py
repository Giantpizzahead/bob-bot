"""Play chess as the black pieces against the computer or a user on chess.com."""

import asyncio
import os
import random
import re
from math import tanh
from pathlib import Path
from typing import Callable, Optional

import chess
import chess.engine
from chess import Board
from PIL import Image
from playwright.async_api import BrowserContext, Locator, Page, TimeoutError

from bobbot.utils import get_logger, get_playwright_browser, get_playwright_page

STATE_FILE = "local/pw/state.json"
logger = get_logger(__name__)
status = "idle"
match_result = None
curr_win_chance: int = 50
last_screenshot: Optional[Image.Image] = None

elo = 800  # Should be in [200, 1600]
against_computer = False

chess_page: Optional[Page] = None
engine: Optional[chess.engine.UciProtocol] = None


async def login(page: Page, context: BrowserContext) -> None:
    """Login to chess.com."""
    await page.goto("https://www.chess.com/")
    # Check if already logged in
    try:
        if os.getenv("ACTIVITIES_USERNAME") in await page.locator(".home-username-link").text_content(timeout=1500):
            logger.info("Already logged in.")
            return
    except TimeoutError:
        pass
    logger.info("Logging in...")
    await page.get_by_label("Log In").click()
    await page.get_by_placeholder("Username or Email").click()
    await page.get_by_placeholder("Username or Email").fill(os.getenv("ACTIVITIES_USERNAME"))
    await page.get_by_placeholder("Username or Email").press("Tab")
    await page.get_by_placeholder("Password").fill(os.getenv("ACTIVITIES_PWD"))
    await page.get_by_text("Remember me").click()
    await page.get_by_role("button", name="Log In").click()
    # Save state, making folders if they don't exist
    logger.info("Saving state...")
    Path(STATE_FILE).parent.mkdir(parents=True, exist_ok=True)
    await context.storage_state(path=STATE_FILE)


async def get_challenge_link(page: Page) -> str:
    """Get a challenge link to play against the bot."""
    logger.info("Creating challenge link...")
    await page.goto("https://www.chess.com/play/online/friend")
    await page.wait_for_timeout(1000)  # Wait for page to load
    await page.get_by_role("button", name="Create Challenge Link …").click()
    await page.locator("button.color-selector-black").click()  # Play as Black
    await page.locator("label").nth(4).click()  # Unrated
    copy_button = page.get_by_role("button", name="Copy Link")
    await copy_button.click()

    # Get the challenge link
    logger.info("Getting link...")
    link_button = page.locator(".challenge-link-button-link")
    await link_button.wait_for(state="attached")
    # Extract URL from text
    button_text = await link_button.text_content()
    url = re.search(r"https?://[^\s]+", button_text)
    assert url
    challenge_link = url.group()
    logger.info(f"Challenge link: {challenge_link}")
    return challenge_link


async def wait_for_accepted_match(page: Page) -> None:
    """Wait for the challenge link match to be accepted (3 minutes)."""
    logger.info("Waiting for match to be accepted...")
    # Poll every second
    for _ in range(180):
        if status == "stopping":
            return
        try:
            await page.locator("h3.challenge-link-modal-title").wait_for(state="detached", timeout=1000)
            logger.info("Match was accepted.")
            await page.wait_for_timeout(1000)  # Wait for board to update
            return
        except TimeoutError:
            pass
    raise TimeoutError("Match was not accepted.")


async def start_match_computer(page: Page) -> None:
    """Start a match against the computer."""
    logger.info("Starting match...")
    await page.goto("https://www.chess.com/play/computer/CoachDannyBot")
    # Potential dialog
    try:
        await page.get_by_role("button", name="Start").click(timeout=1500)
    except TimeoutError:
        pass
    # await page.get_by_role("button", name="Choose").click()
    # await page.locator("div.select-playing-as-radio-black").click()
    await page.locator("#board-layout-sidebar").get_by_role("button").nth(3).click()
    await page.get_by_role("button", name="Play").click()
    await page.wait_for_timeout(1000)  # Wait for board to update


async def get_moves_locator(page: Page) -> tuple[Locator, str]:
    """Get the locator for the move list, along with the selector used."""
    move_list = page.locator("wc-move-list")
    if await move_list.is_visible():
        return move_list, "wc-move-list"
    move_list = page.locator(".play-controller-scrollable")
    if await move_list.is_visible():
        return move_list, ".play-controller-scrollable"
    raise ValueError("Move list not found.")


async def wait_for_move(page: Page) -> None:
    """Wait for the opponent to make a move."""
    move_list, selector = await get_moves_locator(page)
    initial_text = await move_list.text_content()
    assert "`" not in initial_text
    if any(result in initial_text for result in ["1-0", "0-1", "1/2-1/2"]):
        return  # Game already ended

    try:
        if await page.locator(".clock-bottom").is_visible():
            # More reliable
            logger.info("Waiting for clock...")
            await page.wait_for_function(
                "() => document.querySelector('.clock-bottom').classList.contains('clock-player-turn')", timeout=30000
            )
        else:
            # Less reliable, but works for bots
            logger.info("Waiting for move list update...")
            await page.wait_for_function(
                f"() => document.querySelector('{selector}').textContent !== `{initial_text}`",
                timeout=30000,
            )
    except TimeoutError:
        pass
    await page.wait_for_timeout(200)  # Wait for board to update


async def check_game_over(page: Page) -> tuple[str, str] | None:
    """Check if the game is over. Returns None if ongoing. Else, returns white/black/draw/unknown and a description."""
    # Possible endings: 1-0, 0-1, 1/2-1/2
    game_over_locator_1 = page.locator("div.game-over-header-header")
    game_over_locator_2 = page.locator("div.modal-game-over-header-component")
    await page.wait_for_timeout(100)
    if not await game_over_locator_1.is_visible() and not await game_over_locator_2.is_visible():
        return None
    # Get game state
    game_over_locator = game_over_locator_1 if await game_over_locator_1.is_visible() else game_over_locator_2
    description = await game_over_locator.text_content()
    move_list, _ = await get_moves_locator(page)
    moves = await move_list.text_content()
    if "1-0" in moves:
        return "Other bot" if against_computer else "User", description
    elif "0-1" in moves:
        return "Bob", description
    elif "1/2-1/2" in moves:
        return "Draw", description
    else:
        return "Unknown", description


async def close_ending_dialog(page: Page) -> None:
    """Close the game over dialog (if it's open)."""
    game_over_locator_1 = page.locator("button.game-over-header-close")
    game_over_locator_2 = page.locator("button.modal-game-over-header-close")
    if await game_over_locator_1.is_visible():
        await page.locator("button.game-over-header-close").click()
    elif await game_over_locator_2.is_visible():
        await page.locator("button.modal-game-over-header-close").click()
    await page.wait_for_timeout(500)  # Wait for dialog to close


async def play_move(page: Page) -> None:
    """Play a move as Black."""
    # Locate all chess pieces within the board
    # logger.info("Locating pieces...")
    board_locator = page.locator("wc-chess-board")
    pieces = board_locator.locator("div.piece")
    # count = await pieces.count()
    # logger.info(f"Found {count} pieces on the board.")

    # Get pieces in parallel
    tasks = [piece.get_attribute("class") for piece in await pieces.element_handles()]
    classes = await asyncio.gather(*tasks)

    # Parse the board and make a move
    board = parse_board(classes)
    board.turn = chess.BLACK
    move, win_chance = await get_move(page, board)
    global curr_win_chance
    curr_win_chance = win_chance
    # logger.info(board)

    # Make the move
    logger.info(f"Making move {move}...")

    # Get size of board and each square (width = height)
    board_size = (await board_locator.bounding_box())["width"]
    square_size = board_size / 8

    def square_to_coords(square: chess.Square) -> dict[str, int]:
        """Convert square number to x, y coordinates, viewing the board as Black."""
        x = board_size - ((square % 8) * square_size + square_size / 2)
        y = (square // 8) * square_size + square_size / 2
        return {"x": x, "y": y}

    # Click on the squares
    from_square = square_to_coords(move.from_square)
    to_square = square_to_coords(move.to_square)
    try:
        await board_locator.click(position=from_square)
        await page.wait_for_timeout(250)
        await board_locator.click(position=to_square)
        # Double click in case of pawn promotion
        if move.promotion:
            await page.wait_for_timeout(150)
            await board_locator.click(position=to_square)
    except TimeoutError:
        logger.info("Failed to make move.")
        pass
    await page.wait_for_timeout(200)  # Let the move process


async def get_time_left(page: Page) -> Optional[int]:
    """Get Bob's clock time left in seconds, if it exists."""
    if not await page.locator(".clock-bottom").is_visible():
        return None
    time_left = (await page.locator(".clock-bottom").text_content()).strip()
    return int(time_left.split(":")[0]) * 60 + int(time_left.split(":")[1])


def parse_board(classes: list[str]) -> Board:
    """Parse the board from a list of classes representing the pieces."""
    PIECE_TYPES = {
        "r": chess.ROOK,
        "n": chess.KNIGHT,
        "b": chess.BISHOP,
        "q": chess.QUEEN,
        "k": chess.KING,
        "p": chess.PAWN,
    }

    def parse_piece_info(piece_str: str):
        """Parse the piece type, color, and square from a class string."""
        # Example piece_str: "piece wk square-51" or "piece square-23 bp"
        parts = piece_str.split()
        piece_color_and_type = list(filter(lambda x: len(x) == 2, parts))[0]
        coords = list(filter(lambda x: len(x) == 9, parts))[0][7:]
        piece_color = chess.WHITE if piece_color_and_type[0] == "w" else chess.BLACK
        piece_type = PIECE_TYPES[piece_color_and_type[1]]
        square = chess.square(int(coords[0]) - 1, int(coords[1]) - 1)
        return piece_type, piece_color, square

    # Create an empty board and place pieces on it
    board = Board(None)
    for piece_str in classes:
        piece_type, piece_color, square = parse_piece_info(piece_str)
        piece = chess.Piece(piece_type, piece_color)
        board.set_piece_at(square, piece)
    return board


async def start_sunfish_engine() -> None:
    """Start the Sunfish engine."""
    global engine

    async def load_engine_from_cmd(cmd, debug=True):
        _, engine = await chess.engine.popen_uci(cmd.split())
        if hasattr(engine, "debug"):
            engine.debug(debug)
        return engine

    engine_path = Path(__file__).parent / "chess_engine" / "dev_sunfish.py"
    engine_path
    engine = await load_engine_from_cmd(f"python {str(engine_path)}")


async def stop_sunfish_engine() -> None:
    """Stop the Sunfish engine."""
    if engine:
        await engine.quit()


async def get_move_sunfish(board: Board, elo: int) -> tuple[chess.Move, float]:
    """Get a move using Sunfish for the target elo.

    Args:
        board: The current board state.
        elo: The target elo.

    Returns:
        A tuple of the suggested move and the estimated win chance (0-100).
    """
    if not engine:
        raise ValueError("Engine not initialized")

    # Parameters:
    # QS = 40  # Lower leads to less base depth for all positions beyond depth 0
    # QS_A = 140  # Higher leads to less depth for not-amazing positions beyond depth 0
    # EVAL_ROUGHNESS = 15  # Higher leads to faster termination at each depth (less precision)
    # MAX_DEPTH = 8  # Max search depth
    # RAND_SCORE = 0  # All position scores are randomized by +- this amount
    # QS=(0, 300),
    # QS_A=(0, 300),
    # EVAL_ROUGHNESS=(0, 50),
    # MAX_DEPTH=(1, 16),
    # RAND_SCORE=(0, 1000),

    # Get move using weaker search
    limit = chess.engine.Limit(time=0.2)  # Don't limit time, unfair for weaker systems

    # At 600 Elo, QS_A = 240, EVAL_ROUGHNESS = 35, MAX_DEPTH = 3, and bad move chance = 0.55
    # At 1600 Elo, QS_A = 140, EVAL_ROUGHNESS = 15, MAX_DEPTH = 9, and bad move chance = 0
    nerf_qs_a = min(140 + (1600 - elo) / 10, 300)
    nerf_eval_roughness = min(15 + (1600 - elo) / 50, 50)
    nerf_max_depth = max(elo // 200, 2)
    bad_move_chance = min(((1600 - elo) / 1400) ** 1.75, 1)
    if random.random() < bad_move_chance:
        nerf_rand_score = min(((1700 - elo) / 160) ** 2.5, 1000)
    else:
        nerf_rand_score = 0
    nerf_options = {
        "QS_A": nerf_qs_a,
        "EVAL_ROUGHNESS": nerf_eval_roughness,
        "MAX_DEPTH": nerf_max_depth,
        "RAND_SCORE": nerf_rand_score,
    }
    logger.info(f"Making a {'bad' if nerf_rand_score else 'good'} move (bad chance was {bad_move_chance*100:.1f}%)")
    # print(f"Bad move chance: {bad_move_chance}")
    with await engine.analysis(board, limit, info=chess.engine.INFO_ALL, options=nerf_options) as analysis:
        async for _ in analysis:  # Partial results
            pass
        try:
            move = analysis.info["pv"][0]
        except IndexError:
            # Use a random move
            logger.warning(f"No chess move found: {analysis.info}")
            move = random.choice(list(board.legal_moves))

    # Get resulting score using stronger search
    board.push(move)
    good_limit = chess.engine.Limit(time=0.2)
    with await engine.analysis(board, good_limit, info=chess.engine.INFO_ALL) as analysis:
        async for _ in analysis:  # Partial results
            pass
        score = analysis.info["score"].relative
        score = tanh(score.score() / 600) if score.score() is not None else score.mate()
        score = 100 - 50 * (1 + score)
    board.pop()
    return move, score


async def get_move(page: Page, board: Board) -> tuple[chess.Move, float]:
    """Get a move for the given board. Quality varies based on elo and time left. Simulates thinking time.

    Args:
        page: The current page.
        board: The current board state.

    Returns:
        A tuple of the suggested move and the estimated win chance (0-100).
    """
    time_left: Optional[int] = await get_time_left(page)
    # Adjust elo based on time pressure (3 minute game) and good opening moves
    adjusted_elo: int = elo
    sleep_mult = 1.0
    if time_left is not None and time_left < 90:
        adjusted_elo -= (90 - time_left) * 10
        sleep_mult = max((60 - time_left) / 60, 0)
    elif time_left is not None and time_left > 165:
        adjusted_elo += (time_left - 165) * 20
        sleep_mult = min((180 - time_left) / 15, 1)
    adjusted_elo = min(max(adjusted_elo, 200), 1600)
    # Get move based on elo
    move, win_chance = await get_move_sunfish(board, adjusted_elo)
    # Emulate thinking time
    wait_time = (random.uniform(0.7, 2.5) ** 2) * sleep_mult
    await asyncio.sleep(wait_time)
    logger.info(f"Adjusted elo: {adjusted_elo}, Wait time: {wait_time:.2f}s, Bob's win chance: {win_chance:.1f}%")
    return move, win_chance


async def screenshot_chess_activity() -> Optional[Path]:
    """Get a Path to a screenshot of the whole page (including the board), or None if no screenshot is available."""
    global last_screenshot
    if not chess_page:
        return last_screenshot
    SS_PATH = Path("local/pw/chess.jpeg")
    await chess_page.screenshot(type="jpeg", quality=25, path=SS_PATH)
    return SS_PATH


async def play_chess_activity(cmd_handler: Callable) -> None:
    """Play chess against the user (or the computer).

    Args:
        cmd_handler: The callback to send commands directed at Bob.
            The callback should be an async function that accepts exactly one string argument.
            If the activity fails to start, it will be called with the reason.
            Otherwise, it will be called the activity goes on and important things happen.
    """
    global status, chess_page, curr_win_chance, last_screenshot, match_result
    if status != "idle":
        await cmd_handler("Echo this to the user. Failed to start: You are already in a chess match.")
        return
    status = "starting"
    curr_win_chance = 50
    last_screenshot = None
    match_result = None
    try:
        await start_sunfish_engine()
        browser = await get_playwright_browser()
        # Create context and page
        if not Path(STATE_FILE).exists() and os.getenv("CHESS_STATE_JSON") is not None:
            logger.info("Loading initial state from environment variable...")
            Path(STATE_FILE).parent.mkdir(parents=True, exist_ok=True)
            with open(STATE_FILE, "w") as f:
                f.write(os.getenv("CHESS_STATE_JSON"))
        if Path(STATE_FILE).exists():
            logger.info("Restoring state...")
            context = await browser.new_context(storage_state=STATE_FILE)
        else:
            context = await browser.new_context()

        # Play chess
        page = await get_playwright_page(context)
        chess_page = page
        await login(page, context)
        if against_computer:
            await start_match_computer(page)
            await cmd_handler("Tell the user that you are now in a chess game against a bot.")
        else:
            challenge_link = await get_challenge_link(page)
            await cmd_handler(
                f"Send the user this link (don't use Markdown) so they can join your chess match, note that the link is different each time! {challenge_link}"  # noqa: E501
            )
            await wait_for_accepted_match(page)  # Might return early if stopping, but that's ok
        if status == "stopping":
            logger.info("Stopping chess match (before starting)...")
            await stop_sunfish_engine()
            chess_page = None
            await context.close()
            status = "idle"
            return
        status = "playing"
        asyncio.create_task(cmd_handler("start_spectating"))  # Start spectating
        while True:
            await wait_for_move(page)
            match_result = await check_game_over(page)
            if match_result:
                break
            await play_move(page)  # Might dry move, but that's ok
            if status == "stopping":
                logger.info("Stopping chess match (while playing)...")
                await stop_sunfish_engine()
                chess_page = None
                await context.close()
                status = "idle"
                return

        # Close ending dialog
        status = "finished"
        await page.wait_for_timeout(700)
        await close_ending_dialog(page)
        last_screenshot = await screenshot_chess_activity()
        await cmd_handler(
            f"Comment on your chess match against the user. You were playing Black. Make it clear who the winner was (you or the user). Winner: {match_result[0]}. (Reason: {match_result[1].strip()})"  # noqa: E501
        )
        logger.info(f"Finished chess match. Winner: {match_result[0]}. ({match_result[1].strip()})")
        await page.wait_for_timeout(3000)
        await context.close()
        await browser.close()
    except Exception as e:
        logger.exception(e)
        await cmd_handler(f"Tell the user there was an unexpected error while playing chess: {e}")
    await stop_sunfish_engine()
    chess_page = None
    status = "idle"


def stop_playing_chess() -> None:
    """Stops playing chess (when it's feasible to)."""
    global status
    status = "stopping"


def configure_chess(elo: int, against_computer: bool) -> None:
    """Configures the chess activity.

    Args:
        elo: Bob's elo rating. Should be in [200, 1600].
        against_computer: Whether Bob is playing against the computer or a user.
    """
    if not (200 <= elo <= 1600):
        raise ValueError("Elo should be in [200, 1600].")
    globals()["elo"] = elo
    globals()["against_computer"] = against_computer


def get_chess_info() -> str:
    """Get the current chess activity status."""
    if status == "idle":
        return "You are not currently playing chess."
    elif status == "stopping":
        return "You are currently trying to quit a chess match."
    elif status == "starting":
        return f"You are starting a chess match against {'a bot' if against_computer else 'a user'}."
    elif status == "playing":
        return f"You are playing a chess match as the Black pieces against {'a bot' if against_computer else 'a user'}. Your elo is {elo}. Your current win chance is {curr_win_chance:.1f}%."  # noqa: E501
    elif status == "finished":
        return f"You have finished the chess match against {'a bot' if against_computer else 'a user'}. Winner: {match_result[0]}. Full result: {match_result[1].strip()}."  # noqa: E501
    else:
        raise ValueError(f"Invalid chess status: {status}")
