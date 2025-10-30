#!/usr/bin/env node

/**
 * AURA Compression CLI - Compress Command
 */

const fs = require('fs');
const path = require('path');
const { AuraCompressor } = require('../index.js');

function printUsage() {
  console.log(`
AURA Compression CLI - Compress Command

Usage:
    aura-compress [options] [input_file]

Options:
    -o, --output FILE    Output file (default: stdout)
    -f, --force          Overwrite output file if it exists
    -v, --verbose        Verbose output
    -h, --help           Show this help message

Examples:
    # Compress a file
    aura-compress data.txt -o data.compressed

    # Compress from stdin to stdout
    echo "Hello World" | aura-compress

    # Compress with verbose output
    aura-compress -v data.txt
`);
}

function main() {
  const args = process.argv.slice(2);
  let outputFile = null;
  let force = false;
  let verbose = false;
  let inputFile = null;

  // Parse arguments
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];

    switch (arg) {
      case '-h':
      case '--help':
        printUsage();
        process.exit(0);
        break;

      case '-o':
      case '--output':
        if (i + 1 >= args.length) {
          console.error('Error: -o/--output requires a filename');
          process.exit(1);
        }
        outputFile = args[i + 1];
        i++;
        break;

      case '-f':
      case '--force':
        force = true;
        break;

      case '-v':
      case '--verbose':
        verbose = true;
        break;

      default:
        if (arg.startsWith('-')) {
          console.error(`Error: Unknown option: ${arg}`);
          printUsage();
          process.exit(1);
        }
        if (inputFile) {
          console.error('Error: Multiple input files specified');
          process.exit(1);
        }
        inputFile = arg;
        break;
    }
  }

  // Create compressor with aggressive settings
  const compressor = AuraCompressor.withConfig(1.01, 10);

  if (verbose) {
    console.error(`Binary threshold: ${compressor.binaryAdvantageThreshold}`);
    console.error(`Min compression size: ${compressor.minCompressionSize}`);
  }

  // Read input
  let inputText;
  if (inputFile) {
    try {
      inputText = fs.readFileSync(inputFile, 'utf8');
    } catch (error) {
      console.error(`Error reading file ${inputFile}: ${error.message}`);
      process.exit(1);
    }
  } else {
    // Read from stdin
    inputText = fs.readFileSync(0, 'utf8');
  }

  if (verbose) {
    console.error(`Input size: ${inputText.length} characters`);
  }

  // Compress
  try {
    const result = compressor.compress(inputText);

    if (verbose) {
      console.error(`Compressed size: ${result.compressedSize} bytes`);
      console.error(`Compression ratio: ${result.ratio.toFixed(2)}:1`);
      console.error(`Method: ${result.method}`);
    }

    // Write output
    if (outputFile) {
      if (!force && fs.existsSync(outputFile)) {
        console.error(`Error: Output file ${outputFile} exists. Use -f to overwrite.`);
        process.exit(1);
      }
      fs.writeFileSync(outputFile, result.data);
    } else {
      process.stdout.write(result.data);
    }

  } catch (error) {
    console.error(`Error compressing: ${error.message}`);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}