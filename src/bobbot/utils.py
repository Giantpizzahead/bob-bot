"""Logging, environment variables, and other utility functions."""

import logging
import logging.config
import os
import re
from datetime import datetime, timezone
from functools import partialmethod
from typing import Optional

import requests
from discord.utils import _ColourFormatter as ColourFormatter
from dotenv import load_dotenv
from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from playwright_stealth import StealthConfig, stealth_async
from tqdm import tqdm

load_dotenv()
tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)  # Disable tqdm progress bars by default
debug_info: str = ""
browser: Optional[Browser] = None
playwright_instance = None


async def get_playwright_browser() -> Browser:
    """Get the Playwright browser instance, creating it if it doesn't exist yet."""
    global browser, playwright_instance
    if browser is None:
        if playwright_instance is None:
            playwright_instance = await async_playwright().start()
        browser = await playwright_instance.chromium.launch(headless=True, slow_mo=500)
    return browser


async def get_playwright_page(context: BrowserContext) -> Page:
    """Get a stealthy Playwright page instance for the given context."""
    page = await context.new_page()
    # See https://github.com/AtuboDad/playwright_stealth/issues/31 for why navigator_user_agent is disabled
    await stealth_async(
        page, StealthConfig(navigator_languages=False, navigator_user_agent=False, navigator_vendor=False)
    )
    page.set_default_timeout(10000)
    return page


async def close_playwright_browser():
    """Close the Playwright browser instance if it exists."""
    global browser, playwright_instance
    if browser is not None:
        await browser.close()
        del browser
        browser = None
    if playwright_instance is not None:
        await playwright_instance.stop()
        del playwright_instance
        playwright_instance = None


def get_logger(name: str, level: int = logging.INFO, formatter: logging.Formatter | None = None) -> logging.Logger:
    """Get a logger with the specified name and logging level.

    Args:
        name: The name of the logger.
        level: The logging level. Defaults to logging.INFO.
        formatter: The log formatter to use. Defaults to a color formatter.

    Returns:
        The logger.

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info('Here is some info.')
        2024-01-31 06:42:00 INFO     package.module Here is some info.
    """
    if formatter is None:
        formatter = ColourFormatter()
    # Create a logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    # Print logs to console
    if not logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    return logger


def reset_debug_info() -> None:
    """Clear the bot's debug info."""
    global debug_info
    debug_info = ""


def log_debug_info(info: str) -> None:
    """Append to the bot's debug info and log it."""
    global debug_info
    if debug_info:
        debug_info += "\n\n"
    debug_info += info
    logger.info(info)


def get_debug_info() -> str:
    """Get the bot's debug info."""
    return debug_info


def truncate_length(text: str, limit: int = 255, replace_newlines: bool = False) -> str:
    """Make text concise by cutting out the middle, up to limit characters.

    Args:
        text: The text to truncate.
        limit: The maximum length of the text.
        replace_newlines: Whether to replace newlines with 4 spaces.

    Returns:
        The text (with an ellipsis if truncated).
    """
    if replace_newlines:
        text = text.replace("\n", "    ")
    text = text if len(text) <= limit else text[: (limit - 3 + 1) // 2] + "..." + text[-((limit - 3) // 2) :]
    return text


def time_elapsed_str(before: datetime, after: datetime | None = None) -> str:
    """Get a human-readable string representing the time elapsed between two times, or from a time to now."""
    if after is None:
        after = datetime.now(timezone.utc)
    diff = after - before
    seconds = diff.total_seconds()
    minutes = seconds // 60
    hours = minutes // 60
    days = hours // 24
    weeks = days // 7
    months = days // 30
    years = days // 365

    if int(seconds) == 0:
        return "Now"
    elif seconds < 60:
        return "Recent"
        # return f"{int(seconds)} second{'s' if seconds != 1 else ''} ago"
    elif minutes < 60:
        return f"{int(minutes)} minute{'s' if minutes != 1 else ''} ago"
    elif hours < 24:
        return f"{int(hours)} hour{'s' if hours != 1 else ''} ago"
    elif days < 7:
        return f"{int(days)} day{'s' if days != 1 else ''} ago"
    elif weeks < 5:
        return f"{int(weeks)} week{'s' if weeks != 1 else ''} ago"
    elif months < 12:
        return f"{int(months)} month{'s' if months != 1 else ''} ago"
    else:
        return f"~{int(years)} year{'s' if years != 1 else ''} ago"


def get_images_in(content: str) -> list[str]:
    """Get a (potentially empty) list of all URLs that lead to valid, static images in the given content."""
    url_pattern = re.compile(r"(https?://[^\s]+)")
    urls = url_pattern.findall(content)
    image_urls = []
    for url in urls:
        # Check if the URL is valid and points to an image
        try:
            response = requests.head(url, allow_redirects=True)
            content_type = response.headers.get("Content-Type")
            if content_type is not None and content_type.startswith("image"):
                image_urls.append(url)
        except requests.RequestException:
            pass
    return image_urls


def on_heroku() -> bool:
    """Check if the bot is running on Heroku."""
    return "HEROKU_DYNO" in os.environ


logger = get_logger(__name__)
