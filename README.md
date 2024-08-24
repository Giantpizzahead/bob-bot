# Bob Bot

hi i am bob :D

## Setup

Use **Python 3.12** in a virtual environment! Install `make` if on Windows.

```sh
# Make sure you are in a Python 3.12 virtual environment first
pip install pip-tools
pip-sync requirements.txt
make run
```

Environment variables (some required, some optional):

```text
DISCORD_TOKEN = Discord bot token.
DISCORD_CHANNELS = A list of channel ID strings to talk in. Ex: ['123', '456']
OPENAI_KEY = OpenAI API key.
OPENROUTER_KEY = (Unused) OpenRouter API key.
DEEPGRAM_KEY = (Unused) Deepgram API key.
SUPABASE_KEY = (Unused) Supabase vector store API key.
SUPABASE_URL = (Unused) Supabase vector store URL.
SUPABASE_PROJECT_PWD = (Unused) Supabase vector store password.
LANGCHAIN_API_KEY = (Optional) LangChain API key for LangSmith tracing.
LANGCHAIN_TRACING_V2 = (Optional) Boolean for enabling LangSmith tracing.
LANGCHAIN_CALLBACKS_BACKGROUND = true
```

## Development

Use **Python 3.12** in a virtual environment! Install `make` if on Windows.

```sh
# Make sure you are in a Python 3.12 virtual environment first
pip install pip-tools
pip-sync dev-requirements.txt
pre-commit install
make build
make test
```
