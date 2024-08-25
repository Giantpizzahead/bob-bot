"""Main runner for the bot."""

import bobbot


def main() -> None:
    """Run the bot."""
    bobbot.run_bot()
    bobbot.get_logger("bobbot").info("Stopping...")


if __name__ == "__main__":
    main()
