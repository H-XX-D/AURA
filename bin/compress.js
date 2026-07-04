#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const AuraCompression = require('../index.js');

function readInput(path) {
  if (!path || path === '-') {
    return fs.readFileSync(0);
  }
  return fs.readFileSync(path);
}

function main() {
  const args = process.argv.slice(2);
  if (args.includes('--help') || args.includes('-h')) {
    process.stdout.write('Usage: aura-compress [file|-] > frame.bin\n');
    return;
  }
  const input = readInput(args[0]);
  const compressor = new AuraCompression();
  const result = compressor.compress(input);
  process.stdout.write(result.data);
}

main();
