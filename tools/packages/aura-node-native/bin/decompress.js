#!/usr/bin/env node

/**
 * AURA Compression CLI - Decompress Command
 */

const fs = require('fs');
const path = require('path');
const { AuraCompressor } = require('../index.js');

function printUsage() {
  console.log(`
AURA Compression CLI - Decompress Command

Usage:
    aura-decompress [options] [input_file]

Options:
    -o, --output FILE    Output file (default: stdout)
    -f, --force          Overwrite output file if it exists
    -v, --verbose        Verbose output
    -h, --help           Show this help message

Examples:
    # Decompress a file
    aura-decompress data.compressed -o data.txt

    # Decompress from stdin to stdout
    cat data.compressed | aura-decompress

    # Decompress with verbose output
    aura-decompress -v data.compressed
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

  // Create compressor
  const compressor = new AuraCompressor();

  // Read input
  let inputData;
  if (inputFile) {
    try {
      inputData = fs.readFileSync(inputFile);
    } catch (error) {
      console.error(`Error reading file ${inputFile}: ${error.message}`);
      process.exit(1);
    }
  } else {
    // Read from stdin
    inputData = fs.readFileSync(0);
  }

  if (verbose) {
    console.error(`Input size: ${inputData.length} bytes`);
  }

  // Decompress
  try {
    const result = compressor.decompress(inputData);

    if (verbose) {
      console.error(`Decompressed size: ${result.originalSize} characters`);
      console.error(`Compression ratio: ${result.ratio.toFixed(2)}:1`);
      console.error(`Method: ${result.method}`);
    }

    // Write output
    const outputText = result.plaintext;
    if (outputFile) {
      if (!force && fs.existsSync(outputFile)) {
        console.error(`Error: Output file ${outputFile} exists. Use -f to overwrite.`);
        process.exit(1);
      }
      fs.writeFileSync(outputFile, outputText, 'utf8');
    } else {
      process.stdout.write(outputText);
    }

  } catch (error) {
    console.error(`Error decompressing: ${error.message}`);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}