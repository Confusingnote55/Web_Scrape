# ======= Web Scraper =======

# ---- Variables ----
PYTHON := scrape_env/bin/python
PIP := scrape_env/bin/pip
VENV_DIR := scrape_env
SRC := src
DATA := data
OUTPUT := scraped_output

.DEFAULT_GOAL := help

.PHONY: help setup venv install dirs clean distclean debug-screenshot dynamic-scraper get-sub-indexes master-scraper extract-text lint format requirements

help: ## shows command list
	@echo "-------------------"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z0-9_-]+:.*?## / {printf "%-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""

setup: venv install dirs ## ONE COMMAND: Create venv, install deps, create dirs
	@echo "✅ Full setup complete. (venv, deps, dirs ready) Create .env.local if missing."

venv: ## Create python virtual environment for the project if missing
	@if [ ! -d "$(VENV_DIR)" ]; then \
		python3 -m venv $(VENV_DIR); \
		echo "✅ Virtual env created in $(VENV_DIR)"; \
	else \
		echo "Venv already present: $(VENV_DIR)"; \
	fi

install: ## Install or update Python requirements (from requirements.txt)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PYTHON) -m spacy download en_core_web_sm

dirs: ## Ensure all expected output directories exist
	mkdir -p $(DATA)/vectorstore/default $(DATA)/ingest_cache logs models samples

tree: ## Save directory tree as directory_tree.txt (requires 'tree' installed or fallback to 'find')
	@if command -v tree >/dev/null 2>&1; then \
		tree -a -I '.git|$(VENV_DIR)|__pycache__|.mypy_cache|.pytest_cache|*.egg-info|.vscode|.idea|node_modules|*.DS_Store' . > directory_tree.txt; \
	else \
		echo "'tree' not found, using find fallback."; \
		find . \
			-not -path "./$(VENV_DIR)/*" \
			-not -path "./.git/*" \
			-not -path "./__pycache__/*" \
			-not -path "./.mypy_cache/*" \
			-not -path "./.pytest_cache/*" \
			-not -path "*/.egg-info/*" \
			-not -path "./.vscode/*" \
			-not -path "./.idea/*" \
			-not -path "./node_modules/*" \
			-not -name "*.DS_Store" > directory_tree.txt; \
	fi
	@echo "📁 Directory tree saved to directory_tree.txt"

debug-screenshot: ## Run the Selenium screenshot debug script
	$(PYTHON) $(SRC)/debug_screenshot.py $(ARGS)

dynamic-scraper: ## Run the dynamic web scraper; pass ARGS="..." to customize all CLI args
	$(PYTHON) $(SRC)/dynamic_scraper.py $(ARGS)

get-sub-indexes: ## Get and save sub-index URLs; pass ARGS="..." to customize all CLI args
	$(PYTHON) $(SRC)/get_sub_indexes.py $(ARGS)

master-scraper: ## Run the universal master scraper; pass ARGS="..." to customize all CLI args
	$(PYTHON) $(SRC)/master_scraper.py $(ARGS)

extract-text: ## Extract all project source files to Project_Files.txt; use ARGS for extra arguments
	$(PYTHON) Project-TXT.py $(ARGS)

clean: ## Remove all cache, outputs, screenshots, logs, and generated files (NOT the venv!)
	@echo "⚠️  This deletes all generated outputs in $(DATA), $(OUTPUT), and logs!"
	rm -rf __pycache__ .mypy_cache .pytest_cache logs $(DATA)/* $(OUTPUT)/* *.png *.html *.md

distclean: clean ## Clean everything, including the venv itself
	rm -rf $(VENV_DIR)

lint: ## Lint all Python code using flake8
	$(PYTHON) -m flake8 $(SRC) Project-TXT.py

format: ## Format all Python code using black
	$(PYTHON) -m black $(SRC) Project-TXT.py

requirements: ## Regenerate requirements.txt from the current venv (USE CAREFULLY!)
	$(PIP) freeze > requirements.txt
