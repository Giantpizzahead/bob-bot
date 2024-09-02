requirements:
	pip-compile requirements.in --strip-extras
	pip-compile dev-requirements.in --strip-extras
	pip-sync dev-requirements.txt

lint:
	flake8 .

format:
	black .
	isort .

docs:
	sphinx-build docs/config docs

build:
	make lint
	make format
	make docs

clean:
	rm -rf build

run:
	python src/main.py

test:
	flake8 .
	black . --check
	# pytest

.PHONY: requirements lint format docs build clean run test
