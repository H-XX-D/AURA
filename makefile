# AURA Compression - Multi-Language Build System
# Copyright (c) 2025 Todd James Hendricks
# Licensed under Apache License 2.0
# Patent Pending - Application No. 19/366,538

.PHONY: all clean build test install python nodejs rust docker help

# Default target
all: build

help:
	@echo "AURA Compression Build System"
	@echo ""
	@echo "Available targets:"
	@echo "  all           - Build all packages (default)"
	@echo "  build         - Build all packages"
	@echo "  test          - Run all tests"
	@echo "  install       - Install all packages locally"
	@echo "  clean         - Clean all build artifacts"
	@echo ""
	@echo "Python targets:"
	@echo "  python-build  - Build Python package"
	@echo "  python-test   - Run Python tests"
	@echo "  python-install - Install Python package"
	@echo "  python-publish - Publish to PyPI"
	@echo ""
	@echo "Node.js targets:"
	@echo "  nodejs-build  - Build Node.js package"
	@echo "  nodejs-test   - Run Node.js tests"
	@echo "  nodejs-install - Install Node.js package"
	@echo "  nodejs-publish - Publish to npm"
	@echo ""
	@echo "Rust targets:"
	@echo "  rust-build    - Build Rust crate"
	@echo "  rust-test     - Run Rust tests"
	@echo "  rust-install  - Install Rust binaries"
	@echo "  rust-publish  - Publish to crates.io"
	@echo ""
	@echo "Docker targets:"
	@echo "  docker-build  - Build Docker image"
	@echo "  docker-test   - Test Docker image"
	@echo "  docker-run    - Run Docker container"
	@echo "  docker-publish - Push to Docker Hub"

# Build all packages
build: python-build nodejs-build rust-build docker-build

# Test all packages
test: python-test nodejs-test rust-test docker-test

# Install all packages
install: python-install nodejs-install rust-install

# Clean all build artifacts
clean:
	@echo "Cleaning Python build artifacts..."
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ htmlcov/ .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleaning Node.js build artifacts..."
	rm -rf lib/ node_modules/ coverage/
	@echo "Cleaning Rust build artifacts..."
	cargo clean
	@echo "Cleaning Docker artifacts..."
	docker-compose down -v 2>/dev/null || true
	@echo "Clean complete!"

#
# Python targets
#

python-build:
	@echo "Building Python package..."
	pip install build
	python -m build

python-test:
	@echo "Running Python tests..."
	pip install -e ".[dev]"
	pytest tests/ -v --cov=aura_compression --cov-report=html --cov-report=term

python-install:
	@echo "Installing Python package..."
	pip install -e ".[dev,websocket]"

python-publish:
	@echo "Publishing Python package to PyPI..."
	pip install twine
	python -m build
	twine upload dist/*

python-format:
	@echo "Formatting Python code..."
	pip install black
	black aura_compression/ packages/ tests/ experiments/

python-lint:
	@echo "Linting Python code..."
	pip install flake8 mypy
	flake8 aura_compression/ packages/
	mypy aura_compression/ packages/

#
# Node.js targets
#

nodejs-build:
	@echo "Building Node.js package..."
	npm install
	npm run build

nodejs-test:
	@echo "Running Node.js tests..."
	npm install
	npm test

nodejs-install:
	@echo "Installing Node.js package..."
	npm install

nodejs-publish:
	@echo "Publishing Node.js package to npm..."
	npm run build
	npm test
	npm publish --access public

nodejs-format:
	@echo "Formatting Node.js code..."
	npm run format

nodejs-lint:
	@echo "Linting Node.js code..."
	npm run lint

#
# Rust targets
#

rust-build:
	@echo "Building Rust crate..."
	cargo build --release

rust-test:
	@echo "Running Rust tests..."
	cargo test --all-features

rust-install:
	@echo "Installing Rust binaries..."
	cargo install --path .

rust-publish:
	@echo "Publishing Rust crate to crates.io..."
	cargo publish

rust-doc:
	@echo "Building Rust documentation..."
	cargo doc --all-features --open

rust-bench:
	@echo "Running Rust benchmarks..."
	cargo bench

rust-format:
	@echo "Formatting Rust code..."
	cargo fmt

rust-lint:
	@echo "Linting Rust code..."
	cargo clippy --all-features -- -D warnings

#
# Docker targets
#

docker-build:
	@echo "Building Docker image..."
	docker build -t aura/compression:latest .

docker-build-dev:
	@echo "Building Docker development image..."
	docker build -f Dockerfile.dev -t aura/compression:dev .

docker-test:
	@echo "Testing Docker image..."
	docker run --rm aura/compression:latest aura-compress --help
	docker run --rm aura/compression:latest aura-decompress --help

docker-run:
	@echo "Running Docker container..."
	docker-compose up -d

docker-stop:
	@echo "Stopping Docker container..."
	docker-compose down

docker-logs:
	@echo "Showing Docker logs..."
	docker-compose logs -f

docker-publish:
	@echo "Publishing Docker image to Docker Hub..."
	docker tag aura/compression:latest aura/compression:$(shell git describe --tags --abbrev=0)
	docker push aura/compression:latest
	docker push aura/compression:$(shell git describe --tags --abbrev=0)

docker-compose-up:
	@echo "Starting all services with Docker Compose..."
	docker-compose up -d

docker-compose-up-monitoring:
	@echo "Starting services with monitoring..."
	docker-compose --profile monitoring up -d

docker-compose-down:
	@echo "Stopping all Docker Compose services..."
	docker-compose down -v

#
# Development targets
#

dev-setup:
	@echo "Setting up development environment..."
	make python-install
	make nodejs-install
	rustup default stable
	@echo "Development environment ready!"

dev-test-all:
	@echo "Running all tests..."
	make python-test
	make nodejs-test
	make rust-test
	@echo "All tests complete!"

dev-format-all:
	@echo "Formatting all code..."
	make python-format
	make nodejs-format
	make rust-format
	@echo "All code formatted!"

dev-lint-all:
	@echo "Linting all code..."
	make python-lint
	make nodejs-lint
	make rust-lint
	@echo "All linting complete!"

#
# Release targets
#

release-patch:
	@echo "Creating patch release..."
	@./scripts/release.sh patch

release-minor:
	@echo "Creating minor release..."
	@./scripts/release.sh minor

release-major:
	@echo "Creating major release..."
	@./scripts/release.sh major

#
# Documentation targets
#

docs:
	@echo "Building all documentation..."
	make python-docs
	make nodejs-docs
	make rust-doc

python-docs:
	@echo "Building Python documentation..."
	pip install sphinx sphinx-rtd-theme
	cd docs && make html

nodejs-docs:
	@echo "Building Node.js documentation..."
	npm run docs

#
# CI/CD targets
#

ci-test:
	@echo "Running CI tests..."
	make python-test
	make nodejs-test
	make rust-test
	make docker-test

ci-build:
	@echo "Running CI build..."
	make python-build
	make nodejs-build
	make rust-build
	make docker-build

ci-publish:
	@echo "Running CI publish..."
	make python-publish
	make nodejs-publish
	make rust-publish
	make docker-publish
