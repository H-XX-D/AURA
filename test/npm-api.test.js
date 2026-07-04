'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const AuraCompression = require('../index.js');

test('canonical AIWire message encoding sorts object keys', () => {
  const encoded = AuraCompression.encodeAIWireMessage({ z: 1, a: { b: true, a: 'x' } });
  assert.equal(encoded.toString('utf8'), '{"a":{"a":"x","b":true},"z":1}');
  assert.deepEqual(AuraCompression.decodeAIWireMessage(encoded), {
    a: { a: 'x', b: true },
    z: 1,
  });
});

test('AuraCompression round trips structured messages', () => {
  const compressor = new AuraCompression({ threshold: 0 });
  const frame = compressor.compress({
    protocol: 'mcp',
    jsonrpc: '2.0',
    id: 7,
    method: 'tools/call',
    params: { name: 'read_file', arguments: { uri: 'repo://service/path.py' } },
  });

  assert.equal(frame.method, AuraCompression.CompressionMethod.AIWIRE_DEFLATE);
  assert.deepEqual(compressor.decompressMessage(frame.data), {
    id: 7,
    jsonrpc: '2.0',
    method: 'tools/call',
    params: { arguments: { uri: 'repo://service/path.py' }, name: 'read_file' },
    protocol: 'mcp',
  });
});

test('AIWire encoder and decoder expose message-oriented helpers', () => {
  const encoder = new AuraCompression.AIWireSessionEncoder({ threshold: 0 });
  const decoder = new AuraCompression.AIWireSessionDecoder();
  const frame = encoder.compressMessage({ protocol: 'a2a', taskId: 'task-1', status: 'working' });

  assert.deepEqual(decoder.decompressMessage(frame), {
    protocol: 'a2a',
    status: 'working',
    taskId: 'task-1',
  });
  assert.equal(encoder.getStats().frames, 1);
});

test('blob descriptors include digest, lane, and schema metadata', () => {
  const descriptor = AuraCompression.createBlobDescriptor({
    blobId: 'blob-1',
    semanticRole: 'image',
    contentType: 'image/png',
    bytes: Buffer.from('payload'),
    route: { destination: 'edge-worker', priority: 3 },
    status: 'available',
  });

  assert.equal(descriptor.schema, AuraCompression.AIWIRE_BLOB_DESCRIPTOR_SCHEMA);
  assert.equal(descriptor.lane, AuraCompression.AIWIRE_LANES.blobDescriptor);
  assert.equal(descriptor.byte_length, 7);
  assert.equal(descriptor.digest.algorithm, 'sha256');
  assert.equal(AuraCompression.validateBlobDescriptor(descriptor).ok, true);
});
