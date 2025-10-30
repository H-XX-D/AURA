#!/usr/bin/env python3
"""
AURA Compression CLI - Compress Command

Usage:
    aura-compress [options] [input_file]

Options:
    -o, --output FILE    Output file (default: stdout)
    -f, --force          Overwrite output file if it exists
    -v, --verbose        Verbose output
    -h, --help           Show this help message
    --method METHOD      Compression method (auto, gzip, aura_lite, uncompressed)
    --level LEVEL        Compression level (1-9, default: auto)
"""

import argparse
import sys
import os
from pathlib import Path

# Add the parent directory to the path so we can import aura_compression
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from aura_compression import ProductionHybridCompressor


def main():
    """Main entry point for aura-compress CLI."""
    parser = argparse.ArgumentParser(
        description="Compress data using AURA compression",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        'input_file',
        nargs='?',
        help='Input file to compress (default: stdin)'
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

    parser.add_argument(
        '--method',
        choices=['auto', 'gzip', 'aura_lite', 'uncompressed'],
        default='auto',
        help='Compression method (default: auto)'
    )

    parser.add_argument(
        '--level',
        type=int,
        choices=range(1, 10),
        default=None,
        help='Compression level (1-9, default: auto)'
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
        enable_aura = args.method in ['auto', 'aura_lite']
        compressor = ProductionHybridCompressor(enable_aura=enable_aura)

        # Compress data
        compressed_data, method, metadata = compressor.compress(input_data)

        # Write compressed data
        output_file.write(compressed_data)

        if args.verbose:
            compression_ratio = len(compressed_data) / len(input_data) if input_data else 0
            print(f"Compressed {len(input_data)} bytes -> {len(compressed_data)} bytes "
                  f"({compression_ratio:.1%}) using {method}", file=sys.stderr)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if args.output:
            output_file.close()


if __name__ == '__main__':
    main()