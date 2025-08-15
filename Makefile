.DEFAULT_GOAL := help

.PHONY: help
help: ## Show available targets
	@echo "Targets:"
	@awk 'BEGIN {FS=":.*## "}/^[a-zA-Z0-9_.-]+:.*## /{printf "  %-16s %s\n",$$1,$$2}' $(MAKEFILE_LIST)

.PHONY: build
build: ## Build the project
	@echo "Building the project..."

.PHONY: run
run: ## Run the project
	@echo "Running the project..."

.PHONY: test
test: ## Run tests
	@echo "Running tests..."

.PHONY: clean
clean: ## Clean up
	@echo "Cleaning up..."

.PHONY: venv
venv: ## Set up virtual environment
	@echo "Setting up virtual environment..."
	# If env doesnt exists, create with uv
	if [ ! -d venv ]; then \
		@echo "Creating .venv with uv..."
	    uv venv; \
	fi

	. venv/bin/activate


.PHONY: dev-deps
dev-deps: ## Install development dependencies
	@echo "Installing development dependencies..."
	uv pip install -e .[dev]

.PHONY: check-deps
check-deps: ## Check if required deps are installed
	@echo "🔍 Checking dependencies..."

	@command -v uv >/dev/null 2>&1 || { echo "❌ uv not found. Install it: https://github.com/astral-sh/uv"; exit 1; }
	@uv --version

	@command -v python >/dev/null 2>&1 || { echo "❌ python not found."; exit 1; }
	@python --version | grep -q "3\.12" || { echo "❌ Python 3.12.x required."; exit 1; }

	@echo "✅ All dependencies OK"
