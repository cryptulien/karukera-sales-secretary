.PHONY: test install compose-check

test:
	python3 -m venv .venv
	.venv/bin/pip install -e ".[dev]" -q
	.venv/bin/pytest

install:
	python3 -m venv .venv
	.venv/bin/pip install -e ".[dev]"

compose-check:
	docker compose config -q
