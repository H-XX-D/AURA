/**
 * AURA Hybrid Client-Side Compression/Decompression
 *
 * Proprietary client library for large file uploads with compression.
 * Zero npm dependencies - uses native browser APIs.
 *
 * Features:
 * - Intelligent compression: AURA for chat, zlib for files
 * - Client-side compression before upload (saves bandwidth)
 * - Native DecompressionStream API (Chrome 80+, Firefox 113+)
 * - Fallback to pako library for older browsers
 *
 * License: Proprietary - AURA Compression (Patent US 19/366,538 pending)
 */

class AuraHybridClient {
    constructor(options = {}) {
        this.serverUrl = options.serverUrl || 'ws://localhost:8765';
        this.enableClientCompression = options.enableClientCompression !== false;
        this.compressionLevel = options.compressionLevel || 6; // 1-9
        this.fileSizeThreshold = options.fileSizeThreshold || 2048; // 2KB

        this.methods = {
            0x00: 'BINARY_SEMANTIC',
            0x01: 'AURALITE',
            0x02: 'BRIO',
            0x03: 'AURA_LITE',
            0x10: 'ZLIB',
            0x11: 'GZIP',
            0xFF: 'UNCOMPRESSED'
        };

        // Check browser capabilities
        this.hasCompressionStream = typeof CompressionStream !== 'undefined';
        this.hasDecompressionStream = typeof DecompressionStream !== 'undefined';

        if (!this.hasCompressionStream || !this.hasDecompressionStream) {
            console.warn('Native compression not available. Falling back to pako library or server-side compression.');
        }
    }

    /**
     * Compress data before sending (client-side compression for large files)
     */
    async compressFile(data, format = 'deflate') {
        if (!this.enableClientCompression) {
            return { data, compressed: false };
        }

        const bytes = typeof data === 'string' ? new TextEncoder().encode(data) : data;

        // Skip compression for small files
        if (bytes.length < this.fileSizeThreshold) {
            return { data: bytes, compressed: false, originalSize: bytes.length };
        }

        try {
            if (this.hasCompressionStream) {
                const compressed = await this._compressNative(bytes, format);
                const method = format === 'gzip' ? 0x11 : 0x10;

                // Add AURA method header
                const result = new Uint8Array(compressed.length + 1);
                result[0] = method;
                result.set(compressed, 1);

                return {
                    data: result,
                    compressed: true,
                    originalSize: bytes.length,
                    compressedSize: result.length,
                    ratio: bytes.length / result.length,
                    method: this.methods[method]
                };
            } else if (typeof pako !== 'undefined') {
                return this._compressWithPako(bytes, format);
            } else {
                console.warn('No compression available. Sending uncompressed.');
                return { data: bytes, compressed: false };
            }
        } catch (error) {
            console.error('Compression failed:', error);
            return { data: bytes, compressed: false, error: error.message };
        }
    }

    /**
     * Compress using native browser CompressionStream API
     */
    async _compressNative(data, format = 'deflate') {
        const stream = new CompressionStream(format);
        const writer = stream.writable.getWriter();
        writer.write(data);
        writer.close();

        const reader = stream.readable.getReader();
        const chunks = [];

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            chunks.push(value);
        }

        // Combine chunks
        const totalLength = chunks.reduce((acc, chunk) => acc + chunk.length, 0);
        const result = new Uint8Array(totalLength);
        let offset = 0;
        for (const chunk of chunks) {
            result.set(chunk, offset);
            offset += chunk.length;
        }

        return result;
    }

    /**
     * Compress using pako library (fallback for older browsers)
     */
    _compressWithPako(data, format = 'deflate') {
        if (typeof pako === 'undefined') {
            throw new Error('pako library not loaded');
        }

        const compressed = format === 'gzip' ? pako.gzip(data) : pako.deflate(data);
        const method = format === 'gzip' ? 0x11 : 0x10;

        // Add AURA method header
        const result = new Uint8Array(compressed.length + 1);
        result[0] = method;
        result.set(compressed, 1);

        return {
            data: result,
            compressed: true,
            originalSize: data.length,
            compressedSize: result.length,
            ratio: data.length / result.length,
            method: this.methods[method]
        };
    }

    /**
     * Decompress received data
     */
    async decompress(compressedData) {
        const bytes = compressedData instanceof Uint8Array ? compressedData : new Uint8Array(compressedData);

        if (bytes.length === 0) {
            throw new Error('Empty data');
        }

        const methodByte = bytes[0];
        const method = this.methods[methodByte];
        const payload = bytes.slice(1);

        if (!method) {
            throw new Error(`Unknown compression method: 0x${methodByte.toString(16)}`);
        }

        switch (methodByte) {
            case 0x10: // ZLIB (deflate)
                return await this._decompress(payload, 'deflate', method);

            case 0x11: // GZIP
                return await this._decompress(payload, 'gzip', method);

            case 0xFF: // UNCOMPRESSED
                return {
                    data: new TextDecoder().decode(payload),
                    method: 'UNCOMPRESSED',
                    decompressedSize: payload.length
                };

            case 0x00: // BINARY_SEMANTIC
            case 0x01: // AURALITE
            case 0x02: // BRIO
                // BRIO payloads are sanitized (metadata stripped) for client delivery
                // They cannot be decompressed client-side for security reasons
                return {
                    data: null, // Cannot provide decompressed data
                    method: method,
                    sanitized: true,
                    note: 'BRIO payload sanitized for client delivery - requires server-side decompression',
                    compressedSize: bytes.length
                };

            case 0x03: // AURA_LITE
                throw new Error(`${method} requires server-side decompression. Send to /api/decompress endpoint.`);

            default:
                throw new Error(`Unsupported method: ${method}`);
        }
    }

    async _decompress(data, format, methodName) {
        try {
            if (this.hasDecompressionStream) {
                const decompressed = await this._decompressNative(data, format);
                return {
                    data: new TextDecoder().decode(decompressed),
                    method: methodName,
                    decompressedSize: decompressed.length
                };
            } else if (typeof pako !== 'undefined') {
                const decompressed = format === 'gzip' ? pako.ungzip(data) : pako.inflate(data);
                return {
                    data: new TextDecoder().decode(decompressed),
                    method: methodName,
                    decompressedSize: decompressed.length
                };
            } else {
                throw new Error('No decompression support available');
            }
        } catch (error) {
            throw new Error(`Decompression failed: ${error.message}`);
        }
    }

    async _decompressNative(data, format) {
        const stream = new DecompressionStream(format);
        const writer = stream.writable.getWriter();
        writer.write(data);
        writer.close();

        const reader = stream.readable.getReader();
        const chunks = [];

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            chunks.push(value);
        }

        const totalLength = chunks.reduce((acc, chunk) => acc + chunk.length, 0);
        const result = new Uint8Array(totalLength);
        let offset = 0;
        for (const chunk of chunks) {
            result.set(chunk, offset);
            offset += chunk.length;
        }

        return result;
    }

    /**
     * Upload file with automatic compression
     */
    async uploadFile(file, options = {}) {
        const endpoint = options.endpoint || '/api/upload';
        const compressFile = options.compress !== false;

        try {
            // Read file
            const arrayBuffer = await file.arrayBuffer();
            const data = new Uint8Array(arrayBuffer);

            // Compress if enabled
            let uploadData = data;
            let metadata = {
                originalSize: data.length,
                compressed: false
            };

            if (compressFile && this.enableClientCompression) {
                const result = await this.compressFile(data, options.format || 'deflate');
                if (result.compressed) {
                    uploadData = result.data;
                    metadata = {
                        originalSize: result.originalSize,
                        compressedSize: result.compressedSize,
                        ratio: result.ratio,
                        compressed: true,
                        method: result.method
                    };
                    console.log(`File compressed: ${result.originalSize} → ${result.compressedSize} bytes (${result.ratio.toFixed(2)}:1)`);
                }
            }

            // Upload via fetch
            const formData = new FormData();
            formData.append('file', new Blob([uploadData]), file.name);
            formData.append('metadata', JSON.stringify(metadata));

            const response = await fetch(endpoint, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`Upload failed: ${response.statusText}`);
            }

            const result = await response.json();
            return {
                success: true,
                ...result,
                clientCompression: metadata
            };

        } catch (error) {
            console.error('Upload error:', error);
            return {
                success: false,
                error: error.message
            };
        }
    }

    /**
     * Create WebSocket connection with compression support
     */
    createWebSocket(url = this.serverUrl) {
        const ws = new WebSocket(url);
        ws.binaryType = 'arraybuffer';

        // Wrap WebSocket with compression/decompression
        const originalSend = ws.send.bind(ws);
        ws.sendCompressed = async (data) => {
            const result = await this.compressFile(data);
            originalSend(result.data);
            return result;
        };

        ws.addEventListener('message', async (event) => {
            if (event.data instanceof ArrayBuffer) {
                try {
                    const result = await this.decompress(new Uint8Array(event.data));
                    // Handle sanitized BRIO payloads
                    if (result.sanitized) {
                        // Emit custom event for sanitized payload
                        ws.dispatchEvent(new CustomEvent('sanitized', { 
                            detail: {
                                method: result.method,
                                compressedSize: result.compressedSize,
                                note: result.note
                            }
                        }));
                    } else {
                        // Emit custom event with decompressed data
                        ws.dispatchEvent(new CustomEvent('decompressed', { detail: result }));
                    }
                } catch (error) {
                    console.error('Decompression error:', error);
                }
            }
        });

        return ws;
    }

    /**
     * Get browser compression capabilities
     */
    getCapabilities() {
        return {
            nativeCompression: this.hasCompressionStream,
            nativeDecompression: this.hasDecompressionStream,
            pakoAvailable: typeof pako !== 'undefined',
            clientCompressionEnabled: this.enableClientCompression,
            recommendedAction: this.hasCompressionStream
                ? 'Use native browser APIs (optimal)'
                : typeof pako !== 'undefined'
                ? 'Use pako fallback'
                : 'Server-side compression only'
        };
    }
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AuraHybridClient;
}

// Example usage:
/*
// Initialize client
const aura = new AuraHybridClient({
    serverUrl: 'ws://localhost:8765',
    enableClientCompression: true,
    compressionLevel: 6
});

// Check capabilities
console.log(aura.getCapabilities());

// Upload file with compression
const fileInput = document.getElementById('fileInput');
fileInput.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    const result = await aura.uploadFile(file);
    console.log('Upload result:', result);
});

// WebSocket with automatic compression
const ws = aura.createWebSocket();
ws.addEventListener('open', () => {
    ws.sendCompressed('Hello from client with compression!');
});

// Handle decompressed messages
ws.addEventListener('decompressed', (event) => {
    console.log('Received decompressed:', event.detail.data);
});

// Handle sanitized BRIO payloads (cannot be decompressed client-side)
ws.addEventListener('sanitized', (event) => {
    console.log('Received sanitized BRIO payload:', event.detail);
    console.log('Method:', event.detail.method);
    console.log('Compressed size:', event.detail.compressedSize);
    console.log('Note:', event.detail.note);
    // Send to server for decompression if needed
});
*/
