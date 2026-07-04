#!/usr/bin/env python3
"""
AURA Compression - AI-Optimized Hybrid Compression Protocol

A comprehensive compression framework that combines multiple compression techniques
with AI-driven optimization for real-time communication and data storage.
"""

import os
import sys
from setuptools import setup, find_packages
from setuptools.command.build_ext import build_ext
import subprocess

# Read version from version file
def read_version():
    version_file = os.path.join(os.path.dirname(__file__), 'aura_compression', '__version__.py')
    if os.path.exists(version_file):
        with open(version_file, 'r') as f:
            exec(f.read())
            return locals()['__version__']
    return '2.0.0'

# Read README
def read_readme():
    readme_file = os.path.join(os.path.dirname(__file__), 'readme.md')
    if os.path.exists(readme_file):
        with open(readme_file, 'r', encoding='utf-8') as f:
            return f.read()
    return ''

# Read requirements
def read_requirements(filename):
    requirements = []
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    requirements.append(line)
    return requirements

class BuildExt(build_ext):
    """Custom build_ext command to handle Rust extensions."""

    def run(self):
        # Build Rust extensions if available
        rust_dir = os.path.join(os.path.dirname(__file__), 'src', 'rust')
        if os.path.exists(rust_dir):
            try:
                subprocess.check_call(['cargo', 'build', '--release'], cwd=rust_dir)
            except (subprocess.CalledProcessError, FileNotFoundError):
                print("Warning: Rust build failed or cargo not available. Skipping Rust extensions.")

        # Call parent build_ext
        build_ext.run(self)

# Package metadata
VERSION = read_version()
LONG_DESCRIPTION = read_readme()
LONG_DESCRIPTION_CONTENT_TYPE = 'text/markdown'

# Core dependencies
INSTALL_REQUIRES = read_requirements('requirements.txt')

# Development dependencies
EXTRAS_REQUIRE = {
    'dev': read_requirements('requirements-dev.txt') if os.path.exists('requirements-dev.txt') else [
        'pytest>=7.0.0',
        'pytest-cov>=4.0.0',
        'black>=23.0.0',
        'isort>=5.12.0',
        'mypy>=1.0.0',
        'flake8>=6.0.0',
        'sphinx>=5.0.0',
        'sphinx-rtd-theme>=1.2.0',
    ],
    'benchmark': [
        'numpy>=1.24.0',
        'pandas>=2.0.0',
        'matplotlib>=3.7.0',
        'seaborn>=0.12.0',
        'psutil>=5.9.0',
    ],
    'server': [
        'fastapi>=0.100.0',
        'uvicorn>=0.23.0',
        'websockets>=11.0.0',
        'pydantic>=2.0.0',
    ],
    'all': [],  # Will be populated below
}

# Add all extras to 'all'
for extra_deps in EXTRAS_REQUIRE.values():
    EXTRAS_REQUIRE['all'].extend(extra_deps)
EXTRAS_REQUIRE['all'] = list(set(EXTRAS_REQUIRE['all']))  # Remove duplicates

setup(
    name='aura-compression',
    version=VERSION,
    description='AI-Optimized Hybrid Compression Protocol for Real-Time Communication',
    long_description=LONG_DESCRIPTION,
    long_description_content_type=LONG_DESCRIPTION_CONTENT_TYPE,
    author='Todd Hendricks',
    author_email='todd@auraprotocol.org',
    url='https://github.com/H-XX-D/AURA',
    project_urls={
        'Documentation': 'https://github.com/H-XX-D/AURA#readme',
        'Source': 'https://github.com/H-XX-D/AURA',
        'Tracker': 'https://github.com/H-XX-D/AURA/issues',
        'Funding': 'https://opencollective.com/aura-compression',
    },
    license='Apache-2.0',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
    'Programming Language :: Python :: 3.13',
        'Programming Language :: Rust',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Communications',
        'Topic :: Security :: Cryptography',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Archiving :: Compression',
        'Topic :: Utilities',
    ],
    keywords=[
        'compression',
        'ai',
        'machine-learning',
        'real-time',
        'websocket',
        'bandwidth-optimization',
        'data-compression',
        'hybrid-compression',
        'semantic-compression',
        'template-compression',
        'gdpr',
        'hipaa',
        'compliance',
        'energy-efficient',
        'sustainable-computing',
    ],
    packages=find_packages(where="src", exclude=['tests', 'tests.*', 'docs', 'tools', 'benchmarks']),
    include_package_data=True,
    package_data={
        'aura_compression': [
            'templates/*.json',
            'config/*.json',
            'data/*',
        ],
    },
    python_requires='>=3.10',
    install_requires=INSTALL_REQUIRES,
    extras_require=EXTRAS_REQUIRE,
    cmdclass={
        'build_ext': BuildExt,
    },
    zip_safe=False,
    test_suite='tests',
    tests_require=EXTRAS_REQUIRE['dev'],
)
