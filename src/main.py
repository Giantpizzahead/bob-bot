"""Main runner for the bot."""

import bobbot

logger = bobbot.get_logger(__name__)


def main() -> None:
    """Run the bot."""
    bobbot.run_bot()
    logger.info("Stopping...")


if __name__ == "__main__":
    main()
