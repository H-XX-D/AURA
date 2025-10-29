#!/usr/bin/env python3
"""Setup script for Medicine Cabinet."""

from pathlib import Path
from setuptools import setup, find_packages

# Read the README for the long description
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

setup(
    name="medicine-cabinet",
    version="0.1.0",
    author="Todd Hendricks",
    author_email="",
    description="Portable AI agent memory system with Tablets and Capsules",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/hendrixx-cnc/medicine-cabinet",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=[],
    entry_points={
        "console_scripts": [
            "medicine-cabinet=cli:main",
        ],
    },
)
