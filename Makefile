COMPOSE = docker compose
RUN = $(COMPOSE) run --rm pipeline
RUN_NO_DB = $(COMPOSE) run --rm --no-deps pipeline

.DEFAULT_GOAL := help
.PHONY: help build db pipeline ingest load report test lint format psql down clean

help: ## Show available targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "  %-10s %s\n", $$1, $$2}'

build: ## Build the pipeline image
	$(COMPOSE) build pipeline

db: ## Start PostgreSQL in the background
	$(COMPOSE) up -d --wait db

pipeline: ## Run everything: ingest, clean, load and report
	$(RUN) python -m src.pipeline

ingest: ## Download the yearly CSVs from the open data portal
	$(RUN_NO_DB) python -m src.pipeline --step ingest

load: ## Clean the downloaded files and load them into PostgreSQL
	$(RUN) python -m src.pipeline --step load

report: ## Run the SQL analyses and regenerate docs/analises.md
	$(RUN) python -m src.pipeline --step report

test: ## Run the test suite
	$(RUN_NO_DB) pytest

lint: ## Check code style with ruff
	$(RUN_NO_DB) sh -c "ruff check . && ruff format --check ."

format: ## Fix lint issues and format the code
	$(RUN_NO_DB) sh -c "ruff check --fix . && ruff format ."

psql: ## Open a SQL shell on the database
	$(COMPOSE) exec db sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'

down: ## Stop the containers (keeps the database volume)
	$(COMPOSE) down

clean: ## Remove containers, database volume and downloaded data
	$(RUN_NO_DB) rm -rf data/raw
	$(COMPOSE) down -v
