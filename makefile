install-dependencies:
	@ pip install uv
	@ uv sync --all-extras --no-install-project

install:
	@ pip install uv
	@ uv sync --all-extras

install-updates:
	@ pip install uv
	@ uv sync --upgrade --refresh --all-extras

list-outdated: install
	@ pip list -o

lint-check:
	@ uv run lint-check ./src ./tests

lint-check-ci:
	@ uv run lint-check ./src ./tests --output-file lint-check-results.json --output-format annotations

lint-fix:
	@ uv run lint-check --fix ./src ./tests

type-check:
	@ uv run type-check --mypy ./src ./tests

type-check-ci:
	@ uv run type-check --mypy ./src ./tests --output-file type-check-results.json --output-format annotations

security-check:
	@ uv run security-check ./src ./tests

security-check-ci:
	@ uv run security-check ./src ./tests --output-file security-check-results.json --output-format annotations

build:
	@ uv build

start:
	@ echo "Not Supported"

start-prod:
	@ echo "Not Supported"

test:
	@ uv run test-check tests

test-ci:
	@ uv run test-check tests --output-file test-check-results.json --output-format annotations

clean:
	@ rm -rf ./.mypy_cache ./__pycache__ ./build ./dist

publish: build
	@ uv publish

GIT_LAST_TAG=$(shell git describe --tags --abbrev=0 2>/dev/null)
GIT_COUNT=$(shell git rev-list $(if $(GIT_LAST_TAG),$(GIT_LAST_TAG)..HEAD,HEAD) --count)
publish-dev:
	@ uv run version --part dev --count $(GIT_COUNT)
	@ uv build
	@ uv publish

.PHONY: *
