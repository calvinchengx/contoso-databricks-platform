# Windows-safe: recipes call Python scripts. No pipes, rm, &&, or backticks.

ifeq ($(OS),Windows_NT)
  SHELL := sh.exe
  .SHELLFLAGS := -c
endif

UV ?= uv

.PHONY: help doctor up down verify test lint

help:
	@echo "  doctor   Check prerequisites"
	@echo "  up       Start databricks-emulator + Sail + UC + OpenMetadata"
	@echo "  down     Stop the stack"
	@echo "  verify   Provision, ingest, bronze, silver, gold, govern"
	@echo "  test     Repo-boundary tests (no Docker)"

doctor:
	$(UV) run --frozen --group dev python scripts/doctor.py

up:
	$(UV) run --frozen --group dev python scripts/compose.py up -d --wait

down:
	$(UV) run --frozen --group dev python scripts/compose.py down -v

verify:
	$(UV) run --frozen --group engine python platform/provision.py
	$(UV) run --frozen --group engine python platform/seed_secrets.py
	$(UV) run --frozen --group engine python platform/ingest.py
	$(UV) run --frozen --group engine python platform/bronze.py
	$(UV) run --frozen --group engine python platform/silver.py
	$(UV) run --frozen --group engine python platform/register.py
	$(UV) run --frozen --group dbt python platform/gold.py
	$(UV) run --frozen --group engine python platform/govern.py

test:
	$(UV) run --frozen --group dev python -m pytest tests -q

lint:
	$(UV) run --frozen --group dev python -m ruff check platform tests scripts
