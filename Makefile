PYTHON ?= python3

.PHONY: help install install-dev test test-all test-aiwire coverage lint format format-check type-check check clean docs cuda-native cuda-clean aiwire-native aiwire-clean

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

install: ## Install the package
	$(PYTHON) -m pip install -e .

install-dev: ## Install with development dependencies
	$(PYTHON) -m pip install -e ".[dev]"

test: ## Run the complete supported-runtime test suite
	$(PYTHON) -m pytest tests/

test-all: test ## Backwards-compatible alias for the complete test suite

test-aiwire: ## Run the fast AIWire protocol and transport gate
	$(PYTHON) -m pytest tests/test_ai_wire.py tests/test_ai_wire_token.py tests/test_aiwire_proxy.py tests/test_aiwire_transport_examples.py

cuda-native: ## Build and install the optional CUDA native backend
	$(MAKE) -C native/cuda install

cuda-clean: ## Clean CUDA native backend build artifacts
	$(MAKE) -C native/cuda clean

aiwire-native: ## Build and install the optional C++ AI wire backend
	$(MAKE) -C native/aiwire install

aiwire-clean: ## Clean C++ AI wire backend build artifacts
	$(MAKE) -C native/aiwire clean

lint: ## Run linting
	$(PYTHON) -m flake8 src/aura_compression --count --select=E9,F63,F7,F82 --show-source --statistics

format: ## Format code with black
	$(PYTHON) -m black src/aura_compression tests examples tools
	$(PYTHON) -m isort src/aura_compression tests examples tools

format-check: ## Verify formatting and import order without changing files
	$(PYTHON) -m black --check src/aura_compression tests examples tools
	$(PYTHON) -m isort --check-only src/aura_compression tests examples tools

type-check: ## Run mypy type checking
	$(PYTHON) -m mypy src/aura_compression --ignore-missing-imports --no-strict-optional

coverage: ## Run tests with coverage
	$(PYTHON) -m pytest tests/ --cov=aura_compression --cov-report=xml --cov-report=html --cov-report=term

clean: ## Clean up build artifacts and cache
	rm -rf build/ dist/ *.egg-info/
	rm -rf __pycache__/ .pytest_cache/ .mypy_cache/
	rm -rf htmlcov/ .coverage
	rm -f src/aura_compression/native/libaura_cuda.so
	rm -f src/aura_compression/native/libaura_aiwire.so
	rm -f src/aura_compression/native/libaura_aiwire.dylib
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} +

docs: ## Build documentation
	@echo "Documentation would be built here"

check: format-check lint test ## Run every blocking local/CI check
