#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <new>
#include <optional>
#include <string>
#include <unordered_map>
#include <utility>
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
        "\"additionalProperties\":false",
        "\"text\":{\"format\":{\"type\":\"json_schema\"",
        "\"type\":\"json_schema\"",
        "\"strict\":true",
        "\"output_json\"",
        "\"protocol\":\"mcp\"",
        "\"method\":\"initialize\"",
        "\"method\":\"tools/list\"",
        "\"method\":\"tools/call\"",
        "\"method\":\"resources/read\"",
        "\"method\":\"prompts/get\"",
        "\"method\":\"sampling/createMessage\"",
        "\"notifications/tools/list_changed\"",
        "\"io.modelcontextprotocol/protocolVersion\"",
        "\"io.modelcontextprotocol/clientInfo\"",
        "\"io.modelcontextprotocol/clientCapabilities\"",
        "\"resultType\":\"complete\"",
        "\"tools\":",
        "\"inputSchema\":",
        "\"ttlMs\":300000",
        "\"cacheScope\":\"public\"",
        "\"resources/read\"",
        "\"prompts/get\"",
        "\"sampling/createMessage\"",
        "\"uri\":",
        "\"line_start\":",
        "\"line_end\":",
        "\"matches\":",
        "\"file\":",
        "\"line\":",
        "\"score\":",
        "\"protocol\":\"a2a\"",
        "\"method\":\"message/send\"",
        "\"method\":\"message/stream\"",
        "\"method\":\"tasks/get\"",
        "\"event\":\"TaskStatusUpdateEvent\"",
        "\"event\":\"TaskArtifactUpdateEvent\"",
        "\"message\":",
        "\"messageId\":",
        "\"contextId\":",
        "\"taskId\":",
        "\"status\":",
        "\"state\":\"submitted\"",
        "\"state\":\"working\"",
        "\"state\":\"input_required\"",
        "\"state\":\"completed\"",
        "\"artifacts\":",
        "\"artifactId\":",
        "\"historyLength\":",
        "\"acceptedOutputModes\":",
        "\"lastChunk\":",
        "\"append\":true",
        "\"protocol\":\"local.agent\"",
        "\"schema\":\"local.agent.broker.envelope.v1\"",
        "\"schema\":\"local.agent.session.handshake.v1\"",
        "\"schema\":\"local.agent.delta.status.v1\"",
        "\"schema\":\"local.agent.delta.tool_result.v1\"",
        "\"schema\":\"local.agent.route_hint.v1\"",
        "\"partition\":",
        "\"offset\":",
        "\"headers\":",
        "\"route\":",
        "\"codec\":\"aura.aiwire\"",
        "\"delta\":",
        "\"op\":\"replace\"",
        "\"op\":\"append\"",
        "\"clock\":",
        "\"lamport\":",
        "\"route_before_decompress\":true",
        "\"requires_decompression\":false",
        "\"hash_modifiers\":",
        "\"session_template_update\"",
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
        "session template",
        "recurring message shape",
        "bandwidth",
        "structured output",
        "function_call_output",
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
    std::vector<unsigned char> dictionary;
    std::uint64_t frames = 0;
    std::uint64_t bytes_in = 0;
    std::uint64_t bytes_out = 0;
};

bool set_encoder_dictionary(Encoder* encoder, const std::vector<unsigned char>& dictionary) {
    if (dictionary.empty()) {
        return true;
    }
    if (!valid_zlib_size(dictionary.size())) {
        set_error("dictionary is too large for zlib");
        return false;
    }
    const int dict_rc = deflateSetDictionary(
        &encoder->stream,
        reinterpret_cast<const Bytef*>(dictionary.data()),
        static_cast<uInt>(dictionary.size()));
    if (dict_rc != Z_OK) {
        set_error("deflateSetDictionary failed: " + std::to_string(dict_rc));
        return false;
    }
    return true;
}

bool set_decoder_dictionary(Decoder* decoder, const std::vector<unsigned char>& dictionary) {
    decoder->dictionary = dictionary;
    if (dictionary.empty()) {
        return true;
    }
    if (!valid_zlib_size(dictionary.size())) {
        set_error("dictionary is too large for zlib");
        return false;
    }
    const int dict_rc = inflateSetDictionary(
        &decoder->stream,
        reinterpret_cast<const Bytef*>(dictionary.data()),
        static_cast<uInt>(dictionary.size()));
    if (dict_rc != Z_OK) {
        set_error("inflateSetDictionary failed: " + std::to_string(dict_rc));
        return false;
    }
    return true;
}

std::vector<unsigned char> make_dictionary_from_payload(
    const unsigned char* dictionary,
    std::size_t dictionary_size) {
    if (!valid_payload(dictionary, dictionary_size)) {
        set_error("dictionary pointer is null");
        return {};
    }
    if (!valid_zlib_size(dictionary_size)) {
        set_error("dictionary is too large for zlib");
        return {};
    }
    if (dictionary_size == 0) {
        return {};
    }
    return std::vector<unsigned char>(dictionary, dictionary + dictionary_size);
}

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

bool compress_to_vector(
    Encoder* encoder,
    const unsigned char* input,
    std::size_t input_size,
    std::vector<unsigned char>& result) {
    if (encoder == nullptr || !encoder->initialized) {
        set_error("encoder is not initialized");
        return false;
    }
    if (!valid_payload(input, input_size)) {
        set_error("input pointer is null");
        return false;
    }
    if (!valid_zlib_size(input_size)) {
        set_error("input frame is too large for one zlib call");
        return false;
    }

    encoder->stream.next_in = const_cast<Bytef*>(reinterpret_cast<const Bytef*>(input));
    encoder->stream.avail_in = static_cast<uInt>(input_size);

    result.clear();
    unsigned char chunk[16384];
    int rc = Z_OK;
    do {
        encoder->stream.next_out = chunk;
        encoder->stream.avail_out = static_cast<uInt>(sizeof(chunk));
        rc = deflate(&encoder->stream, Z_SYNC_FLUSH);
        if (rc != Z_OK) {
            set_error("deflate failed: " + std::to_string(rc));
            return false;
        }

        const std::size_t produced = sizeof(chunk) - encoder->stream.avail_out;
        result.insert(result.end(), chunk, chunk + produced);
    } while (encoder->stream.avail_out == 0 || encoder->stream.avail_in != 0);

    encoder->frames += 1;
    encoder->bytes_in += input_size;
    encoder->bytes_out += result.size();
    return true;
}

bool decompress_to_vector(
    Decoder* decoder,
    const unsigned char* input,
    std::size_t input_size,
    std::vector<unsigned char>& result) {
    if (decoder == nullptr || !decoder->initialized) {
        set_error("decoder is not initialized");
        return false;
    }
    if (!valid_payload(input, input_size)) {
        set_error("input pointer is null");
        return false;
    }
    if (!valid_zlib_size(input_size)) {
        set_error("input frame is too large for one zlib call");
        return false;
    }

    decoder->stream.next_in = const_cast<Bytef*>(reinterpret_cast<const Bytef*>(input));
    decoder->stream.avail_in = static_cast<uInt>(input_size);

    result.clear();
    unsigned char chunk[16384];
    int rc = Z_OK;
    do {
        decoder->stream.next_out = chunk;
        decoder->stream.avail_out = static_cast<uInt>(sizeof(chunk));
        rc = inflate(&decoder->stream, Z_SYNC_FLUSH);
        if (rc == Z_NEED_DICT) {
            const auto& dict = decoder->dictionary;
            if (dict.empty()) {
                set_error("inflate requested a dictionary but decoder has none");
                return false;
            }
            rc = inflateSetDictionary(
                &decoder->stream,
                reinterpret_cast<const Bytef*>(dict.data()),
                static_cast<uInt>(dict.size()));
            if (rc != Z_OK) {
                set_error("inflateSetDictionary during decode failed: " + std::to_string(rc));
                return false;
            }
            continue;
        }
        if (rc == Z_BUF_ERROR && decoder->stream.avail_in == 0) {
            break;
        }
        if (rc != Z_OK && rc != Z_STREAM_END) {
            set_error("inflate failed: " + std::to_string(rc));
            return false;
        }

        const std::size_t produced = sizeof(chunk) - decoder->stream.avail_out;
        result.insert(result.end(), chunk, chunk + produced);
    } while (decoder->stream.avail_out == 0 || decoder->stream.avail_in != 0);

    decoder->frames += 1;
    decoder->bytes_in += input_size;
    decoder->bytes_out += result.size();
    return true;
}

constexpr std::array<unsigned char, 4> kTokenMagic = {'A', 'W', 'T', '1'};
constexpr unsigned char kTokenVersion = 1;
constexpr unsigned char kFrameRawBytes = 0x01;
constexpr unsigned char kFrameJsonValue = 0x02;
constexpr unsigned char kNull = 0x10;
constexpr unsigned char kFalse = 0x11;
constexpr unsigned char kTrue = 0x12;
constexpr unsigned char kInt = 0x13;
constexpr unsigned char kFloat = 0x14;
constexpr unsigned char kStringRaw = 0x15;
constexpr unsigned char kStringIntern = 0x16;
constexpr unsigned char kStringRef = 0x17;
constexpr unsigned char kKeyToken = 0x18;
constexpr unsigned char kValueToken = 0x19;
constexpr unsigned char kArray = 0x1A;
constexpr unsigned char kObject = 0x1B;

const std::vector<std::string>& common_keys() {
    static const std::vector<std::string> keys = {
        "protocol", "jsonrpc", "id", "method", "params", "result", "error", "name",
        "arguments", "metadata", "trace_id", "task_id", "session_id", "call_id",
        "tool_call_id", "content", "structuredContent", "isError", "type", "kind",
        "text", "role", "model", "input", "tools", "parameters", "properties",
        "required", "description", "uri", "line_start", "line_end", "matches", "file",
        "line", "score", "message", "messageId", "contextId", "status", "state",
        "artifacts", "artifactId", "event", "agent", "from", "to", "handoff",
        "working_memory", "facts", "open_questions", "requested_output_schema", "objective",
        "constraints", "subgoals", "evidence", "confidence", "verdict", "comments",
        "severity", "answer", "summary", "actions", "item", "repository", "path", "query",
        "limit", "tenant", "priority", "operation", "task", "parts", "service", "output",
        "rows", "timestamp", "level", "sequence", "sha256", "request", "transport",
        "exchange", "request_bytes", "tool_results", "next_actions", "ok", "elapsed_ms",
        "schema", "topic", "partition", "offset", "headers", "route", "body", "delta",
        "op", "value", "previous", "clock", "lamport", "source", "response",
        "response_id", "item_id", "output_index", "content_index", "annotations",
        "configuration", "historyLength", "acceptedOutputModes", "taskId", "append",
        "lastChunk", "artifact", "history", "hash_modifiers", "control", "_meta",
        "protocolVersion", "capabilities", "clientInfo", "clientCapabilities",
        "inputSchema", "outputSchema", "resultType", "ttlMs", "cacheScope", "contents",
        "mimeType", "messages", "maxTokens", "includeContext",
    };
    return keys;
}

const std::vector<std::string>& common_values() {
    static const std::vector<std::string> values = {
        "2.0", "openai.responses", "responses.create", "response.output_item.done",
        "function", "function_call", "mcp", "tools/call", "a2a", "message/send",
        "agent.trace", "agent.handoff", "agent.review", "agent.final", "agent.response",
        "plan.created", "text", "object", "string", "integer", "user", "agent",
        "assistant", "system", "working", "completed", "accepted", "needs_review", "ready",
        "queued", "planner", "researcher", "coder", "reviewer", "executor", "summarizer",
        "observer", "web_search", "read_file", "write_patch", "run_shell", "vector_lookup",
        "search_logs", "policy_check", "memory_route", "continue", "record_latency",
        "diagnostic-summary", "aura.aiwire.stress",
        "response.completed", "response.output_text.delta", "response.web_search_call.completed",
        "function_call_output", "web_search_call", "output_json", "json_schema", "initialize",
        "tools/list", "resources/read", "prompts/get", "sampling/createMessage",
        "notifications/tools/list_changed", "complete", "public", "message/stream",
        "tasks/get", "TaskStatusUpdateEvent", "TaskArtifactUpdateEvent", "submitted",
        "input_required", "local.agent", "local.agent.broker.envelope.v1",
        "local.agent.session.handshake.v1", "local.agent.delta.status.v1",
        "local.agent.delta.tool_result.v1", "local.agent.route_hint.v1", "replace",
        "append", "command", "continue_task", "session_template_update",
    };
    return values;
}

std::optional<std::size_t> table_index(
    const std::vector<std::string>& table,
    const std::string& value) {
    const auto it = std::find(table.begin(), table.end(), value);
    if (it == table.end()) {
        return std::nullopt;
    }
    return static_cast<std::size_t>(std::distance(table.begin(), it));
}

void write_varint(std::uint64_t value, std::vector<unsigned char>& output) {
    while (value >= 0x80) {
        output.push_back(static_cast<unsigned char>((value & 0x7F) | 0x80));
        value >>= 7;
    }
    output.push_back(static_cast<unsigned char>(value));
}

bool read_varint(
    const unsigned char* data,
    std::size_t size,
    std::size_t& offset,
    std::uint64_t& value) {
    value = 0;
    int shift = 0;
    while (true) {
        if (offset >= size) {
            set_error("truncated varint");
            return false;
        }
        const unsigned char byte = data[offset++];
        value |= static_cast<std::uint64_t>(byte & 0x7F) << shift;
        if ((byte & 0x80) == 0) {
            return true;
        }
        shift += 7;
        if (shift > 63) {
            set_error("varint is too large");
            return false;
        }
    }
}

std::uint64_t zigzag_encode(std::int64_t value) {
    return (static_cast<std::uint64_t>(value) << 1) ^
           static_cast<std::uint64_t>(value >> 63);
}

std::int64_t zigzag_decode(std::uint64_t value) {
    return static_cast<std::int64_t>((value >> 1) ^ (~(value & 1) + 1));
}

void append_utf8(std::uint32_t codepoint, std::string& output) {
    if (codepoint <= 0x7F) {
        output.push_back(static_cast<char>(codepoint));
    } else if (codepoint <= 0x7FF) {
        output.push_back(static_cast<char>(0xC0 | (codepoint >> 6)));
        output.push_back(static_cast<char>(0x80 | (codepoint & 0x3F)));
    } else if (codepoint <= 0xFFFF) {
        output.push_back(static_cast<char>(0xE0 | (codepoint >> 12)));
        output.push_back(static_cast<char>(0x80 | ((codepoint >> 6) & 0x3F)));
        output.push_back(static_cast<char>(0x80 | (codepoint & 0x3F)));
    } else {
        output.push_back(static_cast<char>(0xF0 | (codepoint >> 18)));
        output.push_back(static_cast<char>(0x80 | ((codepoint >> 12) & 0x3F)));
        output.push_back(static_cast<char>(0x80 | ((codepoint >> 6) & 0x3F)));
        output.push_back(static_cast<char>(0x80 | (codepoint & 0x3F)));
    }
}

int hex_value(unsigned char ch) {
    if (ch >= '0' && ch <= '9') {
        return ch - '0';
    }
    if (ch >= 'a' && ch <= 'f') {
        return 10 + ch - 'a';
    }
    if (ch >= 'A' && ch <= 'F') {
        return 10 + ch - 'A';
    }
    return -1;
}

bool read_hex4(const unsigned char* data, std::size_t size, std::size_t& offset, std::uint32_t& value) {
    if (offset + 4 > size) {
        return false;
    }
    value = 0;
    for (int index = 0; index < 4; ++index) {
        const int nibble = hex_value(data[offset++]);
        if (nibble < 0) {
            return false;
        }
        value = (value << 4) | static_cast<std::uint32_t>(nibble);
    }
    return true;
}

void append_json_string(const std::string& value, std::vector<unsigned char>& output) {
    output.push_back('"');
    static constexpr char hex[] = "0123456789abcdef";
    for (const unsigned char ch : value) {
        switch (ch) {
            case '"':
                output.push_back('\\');
                output.push_back('"');
                break;
            case '\\':
                output.push_back('\\');
                output.push_back('\\');
                break;
            case '\b':
                output.push_back('\\');
                output.push_back('b');
                break;
            case '\f':
                output.push_back('\\');
                output.push_back('f');
                break;
            case '\n':
                output.push_back('\\');
                output.push_back('n');
                break;
            case '\r':
                output.push_back('\\');
                output.push_back('r');
                break;
            case '\t':
                output.push_back('\\');
                output.push_back('t');
                break;
            default:
                if (ch < 0x20) {
                    output.push_back('\\');
                    output.push_back('u');
                    output.push_back('0');
                    output.push_back('0');
                    output.push_back(hex[(ch >> 4) & 0xF]);
                    output.push_back(hex[ch & 0xF]);
                } else {
                    output.push_back(ch);
                }
                break;
        }
    }
    output.push_back('"');
}

enum class JsonType {
    Null,
    Boolean,
    Integer,
    Float,
    String,
    Array,
    Object,
};

struct JsonValue {
    JsonType type = JsonType::Null;
    bool bool_value = false;
    std::int64_t int_value = 0;
    std::string number_text;
    std::string string_value;
    std::vector<JsonValue> array_value;
    std::vector<std::pair<std::string, JsonValue>> object_value;
};

class JsonParser {
public:
    JsonParser(const unsigned char* data, std::size_t size) : data_(data), size_(size) {}

    bool parse(JsonValue& value) {
        skip_ws();
        if (!parse_value(value)) {
            return false;
        }
        skip_ws();
        return offset_ == size_;
    }

private:
    const unsigned char* data_;
    std::size_t size_;
    std::size_t offset_ = 0;

    void skip_ws() {
        while (offset_ < size_) {
            const unsigned char ch = data_[offset_];
            if (ch != ' ' && ch != '\n' && ch != '\r' && ch != '\t') {
                break;
            }
            ++offset_;
        }
    }

    bool consume(const char* literal) {
        const std::size_t length = std::strlen(literal);
        if (offset_ + length > size_ || std::memcmp(data_ + offset_, literal, length) != 0) {
            return false;
        }
        offset_ += length;
        return true;
    }

    bool parse_value(JsonValue& value) {
        skip_ws();
        if (offset_ >= size_) {
            return false;
        }
        const unsigned char ch = data_[offset_];
        if (ch == 'n') {
            if (!consume("null")) {
                return false;
            }
            value = JsonValue{};
            value.type = JsonType::Null;
            return true;
        }
        if (ch == 't') {
            if (!consume("true")) {
                return false;
            }
            value = JsonValue{};
            value.type = JsonType::Boolean;
            value.bool_value = true;
            return true;
        }
        if (ch == 'f') {
            if (!consume("false")) {
                return false;
            }
            value = JsonValue{};
            value.type = JsonType::Boolean;
            value.bool_value = false;
            return true;
        }
        if (ch == '"') {
            std::string parsed;
            if (!parse_string(parsed)) {
                return false;
            }
            value = JsonValue{};
            value.type = JsonType::String;
            value.string_value = std::move(parsed);
            return true;
        }
        if (ch == '[') {
            return parse_array(value);
        }
        if (ch == '{') {
            return parse_object(value);
        }
        if (ch == '-' || (ch >= '0' && ch <= '9')) {
            return parse_number(value);
        }
        return false;
    }

    bool parse_string(std::string& output) {
        if (offset_ >= size_ || data_[offset_] != '"') {
            return false;
        }
        ++offset_;
        output.clear();
        while (offset_ < size_) {
            const unsigned char ch = data_[offset_++];
            if (ch == '"') {
                return true;
            }
            if (ch < 0x20) {
                return false;
            }
            if (ch != '\\') {
                output.push_back(static_cast<char>(ch));
                continue;
            }
            if (offset_ >= size_) {
                return false;
            }
            const unsigned char esc = data_[offset_++];
            switch (esc) {
                case '"':
                case '\\':
                case '/':
                    output.push_back(static_cast<char>(esc));
                    break;
                case 'b':
                    output.push_back('\b');
                    break;
                case 'f':
                    output.push_back('\f');
                    break;
                case 'n':
                    output.push_back('\n');
                    break;
                case 'r':
                    output.push_back('\r');
                    break;
                case 't':
                    output.push_back('\t');
                    break;
                case 'u': {
                    std::uint32_t codepoint = 0;
                    if (!read_hex4(data_, size_, offset_, codepoint)) {
                        return false;
                    }
                    if (codepoint >= 0xD800 && codepoint <= 0xDBFF) {
                        if (offset_ + 6 > size_ || data_[offset_] != '\\' || data_[offset_ + 1] != 'u') {
                            return false;
                        }
                        offset_ += 2;
                        std::uint32_t low = 0;
                        if (!read_hex4(data_, size_, offset_, low) || low < 0xDC00 || low > 0xDFFF) {
                            return false;
                        }
                        codepoint = 0x10000 + (((codepoint - 0xD800) << 10) | (low - 0xDC00));
                    } else if (codepoint >= 0xDC00 && codepoint <= 0xDFFF) {
                        return false;
                    }
                    append_utf8(codepoint, output);
                    break;
                }
                default:
                    return false;
            }
        }
        return false;
    }

    bool parse_array(JsonValue& value) {
        if (data_[offset_] != '[') {
            return false;
        }
        ++offset_;
        value = JsonValue{};
        value.type = JsonType::Array;
        skip_ws();
        if (offset_ < size_ && data_[offset_] == ']') {
            ++offset_;
            return true;
        }
        while (true) {
            JsonValue item;
            if (!parse_value(item)) {
                return false;
            }
            value.array_value.push_back(std::move(item));
            skip_ws();
            if (offset_ >= size_) {
                return false;
            }
            if (data_[offset_] == ']') {
                ++offset_;
                return true;
            }
            if (data_[offset_] != ',') {
                return false;
            }
            ++offset_;
        }
    }

    bool parse_object(JsonValue& value) {
        if (data_[offset_] != '{') {
            return false;
        }
        ++offset_;
        value = JsonValue{};
        value.type = JsonType::Object;
        skip_ws();
        if (offset_ < size_ && data_[offset_] == '}') {
            ++offset_;
            return true;
        }
        while (true) {
            skip_ws();
            std::string key;
            if (!parse_string(key)) {
                return false;
            }
            skip_ws();
            if (offset_ >= size_ || data_[offset_] != ':') {
                return false;
            }
            ++offset_;
            JsonValue item;
            if (!parse_value(item)) {
                return false;
            }
            value.object_value.emplace_back(std::move(key), std::move(item));
            skip_ws();
            if (offset_ >= size_) {
                return false;
            }
            if (data_[offset_] == '}') {
                ++offset_;
                return true;
            }
            if (data_[offset_] != ',') {
                return false;
            }
            ++offset_;
        }
    }

    bool parse_number(JsonValue& value) {
        const std::size_t start = offset_;
        bool is_float = false;
        if (data_[offset_] == '-') {
            ++offset_;
            if (offset_ >= size_) {
                return false;
            }
        }
        if (data_[offset_] == '0') {
            ++offset_;
        } else if (data_[offset_] >= '1' && data_[offset_] <= '9') {
            while (offset_ < size_ && data_[offset_] >= '0' && data_[offset_] <= '9') {
                ++offset_;
            }
        } else {
            return false;
        }
        if (offset_ < size_ && data_[offset_] == '.') {
            is_float = true;
            ++offset_;
            const std::size_t frac_start = offset_;
            while (offset_ < size_ && data_[offset_] >= '0' && data_[offset_] <= '9') {
                ++offset_;
            }
            if (offset_ == frac_start) {
                return false;
            }
        }
        if (offset_ < size_ && (data_[offset_] == 'e' || data_[offset_] == 'E')) {
            is_float = true;
            ++offset_;
            if (offset_ < size_ && (data_[offset_] == '+' || data_[offset_] == '-')) {
                ++offset_;
            }
            const std::size_t exp_start = offset_;
            while (offset_ < size_ && data_[offset_] >= '0' && data_[offset_] <= '9') {
                ++offset_;
            }
            if (offset_ == exp_start) {
                return false;
            }
        }

        const std::string text(
            reinterpret_cast<const char*>(data_ + start),
            reinterpret_cast<const char*>(data_ + offset_));
        value = JsonValue{};
        if (is_float) {
            value.type = JsonType::Float;
            value.number_text = text;
            return true;
        }
        try {
            std::size_t consumed = 0;
            const long long parsed = std::stoll(text, &consumed, 10);
            if (consumed != text.size()) {
                return false;
            }
            value.type = JsonType::Integer;
            value.int_value = static_cast<std::int64_t>(parsed);
            return true;
        } catch (const std::exception&) {
            return false;
        }
    }
};

struct TokenStringTable {
    explicit TokenStringTable(std::size_t max_entries_value) : max_entries(max_entries_value) {}

    std::size_t max_entries;
    std::vector<std::string> values;
    std::unordered_map<std::string, std::size_t> index;

    std::optional<std::size_t> get(const std::string& value) const {
        const auto it = index.find(value);
        if (it == index.end()) {
            return std::nullopt;
        }
        return it->second;
    }

    std::optional<std::size_t> add(const std::string& value) {
        const auto existing = get(value);
        if (existing.has_value()) {
            return existing;
        }
        if (values.size() >= max_entries) {
            return std::nullopt;
        }
        const std::size_t token = values.size();
        values.push_back(value);
        index.emplace(value, token);
        return token;
    }

    bool at(std::size_t token, std::string& value) const {
        if (token >= values.size()) {
            set_error("unknown session string token: " + std::to_string(token));
            return false;
        }
        value = values[token];
        return true;
    }
};

struct TokenEncoder {
    explicit TokenEncoder(std::size_t max_session_strings, std::size_t intern_min_length_value)
        : strings(max_session_strings), intern_min_length(intern_min_length_value) {}

    TokenStringTable strings;
    std::size_t intern_min_length;
    std::uint64_t frames = 0;
    std::uint64_t bytes_in = 0;
    std::uint64_t bytes_out = 0;
};

struct TokenDecoder {
    explicit TokenDecoder(std::size_t max_session_strings) : strings(max_session_strings) {}

    TokenStringTable strings;
    std::uint64_t frames = 0;
    std::uint64_t bytes_in = 0;
    std::uint64_t bytes_out = 0;
};

void encode_token_string(
    TokenEncoder* encoder,
    const std::string& value,
    bool is_key,
    std::vector<unsigned char>& output) {
    if (is_key) {
        const auto token = table_index(common_keys(), value);
        if (token.has_value()) {
            output.push_back(kKeyToken);
            write_varint(*token, output);
            return;
        }
    } else {
        const auto token = table_index(common_values(), value);
        if (token.has_value()) {
            output.push_back(kValueToken);
            write_varint(*token, output);
            return;
        }
    }

    const auto existing = encoder->strings.get(value);
    if (existing.has_value()) {
        output.push_back(kStringRef);
        write_varint(*existing, output);
        return;
    }

    if (value.size() >= encoder->intern_min_length) {
        const auto token = encoder->strings.add(value);
        if (token.has_value()) {
            output.push_back(kStringIntern);
            write_varint(*token, output);
            write_varint(value.size(), output);
            output.insert(output.end(), value.begin(), value.end());
            return;
        }
    }

    output.push_back(kStringRaw);
    write_varint(value.size(), output);
    output.insert(output.end(), value.begin(), value.end());
}

void encode_token_value(
    TokenEncoder* encoder,
    const JsonValue& value,
    std::vector<unsigned char>& output) {
    switch (value.type) {
        case JsonType::Null:
            output.push_back(kNull);
            break;
        case JsonType::Boolean:
            output.push_back(value.bool_value ? kTrue : kFalse);
            break;
        case JsonType::Integer:
            output.push_back(kInt);
            write_varint(zigzag_encode(value.int_value), output);
            break;
        case JsonType::Float:
            output.push_back(kFloat);
            write_varint(value.number_text.size(), output);
            output.insert(output.end(), value.number_text.begin(), value.number_text.end());
            break;
        case JsonType::String:
            encode_token_string(encoder, value.string_value, false, output);
            break;
        case JsonType::Array:
            output.push_back(kArray);
            write_varint(value.array_value.size(), output);
            for (const auto& item : value.array_value) {
                encode_token_value(encoder, item, output);
            }
            break;
        case JsonType::Object: {
            output.push_back(kObject);
            auto items = value.object_value;
            std::sort(
                items.begin(),
                items.end(),
                [](const auto& left, const auto& right) { return left.first < right.first; });
            write_varint(items.size(), output);
            for (const auto& item : items) {
                encode_token_string(encoder, item.first, true, output);
                encode_token_value(encoder, item.second, output);
            }
            break;
        }
    }
}

bool token_encode_to_vector(
    TokenEncoder* encoder,
    const unsigned char* input,
    std::size_t input_size,
    std::vector<unsigned char>& output) {
    if (encoder == nullptr) {
        set_error("token encoder is not initialized");
        return false;
    }
    if (!valid_payload(input, input_size)) {
        set_error("input pointer is null");
        return false;
    }

    output.assign(kTokenMagic.begin(), kTokenMagic.end());
    output.push_back(kTokenVersion);

    JsonValue value;
    JsonParser parser(input, input_size);
    if (parser.parse(value)) {
        output.push_back(kFrameJsonValue);
        encode_token_value(encoder, value, output);
    } else {
        output.push_back(kFrameRawBytes);
        write_varint(input_size, output);
        if (input_size > 0) {
            output.insert(output.end(), input, input + input_size);
        }
    }

    encoder->frames += 1;
    encoder->bytes_in += input_size;
    encoder->bytes_out += output.size();
    return true;
}

bool read_raw_slice(
    const unsigned char* data,
    std::size_t size,
    std::size_t& offset,
    std::string& value) {
    std::uint64_t length = 0;
    if (!read_varint(data, size, offset, length)) {
        return false;
    }
    if (length > size - offset) {
        set_error("truncated string bytes");
        return false;
    }
    value.assign(
        reinterpret_cast<const char*>(data + offset),
        reinterpret_cast<const char*>(data + offset + static_cast<std::size_t>(length)));
    offset += static_cast<std::size_t>(length);
    return true;
}

bool decode_token_string(
    TokenDecoder* decoder,
    const unsigned char* data,
    std::size_t size,
    std::size_t& offset,
    unsigned char tag,
    std::string& value) {
    std::uint64_t token = 0;
    switch (tag) {
        case kKeyToken:
            if (!read_varint(data, size, offset, token)) {
                return false;
            }
            if (token >= common_keys().size()) {
                set_error("unknown key token: " + std::to_string(token));
                return false;
            }
            value = common_keys()[static_cast<std::size_t>(token)];
            return true;
        case kValueToken:
            if (!read_varint(data, size, offset, token)) {
                return false;
            }
            if (token >= common_values().size()) {
                set_error("unknown value token: " + std::to_string(token));
                return false;
            }
            value = common_values()[static_cast<std::size_t>(token)];
            return true;
        case kStringRef:
            if (!read_varint(data, size, offset, token)) {
                return false;
            }
            return decoder->strings.at(static_cast<std::size_t>(token), value);
        case kStringRaw:
            return read_raw_slice(data, size, offset, value);
        case kStringIntern: {
            if (!read_varint(data, size, offset, token)) {
                return false;
            }
            if (!read_raw_slice(data, size, offset, value)) {
                return false;
            }
            const auto expected = decoder->strings.add(value);
            if (expected.has_value() && *expected != token) {
                set_error("session string token mismatch");
                return false;
            }
            return true;
        }
        default:
            set_error("expected string token");
            return false;
    }
}

bool decode_token_value_to_json(
    TokenDecoder* decoder,
    const unsigned char* data,
    std::size_t size,
    std::size_t& offset,
    std::vector<unsigned char>& output) {
    if (offset >= size) {
        set_error("truncated JSON token");
        return false;
    }
    const unsigned char tag = data[offset++];
    switch (tag) {
        case kNull:
            output.insert(output.end(), {'n', 'u', 'l', 'l'});
            return true;
        case kFalse:
            output.insert(output.end(), {'f', 'a', 'l', 's', 'e'});
            return true;
        case kTrue:
            output.insert(output.end(), {'t', 'r', 'u', 'e'});
            return true;
        case kInt: {
            std::uint64_t encoded = 0;
            if (!read_varint(data, size, offset, encoded)) {
                return false;
            }
            const std::string text = std::to_string(zigzag_decode(encoded));
            output.insert(output.end(), text.begin(), text.end());
            return true;
        }
        case kFloat: {
            std::string text;
            if (!read_raw_slice(data, size, offset, text)) {
                return false;
            }
            output.insert(output.end(), text.begin(), text.end());
            return true;
        }
        case kStringRaw:
        case kStringIntern:
        case kStringRef:
        case kKeyToken:
        case kValueToken: {
            std::string value;
            if (!decode_token_string(decoder, data, size, offset, tag, value)) {
                return false;
            }
            append_json_string(value, output);
            return true;
        }
        case kArray: {
            std::uint64_t length = 0;
            if (!read_varint(data, size, offset, length)) {
                return false;
            }
            output.push_back('[');
            for (std::uint64_t index = 0; index < length; ++index) {
                if (index != 0) {
                    output.push_back(',');
                }
                if (!decode_token_value_to_json(decoder, data, size, offset, output)) {
                    return false;
                }
            }
            output.push_back(']');
            return true;
        }
        case kObject: {
            std::uint64_t length = 0;
            if (!read_varint(data, size, offset, length)) {
                return false;
            }
            std::vector<std::pair<std::string, std::vector<unsigned char>>> items;
            items.reserve(static_cast<std::size_t>(length));
            for (std::uint64_t index = 0; index < length; ++index) {
                if (offset >= size) {
                    set_error("truncated object key");
                    return false;
                }
                const unsigned char key_tag = data[offset++];
                std::string key;
                if (!decode_token_string(decoder, data, size, offset, key_tag, key)) {
                    return false;
                }
                std::vector<unsigned char> item_json;
                if (!decode_token_value_to_json(decoder, data, size, offset, item_json)) {
                    return false;
                }
                items.emplace_back(std::move(key), std::move(item_json));
            }
            std::sort(
                items.begin(),
                items.end(),
                [](const auto& left, const auto& right) { return left.first < right.first; });
            output.push_back('{');
            for (std::size_t index = 0; index < items.size(); ++index) {
                if (index != 0) {
                    output.push_back(',');
                }
                append_json_string(items[index].first, output);
                output.push_back(':');
                output.insert(output.end(), items[index].second.begin(), items[index].second.end());
            }
            output.push_back('}');
            return true;
        }
        default:
            set_error("unknown JSON token tag: " + std::to_string(tag));
            return false;
    }
}

bool token_decode_to_vector(
    TokenDecoder* decoder,
    const unsigned char* input,
    std::size_t input_size,
    std::vector<unsigned char>& output) {
    if (decoder == nullptr) {
        set_error("token decoder is not initialized");
        return false;
    }
    if (!valid_payload(input, input_size)) {
        set_error("input pointer is null");
        return false;
    }
    if (input_size < kTokenMagic.size() + 2 ||
        !std::equal(kTokenMagic.begin(), kTokenMagic.end(), input)) {
        set_error("invalid AIWire token frame magic");
        return false;
    }
    std::size_t offset = kTokenMagic.size();
    if (input[offset++] != kTokenVersion) {
        set_error("unsupported AIWire token frame version");
        return false;
    }
    const unsigned char frame_type = input[offset++];
    if (frame_type == kFrameRawBytes) {
        std::uint64_t length = 0;
        if (!read_varint(input, input_size, offset, length)) {
            return false;
        }
        if (length != input_size - offset) {
            set_error("raw token frame length mismatch");
            return false;
        }
        output.assign(input + offset, input + input_size);
    } else if (frame_type == kFrameJsonValue) {
        output.clear();
        if (!decode_token_value_to_json(decoder, input, input_size, offset, output)) {
            return false;
        }
        if (offset != input_size) {
            set_error("trailing bytes in token frame");
            return false;
        }
    } else {
        set_error("unknown AIWire token frame type: " + std::to_string(frame_type));
        return false;
    }

    decoder->frames += 1;
    decoder->bytes_in += input_size;
    decoder->bytes_out += output.size();
    return true;
}

struct TokenAIWireEncoder {
    explicit TokenAIWireEncoder(TokenEncoder* token_encoder_value, Encoder* wire_encoder_value)
        : token_encoder(token_encoder_value), wire_encoder(wire_encoder_value) {}

    TokenEncoder* token_encoder = nullptr;
    Encoder* wire_encoder = nullptr;
};

struct TokenAIWireDecoder {
    explicit TokenAIWireDecoder(TokenDecoder* token_decoder_value, Decoder* wire_decoder_value)
        : token_decoder(token_decoder_value), wire_decoder(wire_decoder_value) {}

    TokenDecoder* token_decoder = nullptr;
    Decoder* wire_decoder = nullptr;
};

}  // namespace

extern "C" {

const char* aura_aiwire_last_error() {
    return g_last_error.c_str();
}

const char* aura_aiwire_backend_version() {
    return "aura-aiwire-native-cpp/3";
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

Encoder* aura_aiwire_encoder_create_with_dictionary(
    int level,
    const unsigned char* dictionary,
    std::size_t dictionary_size);

Decoder* aura_aiwire_decoder_create_with_dictionary(
    const unsigned char* dictionary,
    std::size_t dictionary_size);

Encoder* aura_aiwire_encoder_create(int level, int use_static_dictionary) {
    const auto& dict = static_dictionary();
    const std::vector<unsigned char> dictionary =
        use_static_dictionary ? std::vector<unsigned char>(dict.begin(), dict.end())
                              : std::vector<unsigned char>();
    return aura_aiwire_encoder_create_with_dictionary(
        level,
        dictionary.empty() ? nullptr : dictionary.data(),
        dictionary.size());
}

Encoder* aura_aiwire_encoder_create_with_dictionary(
    int level,
    const unsigned char* dictionary,
    std::size_t dictionary_size) {
    if (level < 0 || level > 9) {
        set_error("zlib level must be in [0, 9]");
        return nullptr;
    }
    std::vector<unsigned char> session_dictionary =
        make_dictionary_from_payload(dictionary, dictionary_size);
    if (dictionary_size > 0 && session_dictionary.empty()) {
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

    if (!set_encoder_dictionary(encoder, session_dictionary)) {
        deflateEnd(&encoder->stream);
        delete encoder;
        return nullptr;
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
    std::vector<unsigned char> result;
    return compress_to_vector(encoder, input, input_size, result)
               ? copy_result(result, output, output_size)
               : -1;
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
    const auto& dict = static_dictionary();
    const std::vector<unsigned char> dictionary =
        use_static_dictionary ? std::vector<unsigned char>(dict.begin(), dict.end())
                              : std::vector<unsigned char>();
    return aura_aiwire_decoder_create_with_dictionary(
        dictionary.empty() ? nullptr : dictionary.data(),
        dictionary.size());
}

Decoder* aura_aiwire_decoder_create_with_dictionary(
    const unsigned char* dictionary,
    std::size_t dictionary_size) {
    std::vector<unsigned char> session_dictionary =
        make_dictionary_from_payload(dictionary, dictionary_size);
    if (dictionary_size > 0 && session_dictionary.empty()) {
        return nullptr;
    }

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

    if (!set_decoder_dictionary(decoder, session_dictionary)) {
        inflateEnd(&decoder->stream);
        delete decoder;
        return nullptr;
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
    std::vector<unsigned char> result;
    return decompress_to_vector(decoder, input, input_size, result)
               ? copy_result(result, output, output_size)
               : -1;
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

TokenEncoder* aura_aiwire_token_encoder_create(
    std::size_t max_session_strings,
    std::size_t intern_min_length) {
    TokenEncoder* encoder = new (std::nothrow) TokenEncoder(max_session_strings, intern_min_length);
    if (encoder == nullptr) {
        set_error("failed to allocate token encoder");
    }
    return encoder;
}

void aura_aiwire_token_encoder_destroy(TokenEncoder* encoder) {
    delete encoder;
}

int aura_aiwire_token_encoder_encode(
    TokenEncoder* encoder,
    const unsigned char* input,
    std::size_t input_size,
    unsigned char** output,
    std::size_t* output_size) {
    std::vector<unsigned char> result;
    return token_encode_to_vector(encoder, input, input_size, result)
               ? copy_result(result, output, output_size)
               : -1;
}

std::uint64_t aura_aiwire_token_encoder_frames(const TokenEncoder* encoder) {
    return encoder == nullptr ? 0 : encoder->frames;
}

std::uint64_t aura_aiwire_token_encoder_bytes_in(const TokenEncoder* encoder) {
    return encoder == nullptr ? 0 : encoder->bytes_in;
}

std::uint64_t aura_aiwire_token_encoder_bytes_out(const TokenEncoder* encoder) {
    return encoder == nullptr ? 0 : encoder->bytes_out;
}

TokenDecoder* aura_aiwire_token_decoder_create(std::size_t max_session_strings) {
    TokenDecoder* decoder = new (std::nothrow) TokenDecoder(max_session_strings);
    if (decoder == nullptr) {
        set_error("failed to allocate token decoder");
    }
    return decoder;
}

void aura_aiwire_token_decoder_destroy(TokenDecoder* decoder) {
    delete decoder;
}

int aura_aiwire_token_decoder_decode(
    TokenDecoder* decoder,
    const unsigned char* input,
    std::size_t input_size,
    unsigned char** output,
    std::size_t* output_size) {
    std::vector<unsigned char> result;
    return token_decode_to_vector(decoder, input, input_size, result)
               ? copy_result(result, output, output_size)
               : -1;
}

std::uint64_t aura_aiwire_token_decoder_frames(const TokenDecoder* decoder) {
    return decoder == nullptr ? 0 : decoder->frames;
}

std::uint64_t aura_aiwire_token_decoder_bytes_in(const TokenDecoder* decoder) {
    return decoder == nullptr ? 0 : decoder->bytes_in;
}

std::uint64_t aura_aiwire_token_decoder_bytes_out(const TokenDecoder* decoder) {
    return decoder == nullptr ? 0 : decoder->bytes_out;
}

TokenAIWireEncoder* aura_aiwire_token_aiwire_encoder_create_with_dictionary(
    int level,
    const unsigned char* dictionary,
    std::size_t dictionary_size) {
    TokenEncoder* token_encoder = aura_aiwire_token_encoder_create(4096, 6);
    if (token_encoder == nullptr) {
        return nullptr;
    }
    Encoder* wire_encoder = aura_aiwire_encoder_create_with_dictionary(
        level,
        dictionary,
        dictionary_size);
    if (wire_encoder == nullptr) {
        aura_aiwire_token_encoder_destroy(token_encoder);
        return nullptr;
    }
    TokenAIWireEncoder* encoder =
        new (std::nothrow) TokenAIWireEncoder(token_encoder, wire_encoder);
    if (encoder == nullptr) {
        set_error("failed to allocate token+AIWire encoder");
        aura_aiwire_token_encoder_destroy(token_encoder);
        aura_aiwire_encoder_destroy(wire_encoder);
    }
    return encoder;
}

TokenAIWireEncoder* aura_aiwire_token_aiwire_encoder_create(
    int level,
    int use_static_dictionary) {
    const auto& dict = static_dictionary();
    const std::vector<unsigned char> dictionary =
        use_static_dictionary ? std::vector<unsigned char>(dict.begin(), dict.end())
                              : std::vector<unsigned char>();
    return aura_aiwire_token_aiwire_encoder_create_with_dictionary(
        level,
        dictionary.empty() ? nullptr : dictionary.data(),
        dictionary.size());
}

void aura_aiwire_token_aiwire_encoder_destroy(TokenAIWireEncoder* encoder) {
    if (encoder == nullptr) {
        return;
    }
    aura_aiwire_token_encoder_destroy(encoder->token_encoder);
    aura_aiwire_encoder_destroy(encoder->wire_encoder);
    delete encoder;
}

int aura_aiwire_token_aiwire_encoder_encode(
    TokenAIWireEncoder* encoder,
    const unsigned char* input,
    std::size_t input_size,
    unsigned char** output,
    std::size_t* output_size) {
    if (encoder == nullptr) {
        set_error("token+AIWire encoder is not initialized");
        return -1;
    }
    std::vector<unsigned char> token_frame;
    if (!token_encode_to_vector(encoder->token_encoder, input, input_size, token_frame)) {
        return -1;
    }
    std::vector<unsigned char> result;
    return compress_to_vector(
               encoder->wire_encoder,
               token_frame.empty() ? nullptr : token_frame.data(),
               token_frame.size(),
               result)
               ? copy_result(result, output, output_size)
               : -1;
}

std::uint64_t aura_aiwire_token_aiwire_encoder_frames(const TokenAIWireEncoder* encoder) {
    return encoder == nullptr || encoder->token_encoder == nullptr
               ? 0
               : encoder->token_encoder->frames;
}

std::uint64_t aura_aiwire_token_aiwire_encoder_bytes_in(const TokenAIWireEncoder* encoder) {
    return encoder == nullptr || encoder->token_encoder == nullptr
               ? 0
               : encoder->token_encoder->bytes_in;
}

std::uint64_t aura_aiwire_token_aiwire_encoder_token_bytes(const TokenAIWireEncoder* encoder) {
    return encoder == nullptr || encoder->token_encoder == nullptr
               ? 0
               : encoder->token_encoder->bytes_out;
}

std::uint64_t aura_aiwire_token_aiwire_encoder_bytes_out(const TokenAIWireEncoder* encoder) {
    return encoder == nullptr || encoder->wire_encoder == nullptr
               ? 0
               : encoder->wire_encoder->bytes_out;
}

TokenAIWireDecoder* aura_aiwire_token_aiwire_decoder_create_with_dictionary(
    const unsigned char* dictionary,
    std::size_t dictionary_size) {
    TokenDecoder* token_decoder = aura_aiwire_token_decoder_create(4096);
    if (token_decoder == nullptr) {
        return nullptr;
    }
    Decoder* wire_decoder = aura_aiwire_decoder_create_with_dictionary(dictionary, dictionary_size);
    if (wire_decoder == nullptr) {
        aura_aiwire_token_decoder_destroy(token_decoder);
        return nullptr;
    }
    TokenAIWireDecoder* decoder =
        new (std::nothrow) TokenAIWireDecoder(token_decoder, wire_decoder);
    if (decoder == nullptr) {
        set_error("failed to allocate token+AIWire decoder");
        aura_aiwire_token_decoder_destroy(token_decoder);
        aura_aiwire_decoder_destroy(wire_decoder);
    }
    return decoder;
}

TokenAIWireDecoder* aura_aiwire_token_aiwire_decoder_create(int use_static_dictionary) {
    const auto& dict = static_dictionary();
    const std::vector<unsigned char> dictionary =
        use_static_dictionary ? std::vector<unsigned char>(dict.begin(), dict.end())
                              : std::vector<unsigned char>();
    return aura_aiwire_token_aiwire_decoder_create_with_dictionary(
        dictionary.empty() ? nullptr : dictionary.data(),
        dictionary.size());
}

void aura_aiwire_token_aiwire_decoder_destroy(TokenAIWireDecoder* decoder) {
    if (decoder == nullptr) {
        return;
    }
    aura_aiwire_token_decoder_destroy(decoder->token_decoder);
    aura_aiwire_decoder_destroy(decoder->wire_decoder);
    delete decoder;
}

int aura_aiwire_token_aiwire_decoder_decode(
    TokenAIWireDecoder* decoder,
    const unsigned char* input,
    std::size_t input_size,
    unsigned char** output,
    std::size_t* output_size) {
    if (decoder == nullptr) {
        set_error("token+AIWire decoder is not initialized");
        return -1;
    }
    std::vector<unsigned char> token_frame;
    if (!decompress_to_vector(decoder->wire_decoder, input, input_size, token_frame)) {
        return -1;
    }
    std::vector<unsigned char> result;
    return token_decode_to_vector(
               decoder->token_decoder,
               token_frame.empty() ? nullptr : token_frame.data(),
               token_frame.size(),
               result)
               ? copy_result(result, output, output_size)
               : -1;
}

std::uint64_t aura_aiwire_token_aiwire_decoder_frames(const TokenAIWireDecoder* decoder) {
    return decoder == nullptr || decoder->token_decoder == nullptr
               ? 0
               : decoder->token_decoder->frames;
}

std::uint64_t aura_aiwire_token_aiwire_decoder_bytes_in(const TokenAIWireDecoder* decoder) {
    return decoder == nullptr || decoder->token_decoder == nullptr
               ? 0
               : decoder->token_decoder->bytes_out;
}

std::uint64_t aura_aiwire_token_aiwire_decoder_token_bytes(const TokenAIWireDecoder* decoder) {
    return decoder == nullptr || decoder->token_decoder == nullptr
               ? 0
               : decoder->token_decoder->bytes_in;
}

std::uint64_t aura_aiwire_token_aiwire_decoder_bytes_out(const TokenAIWireDecoder* decoder) {
    return decoder == nullptr || decoder->wire_decoder == nullptr
               ? 0
               : decoder->wire_decoder->bytes_in;
}

}  // extern "C"
