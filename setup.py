"""
AURA Compression - AI-Optimized Hybrid Compression Protocol
"""

from setuptools import setup, find_packages
import os

# Read README for long description
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read requirements
with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="aura-compression",
    version="1.0.0",
    author="Todd Hendricks",
    author_email="todd@auraprotocol.org",
    description="AI-Optimized Hybrid Compression Protocol for Real-Time Communication",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/hendrixx-cnc/AURA",
    project_urls={
        "Bug Tracker": "https://github.com/hendrixx-cnc/AURA/issues",
        "Documentation": "https://github.com/hendrixx-cnc/AURA/blob/main/docs/technical/DEVELOPER_GUIDE.md",
        "Source Code": "https://github.com/hendrixx-cnc/AURA",
    },
    package_dir={"": "src/python"},
    packages=find_packages(where="src/python", exclude=["tests", "archive", "docs", "examples"]),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Archiving :: Compression",
        "Topic :: Communications",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "flake8>=5.0.0",
            "mypy>=0.990",
        ],
        "websocket": [
            "websockets>=10.0",
        ],
    },
    keywords=[
        "compression",
        "ai",
        "chat",
        "websocket",
        "brotli",
        "semantic-compression",
        "template-compression",
        "bandwidth-optimization",
        "gdpr",
        "hipaa",
        "compliance",
    ],
    entry_points={
        "console_scripts": [
            "aura-compress=aura_compression.cli:compress_cli",
            "aura-decompress=aura_compression.cli:decompress_cli",
            "aura-server=aura_compression.server:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
