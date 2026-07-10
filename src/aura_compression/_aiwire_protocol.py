"""Dependency-light AIWire v1 protocol definitions.

This module contains values that must be shared by the protocol, compatibility,
native, and codec layers without creating import cycles.
"""

AI_WIRE_VERSION = 1
AI_WIRE_SUPPORTED_VERSIONS = (AI_WIRE_VERSION,)
AI_WIRE_PROTOCOL = "aura.aiwire"
AI_WIRE_HANDSHAKE_SCHEMA = "aura.aiwire.handshake.v1"
AI_WIRE_NEGOTIATION_SCHEMA = "aura.aiwire.negotiation.v1"
AI_WIRE_NARY_NEGOTIATION_SCHEMA = "aura.aiwire.nary_negotiation.v1"
AI_WIRE_COMPATIBILITY_MANIFEST_SCHEMA = "aura.aiwire.compatibility_manifest.v1"
AI_WIRE_STATIC_DICTIONARY_CATALOG_SCHEMA = "aura.aiwire.static_dictionary_catalog.v1"
AI_WIRE_SESSION_TEMPLATE_CATALOG_SCHEMA = "aura.aiwire.session_template_catalog.v1"
AI_WIRE_DICTIONARY_EXTENSION_SCHEMA = "aura.aiwire.dictionary_extension.v1"
AI_WIRE_CONTROL_LUT_SCHEMA = "aura.aiwire.control_lut.v1"
AI_WIRE_SYSTEM_CONTROL_SCHEMA = "aura.aiwire.system_control.v1"
AI_WIRE_SESSION_TEMPLATE_UPDATE_SCHEMA = "aura.aiwire.session_templates.update.v1"
AI_WIRE_SESSION_DICTIONARY_STATE_SCHEMA = "aura.aiwire.session_dictionary.state.v1"
AI_WIRE_SESSION_DICTIONARY_DIFF_SCHEMA = "aura.aiwire.session_dictionary.diff.v1"
AI_WIRE_SESSION_DICTIONARY_ACK_SCHEMA = "aura.aiwire.session_dictionary.ack.v1"
AI_WIRE_SESSION_RESUME_HELLO_SCHEMA = "aura.aiwire.session_resume.hello.v1"
AI_WIRE_SESSION_RESUME_RESPONSE_SCHEMA = "aura.aiwire.session_resume.response.v1"

AI_WIRE_WBITS = -15
AI_WIRE_MEM_LEVEL = 8
AI_WIRE_DEFAULT_LEVEL = 3
AI_WIRE_FLUSH_MODE = "z_sync_flush"
AI_WIRE_SYNC_FLUSH_SUFFIX = b"\x00\x00\xff\xff"
AI_WIRE_FALLBACK_CODECS = ("zlib", "raw")
AI_WIRE_DELTA_VERSION = 1
AI_WIRE_STATIC_DICTIONARY_VERSION = "aiwire-static-v1"
AI_WIRE_DEFAULT_SESSION_TEMPLATE_CATALOG_VERSION = "session-templates-v1"

AI_WIRE_MAX_SESSION_TEMPLATES = 4096
AI_WIRE_MAX_SESSION_DICTIONARY_DIFF_ADDITIONS = 128
AI_WIRE_MAX_SESSION_TEMPLATE_BYTES = 4096
AI_WIRE_MAX_SESSION_DICTIONARY_BYTES = 262144
AI_WIRE_MAX_DICTIONARY_EXTENSION_BYTES = 262144
AI_WIRE_MAX_CONTROL_LUT_ENTRIES = 1024
AI_WIRE_NONCE_BYTES = 16

AI_WIRE_MISSION_CRITICAL = "mission_critical"
AI_WIRE_ROUTINE_CONTROL_CRITICALITIES = ("routine", "important")
AI_WIRE_MISSION_CRITICAL_CONTROL_TYPES = frozenset(
    {
        "handshake_accept",
        "handshake_reject",
        "dictionary_update",
        "epoch_reset",
        "resync_required",
        "auth_failure",
        "safety_policy",
        "key_rotation",
        "emergency_stop",
        "critical_route_authority",
        "critical_verification_failure",
    }
)
