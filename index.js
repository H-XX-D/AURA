'use strict';

const crypto = require('node:crypto');
const zlib = require('node:zlib');

const AIWIRE_PROTOCOL = 'aura.aiwire';
const AIWIRE_VERSION = 1;
const AIWIRE_BLOB_DESCRIPTOR_SCHEMA = 'aura.aiwire.blob_descriptor.v1';

const AIWIRE_LANES = Object.freeze({
  semantic: 'semantic',
  control: 'control',
  blobDescriptor: 'blob_descriptor',
});

const CompressionMethod = Object.freeze({
  BINARY_SEMANTIC: 1,
  BRIO: 2,
  AIWIRE_DEFLATE: 3,
  UNCOMPRESSED: 255,
});

function isPlainObject(value) {
  if (value === null || typeof value !== 'object') {
    return false;
  }
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function normalizeForJson(value) {
  if (value === null || typeof value === 'string' || typeof value === 'boolean') {
    return value;
  }
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) {
      throw new TypeError('canonical JSON does not support non-finite numbers');
    }
    return value;
  }
  if (Array.isArray(value)) {
    return value.map(normalizeForJson);
  }
  if (value instanceof Date) {
    return value.toJSON();
  }
  if (isPlainObject(value)) {
    const output = {};
    for (const key of Object.keys(value).sort()) {
      const field = value[key];
      if (field === undefined || typeof field === 'function' || typeof field === 'symbol') {
        continue;
      }
      output[key] = normalizeForJson(field);
    }
    return output;
  }
  throw new TypeError(`unsupported canonical JSON value: ${Object.prototype.toString.call(value)}`);
}

function canonicalJson(value) {
  return JSON.stringify(normalizeForJson(value));
}

function toBuffer(input) {
  if (Buffer.isBuffer(input)) {
    return Buffer.from(input);
  }
  if (input instanceof Uint8Array) {
    return Buffer.from(input.buffer, input.byteOffset, input.byteLength);
  }
  if (input instanceof ArrayBuffer) {
    return Buffer.from(input);
  }
  return null;
}

function encodeAIWireMessage(message) {
  const rawBuffer = toBuffer(message);
  if (rawBuffer) {
    return rawBuffer;
  }
  if (typeof message === 'string') {
    return Buffer.from(message, 'utf8');
  }
  if (message && typeof message === 'object') {
    return Buffer.from(canonicalJson(message), 'utf8');
  }
  throw new TypeError(`unsupported AIWire message type: ${typeof message}`);
}

function decodeAIWireMessage(payload) {
  const rawBuffer = toBuffer(payload);
  const text = rawBuffer ? rawBuffer.toString('utf8') : String(payload);
  return JSON.parse(text);
}

function digestBytes(bytes, algorithm = 'sha256') {
  const raw = encodeAIWireMessage(bytes);
  return {
    algorithm,
    value: crypto.createHash(algorithm).update(raw).digest('hex'),
  };
}

function normalizeDigest(digest, bytes) {
  if (!digest && bytes !== undefined) {
    return digestBytes(bytes);
  }
  if (typeof digest === 'string') {
    return { algorithm: 'sha256', value: digest };
  }
  if (digest && typeof digest === 'object' && digest.algorithm && digest.value) {
    return { algorithm: String(digest.algorithm), value: String(digest.value) };
  }
  throw new TypeError('blob descriptor requires a digest or bytes to hash');
}

function pick(options, snakeName, camelName) {
  if (Object.prototype.hasOwnProperty.call(options, snakeName)) {
    return options[snakeName];
  }
  return options[camelName];
}

function createBlobDescriptor(options = {}) {
  const bytes = options.bytes;
  const rawBytes = bytes === undefined ? null : encodeAIWireMessage(bytes);
  const blobId = pick(options, 'blob_id', 'blobId');
  const contentType = pick(options, 'content_type', 'contentType');
  const byteLength = pick(options, 'byte_length', 'byteLength') ?? rawBytes?.length;

  if (!blobId) {
    throw new TypeError('blob descriptor requires blob_id or blobId');
  }
  if (!contentType) {
    throw new TypeError('blob descriptor requires content_type or contentType');
  }
  if (!Number.isSafeInteger(byteLength) || byteLength < 0) {
    throw new TypeError('blob descriptor requires a non-negative integer byte_length');
  }

  const descriptor = {
    schema: AIWIRE_BLOB_DESCRIPTOR_SCHEMA,
    protocol: AIWIRE_PROTOCOL,
    lane: AIWIRE_LANES.blobDescriptor,
    blob_id: String(blobId),
    content_type: String(contentType),
    byte_length: byteLength,
    digest: normalizeDigest(options.digest, rawBytes),
    status: options.status ? String(options.status) : 'pending',
  };

  const optionalFields = [
    ['session_id', 'sessionId'],
    ['semantic_role', 'semanticRole'],
    ['chunk', 'chunk'],
    ['route', 'route'],
    ['encryption', 'encryption'],
    ['compression', 'compression'],
    ['dependencies', 'dependencies'],
    ['ttl_ms', 'ttlMs'],
    ['metadata', 'metadata'],
  ];

  for (const [snakeName, camelName] of optionalFields) {
    const value = pick(options, snakeName, camelName);
    if (value !== undefined) {
      descriptor[snakeName] = value;
    }
  }

  return descriptor;
}

function validateBlobDescriptor(descriptor) {
  const errors = [];
  if (!descriptor || typeof descriptor !== 'object') {
    return { ok: false, errors: ['descriptor must be an object'] };
  }
  if (descriptor.schema !== AIWIRE_BLOB_DESCRIPTOR_SCHEMA) {
    errors.push(`schema must be ${AIWIRE_BLOB_DESCRIPTOR_SCHEMA}`);
  }
  if (descriptor.protocol !== AIWIRE_PROTOCOL) {
    errors.push(`protocol must be ${AIWIRE_PROTOCOL}`);
  }
  if (descriptor.lane !== AIWIRE_LANES.blobDescriptor) {
    errors.push(`lane must be ${AIWIRE_LANES.blobDescriptor}`);
  }
  if (!descriptor.blob_id || typeof descriptor.blob_id !== 'string') {
    errors.push('blob_id must be a non-empty string');
  }
  if (!descriptor.content_type || typeof descriptor.content_type !== 'string') {
    errors.push('content_type must be a non-empty string');
  }
  if (!Number.isSafeInteger(descriptor.byte_length) || descriptor.byte_length < 0) {
    errors.push('byte_length must be a non-negative integer');
  }
  if (
    !descriptor.digest ||
    typeof descriptor.digest !== 'object' ||
    !descriptor.digest.algorithm ||
    !descriptor.digest.value
  ) {
    errors.push('digest must contain algorithm and value');
  }
  const validStatuses = new Set([
    'pending',
    'available',
    'in_flight',
    'complete',
    'failed',
    'cancelled',
  ]);
  if (!validStatuses.has(descriptor.status)) {
    errors.push('status must be pending, available, in_flight, complete, failed, or cancelled');
  }
  return { ok: errors.length === 0, errors };
}

class AuraCompression {
  constructor(options = {}) {
    this.level = options.level ?? 3;
    this.threshold = options.threshold ?? 1.01;
  }

  compress(message) {
    const raw = encodeAIWireMessage(message);
    const compressedPayload = zlib.deflateRawSync(raw, { level: this.level });
    const compressed = Buffer.concat([
      Buffer.from([CompressionMethod.AIWIRE_DEFLATE]),
      compressedPayload,
    ]);
    const uncompressed = Buffer.concat([Buffer.from([CompressionMethod.UNCOMPRESSED]), raw]);
    const selected = raw.length / compressed.length >= this.threshold ? compressed : uncompressed;
    const method = selected === compressed ? CompressionMethod.AIWIRE_DEFLATE : CompressionMethod.UNCOMPRESSED;

    return {
      data: selected,
      method,
      originalSize: raw.length,
      original_size: raw.length,
      compressedSize: selected.length,
      compressed_size: selected.length,
      ratio: raw.length === 0 ? 1 : raw.length / selected.length,
    };
  }

  decompressToBuffer(frame) {
    const data = encodeAIWireMessage(frame);
    if (data.length === 0) {
      throw new TypeError('cannot decompress an empty frame');
    }
    const method = data[0];
    const payload = data.subarray(1);
    if (method === CompressionMethod.UNCOMPRESSED) {
      return Buffer.from(payload);
    }
    if (method === CompressionMethod.AIWIRE_DEFLATE) {
      return zlib.inflateRawSync(payload);
    }
    throw new TypeError(`unsupported compression method: ${method}`);
  }

  decompress(frame) {
    return this.decompressToBuffer(frame).toString('utf8');
  }

  decompressMessage(frame) {
    return decodeAIWireMessage(this.decompressToBuffer(frame));
  }
}

class AIWireSessionEncoder {
  constructor(options = {}) {
    this.compressor = new AuraCompression(options);
    this.frames = 0;
    this.bytesIn = 0;
    this.bytesOut = 0;
  }

  compressMessage(message) {
    const raw = encodeAIWireMessage(message);
    const result = this.compressor.compress(raw);
    this.frames += 1;
    this.bytesIn += raw.length;
    this.bytesOut += result.data.length;
    return result.data;
  }

  getStats() {
    return {
      frames: this.frames,
      bytesIn: this.bytesIn,
      bytesOut: this.bytesOut,
      ratio: this.bytesOut === 0 ? 1 : this.bytesIn / this.bytesOut,
    };
  }
}

class AIWireSessionDecoder {
  constructor(options = {}) {
    this.compressor = new AuraCompression(options);
  }

  decompressMessage(frame) {
    return this.compressor.decompressMessage(frame);
  }
}

module.exports = AuraCompression;
Object.assign(module.exports, {
  AuraCompression,
  AIWireSessionEncoder,
  AIWireSessionDecoder,
  CompressionMethod,
  AIWIRE_PROTOCOL,
  AIWIRE_VERSION,
  AIWIRE_BLOB_DESCRIPTOR_SCHEMA,
  AIWIRE_LANES,
  canonicalJson,
  encodeAIWireMessage,
  decodeAIWireMessage,
  digestBytes,
  createBlobDescriptor,
  validateBlobDescriptor,
});
