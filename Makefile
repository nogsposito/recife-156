COMPOSE = docker compose
RUN = $(COMPOSE) run --rm pipeline
RUN_NO_DB = $(COMPOSE) run --rm --no-deps pipeline

.DEFAULT_GOAL := help
.PHONY: help build db pipeline refresh ingest load train benchmark dashboard notebooks jupyter test lint format psql down clean

help: ## Show available targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "  %-10s %s\n", $$1, $$2}'

build: ## Build the pipeline image
	$(COMPOSE) build pipeline

db: ## Start PostgreSQL in the background
	$(COMPOSE) up -d --wait db

pipeline: ## Run everything: ingest what changed, build silver, check quality, load gold
	$(RUN) python -m src.pipeline

refresh: ## Same as pipeline, but downloads and rebuilds every layer from scratch
	$(RUN) python -m src.pipeline --full-refresh

ingest: ## Bring new or changed source files into the bronze layer
	$(RUN_NO_DB) python -m src.pipeline --step ingest

load: ## Build silver from bronze, run the quality checks and load the gold tables
	$(RUN) python -m src.pipeline --step load

train: ## Train the 30-day resolution model and write docs/ml_results.md
	$(RUN) python -m src.ml.train

benchmark: ## Time the heavy queries with and without indexes (docs/sql_optimization.md)
	$(RUN) python -m src.benchmark

dashboard: ## Open the dashboard at http://localhost:8501 with the data already loaded
	$(COMPOSE) up -d --wait db
	$(COMPOSE) up -d --no-deps dashboard

notebooks: ## Re-run both notebooks, refreshing their outputs and the charts in docs/img
	$(RUN) jupyter nbconvert --to notebook --execute --inplace notebooks/*.ipynb

jupyter: ## Open JupyterLab at http://localhost:8888 (no token, bound to localhost only)
	$(COMPOSE) run --rm -p 127.0.0.1:8888:8888 pipeline jupyter lab --ip=0.0.0.0 --allow-root --no-browser --IdentityProvider.token='' --notebook-dir=notebooks

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
	$(RUN_NO_DB) sh -c "rm -rf data/raw data/bronze data/silver"
	$(COMPOSE) down -v
