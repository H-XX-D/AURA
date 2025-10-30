/**
 * AURA Compression - Node.js SDK
 * AI-Optimized Hybrid Compression Protocol
 *
 * Copyright (c) 2025 Todd James Hendricks
 * Licensed under Apache License 2.0
 * Patent Pending - Application No. 19/366,538
 */

import { createRequire } from 'module';
import { join } from 'path';

const require = createRequire(import.meta.url);
const native = require('node-gyp-build')(join(__dirname, '..'));

export enum CompressionMethod {
  BINARY_SEMANTIC = 0x00,
  AURALITE = 0x01,
  BRIO = 0x02,
  AURA_LITE = 0x03,
  UNCOMPRESSED = 0xFF
}

export interface CompressionResult {
  payload: Buffer;
  method: CompressionMethod;
  metadata: CompressionMetadata;
}

export interface DecompressionResult {
  text: string;
  metadata: DecompressionMetadata;
}

export interface CompressionMetadata {
  originalSize: number;
  compressedSize: number;
  ratio: number;
  method: string;
  templateIds?: number[];
  timestamp: number;
}

export interface DecompressionMetadata {
  method: string;
  templateIds?: number[];
}

export interface CompressorOptions {
  enableAura?: boolean;
  templateStorePath?: string;
  enableAuditLogging?: boolean;
  sessionId?: string;
  userId?: string;
  auraPreferenceMargin?: number;
}

export interface ClientSDKOptions {
  templateStorePath?: string;
  extraTemplates?: Record<number, string>;
}

export class Compressor {
  private _handle: any;

  constructor(options: CompressorOptions = {}) {
    this._handle = new native.Compressor({
      enableAura: options.enableAura ?? true,
      templateStorePath: options.templateStorePath,
      enableAuditLogging: options.enableAuditLogging ?? false,
      sessionId: options.sessionId,
      userId: options.userId,
      auraPreferenceMargin: options.auraPreferenceMargin ?? 0.1
    });
  }

  compress(text: string, templateId?: number, slots?: string[]): CompressionResult {
    const result = this._handle.compress(text, templateId, slots);
    return {
      payload: result.payload,
      method: result.method,
      metadata: {
        originalSize: result.metadata.original_size,
        compressedSize: result.metadata.compressed_size,
        ratio: result.metadata.ratio,
        method: result.metadata.method,
        templateIds: result.metadata.template_ids,
        timestamp: Date.now()
      }
    };
  }

  decompress(payload: Buffer): string {
    return this._handle.decompress(payload);
  }

  extractMetadata(payload: Buffer): DecompressionMetadata {
    const meta = this._handle.extractMetadata(payload);
    return {
      method: meta.method,
      templateIds: meta.template_ids
    };
  }

  registerTemplate(templateId: number, pattern: string): void {
    this._handle.registerTemplate(templateId, pattern);
  }

  listTemplates(): Record<number, string> {
    return this._handle.listTemplates();
  }
}

export class ClientSDK {
  private _handle: any;

  constructor(options: ClientSDKOptions = {}) {
    this._handle = new native.ClientSDK({
      templateStorePath: options.templateStorePath,
      extraTemplates: options.extraTemplates
    });
  }

  decodePayload(payload: Buffer, returnMetadata = false): string | { text: string; metadata: DecompressionMetadata } {
    const result = this._handle.decodePayload(payload, returnMetadata);

    if (returnMetadata) {
      return {
        text: result.text,
        metadata: {
          method: result.metadata.method,
          templateIds: result.metadata.template_ids
        }
      };
    }

    return result.text;
  }

  compress(text: string, templateId?: number, slots?: string[]): CompressionResult {
    const result = this._handle.compress(text, templateId, slots);
    return {
      payload: result.payload,
      method: result.method,
      metadata: {
        originalSize: result.metadata.original_size,
        compressedSize: result.metadata.compressed_size,
        ratio: result.metadata.ratio,
        method: result.metadata.method,
        templateIds: result.metadata.template_ids,
        timestamp: Date.now()
      }
    };
  }

  registerTemplate(templateId: number, pattern: string): void {
    this._handle.registerTemplate(templateId, pattern);
  }

  listTemplates(): Record<number, string> {
    return this._handle.listTemplates();
  }
}

export class ServerSDK extends Compressor {
  constructor(options: CompressorOptions = {}) {
    super({
      ...options,
      enableAura: options.enableAura ?? true,
      enableAuditLogging: options.enableAuditLogging ?? true
    });
  }

  classifyIntent(payload: Buffer): string {
    return this._handle.classifyIntent(payload);
  }

  screenFastPath(payload: Buffer): boolean {
    return this._handle.screenFastPath(payload);
  }
}

export default {
  Compressor,
  ClientSDK,
  ServerSDK,
  CompressionMethod
};
