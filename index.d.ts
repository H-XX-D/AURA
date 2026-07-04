export const AIWIRE_PROTOCOL: 'aura.aiwire';
export const AIWIRE_VERSION: 1;
export const AIWIRE_BLOB_DESCRIPTOR_SCHEMA: 'aura.aiwire.blob_descriptor.v1';

export const AIWIRE_LANES: Readonly<{
  semantic: 'semantic';
  control: 'control';
  blobDescriptor: 'blob_descriptor';
}>;

export enum CompressionMethod {
  BINARY_SEMANTIC = 1,
  BRIO = 2,
  AIWIRE_DEFLATE = 3,
  UNCOMPRESSED = 255,
}

export type AIWireFrame =
  | Uint8Array
  | ArrayBuffer
  | string
  | Record<string, unknown>
  | unknown[];

export interface CompressionResult {
  data: Uint8Array;
  method: CompressionMethod;
  originalSize: number;
  original_size: number;
  compressedSize: number;
  compressed_size: number;
  ratio: number;
}

export interface AuraCompressionOptions {
  level?: number;
  threshold?: number;
}

export interface Digest {
  algorithm: string;
  value: string;
}

export interface BlobDescriptor {
  schema: typeof AIWIRE_BLOB_DESCRIPTOR_SCHEMA;
  protocol: typeof AIWIRE_PROTOCOL;
  lane: 'blob_descriptor';
  blob_id: string;
  session_id?: string;
  semantic_role?: string;
  content_type: string;
  byte_length: number;
  digest: Digest;
  chunk?: Record<string, unknown>;
  route?: Record<string, unknown>;
  status: 'pending' | 'available' | 'in_flight' | 'complete' | 'failed' | 'cancelled';
  encryption?: Record<string, unknown>;
  compression?: string | Record<string, unknown>;
  dependencies?: unknown[];
  ttl_ms?: number;
  metadata?: Record<string, unknown>;
}

export interface BlobDescriptorOptions {
  blob_id?: string;
  blobId?: string;
  session_id?: string;
  sessionId?: string;
  semantic_role?: string;
  semanticRole?: string;
  content_type?: string;
  contentType?: string;
  byte_length?: number;
  byteLength?: number;
  digest?: string | Digest;
  bytes?: AIWireFrame;
  chunk?: Record<string, unknown>;
  route?: Record<string, unknown>;
  status?: BlobDescriptor['status'];
  encryption?: Record<string, unknown>;
  compression?: string | Record<string, unknown>;
  dependencies?: unknown[];
  ttl_ms?: number;
  ttlMs?: number;
  metadata?: Record<string, unknown>;
}

export class AuraCompression {
  constructor(options?: AuraCompressionOptions);
  compress(message: AIWireFrame): CompressionResult;
  decompressToBuffer(frame: AIWireFrame): Uint8Array;
  decompress(frame: AIWireFrame): string;
  decompressMessage(frame: AIWireFrame): unknown;
}

export class AIWireSessionEncoder {
  constructor(options?: AuraCompressionOptions);
  compressMessage(message: AIWireFrame): Uint8Array;
  getStats(): { frames: number; bytesIn: number; bytesOut: number; ratio: number };
}

export class AIWireSessionDecoder {
  constructor(options?: AuraCompressionOptions);
  decompressMessage(frame: AIWireFrame): unknown;
}

export function canonicalJson(value: unknown): string;
export function encodeAIWireMessage(message: AIWireFrame): Uint8Array;
export function decodeAIWireMessage(payload: AIWireFrame): unknown;
export function digestBytes(bytes: AIWireFrame, algorithm?: string): Digest;
export function createBlobDescriptor(options: BlobDescriptorOptions): BlobDescriptor;
export function validateBlobDescriptor(
  descriptor: unknown
): { ok: boolean; errors: string[] };

export default AuraCompression;
