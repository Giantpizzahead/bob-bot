# Bob Bot v2

## Overall Vision

hi

## Design Overview

hi

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
