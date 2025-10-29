#!/usr/bin/env python3
"""
AURA Compression CLI - Decompress Command

Usage:
    aura-decompress [options] [input_file]

Options:
    -o, --output FILE    Output file (default: stdout)
    -f, --force          Overwrite output file if it exists
    -v, --verbose        Verbose output
    -h, --help           Show this help message
"""

import argparse
import sys
import os
from pathlib import Path

# Add the parent directory to the path so we can import aura_compression
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from aura_compression import ProductionHybridCompressor


def main():
    """Main entry point for aura-decompress CLI."""
    parser = argparse.ArgumentParser(
        description="Decompress data using AURA compression",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        'input_file',
        nargs='?',
        help='Input file to decompress (default: stdin)'
    )

    parser.add_argument(
        '-o', '--output',
        help='Output file (default: stdout)'
    )

    parser.add_argument(
        '-f', '--force',
        action='store_true',
        help='Overwrite output file if it exists'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    args = parser.parse_args()

    # Determine input source
    if args.input_file:
        if not os.path.exists(args.input_file):
            print(f"Error: Input file '{args.input_file}' does not exist", file=sys.stderr)
            sys.exit(1)
        with open(args.input_file, 'rb') as f:
            input_data = f.read()
    else:
        input_data = sys.stdin.buffer.read()

    if not input_data:
        print("Error: No input data provided", file=sys.stderr)
        sys.exit(1)

    # Determine output destination
    if args.output:
        output_path = Path(args.output)
        if output_path.exists() and not args.force:
            print(f"Error: Output file '{args.output}' exists. Use -f to overwrite.", file=sys.stderr)
            sys.exit(1)
        output_file = open(args.output, 'wb')
    else:
        output_file = sys.stdout.buffer

    try:
        # Initialize compressor
        compressor = ProductionHybridCompressor(enable_aura=True)

        # Decompress data
        decompressed_data = compressor.decompress(input_data)

        # Write decompressed data
        output_file.write(decompressed_data)

        if args.verbose:
            print(f"Decompressed {len(input_data)} bytes -> {len(decompressed_data)} bytes", file=sys.stderr)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if args.output:
            output_file.close()


if __name__ == '__main__':
    main()