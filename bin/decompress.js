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
    process.stdout.write('Usage: aura-decompress [frame.bin|-] > payload.txt\n');
    return;
  }
  const input = readInput(args[0]);
  const compressor = new AuraCompression();
  process.stdout.write(compressor.decompressToBuffer(input));
}

main();
