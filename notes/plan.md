# Bob Bot 2nd Edition

## Overall Vision

I envision Bob as a simulation of a human being. The best way to code him isn't just as a Discord chatbot anymore. Instead, he should be doing real life things (simulated work, play, etc), have moods/memories, want to make friends and get to know people, have desires like wanting to play a specific game, etc... and he should be heavily incentivized (or forced) to do these things through Discord. Streaming won't be a part of this project - that can be done manually just by starting the stream on the laptop Windows computer.

Bob will have a "default" mode, along with persistent long-term storage (stays across different versions), in which he will act just like any human would. That is, he can respond to pings on Discord, but he can also initiate messages, start and respond to DMs, and so on. He does not and should not try to comply with every request he's given, he should treat some people as close friends and some as strangers, and he should treat many things jokingly. There should still be some safeguard in place for self-deprecating and/or mentally concerning messages, but apart from that, Bob should be ok with being very edgy and toxic. He shouldn't be cringe though.

To give some level of control, first, Bob should have some sort of "debug screen" - like a bare bones "website" that shows his current mood, what he is doing/thinking, etc. to quickly diagnose why he's acting certain ways. Second, Bob should have an "obedient" mode, in which he should strive to comply with every human request he's given - that should override his mood / willingness to do so. Finally, Bob should also have an "off" mode, and an option to remove all simulated latency between actions (for debugging).

### Update

A bit of a shift in vision: It doesn't feel right to try to pretend that Bob is human. I don't think that would work well. Instead, we'll make it interactive and feel like a real Discord user, but we won't blur the lines that it's a bot. It won't have simulated life events, make up stories, etc... due to real life concerns and time constraints, I think this is the way to go.

## Ideal Features

- Discord Text
  - Detect when Bob is pinged (DM, direct ping, or name), and differentiate that from just a new message.
  - Be able to remember a short conversation history (last 6 non-command messages truncated to last 128 tokens, not including current one), for context.
  - Make a running summary / status report of what Bob is talking about (and with who), shared across server and DMs.
  - Be able to see if someone is currently typing (ex: to decide whether to respond or not).
  - Be able to see if the message was sent as a reply to another message.
  - Be able to see if a previous or current message was edited (ex: right before sending a response).
  - Be able to remember deleted messages (if Bob saw them before).
  - Be able to see image attachments.
  - Let Bob decide whether to look at the message based on whether he was pinged.
  - Let Bob decide whether to send messages as a reply.
  - Query external tools (web search, image search, reasoning, mood, etc) to determine a good reply.
  - Give a reply in Discord's writing/humor style.
  - Be fine and open with NSFW messages and replies.
  - Still, send all messages with the intention of ensuring everyone has a good time.
- Voice Chat
  - Be able to join and leave VCs.
  - Be able to hear people in VC (using Whisper or similar).
  - Be able to speak reasonably well in VC (using smart TTS tools).
  - Be able to respond to someone else in real time (similar to human response time).
  - Recognize when Bob should talk (being called on or period of silence, don't try to interrupt).
  - Talk in a style that's appropriate for Discord VCs.
  - Query external tools in the background to determine good replies.
  - Be able to work with other portions of the bot (ex: what Bob says/hears in VC should influence his mood, what he types in text chat, etc.).
- Human-like
  - Have a semi-persistent mood.
  - Know what Bob (himself) is doing at the moment, and factor that in when sending messages.
  - Have desires (ex: to make/hang out with friends), and factor that in when making decisions.
  - Learn about people through their real names, as opposed to Discord handles (only care about handles when immediately relevant).
  - Be able to store and recall facts and tidbits about people/events through long-term memory.
  - Consolidate long-term memory as needed to maintain effective recall.
  - Understand its relationship with other people (ex: whether they're strangers or friends).
  - Do tasks normal humans do - sleep, eat, do some work/classes, etc. don't just be terminally online.
  - Choose when to do these tasks, potentially asking friends to join or joining friends.
  - Understand college-level and/or server-specific slang and jokes without needing to do a web search.
  - Have a deep, consistent life background and writing style. Stick to it.
  - Do not give misleading info. Do not lie with malicious intent.
- Tools
  - Know the current time and date.
  - Be able to search the web for up-to-date content, look for relevant images, and do reverse image search.
  - Be able to roughly understand YouTube videos/shorts (ex: through their transcripts).
  - Be able to reason through complex problems through multi-step LLM thought processes.
  - Have access to a code interpreter to help with solving complex problems (ex: calculator).
  - Be able to choose to read/send messages, join/leave VCs, and play games as needed.
- Gaming
  - Be able to join a Chess.com match (in regular chess, possibly timed) using an invite link.
  - Play chess at a configurable level of difficulty (anything is fine).
  - Be able to join a Skribbl.io match using an invite link.
  - Be able to guess a word sometimes, given someone else's drawing and the guesses so far.
  - Be able to draw a word well enough such that others can guess it sometimes, given a vector art image of the word. Stop drawing when the round ends.
  - Extra: Use OCR of some sort to filter out words in the image that may give away the answer. Or, start drawing related text if no one guesses the image.
  - Be able to join a League of Legends lobby when being sent an invite.
  - Be able to play games of Coop vs. AI as a solo mid laner with one champ, on Beginner difficulty.
  - Be able to play games of Coop vs. AI as a duo bot lane with one champ, on Beginner difficulty.
- Ease of Use
  - Have a default mode which incorporates all the above features.
  - Have an obedient mode which heavily encourages the bot to honor any request people make of it.
  - Have an off mode that turns the bot off. No requests of any sort should be made during this time.
  - Create a simple web interface for debugging and/or tuning core features without needing to reboot.
- Efficiency
  - Almost all LLM requests should be tied to a Discord message. Periodic updates should happen at most once every 1-2 hours.
  - Prompts and repsonses between agents should try to keep token use low.
  - Keep the system simple to think about, avoid adding too many agents.

## Design Overview

See the flow chart.

**Do one part at a time. Start small. Build with the intention of iterating.**

## Guidelines

### Safe From Bugs

- Use Python's type hints along with the `Typing` module to avoid ambiguity about types and provide editor autocompletions. Do not mix types.
- Use `flake8`, `flake8-docstrings`, and `mypy` to perform code/documentation linting and type checking.
- Use `pytest` to lightly test each individual package's API when applicable.
  - Don't emphasize the tests too much - you can try making small ones to think through specs. For the most part though, make them when you're done implementing, just to ensure you don't break stuff.
  - Some manual integration tests are fine (and good for documentation).
- Use Github Actions to make a CI that runs `make lint` and `make test`.

### Easy To Understand

- Code everything in Python if possible. No more TypeScript :/
- Write Google style docstrings for functions (no need to repeat types), along with a module-level docstring at the top of each file (no format, just a brief description).
- Use Sphinx, the industry standard, along with `autodoc` and the Read the Docs theme, to generate nice-looking documentation. See `sphinx-rtd-theme`.
- Setup Github Pages to go to the generated docs.
- Use the `black` code formatter, along with `isort` import sorting, to ensure a consistent code style.
- Use Python's `logging` module for logs, `warnings` module for warnings, and define custom exceptions if needed to raise errors. Only use print statements for testing.

### Ready For Change

- Keep packages separate from each other, with distinct purposes.
  - A module is a single Python file, while a package contains multiple module files and an `__init__.py` to specify package-level exports.
- Avoid circular imports by being careful with your design (keep it as a DAG!), or, if you must, import packages locally (in functions or classes).
- Each package should expose a simple, relatively stable API (through functions or classes).
- Use `make` with the options `lint`, `format`, `docs`, `build`, `run`, `test`, and `script` for easy cross-platform entry points.
- Commit frequently. Make small, logical changes with clear messages. Only push working code. No need to make branches.

### Other

- Use Visual Studio Code for development. PyCharm is too heavy.
- Use ChatGPT and/or GitHub Copilot to help with development.
- Use `pip`, `pip-tools`, and `venv`, along with a `requirements.txt` file, as the dependency manager. Conda is unnecessarily complex.
- Use a `.env` file and `python-dotenv` to securely store credentials and other secret variables.
- Lighten the development load using `pre-commit` with `make build` and `make test`. Ideally, all we need to worry about is actually coding the bot, running it, and having all the tests be auto-run before committing.
- We've set the linters/checkers up so that code files in `old` or starting with `dev_` do not have strict style or type hint requirements, for quicker/easier experimenting.
  - Formatters will still run on save in these files.
- Follow good practices, like test coverage of critical modules, deliberate comments, good naming, etc.
