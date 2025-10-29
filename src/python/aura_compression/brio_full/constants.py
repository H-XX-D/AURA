"""Constants for the experimental Brio compressor."""

MAGIC = b"AURA"
VERSION = 1

WINDOW_SIZE = 1 << 15  # 32 KiB sliding window
MIN_MATCH = 4
MAX_MATCH = 255

ANS_SCALE_BITS = 12
ANS_SCALE = 1 << ANS_SCALE_BITS

MAX_DICTIONARY_SIZE = 2048  # Increased from 255 to support 1200+ common words
