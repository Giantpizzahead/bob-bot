# Bob Bot

<!-- index.rst content start -->

hi i am bob :D

## Setup

Use **Python 3.12** in a virtual environment! Install `make` if on Windows.

```sh
# Make sure you are in a Python 3.12 virtual environment first
pip install pip-tools
pip-sync requirements.txt
playwright install
make run
```

Environment variables (some required, some optional):

```text
DISCORD_TOKEN = [Discord bot token](https://www.writebots.com/discord-bot-token/).
DISCORD_CHANNELS = A list of channel ID strings to talk in. It's best to have at most one channel per server. Use Discord's developer mode to get these IDs. Ex: ['123...', '456...']
OPENAI_KEY = [OpenAI API key](https://platform.openai.com/api-keys).
SERPER_API_KEY = [Serper API key](https://serper.dev/api-key) (for Google search).

ACTIVITIES_USERNAME = (Optional) Username for logging into all activities. Needed to use activities.
ACTIVITIES_PWD = (Optional) Password for logging into all activities. Needed to use activities.
CHESS_STATE_JSON = (Optional) Playwright state.json file, logged in as the activities user, to use for chess (copy-pasted here). Without this, the chess activity *might* fail due to a "locator timeout exceeded" error.

OPENROUTER_KEY = (Unused) OpenRouter API key.
DEEPGRAM_KEY = (Unused) Deepgram API key.
SUPABASE_KEY = (Unused) Supabase vector store API key.
SUPABASE_URL = (Unused) Supabase vector store URL.
SUPABASE_PROJECT_PWD = (Unused) Supabase vector store password.

LANGCHAIN_API_KEY = (Optional) LangChain API key for LangSmith tracing.
LANGCHAIN_TRACING_V2 = (Optional) Boolean for enabling LangSmith tracing.
```

## Development

Use **Python 3.12** in a virtual environment! Install `make` if on Windows.

```sh
# Make sure you are in a Python 3.12 virtual environment first
pip install pip-tools
pip-sync dev-requirements.txt
playwright install
pre-commit install
make build
make test
```

## Issues

**Chess.com doesn't work, the locator keeps timing out.**

1. Login to chess.com locally using Playwright.
2. Save storage to `state.json`.
3. Set the environment variable `CHESS_STATE_JSON` to the copy-pasted content of `state.json`.
4. Profit
