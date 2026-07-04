#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <new>
#include <string>
#include <vector>

#include <zlib.h>

namespace {

thread_local std::string g_last_error;

constexpr int kWindowBits = -15;
constexpr int kMemLevel = 8;

void set_error(const std::string& message) {
    g_last_error = message;
}

std::vector<unsigned char> build_dictionary() {
    const std::string generic_json =
        "{}[],:"
        "\"protocol\":"
        "\"operation\":"
        "\"tenant\":"
        "\"priority\":"
        "\"repository\":"
        "\"path\":"
        "\"query\":"
        "\"limit\":"
        "\"output\":"
        "\"rows\":"
        "\"timestamp\":"
        "\"level\":"
        "\"message\":";

    const std::vector<std::string> terms = {
        generic_json,
        "\"jsonrpc\":\"2.0\"",
        "\"id\":",
        "\"method\":",
        "\"params\":",
        "\"result\":",
        "\"error\":",
        "\"name\":",
        "\"arguments\":",
        "\"metadata\":",
        "\"trace_id\":",
        "\"task_id\":",
        "\"session_id\":",
        "\"call_id\":",
        "\"tool_call_id\":",
        "\"content\":",
        "\"structuredContent\":",
        "\"isError\":false",
        "\"type\":\"text\"",
        "\"kind\":\"text\"",
        "\"text\":",
        "\"role\":\"user\"",
        "\"role\":\"agent\"",
        "\"role\":\"assistant\"",
        "\"role\":\"system\"",
        "\"parts\":[{\"kind\":\"text\",\"text\":",
        "\"protocol\":\"openai.responses\"",
        "\"operation\":\"responses.create\"",
        "\"model\":",
        "\"input\":",
        "\"tools\":",
        "\"type\":\"function\"",
        "\"type\":\"function_call\"",
        "\"response.output_item.done\"",
        "\"parameters\":",
        "\"properties\":",
        "\"required\":",
        "\"description\":",
        "\"protocol\":\"mcp\"",
        "\"method\":\"tools/call\"",
        "\"uri\":",
        "\"line_start\":",
        "\"line_end\":",
        "\"matches\":",
        "\"file\":",
        "\"line\":",
        "\"score\":",
        "\"protocol\":\"a2a\"",
        "\"method\":\"message/send\"",
        "\"message\":",
        "\"messageId\":",
        "\"contextId\":",
        "\"status\":",
        "\"state\":\"working\"",
        "\"state\":\"completed\"",
        "\"artifacts\":",
        "\"artifactId\":",
        "\"protocol\":\"agent.trace\"",
        "\"protocol\":\"agent.handoff\"",
        "\"protocol\":\"agent.review\"",
        "\"protocol\":\"agent.final\"",
        "\"event\":\"plan.created\"",
        "\"agent\":",
        "\"from\":",
        "\"to\":",
        "\"handoff\":",
        "\"working_memory\":",
        "\"facts\":",
        "\"open_questions\":",
        "\"requested_output_schema\":",
        "\"objective\":",
        "\"constraints\":",
        "\"subgoals\":",
        "\"evidence\":",
        "\"confidence\":",
        "\"verdict\":",
        "\"comments\":",
        "\"severity\":",
        "\"answer\":",
        "\"summary\":",
        "\"actions\":",
        "latency regression",
        "tail latency",
        "retry budget",
        "retry fanout",
        "patch validation",
        "verified evidence",
        "deployment",
        "repository",
        "service",
        "trace",
        "planner",
        "researcher",
        "coder",
        "reviewer",
        "executor",
        "summarizer",
    };

    std::string joined;
    for (std::size_t index = 0; index < terms.size(); ++index) {
        if (index != 0) {
            joined.push_back('\n');
        }
        joined.append(terms[index]);
    }

    std::string repeated;
    repeated.reserve((joined.size() + 1) * 12);
    for (int index = 0; index < 12; ++index) {
        repeated.append(joined);
        repeated.push_back('\n');
    }

    const std::size_t start = repeated.size() > 32768 ? repeated.size() - 32768 : 0;
    return std::vector<unsigned char>(repeated.begin() + static_cast<std::ptrdiff_t>(start), repeated.end());
}

const std::vector<unsigned char>& static_dictionary() {
    static const std::vector<unsigned char> dict = build_dictionary();
    return dict;
}

bool valid_payload(const unsigned char* data, std::size_t size) {
    return size == 0 || data != nullptr;
}

bool valid_zlib_size(std::size_t size) {
    return size <= static_cast<std::size_t>(std::numeric_limits<uInt>::max());
}

std::uint64_t fnv1a64(const std::vector<unsigned char>& data) {
    std::uint64_t value = 14695981039346656037ULL;
    for (const unsigned char byte : data) {
        value ^= static_cast<std::uint64_t>(byte);
        value *= 1099511628211ULL;
    }
    return value;
}

struct Encoder {
    z_stream stream{};
    bool initialized = false;
    std::uint64_t frames = 0;
    std::uint64_t bytes_in = 0;
    std::uint64_t bytes_out = 0;
};

struct Decoder {
    z_stream stream{};
    bool initialized = false;
    std::uint64_t frames = 0;
    std::uint64_t bytes_in = 0;
    std::uint64_t bytes_out = 0;
};

int copy_result(const std::vector<unsigned char>& result, unsigned char** output, std::size_t* output_size) {
    if (output == nullptr || output_size == nullptr) {
        set_error("output pointer is null");
        return -1;
    }

    unsigned char* buffer = nullptr;
    if (!result.empty()) {
        buffer = static_cast<unsigned char*>(std::malloc(result.size()));
        if (buffer == nullptr) {
            set_error("malloc failed");
            return -1;
        }
        std::memcpy(buffer, result.data(), result.size());
    }

    *output = buffer;
    *output_size = result.size();
    return 0;
}

}  // namespace

extern "C" {

const char* aura_aiwire_last_error() {
    return g_last_error.c_str();
}

const char* aura_aiwire_backend_version() {
    return "aura-aiwire-native-cpp/1";
}

std::size_t aura_aiwire_static_dictionary_size() {
    return static_dictionary().size();
}

std::uint64_t aura_aiwire_static_dictionary_checksum() {
    return fnv1a64(static_dictionary());
}

void aura_aiwire_free(void* ptr) {
    std::free(ptr);
}

Encoder* aura_aiwire_encoder_create(int level, int use_static_dictionary) {
    if (level < 0 || level > 9) {
        set_error("zlib level must be in [0, 9]");
        return nullptr;
    }

    Encoder* encoder = new (std::nothrow) Encoder();
    if (encoder == nullptr) {
        set_error("failed to allocate encoder");
        return nullptr;
    }

    const int rc = deflateInit2(
        &encoder->stream,
        level,
        Z_DEFLATED,
        kWindowBits,
        kMemLevel,
        Z_DEFAULT_STRATEGY);
    if (rc != Z_OK) {
        set_error("deflateInit2 failed: " + std::to_string(rc));
        delete encoder;
        return nullptr;
    }
    encoder->initialized = true;

    if (use_static_dictionary) {
        const auto& dict = static_dictionary();
        const int dict_rc = deflateSetDictionary(
            &encoder->stream,
            reinterpret_cast<const Bytef*>(dict.data()),
            static_cast<uInt>(dict.size()));
        if (dict_rc != Z_OK) {
            set_error("deflateSetDictionary failed: " + std::to_string(dict_rc));
            deflateEnd(&encoder->stream);
            delete encoder;
            return nullptr;
        }
    }

    return encoder;
}

void aura_aiwire_encoder_destroy(Encoder* encoder) {
    if (encoder == nullptr) {
        return;
    }
    if (encoder->initialized) {
        deflateEnd(&encoder->stream);
    }
    delete encoder;
}

int aura_aiwire_encoder_compress(
    Encoder* encoder,
    const unsigned char* input,
    std::size_t input_size,
    unsigned char** output,
    std::size_t* output_size) {
    if (encoder == nullptr || !encoder->initialized) {
        set_error("encoder is not initialized");
        return -1;
    }
    if (!valid_payload(input, input_size)) {
        set_error("input pointer is null");
        return -1;
    }
    if (!valid_zlib_size(input_size)) {
        set_error("input frame is too large for one zlib call");
        return -1;
    }

    encoder->stream.next_in = const_cast<Bytef*>(reinterpret_cast<const Bytef*>(input));
    encoder->stream.avail_in = static_cast<uInt>(input_size);

    std::vector<unsigned char> result;
    unsigned char chunk[16384];
    int rc = Z_OK;
    do {
        encoder->stream.next_out = chunk;
        encoder->stream.avail_out = static_cast<uInt>(sizeof(chunk));
        rc = deflate(&encoder->stream, Z_SYNC_FLUSH);
        if (rc != Z_OK) {
            set_error("deflate failed: " + std::to_string(rc));
            return -1;
        }

        const std::size_t produced = sizeof(chunk) - encoder->stream.avail_out;
        result.insert(result.end(), chunk, chunk + produced);
    } while (encoder->stream.avail_out == 0 || encoder->stream.avail_in != 0);

    if (copy_result(result, output, output_size) != 0) {
        return -1;
    }

    encoder->frames += 1;
    encoder->bytes_in += input_size;
    encoder->bytes_out += result.size();
    return 0;
}

std::uint64_t aura_aiwire_encoder_frames(const Encoder* encoder) {
    return encoder == nullptr ? 0 : encoder->frames;
}

std::uint64_t aura_aiwire_encoder_bytes_in(const Encoder* encoder) {
    return encoder == nullptr ? 0 : encoder->bytes_in;
}

std::uint64_t aura_aiwire_encoder_bytes_out(const Encoder* encoder) {
    return encoder == nullptr ? 0 : encoder->bytes_out;
}

Decoder* aura_aiwire_decoder_create(int use_static_dictionary) {
    Decoder* decoder = new (std::nothrow) Decoder();
    if (decoder == nullptr) {
        set_error("failed to allocate decoder");
        return nullptr;
    }

    const int rc = inflateInit2(&decoder->stream, kWindowBits);
    if (rc != Z_OK) {
        set_error("inflateInit2 failed: " + std::to_string(rc));
        delete decoder;
        return nullptr;
    }
    decoder->initialized = true;

    if (use_static_dictionary) {
        const auto& dict = static_dictionary();
        const int dict_rc = inflateSetDictionary(
            &decoder->stream,
            reinterpret_cast<const Bytef*>(dict.data()),
            static_cast<uInt>(dict.size()));
        if (dict_rc != Z_OK) {
            set_error("inflateSetDictionary failed: " + std::to_string(dict_rc));
            inflateEnd(&decoder->stream);
            delete decoder;
            return nullptr;
        }
    }

    return decoder;
}

void aura_aiwire_decoder_destroy(Decoder* decoder) {
    if (decoder == nullptr) {
        return;
    }
    if (decoder->initialized) {
        inflateEnd(&decoder->stream);
    }
    delete decoder;
}

int aura_aiwire_decoder_decompress(
    Decoder* decoder,
    const unsigned char* input,
    std::size_t input_size,
    unsigned char** output,
    std::size_t* output_size) {
    if (decoder == nullptr || !decoder->initialized) {
        set_error("decoder is not initialized");
        return -1;
    }
    if (!valid_payload(input, input_size)) {
        set_error("input pointer is null");
        return -1;
    }
    if (!valid_zlib_size(input_size)) {
        set_error("input frame is too large for one zlib call");
        return -1;
    }

    decoder->stream.next_in = const_cast<Bytef*>(reinterpret_cast<const Bytef*>(input));
    decoder->stream.avail_in = static_cast<uInt>(input_size);

    std::vector<unsigned char> result;
    unsigned char chunk[16384];
    int rc = Z_OK;
    do {
        decoder->stream.next_out = chunk;
        decoder->stream.avail_out = static_cast<uInt>(sizeof(chunk));
        rc = inflate(&decoder->stream, Z_SYNC_FLUSH);
        if (rc == Z_NEED_DICT) {
            const auto& dict = static_dictionary();
            rc = inflateSetDictionary(
                &decoder->stream,
                reinterpret_cast<const Bytef*>(dict.data()),
                static_cast<uInt>(dict.size()));
            if (rc != Z_OK) {
                set_error("inflateSetDictionary during decode failed: " + std::to_string(rc));
                return -1;
            }
            continue;
        }
        if (rc == Z_BUF_ERROR && decoder->stream.avail_in == 0) {
            break;
        }
        if (rc != Z_OK && rc != Z_STREAM_END) {
            set_error("inflate failed: " + std::to_string(rc));
            return -1;
        }

        const std::size_t produced = sizeof(chunk) - decoder->stream.avail_out;
        result.insert(result.end(), chunk, chunk + produced);
    } while (decoder->stream.avail_out == 0 || decoder->stream.avail_in != 0);

    if (copy_result(result, output, output_size) != 0) {
        return -1;
    }

    decoder->frames += 1;
    decoder->bytes_in += input_size;
    decoder->bytes_out += result.size();
    return 0;
}

std::uint64_t aura_aiwire_decoder_frames(const Decoder* decoder) {
    return decoder == nullptr ? 0 : decoder->frames;
}

std::uint64_t aura_aiwire_decoder_bytes_in(const Decoder* decoder) {
    return decoder == nullptr ? 0 : decoder->bytes_in;
}

std::uint64_t aura_aiwire_decoder_bytes_out(const Decoder* decoder) {
    return decoder == nullptr ? 0 : decoder->bytes_out;
}

}  // extern "C"
