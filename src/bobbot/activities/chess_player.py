"""Play chess as the black pieces against the computer or a user on chess.com."""

import asyncio
import io
import os
import random
import re
from pathlib import Path
from typing import Optional

import aiohttp
import chess
from chess import Board
from PIL import Image
from playwright.async_api import (
    BrowserContext,
    Locator,
    Page,
    TimeoutError,
    async_playwright,
)

from bobbot.utils import get_logger

STATE_FILE = "local/pw/state.json"
logger = get_logger(__name__)
status = "idle"
more_info = ""
curr_win_chance: int = 50
last_screenshot: Optional[Image.Image] = None

elo = 800  # Should be in [200, 2400]
against_computer = False

chess_page: Optional[Page] = None


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
    Path("local/pw").mkdir(parents=True, exist_ok=True)
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
    try:
        await page.locator("h3.challenge-link-modal-title").wait_for(state="detached", timeout=180000)
    except TimeoutError:
        raise TimeoutError("Match was not accepted.")
    logger.info("Match was accepted.")
    await page.wait_for_timeout(1000)  # Wait for board to update


async def start_match_computer(page: Page) -> None:
    """Start a match against the computer."""
    logger.info("Starting match...")
    await page.goto("https://www.chess.com/play/computer/CoachDannyBot")
    # Potential dialog
    try:
        await page.get_by_role("button", name="Start").click(timeout=1500)
    except TimeoutError:
        pass
    await page.get_by_role("button", name="Choose").click()
    await page.locator("div.select-playing-as-radio-black").click()
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
    print(time_left)
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


async def query_chess_api(board: Board, search_moves: Optional[list[chess.Move]]) -> dict:
    """Query the chess API at https://chess-api.com/ and return the response.

    Args:
        board: The current board state.
        search_moves: A subset of moves to consider. If None, all legal moves are considered.

    Returns:
        The response from the API. See https://chess-api.com/ for the format.
    """
    data = {
        "fen": board.fen(),
        "depth": 1,
        "variants": 1,
        "maxThinkingTime": 1,
    }
    if search_moves:
        data["searchMoves"] = " ".join([move.uci() for move in search_moves])
    print(data)
    async with aiohttp.ClientSession() as session:
        async with session.post("https://chess-api.com/v1", json=data) as response:
            return await response.json()


async def _get_move_stockfish(
    board: Board, obvious_chance: float, other_chance: float, min_choices: int
) -> tuple[chess.Move, float]:
    """Get a move using Stockfish, with different chances to check obvious and non-obvious moves.

    Obvious moves are captures/promotions/checkmates. The rest are non-obvious moves.
    A random subset of moves are considered based on the chances given.
    If not enough random choices are made, moves are randomly added until the minimum is reached.

    Args:
        board: The current board state.
        obvious_chance: The chance to consider an obvious move (0 to 1).
        other_chance: The chance to consider a non-obvious move (0 to 1).
        min_choices: The minimum number of choices to consider in total.

    Returns:
        A tuple of the suggested move and the estimated win chance (0-100).
    """
    obvious_chance = 0
    other_chance = 0
    legal_moves = list(board.legal_moves)
    # Shuffle moves for randomness
    random.shuffle(legal_moves)
    # Split moves into obvious and non-obvious
    obvious_moves = []
    non_obvious_moves = []
    for move in legal_moves:
        board.push(move)
        if board.is_capture(move) or board.is_checkmate() or move.promotion:
            obvious_moves.append(move)
        else:
            non_obvious_moves.append(move)
        board.pop()
    # Decide what moves to consider
    search_moves = []
    for move in obvious_moves:
        if random.random() < obvious_chance:
            search_moves.append(move)
    for move in non_obvious_moves:
        if random.random() < other_chance:
            search_moves.append(move)
    # Add more moves if needed
    while len(search_moves) < min_choices and legal_moves:
        move = legal_moves[-1]
        if move not in search_moves:
            search_moves.append(move)
        legal_moves.pop()
    # Get suggested move
    logger.info(f"Considering {len(search_moves)} moves: {search_moves}")
    stockfish_res = await query_chess_api(board, search_moves)
    return chess.Move.from_uci(stockfish_res["move"]), 100 - stockfish_res["winChance"]


async def get_move(page: Page, board: Board) -> tuple[chess.Move, float]:
    """Get a move for the given board. Quality varies based on elo and time left. Simulates thinking time.

    First, we split moves into obvious (captures/promotions/checkmates) and non-obvious moves.
    Then, we decide what move to make (all fractions are chances, left-to-right to fill):
    Noob (~600?): Stockfish query with 1/3 obvious and 1/12 of the non-obvious moves, with at least 1 choice
    Amateur (~1000?): Stockfish query with 3/4 obvious and 1/4 of the non-obvious moves, with at least 2 choices
    Pro (~1600?): Stockfish query with all obvious and 2/3 of the non-obvious moves, with at least 4 choices

    Args:
        page: The current page.
        board: The current board state.

    Returns:
        A tuple of the suggested move and the estimated win chance (0-100).
    """
    time_left: Optional[int] = await get_time_left(page)
    # Adjust elo based on time pressure (3 minute game)
    adjusted_elo: int = elo
    if time_left is not None and time_left < 90:
        adjusted_elo -= (90 - time_left) * 10
    # Get move based on elo
    obvious_chance = 1 / (1 + 10 ** ((750 - adjusted_elo) / 500))
    other_chance = 1 / (1 + 10 ** ((1400 - adjusted_elo) / 750))
    min_choices = max((adjusted_elo - 700) // 300 + 1, 1)
    move, win_chance = await _get_move_stockfish(board, obvious_chance, other_chance, min_choices)
    logger.info(
        f"Adjusted elo: {adjusted_elo}, {obvious_chance:.2f}/{other_chance:.2f}/{min_choices}, Win: {win_chance:.2f}%"
    )
    return move, win_chance


async def screenshot_chess_activity() -> Optional[Image.Image]:
    """Get a screenshot of the whole page (including the board), or None if no screenshot is available."""
    global last_screenshot
    if not chess_page:
        return last_screenshot
    last_screenshot = Image.open(io.BytesIO(await chess_page.screenshot()))
    return last_screenshot


async def play_chess_activity(callback) -> str:
    """Play chess against the user (or the computer).

    The callback should be an async function that accepts exactly one string argument.
    Awaits the callback with messages representing an invite link or info about the game.
    """
    global status, chess_page, curr_win_chance, more_info, last_screenshot
    if status != "idle":
        await callback("Error: Already in a match.")
        return "Error: Already in a match."
    status = "starting"
    more_info = f"You are starting a chess match against {'a bot' if against_computer else 'a user'}."
    curr_win_chance = 50
    last_screenshot = None
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=False, slow_mo=500)
            # Create context and page
            if Path(STATE_FILE).exists():
                logger.info("Restoring state...")
                context = await browser.new_context(storage_state=STATE_FILE)
            else:
                context = await browser.new_context()

            # Play chess
            page = await context.new_page()
            chess_page = page
            page.set_default_timeout(10000)
            await login(page, context)
            if against_computer:
                await start_match_computer(page)
                await callback("im in, spectate me!")
            else:
                challenge_link = await get_challenge_link(page)
                await callback(f"join up {challenge_link}")
                await wait_for_accepted_match(page)
            status = "playing"
            while True:
                more_info = f"You are playing a chess match as the Black pieces against {'a bot' if against_computer else 'a user'}. Your current win chance is {curr_win_chance:.1f}%."  # noqa: E501
                await wait_for_move(page)
                match_result = await check_game_over(page)
                if match_result:
                    break
                await play_move(page)  # Might dry move, but that's ok

            # Close ending dialog
            await page.wait_for_timeout(700)
            await page.locator("button.game-over-header-close").click()
            await page.wait_for_timeout(500)
            last_screenshot = await screenshot_chess_activity()
            more_info = (
                f"You have finished the chess match. Winner: {match_result[0]}. Full result: {match_result[1].strip()}."
            )
            logger.info(f"Finished. {more_info}")
            await callback(f"chess: game over! winner: {match_result[0]}. ({match_result[1].strip()})")
            await page.wait_for_timeout(1000)
            await context.close()
            await browser.close()
    except Exception as e:
        logger.exception(e)
        await callback(f"Error: {e}")
    status = "idle"
    chess_page = None
    return "Finished playing chess."


def configure_chess(elo: int, against_computer: bool) -> None:
    """Configures the chess activity.

    Args:
        elo: Bob's elo rating. Should be in [200, 2400].
        against_computer: Whether Bob is playing against the computer or a user.
    """
    globals()["elo"] = elo
    globals()["against_computer"] = against_computer


def get_chess_info() -> str:
    """Get the current chess activity status."""
    return more_info
