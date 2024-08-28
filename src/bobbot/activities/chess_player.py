"""Play chess against the computer or a user on chess.com."""

import asyncio
import io
import os
import random
import re
from pathlib import Path
from typing import Optional

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
chess_page: Optional[Page] = None
last_screenshot: Optional[Image.Image] = None


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
    # Save state
    logger.info("Saving state...")
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
        return "white", description
    elif "0-1" in moves:
        return "black", description
    elif "1/2-1/2" in moves:
        return "draw", description
    else:
        return "unknown", description


async def play_move(page: Page) -> None:
    """Play a move as Black."""
    # Locate all chess pieces within the board
    logger.info("Locating pieces...")
    board_locator = page.locator("wc-chess-board")
    pieces = board_locator.locator("div.piece")
    count = await pieces.count()
    logger.info(f"Found {count} pieces on the board.")

    # Get pieces in parallel
    tasks = [piece.get_attribute("class") for piece in await pieces.element_handles()]
    classes = await asyncio.gather(*tasks)

    # Parse the board and make a move
    board = parse_board(classes)
    board.turn = chess.BLACK
    move = get_move(board)
    logger.info(board)

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


def get_move(board: Board) -> chess.Move:
    """Get a decent move for the given board. For now, it just picks a random legal move."""
    legal_moves = list(board.legal_moves)
    # Shuffle moves for randomness
    random.shuffle(legal_moves)
    # If there is a checkmate move, return it
    for move in legal_moves:
        board.push(move)
        if board.is_checkmate():
            board.pop()
            return move
        board.pop()
    # Otherwise, if a move captures a piece, return it
    for move in legal_moves:
        if board.is_capture(move):
            return move
    # Otherwise, return a random move
    return random.choice(legal_moves)


async def screenshot_chess_activity() -> Optional[Image.Image]:
    """Get a screenshot of the whole page (including the board), or None if no screenshot is available."""
    global last_screenshot
    if not chess_page:
        return last_screenshot
    last_screenshot = Image.open(io.BytesIO(await chess_page.screenshot()))
    return last_screenshot


async def play_chess_activity(callback, against_computer: bool = False) -> None:
    """Play chess against the user (or the computer).

    The callback should be an async function that accepts exactly one string argument.
    Awaits the callback with strings representing an invite link or misc messages.
    """
    global status, chess_page
    if status != "idle":
        await callback("Error: Already playing a game.")
        return
    status = "playing"
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True, slow_mo=500)
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
            while True:
                await wait_for_move(page)
                match_result = await check_game_over(page)
                if match_result:
                    break
                await play_move(page)  # Might dry move, but that's ok
            await callback(f"Game over! Result: {match_result[0]}. {match_result[1]}")
            logger.info(f"Final result: {match_result}")
            await page.wait_for_timeout(1000)
            global last_screenshot
            last_screenshot = await screenshot_chess_activity()
            last_screenshot.save("local/pw/chess_board.png")
            logger.info("Finished.")
            await context.close()
            await browser.close()
    except Exception as e:
        logger.exception(e)
        await callback(f"Error: {e}")
    finally:
        status = "idle"
        chess_page = None
