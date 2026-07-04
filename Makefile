.PHONY: help install install-dev test test-comprehensive lint format clean docs cuda-native cuda-clean aiwire-native aiwire-clean

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

install: ## Install the package
	pip install -e .

install-dev: ## Install with development dependencies
	pip install -e ".[dev]"

test: ## Run basic tests
	python tests/test_metadata_sidechain_routing.py

test-comprehensive: ## Run comprehensive performance tests
	python tests/test_metadata_sidechain_routing.py --comprehensive

test-all: ## Run all tests with pytest
	pytest tests/ -v

cuda-native: ## Build and install the optional CUDA native backend
	$(MAKE) -C native/cuda install

cuda-clean: ## Clean CUDA native backend build artifacts
	$(MAKE) -C native/cuda clean

aiwire-native: ## Build and install the optional C++ AI wire backend
	$(MAKE) -C native/aiwire install

aiwire-clean: ## Clean C++ AI wire backend build artifacts
	$(MAKE) -C native/aiwire clean

lint: ## Run linting
	flake8 src/ tests/

format: ## Format code with black
	black src/ tests/

type-check: ## Run mypy type checking
	mypy src/

coverage: ## Run tests with coverage
	pytest --cov=aura_compression --cov-report=html --cov-report=term

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

check: lint type-check test ## Run all checks
