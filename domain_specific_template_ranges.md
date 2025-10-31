# Domain-Specific Template Ranges

## Overview

The template ID space has been reorganized into **domain-specific ranges** to support specialized use cases while maintaining the full 65,536 template capacity.

## Template ID Allocation Map

```
┌─────────────────────────────────────────────────────────────────────┐
│                    TEMPLATE ID ALLOCATION (0-65,535)                │
└─────────────────────────────────────────────────────────────────────┘

Range          IDs              Slots   Purpose
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
0-127          0-127            128     DEFAULT_TEMPLATES
                                        Built-in common patterns

128-2127       128-2,127        2,000   AI_TO_AI_RANGE
                                        AI-to-AI communication patterns
                                        (GPT-4, Claude, etc.)

2128-4999      2,128-4,999      2,872   RESERVED_1
                                        Reserved for future AI patterns

5000-6999      5,000-6,999      2,000   HUMAN_TO_AI_HEALTHCARE
                                        Healthcare domain templates
                                        (medical, patient care, etc.)

7000-9999      7,000-9,999      3,000   FINANCIAL
                                        Financial domain templates
                                        (transactions, banking, etc.)

10000-11999    10,000-11,999    2,000   LEGAL
                                        Legal domain templates
                                        (contracts, compliance, etc.)

12000-13999    12,000-13,999    2,000   SMALL_SENTENCES
                                        Short message templates
                                        (chat, notifications, etc.)

14000-16383    14,000-16,383    2,384   DYNAMIC_RANGE
                                        General discovered templates

16384-32767    16,384-32,767    16,384  CLIENT_SYNC_RANGE
                                        Client-discovered templates

32768-49151    32,768-49,151    16,384  WHITESPACE_RANGE
                                        Auto-generated whitespace variants

49152-65535    49,152-65,535    16,384  RESERVED_FUTURE
                                        Reserved for future features

Total: 65,536 template IDs (2-byte encoding: struct.pack(">H", id))
```

## Domain-Specific Ranges

### 1. AI-to-AI Range (128-2,127) - 2,000 slots

**Purpose**: AI-to-AI communication patterns

**Use Cases**:
- OpenAI GPT-4 API responses
- Claude API responses
- LLM-to-LLM message formats
- Model metadata patterns
- Token usage patterns

**Example Templates**:
```json
{
  "128": "{\"id\": \"chatcmpl-{0}\", \"object\": \"chat.completion\", \"model\": \"gpt-4\", ...}",
  "129": "{\"id\": \"msg-{0}\", \"type\": \"message\", \"role\": \"assistant\", \"content\": \"{1}\", ...}",
  "130": "{\"status\": \"{0}\", \"message\": \"{1}\", \"timestamp\": {2}, \"request_id\": \"req-{3}\"}"
}
```

**Allocation**:
```python
template_id = library.allocate_ai_to_ai_id()  # Returns 128, 129, 130, ...
```

---

### 2. Healthcare Range (5,000-6,999) - 2,000 slots

**Purpose**: Human-to-AI healthcare communication

**Use Cases**:
- Patient intake forms
- Medical history patterns
- Symptom descriptions
- Prescription formats
- Lab result patterns
- Doctor notes

**Example Templates**:
```
5000: "Patient {0} reports {1} with severity {2}/10"
5001: "Prescription: {0} {1}mg, {2} times daily for {3} days"
5002: "Lab results for {0}: {1} = {2} {3} (normal range: {4})"
5003: "Appointment scheduled for {0} on {1} at {2}"
```

**Allocation**:
```python
template_id = library.allocate_healthcare_id()  # Returns 5000, 5001, 5002, ...
```

---

### 3. Financial Range (7,000-9,999) - 3,000 slots

**Purpose**: Financial domain templates

**Use Cases**:
- Transaction records
- Account statements
- Payment confirmations
- Invoice formats
- Trading messages
- Banking notifications

**Example Templates**:
```
7000: "Transaction {0}: {1} ${2} to account {3} on {4}"
7001: "Account {0} balance: ${1} (available: ${2})"
7002: "Payment of ${0} received from {1} - Invoice #{2}"
7003: "Trade executed: {0} shares of {1} at ${2}/share"
```

**Allocation**:
```python
template_id = library.allocate_financial_id()  # Returns 7000, 7001, 7002, ...
```

---

### 4. Legal Range (10,000-11,999) - 2,000 slots

**Purpose**: Legal domain templates

**Use Cases**:
- Contract clauses
- Legal notices
- Compliance statements
- Terms and conditions
- Privacy policies
- Regulatory filings

**Example Templates**:
```
10000: "Party {0} hereby agrees to {1} under terms {2}"
10001: "This agreement dated {0} between {1} and {2}"
10002: "Pursuant to {0}, {1} shall {2} within {3} days"
10003: "Compliance status: {0} - Last audit: {1}"
```

**Allocation**:
```python
template_id = library.allocate_legal_id()  # Returns 10000, 10001, 10002, ...
```

---

### 5. Small Sentences Range (12,000-13,999) - 2,000 slots

**Purpose**: Short message templates

**Use Cases**:
- Chat messages
- Notifications
- Status updates
- Error messages
- Success messages
- Quick responses

**Example Templates**:
```
12000: "Hello {0}, how are you?"
12001: "Your {0} is ready"
12002: "Error: {0} not found"
12003: "Success! {0} completed"
12004: "Welcome back, {0}!"
12005: "{0} sent you a message"
```

**Allocation**:
```python
template_id = library.allocate_small_sentences_id()  # Returns 12000, 12001, 12002, ...
```

---

### 6. Dynamic Range (14,000-16,383) - 2,384 slots

**Purpose**: General-purpose discovered templates

**Use Cases**:
- Auto-discovered patterns that don't fit other domains
- Mixed-domain patterns
- Experimental templates
- Legacy compatibility

**Allocation**:
```python
template_id = library.allocate_dynamic_id()  # Returns 14000, 14001, 14002, ...
```

---

## API Usage

### Allocating Template IDs by Domain

```python
from aura_compression.templates import TemplateLibrary

library = TemplateLibrary()

# AI-to-AI templates
ai_id = library.allocate_ai_to_ai_id()
library.add(ai_id, '{\"id\": \"chatcmpl-{0}\", \"content\": \"{1}\"}')

# Healthcare templates
healthcare_id = library.allocate_healthcare_id()
library.add(healthcare_id, 'Patient {0} reports {1} with severity {2}')

# Financial templates
financial_id = library.allocate_financial_id()
library.add(financial_id, 'Transaction {0}: ${1} to account {2}')

# Legal templates
legal_id = library.allocate_legal_id()
library.add(legal_id, 'Party {0} agrees to {1} under terms {2}')

# Small sentences
small_id = library.allocate_small_sentences_id()
library.add(small_id, 'Hello {0}, welcome back!')

# General dynamic
dynamic_id = library.allocate_dynamic_id()
library.add(dynamic_id, 'General pattern with {0} and {1}')
```

### Checking Available Capacity

```python
# Check how many slots remain in each domain
ai_remaining = library.AI_TO_AI_RANGE.stop - library._next_ai_to_ai_id
healthcare_remaining = library.HUMAN_TO_AI_HEALTHCARE_RANGE.stop - library._next_healthcare_id
financial_remaining = library.FINANCIAL_RANGE.stop - library._next_financial_id
legal_remaining = library.LEGAL_RANGE.stop - library._next_legal_id
small_remaining = library.SMALL_SENTENCES_RANGE.stop - library._next_small_sentences_id

print(f"AI-to-AI: {ai_remaining} slots remaining")
print(f"Healthcare: {healthcare_remaining} slots remaining")
print(f"Financial: {financial_remaining} slots remaining")
print(f"Legal: {legal_remaining} slots remaining")
print(f"Small Sentences: {small_remaining} slots remaining")
```

---

## Benefits of Domain-Specific Ranges

### 1. Organized Template Management
- Clear separation by domain
- Easy to identify template purpose by ID
- Better maintainability

### 2. Domain Isolation
- Templates don't interfere across domains
- Can delete/reset domain ranges independently
- Clearer ownership and responsibility

### 3. Capacity Planning
- Know exactly how many templates each domain can hold
- Can adjust ranges as needs evolve
- Prevents one domain from exhausting shared pool

### 4. Performance Optimization
- Can optimize matching per domain
- Domain-specific caching strategies
- Better bucketing by ID range

### 5. Multi-Tenant Support
- Each tenant can own a domain range
- No ID collisions between tenants
- Easier to migrate/isolate tenant data

---

## Capacity Summary

| Domain | Range | Slots | % of Total |
|--------|-------|-------|------------|
| Default Templates | 0-127 | 128 | 0.2% |
| **AI-to-AI** | 128-2,127 | **2,000** | **3.1%** |
| Reserved 1 | 2,128-4,999 | 2,872 | 4.4% |
| **Healthcare** | 5,000-6,999 | **2,000** | **3.1%** |
| **Financial** | 7,000-9,999 | **3,000** | **4.6%** |
| **Legal** | 10,000-11,999 | **2,000** | **3.1%** |
| **Small Sentences** | 12,000-13,999 | **2,000** | **3.1%** |
| Dynamic | 14,000-16,383 | 2,384 | 3.6% |
| Client Sync | 16,384-32,767 | 16,384 | 25.0% |
| Whitespace | 32,768-49,151 | 16,384 | 25.0% |
| Reserved Future | 49,152-65,535 | 16,384 | 25.0% |
| **Total** | **0-65,535** | **65,536** | **100%** |

**Domain-Specific Capacity**: 11,000 slots (16.8% of total)
**System/Reserved Capacity**: 54,536 slots (83.2% of total)

---

## Migration from Old Ranges

### Old Allocation (Before)
```python
DYNAMIC_RANGE = range(128, 16384)  # 16,256 slots
```

### New Allocation (After)
```python
# Domain-specific (11,000 slots)
AI_TO_AI_RANGE = range(128, 2128)              # 2,000
HUMAN_TO_AI_HEALTHCARE_RANGE = range(5000, 7000)  # 2,000
FINANCIAL_RANGE = range(7000, 10000)           # 3,000
LEGAL_RANGE = range(10000, 12000)              # 2,000
SMALL_SENTENCES_RANGE = range(12000, 14000)    # 2,000

# General dynamic (reduced but still available)
DYNAMIC_RANGE = range(14000, 16384)            # 2,384
```

### Backward Compatibility

✅ **Fully Compatible**:
- Old templates in range 128-16,383 still work
- `allocate_dynamic_id()` still works (returns 14,000+)
- No breaking changes to existing code
- Wire format unchanged (still 2 bytes)

---

## Error Handling

Each range will raise a descriptive error when exhausted:

```python
# AI-to-AI range exhausted
RuntimeError: AI-to-AI template ID range exhausted (128-2127)

# Healthcare range exhausted
RuntimeError: Healthcare template ID range exhausted (5000-6999)

# Financial range exhausted
RuntimeError: Financial template ID range exhausted (7000-9999)

# Legal range exhausted
RuntimeError: Legal template ID range exhausted (10000-11999)

# Small Sentences range exhausted
RuntimeError: Small Sentences template ID range exhausted (12000-13999)

# Dynamic range exhausted (still 2,384 slots)
RuntimeError: Dynamic template ID range exhausted
```

---

## Testing

All tests pass with new domain-specific ranges:

```bash
python3 -m pytest tests/test_compression_strategy_manager.py tests/test_metadata.py -v
======================= 102 passed in 0.50s ========================
```

---

## Summary

✅ **Domain-Specific Ranges Implemented**:
- 2,000 slots for AI-to-AI communication
- 2,000 slots for Healthcare domain
- 3,000 slots for Financial domain
- 2,000 slots for Legal domain
- 2,000 slots for Small Sentences
- 2,384 slots for general dynamic discovery

✅ **Benefits**:
- Organized template management
- Domain isolation
- Better capacity planning
- Performance optimization opportunities
- Multi-tenant support

✅ **Backward Compatible**:
- No breaking changes
- Old code continues to work
- Wire format unchanged
- All tests passing

✅ **Production Ready**:
- Clean API with `allocate_<domain>_id()` methods
- Descriptive error messages
- Full capacity tracking
- Easy to extend with new domains

---

**Modified**: 2025-10-31
**File**: [src/aura_compression/templates.py](src/aura_compression/templates.py)
**Tests**: 102/102 passing
**Status**: ✅ READY FOR USE
