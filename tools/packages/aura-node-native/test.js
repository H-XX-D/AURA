/**
 * AURA Native - Jest Tests
 *
 * Tests basic functionality of the native bindings
 */

const { AuraCompressor } = require('./index.js');

describe('AURA Native Node.js Bindings', () => {
  let compressor;

  beforeAll(() => {
    compressor = new AuraCompressor();
  });

  test('Basic Compression', () => {
    const message = "Hello, this is a test message for AURA compression!";
    const result = compressor.compress(message);

    expect(result).toHaveProperty('originalSize');
    expect(result).toHaveProperty('compressedSize');
    expect(result).toHaveProperty('ratio');
    expect(result).toHaveProperty('method');
    expect(result).toHaveProperty('data');

    expect(result.originalSize).toBeGreaterThan(0);
    expect(result.compressedSize).toBeGreaterThan(0);
    expect(result.ratio).toBeGreaterThan(1);
    expect([1, 2]).toContain(result.method); // 1 = Binary Semantic, 2 = Brotli
  });

  test('Round-Trip Compression/Decompression', () => {
    const message = "Hello, this is a test message for AURA compression!";
    const result = compressor.compress(message);
    const decompressed = compressor.decompress(result.data);

    expect(decompressed).toHaveProperty('plaintext');
    expect(decompressed.plaintext).toBe(message);
  });

  test('Template-Based Compression', () => {
    const slots = [
      "real-time weather data",
      "Please check a weather website"
    ];
    const templateResult = compressor.compressWithTemplate(0, slots);
    const templateDecompressed = compressor.decompress(templateResult.data);

    expect(templateResult).toHaveProperty('originalSize');
    expect(templateResult).toHaveProperty('compressedSize');
    expect(templateResult).toHaveProperty('ratio');
    expect(templateResult).toHaveProperty('method');

    expect(templateDecompressed).toHaveProperty('plaintext');
    expect(templateDecompressed).toHaveProperty('templateId');
    expect(templateDecompressed.templateId).toBe(0);
  });

  test('Custom Template', () => {
    compressor.addTemplate({
      id: 200,
      pattern: "Order #{0} has been {1}",
      description: "Order status",
      slots: 2
    });

    const customSlots = ["12345", "shipped"];
    const customResult = compressor.compressWithTemplate(200, customSlots);
    const customDecompressed = compressor.decompress(customResult.data);

    expect(customDecompressed.plaintext).toBe("Order #12345 has been shipped");
  });

  test('Performance Benchmark', () => {
    const iterations = 100;
    const testMessage = "I don't have access to real-time weather information. Please check a weather website or app for current conditions.";

    // Test compression performance
    const startCompress = Date.now();
    for (let i = 0; i < iterations; i++) {
      compressor.compress(testMessage);
    }
    const compressTime = Date.now() - startCompress;

    // Test decompression performance
    const compressed = compressor.compress(testMessage);
    const startDecompress = Date.now();
    for (let i = 0; i < iterations; i++) {
      compressor.decompress(compressed.data);
    }
    const decompressTime = Date.now() - startDecompress;

    // Performance should be reasonable (less than 100ms total for 100 iterations)
    expect(compressTime).toBeLessThan(100);
    expect(decompressTime).toBeLessThan(100);

    // Each operation should be fast (less than 1ms average)
    expect(compressTime / iterations).toBeLessThan(1);
    expect(decompressTime / iterations).toBeLessThan(1);
  });
});
