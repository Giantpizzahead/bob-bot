"""Main runner for the bot."""

import os
import resource

import bobbot

logger = bobbot.get_logger(__name__)


def main() -> None:
    """Run the bot."""
    try:
        limit_mb = 1024 + 128  # Heroku RAM limit
        if os.getenv("MEMORY_LIMIT"):
            limit_mb = int(os.getenv("MEMORY_LIMIT"))
        limit_bytes = limit_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))
        logger.info(f"Memory limit set to {limit_mb} MB.")
    except Exception:
        pass
    bobbot.run_bot()
    logger.info("Stopping...")


if __name__ == "__main__":
    main()
