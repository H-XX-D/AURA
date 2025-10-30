#!/usr/bin/env python3
"""
AURA Appendix C Template Library

Complete template library specification from Appendix C of provisional patent.

Current Library: 607 templates (120 core + 487 discovered)
Coverage: 72% of AI conversation messages
Average Ratio: 5.1:1

Copyright (c) 2025 Todd James Hendricks
Licensed under Apache License 2.0
Patent Pending - Application No. 19/366,538
"""

from typing import Dict, List
from dataclasses import dataclass


@dataclass
class TemplateSpec:
    """Template specification from Appendix C"""
    template_id: int
    pattern: str
    slot_count: int
    category: str
    avg_ratio: float
    example: str


# ============================================================================
# CATEGORY 0: LIMITATIONS (IDs 0-9)
# Coverage: 20%, Avg Ratio: 6.5:1
# ============================================================================

LIMITATIONS_TEMPLATES = {
    0: "I don't have access to {0}. {1}",
    1: "I cannot {0}.",
    2: "I'm unable to {0}.",
    3: "I don't have the ability to {0}.",
    4: "I'm not able to {0} because {1}.",
    5: "I can't {0} as {1}.",
    6: "That's beyond my capabilities. {0}",
    7: "I don't have information about {0}.",
    8: "I'm not designed to {0}.",
    9: "I lack the capability to {0}.",
}

# ============================================================================
# CATEGORY 1: FACTS (IDs 10-19)
# Coverage: 30%, Avg Ratio: 5.0:1
# ============================================================================

FACTS_TEMPLATES = {
    10: "The {0} of {1} is {2}.",
    11: "{0} is {1}.",
    12: "{0} are {1}.",
    13: "{0} was {1}.",
    14: "{0} were {1}.",
    15: "{0} has {1}.",
    16: "{0} have {1}.",
    17: "{0} contains {1}.",
    18: "{0} consists of {1}.",
    19: "{0} represents {1}.",
}

# ============================================================================
# CATEGORY 2: DEFINITIONS (IDs 20-29)
# Coverage: 10%, Avg Ratio: 4.5:1
# ============================================================================

DEFINITIONS_TEMPLATES = {
    20: "{0} is {1} {2} of {3}.",
    21: "{0} is {1} {2} for {3}.",
    22: "{0} is {1} {2} used for {3}.",
    23: "{0} refers to {1}.",
    24: "{0} means {1}.",
    25: "{0} can be defined as {1}.",
    26: "In {0}, {1} is {2}.",
    27: "The term {0} describes {1}.",
    28: "{0} denotes {1}.",
    29: "By {0}, we mean {1}.",
}

# ============================================================================
# CATEGORY 3: CODE EXAMPLES (IDs 30-39)
# Coverage: 15%, Avg Ratio: 5.2:1
# ============================================================================

CODE_EXAMPLES_TEMPLATES = {
    30: "Here's {0} {1} example:\n\n```{2}\n{3}\n```",
    31: "Here's how to {0}:\n\n```{1}\n{2}\n```",
    32: "```{0}\n{1}\n```",
    33: "In {0}, you can {1}:\n\n```{0}\n{2}\n```",
    34: "Example {0} code:\n\n```{1}\n{2}\n```",
    35: "Here's a {0} snippet:\n\n```{1}\n{2}\n```",
    36: "Try this {0} code:\n\n```{1}\n{2}\n```",
    37: "{0} implementation:\n\n```{1}\n{2}\n```",
    38: "Sample {0}:\n\n```{1}\n{2}\n```",
    39: "Basic {0} example:\n\n```{1}\n{2}\n```",
}

# ============================================================================
# CATEGORY 4: INSTRUCTIONS (IDs 40-49)
# Coverage: 18%, Avg Ratio: 5.0:1
# ============================================================================

INSTRUCTIONS_TEMPLATES = {
    40: "To {0}, use {1}: `{2}`",
    41: "To {0}, {1}.",
    42: "You can {0} by {1}.",
    43: "Follow these steps to {0}: {1}",
    44: "The way to {0} is to {1}.",
    45: "In order to {0}, you need to {1}.",
    46: "To achieve {0}, {1}.",
    47: "{0} can be done by {1}.",
    48: "Start by {0}, then {1}.",
    49: "First {0}, then {1}.",
}

# ============================================================================
# CATEGORY 5: AFFIRMATIONS (IDs 50-59)
# Coverage: 8%, Avg Ratio: 7.0:1
# ============================================================================

AFFIRMATIONS_TEMPLATES = {
    50: "Yes, I can help with that.",
    51: "Yes, that's correct.",
    52: "That's right.",
    53: "Absolutely.",
    54: "Certainly.",
    55: "Of course.",
    56: "Yes, {0}.",
    57: "I'd be happy to help with {0}.",
    58: "I can assist with {0}.",
    59: "Let me help you with {0}.",
}

# ============================================================================
# CATEGORY 6: COMPARISONS (IDs 60-69)
# Coverage: 5%, Avg Ratio: 4.8:1
# ============================================================================

COMPARISONS_TEMPLATES = {
    60: "{0} is different from {1} because {2}.",
    61: "Unlike {0}, {1} {2}.",
    62: "{0} is similar to {1} in that {2}.",
    63: "Compared to {0}, {1} is {2}.",
    64: "The difference between {0} and {1} is {2}.",
    65: "{0} versus {1}: {2}",
    66: "While {0} {1}, {2} {3}.",
    67: "{0} and {1} both {2}, but {3}.",
    68: "In contrast to {0}, {1}.",
    69: "{0} differs from {1} in {2}.",
}

# ============================================================================
# CATEGORY 7: EXPLANATIONS (IDs 70-79)
# Coverage: 8%, Avg Ratio: 5.1:1
# ============================================================================

EXPLANATIONS_TEMPLATES = {
    70: "This is because {0}.",
    71: "The reason is {0}.",
    72: "This happens because {0}.",
    73: "{0} because {1}.",
    74: "The explanation is that {0}.",
    75: "This occurs due to {0}.",
    76: "It works by {0}.",
    77: "The process involves {0}.",
    78: "This is a result of {0}.",
    79: "The cause is {0}.",
}

# ============================================================================
# CATEGORY 8: ENUMERATIONS (IDs 80-89)
# Coverage: 6%, Avg Ratio: 5.0:1
# ============================================================================

ENUMERATIONS_TEMPLATES = {
    80: "The main {0} are: {1}",
    81: "Here are the {0}: {1}",
    82: "There are {0} types: {1}",
    83: "The key {0} include: {1}",
    84: "Some examples of {0} are: {1}",
    85: "{0} can be categorized as: {1}",
    86: "The primary {0} consist of: {1}",
    87: "Common {0} include: {1}",
    88: "Notable {0} are: {1}",
    89: "Several {0} exist: {1}",
}

# ============================================================================
# CATEGORY 9: RECOMMENDATIONS (IDs 90-99)
# Coverage: 4%, Avg Ratio: 5.3:1
# ============================================================================

RECOMMENDATIONS_TEMPLATES = {
    90: "I recommend {0}.",
    91: "You should {0}.",
    92: "It's best to {0}.",
    93: "Consider {0}.",
    94: "I suggest {0}.",
    95: "A good approach is to {0}.",
    96: "It would be wise to {0}.",
    97: "The recommended way is to {0}.",
    98: "Try {0}.",
    99: "For best results, {0}.",
}

# ============================================================================
# CATEGORY 10: CLARIFICATIONS (IDs 100-119)
# Coverage: 12%, Avg Ratio: 7.2:1
# ============================================================================

CLARIFICATIONS_TEMPLATES = {
    100: "Could you clarify what you mean by {0}?",
    101: "What specific {0} are you interested in?",
    102: "Are you asking about {0}?",
    103: "Do you mean {0}?",
    104: "Can you provide more details about {0}?",
    105: "What aspect of {0} would you like to know?",
    106: "Could you be more specific about {0}?",
    107: "Are you referring to {0} or {1}?",
    108: "To clarify, do you want to know about {0}?",
    109: "Just to confirm, you're asking about {0}?",
    110: "What type of {0} are you looking for?",
    111: "Which {0} specifically?",
    112: "In what context are you asking about {0}?",
    113: "Could you elaborate on {0}?",
    114: "What do you mean by {0}?",
    115: "Can you give an example of {0}?",
    116: "Are you interested in {0} or {1}?",
    117: "Would you like to know about {0}?",
    118: "Is this related to {0}?",
    119: "What would you like to know about {0}?",
}

# ============================================================================
# COMBINE ALL CORE TEMPLATES (IDs 0-119)
# ============================================================================

CORE_TEMPLATES: Dict[int, str] = {}
CORE_TEMPLATES.update(LIMITATIONS_TEMPLATES)
CORE_TEMPLATES.update(FACTS_TEMPLATES)
CORE_TEMPLATES.update(DEFINITIONS_TEMPLATES)
CORE_TEMPLATES.update(CODE_EXAMPLES_TEMPLATES)
CORE_TEMPLATES.update(INSTRUCTIONS_TEMPLATES)
CORE_TEMPLATES.update(AFFIRMATIONS_TEMPLATES)
CORE_TEMPLATES.update(COMPARISONS_TEMPLATES)
CORE_TEMPLATES.update(EXPLANATIONS_TEMPLATES)
CORE_TEMPLATES.update(ENUMERATIONS_TEMPLATES)
CORE_TEMPLATES.update(RECOMMENDATIONS_TEMPLATES)
CORE_TEMPLATES.update(CLARIFICATIONS_TEMPLATES)

# ============================================================================
# DISCOVERED TEMPLATES (IDs 200-686)
# These are examples from Appendix C - in production, these would be
# automatically discovered from traffic using template_discovery.py
# ============================================================================

DISCOVERED_TEMPLATES = {
    # Clarifications and Follow-ups (200-249)
    200: "Yes, I can help with that. What specific {0} would you like to know more about?",
    201: "I apologize, but I don't have information about {0}. {1}",
    202: "Based on {0}, I would say {1}.",
    203: "Let me explain {0}. {1}",
    204: "In the context of {0}, {1}.",
    205: "According to {0}, {1}.",
    206: "Research shows that {0}.",
    207: "Studies indicate that {0}.",
    208: "Evidence suggests that {0}.",
    209: "It's important to note that {0}.",
    210: "Keep in mind that {0}.",
    211: "Remember that {0}.",
    212: "One thing to consider is {0}.",
    213: "A key point is that {0}.",
    214: "The important thing is {0}.",
    215: "What matters most is {0}.",
    216: "The main issue is {0}.",
    217: "The problem is that {0}.",
    218: "The challenge here is {0}.",
    219: "The difficulty lies in {0}.",
    220: "Let me break this down for you. {0}",
    221: "Here's what you need to know about {0}: {1}",
    222: "In simple terms, {0}.",
    223: "To put it another way, {0}.",
    224: "What I mean is {0}.",
    225: "Essentially, {0}.",
    226: "In other words, {0}.",
    227: "The key takeaway is {0}.",
    228: "The bottom line is {0}.",
    229: "Simply put, {0}.",
    230: "To summarize, {0}.",
    231: "In summary, {0}.",
    232: "To recap, {0}.",
    233: "Overall, {0}.",
    234: "In conclusion, {0}.",
    235: "The main point is {0}.",
    236: "What you should know is {0}.",
    237: "The critical thing to understand is {0}.",
    238: "Here's the key insight: {0}",
    239: "The fundamental concept is {0}.",
    240: "At its core, {0}.",
    241: "Fundamentally, {0}.",
    242: "Basically, {0}.",
    243: "In essence, {0}.",
    244: "The gist is {0}.",
    245: "The crux of the matter is {0}.",
    246: "What it boils down to is {0}.",
    247: "The central idea is {0}.",
    248: "The main concept is {0}.",
    249: "The primary principle is {0}.",

    # Contextual Responses (250-299)
    250: "In {0}, this typically means {1}.",
    251: "When it comes to {0}, {1}.",
    252: "Regarding {0}, I should mention that {1}.",
    253: "As for {0}, {1}.",
    254: "Concerning {0}, {1}.",
    255: "With respect to {0}, {1}.",
    256: "In terms of {0}, {1}.",
    257: "Speaking of {0}, {1}.",
    258: "On the topic of {0}, {1}.",
    259: "About {0}, {1}.",
    260: "For {0}, you'll want to {1}.",
    261: "With {0}, it's important to {1}.",
    262: "In the case of {0}, {1}.",
    263: "When dealing with {0}, {1}.",
    264: "If you're working with {0}, {1}.",
    265: "While using {0}, {1}.",
    266: "During {0}, {1}.",
    267: "Throughout {0}, {1}.",
    268: "After {0}, {1}.",
    269: "Before {0}, {1}.",
    270: "Following {0}, {1}.",
    271: "Prior to {0}, {1}.",
    272: "Upon {0}, {1}.",
    273: "Once {0}, {1}.",
    274: "When {0}, {1}.",
    275: "Whenever {0}, {1}.",
    276: "As soon as {0}, {1}.",
    277: "Until {0}, {1}.",
    278: "Unless {0}, {1}.",
    279: "Although {0}, {1}.",
    280: "Even though {0}, {1}.",
    281: "Despite {0}, {1}.",
    282: "Regardless of {0}, {1}.",
    283: "Irrespective of {0}, {1}.",
    284: "Notwithstanding {0}, {1}.",
    285: "In spite of {0}, {1}.",
    286: "Apart from {0}, {1}.",
    287: "Aside from {0}, {1}.",
    288: "Besides {0}, {1}.",
    289: "Beyond {0}, {1}.",
    290: "Excluding {0}, {1}.",
    291: "Except for {0}, {1}.",
    292: "Other than {0}, {1}.",
    293: "Without {0}, {1}.",
    294: "Instead of {0}, {1}.",
    295: "Rather than {0}, {1}.",
    296: "As opposed to {0}, {1}.",
    297: "In lieu of {0}, {1}.",
    298: "In place of {0}, {1}.",
    299: "As an alternative to {0}, {1}.",

    # Technical Explanations (300-349)
    300: "The {0} method takes {1} and returns {2}.",
    301: "This function accepts {0} as input and produces {1}.",
    302: "The syntax for {0} is: {1}",
    303: "You'll need to import {0} from {1}.",
    304: "Make sure to install {0} using {1}.",
    305: "The {0} parameter controls {1}.",
    306: "Set {0} to {1} for {2}.",
    307: "The default value for {0} is {1}.",
    308: "You can override {0} by setting {1}.",
    309: "Configure {0} in your {1} file.",
    310: "Add {0} to your {1}.",
    311: "Update {0} with {1}.",
    312: "Modify {0} to include {1}.",
    313: "Change {0} from {1} to {2}.",
    314: "Replace {0} with {1}.",
    315: "Swap {0} for {1}.",
    316: "Substitute {0} with {1}.",
    317: "Use {0} instead of {1}.",
    318: "Prefer {0} over {1} because {2}.",
    319: "Choose {0} when {1}.",
    320: "Select {0} if {1}.",
    321: "Opt for {0} in cases where {1}.",
    322: "Go with {0} for {1}.",
    323: "Pick {0} for {1} scenarios.",
    324: "Apply {0} to {1}.",
    325: "Implement {0} using {1}.",
    326: "Execute {0} by {1}.",
    327: "Run {0} with {1} flags.",
    328: "Launch {0} from {1}.",
    329: "Start {0} by running {1}.",
    330: "Initialize {0} with {1}.",
    331: "Create {0} using {1}.",
    332: "Build {0} from {1}.",
    333: "Construct {0} with {1}.",
    334: "Generate {0} by {1}.",
    335: "Compile {0} using {1}.",
    336: "Package {0} with {1}.",
    337: "Deploy {0} to {1}.",
    338: "Publish {0} on {1}.",
    339: "Release {0} via {1}.",
    340: "Distribute {0} through {1}.",
    341: "Share {0} using {1}.",
    342: "Export {0} as {1}.",
    343: "Save {0} in {1} format.",
    344: "Store {0} as {1}.",
    345: "Write {0} to {1}.",
    346: "Output {0} to {1}.",
    347: "Send {0} to {1}.",
    348: "Transmit {0} via {1}.",
    349: "Transfer {0} using {1}.",

    # Problem Solving (350-399)
    350: "If you encounter {0}, try {1}.",
    351: "To fix {0}, you should {1}.",
    352: "To resolve {0}, {1}.",
    353: "To address {0}, {1}.",
    354: "To solve {0}, {1}.",
    355: "To correct {0}, {1}.",
    356: "To repair {0}, {1}.",
    357: "To remedy {0}, {1}.",
    358: "To troubleshoot {0}, {1}.",
    359: "To debug {0}, {1}.",
    360: "Check {0} for {1}.",
    361: "Verify {0} is set to {1}.",
    362: "Confirm {0} matches {1}.",
    363: "Ensure {0} is {1}.",
    364: "Make sure {0} is {1}.",
    365: "Validate {0} against {1}.",
    366: "Test {0} with {1}.",
    367: "Try {0} and see if {1}.",
    368: "Attempt {0} to {1}.",
    369: "Experiment with {0} for {1}.",
    370: "The error {0} indicates {1}.",
    371: "This warning means {0}.",
    372: "The message {0} suggests {1}.",
    373: "When you see {0}, it means {1}.",
    374: "If {0} appears, {1}.",
    375: "The exception {0} occurs when {1}.",
    376: "This fails because {0}.",
    377: "The issue is caused by {0}.",
    378: "This happens due to {0}.",
    379: "The root cause is {0}.",
    380: "This stems from {0}.",
    381: "This results from {0}.",
    382: "This is triggered by {0}.",
    383: "This originates from {0}.",
    384: "The source of the problem is {0}.",
    385: "This can be traced to {0}.",
    386: "Look for {0} in {1}.",
    387: "Search for {0} within {1}.",
    388: "Find {0} by checking {1}.",
    389: "Locate {0} in the {1}.",
    390: "Identify {0} by examining {1}.",
    391: "Detect {0} using {1}.",
    392: "Discover {0} by {1}.",
    393: "Uncover {0} through {1}.",
    394: "Reveal {0} by {1}.",
    395: "Expose {0} via {1}.",
    396: "Inspect {0} for {1}.",
    397: "Review {0} to find {1}.",
    398: "Examine {0} for signs of {1}.",
    399: "Analyze {0} to determine {1}.",

    # Best Practices (400-449)
    400: "It's generally better to {0} than {1}.",
    401: "The recommended approach is {0}.",
    402: "Best practice is to {0}.",
    403: "It's advisable to {0}.",
    404: "You should always {0}.",
    405: "Never {0} without {1}.",
    406: "Avoid {0} when {1}.",
    407: "Don't {0} unless {1}.",
    408: "Refrain from {0} if {1}.",
    409: "Be careful not to {0}.",
    410: "Watch out for {0} when {1}.",
    411: "Be aware that {0}.",
    412: "Note that {0}.",
    413: "Bear in mind that {0}.",
    414: "Take into account that {0}.",
    415: "Consider that {0}.",
    416: "Recognize that {0}.",
    417: "Understand that {0}.",
    418: "Realize that {0}.",
    419: "Acknowledge that {0}.",
    420: "For optimal performance, {0}.",
    421: "To maximize {0}, {1}.",
    422: "To minimize {0}, {1}.",
    423: "To optimize {0}, {1}.",
    424: "To improve {0}, {1}.",
    425: "To enhance {0}, {1}.",
    426: "To boost {0}, {1}.",
    427: "To increase {0}, {1}.",
    428: "To reduce {0}, {1}.",
    429: "To decrease {0}, {1}.",
    430: "To maintain {0}, {1}.",
    431: "To preserve {0}, {1}.",
    432: "To sustain {0}, {1}.",
    433: "To ensure {0}, {1}.",
    434: "To guarantee {0}, {1}.",
    435: "To achieve {0}, you must {1}.",
    436: "To accomplish {0}, {1}.",
    437: "To attain {0}, {1}.",
    438: "To reach {0}, {1}.",
    439: "To obtain {0}, {1}.",
    440: "To gain {0}, {1}.",
    441: "To secure {0}, {1}.",
    442: "To acquire {0}, {1}.",
    443: "To get {0}, {1}.",
    444: "For {0}, use {1}.",
    445: "In {0} situations, {1}.",
    446: "Under {0} conditions, {1}.",
    447: "In {0} environments, {1}.",
    448: "On {0} systems, {1}.",
    449: "With {0} configurations, {1}.",

    # Conceptual Explanations (450-499)
    450: "The concept of {0} involves {1}.",
    451: "The idea behind {0} is {1}.",
    452: "The theory of {0} states that {1}.",
    453: "The principle of {0} is {1}.",
    454: "The law of {0} dictates that {1}.",
    455: "The rule of {0} is {1}.",
    456: "The pattern of {0} shows {1}.",
    457: "The trend toward {0} indicates {1}.",
    458: "The shift from {0} to {1} reflects {2}.",
    459: "The evolution of {0} demonstrates {1}.",
    460: "The development of {0} led to {1}.",
    461: "The advancement in {0} enabled {1}.",
    462: "The progress in {0} allows {1}.",
    463: "The innovation of {0} introduced {1}.",
    464: "The invention of {0} created {1}.",
    465: "The discovery of {0} revealed {1}.",
    466: "The finding that {0} suggests {1}.",
    467: "The observation that {0} implies {1}.",
    468: "The fact that {0} means {1}.",
    469: "The reality is that {0}.",
    470: "The truth is {0}.",
    471: "Actually, {0}.",
    472: "In fact, {0}.",
    473: "As a matter of fact, {0}.",
    474: "Indeed, {0}.",
    475: "Certainly, {0}.",
    476: "Undoubtedly, {0}.",
    477: "Clearly, {0}.",
    478: "Obviously, {0}.",
    479: "Evidently, {0}.",
    480: "Apparently, {0}.",
    481: "Seemingly, {0}.",
    482: "Presumably, {0}.",
    483: "Likely, {0}.",
    484: "Probably, {0}.",
    485: "Possibly, {0}.",
    486: "Perhaps, {0}.",
    487: "Maybe, {0}.",
    488: "Potentially, {0}.",
    489: "Conceivably, {0}.",
    490: "Theoretically, {0}.",
    491: "Hypothetically, {0}.",
    492: "Ideally, {0}.",
    493: "Optimally, {0}.",
    494: "Preferably, {0}.",
    495: "Ideally speaking, {0}.",
    496: "In a perfect world, {0}.",
    497: "Under ideal circumstances, {0}.",
    498: "All things being equal, {0}.",
    499: "Generally speaking, {0}.",

    # Practical Applications (500-549)
    500: "In practice, {0}.",
    501: "Practically speaking, {0}.",
    502: "From a practical standpoint, {0}.",
    503: "In real-world applications, {0}.",
    504: "In production environments, {0}.",
    505: "In actual use, {0}.",
    506: "When actually implemented, {0}.",
    507: "In deployment, {0}.",
    508: "During runtime, {0}.",
    509: "At execution time, {0}.",
    510: "When running, {0}.",
    511: "While active, {0}.",
    512: "In operation, {0}.",
    513: "During normal operation, {0}.",
    514: "Under normal conditions, {0}.",
    515: "In typical scenarios, {0}.",
    516: "In most cases, {0}.",
    517: "Usually, {0}.",
    518: "Typically, {0}.",
    519: "Generally, {0}.",
    520: "Commonly, {0}.",
    521: "Frequently, {0}.",
    522: "Often, {0}.",
    523: "Sometimes, {0}.",
    524: "Occasionally, {0}.",
    525: "Rarely, {0}.",
    526: "Seldom, {0}.",
    527: "Infrequently, {0}.",
    528: "On rare occasions, {0}.",
    529: "In rare instances, {0}.",
    530: "In exceptional cases, {0}.",
    531: "In special circumstances, {0}.",
    532: "In unique situations, {0}.",
    533: "In particular cases, {0}.",
    534: "In specific instances, {0}.",
    535: "In certain scenarios, {0}.",
    536: "Under certain conditions, {0}.",
    537: "Given {0}, {1}.",
    538: "Assuming {0}, {1}.",
    539: "Provided that {0}, {1}.",
    540: "On the condition that {0}, {1}.",
    541: "In the event that {0}, {1}.",
    542: "Should {0} occur, {1}.",
    543: "If and when {0}, {1}.",
    544: "Once {0} happens, {1}.",
    545: "After {0} completes, {1}.",
    546: "When {0} finishes, {1}.",
    547: "Upon completion of {0}, {1}.",
    548: "Following the {0}, {1}.",
    549: "Subsequent to {0}, {1}.",

    # Documentation and References (550-599)
    550: "For more information on {0}, see {1}.",
    551: "Refer to {0} for details about {1}.",
    552: "Check the {0} documentation for {1}.",
    553: "Consult the {0} guide regarding {1}.",
    554: "See the {0} manual for {1}.",
    555: "Review the {0} reference for {1}.",
    556: "Read about {0} in the {1}.",
    557: "Learn more about {0} from {1}.",
    558: "Find additional information on {0} at {1}.",
    559: "For further details on {0}, visit {1}.",
    560: "Additional resources for {0} are available at {1}.",
    561: "More information about {0} can be found in {1}.",
    562: "The {0} section explains {1}.",
    563: "The {0} chapter covers {1}.",
    564: "The {0} article discusses {1}.",
    565: "The {0} tutorial demonstrates {1}.",
    566: "The {0} example shows {1}.",
    567: "The {0} sample illustrates {1}.",
    568: "The {0} documentation describes {1}.",
    569: "The {0} specification defines {1}.",
    570: "The {0} standard specifies {1}.",
    571: "According to the {0} specification, {1}.",
    572: "Per the {0} documentation, {1}.",
    573: "As stated in {0}, {1}.",
    574: "As mentioned in {0}, {1}.",
    575: "As described in {0}, {1}.",
    576: "As outlined in {0}, {1}.",
    577: "As detailed in {0}, {1}.",
    578: "As explained in {0}, {1}.",
    579: "As noted in {0}, {1}.",
    580: "As indicated in {0}, {1}.",
    581: "As specified in {0}, {1}.",
    582: "As defined in {0}, {1}.",
    583: "The documentation states that {0}.",
    584: "The specification requires that {0}.",
    585: "The standard mandates that {0}.",
    586: "The guidelines recommend that {0}.",
    587: "The policy dictates that {0}.",
    588: "The protocol specifies that {0}.",
    589: "The convention is to {0}.",
    590: "The tradition is to {0}.",
    591: "The custom is to {0}.",
    592: "The norm is to {0}.",
    593: "The standard practice is to {0}.",
    594: "The usual approach is to {0}.",
    595: "The typical method is to {0}.",
    596: "The common technique is to {0}.",
    597: "The popular solution is to {0}.",
    598: "The preferred option is to {0}.",
    599: "The recommended choice is to {0}.",

    # Versioning and Compatibility (600-649)
    600: "In version {0}, {1}.",
    601: "As of version {0}, {1}.",
    602: "Starting from version {0}, {1}.",
    603: "Since version {0}, {1}.",
    604: "From version {0} onwards, {1}.",
    605: "Version {0} introduced {1}.",
    606: "Version {0} added {1}.",
    607: "Version {0} deprecated {1}.",
    608: "Version {0} removed {1}.",
    609: "Version {0} changed {1}.",
    610: "The {0} version includes {1}.",
    611: "The latest version supports {0}.",
    612: "The current version features {0}.",
    613: "The newest release contains {0}.",
    614: "The recent update added {0}.",
    615: "This feature is available in {0}.",
    616: "This functionality requires {0}.",
    617: "This capability needs {0}.",
    618: "This option is only available in {0}.",
    619: "This is supported in {0} and later.",
    620: "This works with {0}.",
    621: "This is compatible with {0}.",
    622: "This integrates with {0}.",
    623: "This interfaces with {0}.",
    624: "This connects to {0}.",
    625: "This communicates with {0}.",
    626: "This interacts with {0}.",
    627: "This works alongside {0}.",
    628: "This operates with {0}.",
    629: "This functions with {0}.",
    630: "This pairs with {0}.",
    631: "This combines with {0}.",
    632: "This merges with {0}.",
    633: "This joins with {0}.",
    634: "This links to {0}.",
    635: "This binds to {0}.",
    636: "This attaches to {0}.",
    637: "This plugs into {0}.",
    638: "This extends {0}.",
    639: "This enhances {0}.",
    640: "This augments {0}.",
    641: "This supplements {0}.",
    642: "This complements {0}.",
    643: "This adds to {0}.",
    644: "This builds on {0}.",
    645: "This expands {0}.",
    646: "This improves upon {0}.",
    647: "This refines {0}.",
    648: "This polishes {0}.",
    649: "This perfects {0}.",

    # Additional Common Patterns (650-686)
    650: "The difference is that {0}.",
    651: "What sets {0} apart is {1}.",
    652: "What makes {0} unique is {1}.",
    653: "What distinguishes {0} is {1}.",
    654: "The distinguishing feature of {0} is {1}.",
    655: "The defining characteristic of {0} is {1}.",
    656: "The hallmark of {0} is {1}.",
    657: "The signature of {0} is {1}.",
    658: "The trademark of {0} is {1}.",
    659: "The specialty of {0} is {1}.",
    660: "The strength of {0} is {1}.",
    661: "The advantage of {0} is {1}.",
    662: "The benefit of {0} is {1}.",
    663: "The upside of {0} is {1}.",
    664: "The downside of {0} is {1}.",
    665: "The drawback of {0} is {1}.",
    666: "The disadvantage of {0} is {1}.",
    667: "The limitation of {0} is {1}.",
    668: "The constraint of {0} is {1}.",
    669: "The restriction of {0} is {1}.",
    670: "The requirement for {0} is {1}.",
    671: "The prerequisite for {0} is {1}.",
    672: "The condition for {0} is {1}.",
    673: "The dependency of {0} is {1}.",
    674: "The reliance on {0} means {1}.",
    675: "The need for {0} arises from {1}.",
    676: "The demand for {0} comes from {1}.",
    677: "The purpose of {0} is to {1}.",
    678: "The goal of {0} is to {1}.",
    679: "The objective of {0} is to {1}.",
    680: "The aim of {0} is to {1}.",
    681: "The intention of {0} is to {1}.",
    682: "The function of {0} is to {1}.",
    683: "The role of {0} is to {1}.",
    684: "The job of {0} is to {1}.",
    685: "The task of {0} is to {1}.",
    686: "The responsibility of {0} is to {1}.",
}

# ============================================================================
# TEMPLATE CATEGORIES
# ============================================================================

TEMPLATE_CATEGORIES = {
    'limitations': (0, 9),
    'facts': (10, 19),
    'definitions': (20, 29),
    'code_examples': (30, 39),
    'instructions': (40, 49),
    'affirmations': (50, 59),
    'comparisons': (60, 69),
    'explanations': (70, 79),
    'enumerations': (80, 89),
    'recommendations': (90, 99),
    'clarifications': (100, 119),
    'discovered': (200, 686),
}

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_template(template_id: int) -> str:
    """Get template pattern by ID"""
    if template_id in CORE_TEMPLATES:
        return CORE_TEMPLATES[template_id]
    elif template_id in DISCOVERED_TEMPLATES:
        return DISCOVERED_TEMPLATES[template_id]
    else:
        raise ValueError(f"Unknown template ID: {template_id}")


def get_category_templates(category: str) -> Dict[int, str]:
    """Get all templates in a category"""
    if category not in TEMPLATE_CATEGORIES:
        raise ValueError(f"Unknown category: {category}")

    start_id, end_id = TEMPLATE_CATEGORIES[category]
    templates = {}

    for template_id in range(start_id, end_id + 1):
        try:
            templates[template_id] = get_template(template_id)
        except ValueError:
            # Template ID not yet defined
            pass

    return templates


def get_all_templates() -> Dict[int, str]:
    """Get all defined templates"""
    all_templates = {}
    all_templates.update(CORE_TEMPLATES)
    all_templates.update(DISCOVERED_TEMPLATES)
    return all_templates


def get_slot_count(template_id: int) -> int:
    """Count parameter slots in template"""
    pattern = get_template(template_id)
    return pattern.count('{')


def get_template_stats() -> Dict[str, any]:
    """Get template library statistics"""
    all_templates = get_all_templates()

    category_counts = {}
    for category, (start_id, end_id) in TEMPLATE_CATEGORIES.items():
        count = len(get_category_templates(category))
        category_counts[category] = count

    return {
        'total_templates': len(all_templates),
        'core_templates': len(CORE_TEMPLATES),
        'discovered_templates': len(DISCOVERED_TEMPLATES),
        'categories': category_counts,
        'coverage_target': 0.72,  # 72% from Appendix C
        'avg_ratio_target': 5.1,  # 5.1:1 from Appendix C
    }


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == '__main__':
    stats = get_template_stats()
    print("=" * 70)
    print("AURA TEMPLATE LIBRARY - APPENDIX C SPECIFICATION")
    print("=" * 70)
    print(f"Total Templates: {stats['total_templates']}")
    print(f"Core Templates: {stats['core_templates']}")
    print(f"Discovered Templates: {stats['discovered_templates']}")
    print(f"\nTarget Coverage: {stats['coverage_target'] * 100}% of AI messages")
    print(f"Target Avg Ratio: {stats['avg_ratio_target']}:1")
    print("\nCategory Breakdown:")
    for category, count in stats['categories'].items():
        print(f"  {category}: {count} templates")
    print("=" * 70)

    # Show examples
    print("\nExample Templates:")
    print(f"  ID 0 (Limitations): {get_template(0)}")
    print(f"  ID 11 (Facts): {get_template(11)}")
    print(f"  ID 30 (Code): {get_template(30)}")
    print(f"  ID 50 (Affirmations): {get_template(50)}")
    print(f"  ID 200 (Discovered): {get_template(200)}")
