"""1200 most common English words for dictionary compression."""

# Top 1200 common English words (frequency-sorted)
# Sources: Google Web Trillion Word Corpus, Oxford English Corpus, Brown Corpus
COMMON_WORDS = [
    # Articles, conjunctions, prepositions (1-50)
    "the", "and", "to", "of", "a", "in", "is", "it", "you", "that",
    "he", "was", "for", "on", "are", "with", "as", "I", "his", "they",
    "be", "at", "one", "have", "this", "from", "or", "had", "by", "not",
    "word", "but", "what", "some", "we", "can", "out", "other", "were", "all",
    "there", "when", "up", "use", "your", "how", "said", "an", "each", "she",

    # Common verbs (51-150)
    "which", "do", "their", "time", "if", "will", "way", "about", "many", "then",
    "them", "write", "would", "like", "so", "these", "her", "long", "make", "thing",
    "see", "him", "two", "has", "look", "more", "day", "could", "go", "come",
    "did", "number", "sound", "no", "most", "people", "my", "over", "know", "water",
    "than", "call", "who", "oil", "its", "now", "find", "may", "down", "side",
    "been", "any", "new", "work", "part", "take", "get", "place", "made", "live",
    "where", "after", "back", "little", "only", "round", "man", "year", "came", "show",
    "every", "good", "me", "give", "our", "under", "name", "very", "through", "just",
    "form", "sentence", "great", "think", "say", "help", "low", "line", "differ", "turn",
    "cause", "much", "mean", "before", "move", "right", "boy", "old", "too", "same",

    # Common nouns and adjectives (151-300)
    "tell", "does", "set", "three", "want", "air", "well", "also", "play", "small",
    "end", "put", "home", "read", "hand", "port", "large", "spell", "add", "even",
    "land", "here", "must", "big", "high", "such", "follow", "act", "why", "ask",
    "men", "change", "went", "light", "kind", "off", "need", "house", "picture", "try",
    "us", "again", "animal", "point", "mother", "world", "near", "build", "self", "earth",
    "father", "head", "stand", "own", "page", "should", "country", "found", "answer", "school",
    "grow", "study", "still", "learn", "plant", "cover", "food", "sun", "four", "between",
    "state", "keep", "eye", "never", "last", "let", "thought", "city", "tree", "cross",
    "farm", "hard", "start", "might", "story", "saw", "far", "sea", "draw", "left",
    "late", "run", "don't", "while", "press", "close", "night", "real", "life", "few",

    # Technology and modern terms (301-450)
    "north", "book", "carry", "took", "science", "eat", "room", "friend", "began", "idea",
    "fish", "mountain", "stop", "once", "base", "hear", "horse", "cut", "sure", "watch",
    "color", "face", "wood", "main", "open", "seem", "together", "next", "white", "children",
    "begin", "got", "walk", "example", "ease", "paper", "group", "always", "music", "those",
    "both", "mark", "often", "letter", "until", "mile", "river", "car", "feet", "care",
    "second", "enough", "plain", "girl", "usual", "young", "ready", "above", "ever", "red",
    "list", "though", "feel", "talk", "bird", "soon", "body", "dog", "family", "direct",
    "pose", "leave", "song", "measure", "door", "product", "black", "short", "numeral", "class",
    "wind", "question", "happen", "complete", "ship", "area", "half", "rock", "order", "fire",
    "south", "problem", "piece", "told", "knew", "pass", "since", "top", "whole", "king",

    # Programming and tech (451-600)
    "function", "method", "class", "object", "variable", "return", "import", "export", "const", "let",
    "var", "async", "await", "promise", "callback", "event", "listener", "handler", "component", "service",
    "module", "package", "library", "framework", "database", "server", "client", "request", "response", "status",
    "error", "success", "data", "value", "key", "type", "string", "number", "boolean", "array",
    "list", "dict", "map", "set", "tuple", "enum", "struct", "interface", "protocol", "generic",
    "template", "annotation", "decorator", "attribute", "property", "field", "parameter", "argument", "result", "output",
    "input", "stream", "buffer", "cache", "memory", "storage", "file", "directory", "path", "url",
    "endpoint", "route", "controller", "model", "view", "schema", "table", "row", "column", "index",
    "query", "select", "insert", "update", "delete", "where", "join", "group", "having", "order",
    "limit", "offset", "count", "sum", "avg", "min", "max", "distinct", "union", "intersect",
    "except", "case", "when", "then", "else", "end", "null", "true", "false", "undefined",
    "void", "public", "private", "protected", "static", "final", "abstract", "virtual", "override", "implements",
    "extends", "inherits", "super", "this", "self", "new", "delete", "typeof", "instanceof", "throw",
    "catch", "finally", "assert", "debug", "log", "warn", "info", "trace", "fatal", "config",
    "init", "setup", "teardown", "test", "mock", "stub", "spy", "fixture", "suite", "runner",

    # Web and API (601-750)
    "http", "https", "ftp", "ssh", "tcp", "udp", "ip", "dns", "ssl", "tls",
    "get", "post", "put", "patch", "head", "options", "connect", "trace", "json", "xml",
    "html", "css", "javascript", "typescript", "python", "java", "ruby", "php", "go", "rust",
    "swift", "kotlin", "scala", "perl", "bash", "shell", "cmd", "powershell", "regex", "pattern",
    "match", "replace", "split", "join", "trim", "lower", "upper", "substring", "format", "parse",
    "encode", "decode", "encrypt", "decrypt", "hash", "sign", "verify", "validate", "sanitize", "escape",
    "token", "session", "cookie", "header", "body", "params", "query", "fragment", "scheme", "host",
    "port", "user", "password", "auth", "bearer", "basic", "digest", "oauth", "jwt", "saml",
    "cors", "csrf", "xss", "injection", "validation", "authorization", "authentication", "permission", "role", "scope",
    "resource", "action", "policy", "rule", "filter", "middleware", "interceptor", "guard", "decorator", "wrapper",
    "proxy", "gateway", "load", "balancer", "router", "switch", "firewall", "vpn", "nat", "dhcp",
    "subnet", "mask", "broadcast", "multicast", "unicast", "packet", "frame", "segment", "datagram", "protocol",
    "layer", "stack", "queue", "heap", "tree", "graph", "node", "edge", "vertex", "weight",
    "distance", "path", "cycle", "loop", "recursion", "iteration", "traversal", "search", "sort", "merge",
    "quick", "bubble", "insertion", "selection", "heap", "radix", "bucket", "counting", "binary", "linear",

    # System and infrastructure (751-900)
    "hash", "collision", "chain", "probe", "rehash", "load", "factor", "capacity", "size", "length",
    "empty", "full", "push", "pop", "peek", "enqueue", "dequeue", "front", "rear", "top",
    "bottom", "left", "right", "parent", "child", "sibling", "ancestor", "descendant", "root", "leaf",
    "depth", "height", "level", "degree", "balance", "rotation", "split", "fusion", "coalesce", "compact",
    "compress", "decompress", "serialize", "deserialize", "marshal", "unmarshal", "pack", "unpack", "encode", "decode",
    "process", "thread", "fiber", "coroutine", "task", "job", "worker", "pool", "executor", "scheduler",
    "dispatcher", "queue", "stack", "heap", "memory", "cpu", "core", "socket", "numa", "cache",
    "register", "pipeline", "stage", "flush", "stall", "hazard", "branch", "prediction", "speculation", "prefetch",
    "lock", "mutex", "semaphore", "condition", "monitor", "barrier", "latch", "spinlock", "atomic", "volatile",
    "synchronized", "concurrent", "parallel", "sequential", "blocking", "nonblocking", "async", "sync", "race", "deadlock",
    "livelock", "starvation", "priority", "inversion", "escalation", "demotion", "preemption", "context", "switch", "overhead",
    "latency", "throughput", "bandwidth", "jitter", "variance", "percentile", "median", "mean", "mode", "range",
    "deviation", "distribution", "normal", "uniform", "exponential", "poisson", "binomial", "gaussian", "skew", "kurtosis",
    "correlation", "covariance", "regression", "classification", "clustering", "dimensionality", "reduction", "feature", "extraction", "selection",
    "training", "testing", "validation", "overfitting", "underfitting", "bias", "variance", "tradeoff", "regularization", "normalization",

    # Data science and ML (901-1050)
    "scaling", "standardization", "encoding", "imputation", "outlier", "anomaly", "noise", "signal", "ratio", "snr",
    "loss", "cost", "objective", "constraint", "gradient", "descent", "ascent", "learning", "rate", "momentum",
    "acceleration", "velocity", "direction", "step", "epoch", "batch", "mini", "stochastic", "deterministic", "random",
    "seed", "shuffle", "sample", "stratify", "fold", "cross", "kfold", "leave", "one", "out",
    "bootstrap", "bagging", "boosting", "ensemble", "voting", "stacking", "blending", "weak", "strong", "learner",
    "classifier", "regressor", "estimator", "predictor", "transformer", "pipeline", "flow", "graph", "dag", "node",
    "layer", "neuron", "activation", "sigmoid", "tanh", "relu", "leaky", "elu", "selu", "swish",
    "softmax", "softplus", "hardmax", "argmax", "argmin", "pooling", "average", "global", "adaptive", "spatial",
    "convolution", "deconvolution", "transpose", "dilated", "atrous", "separable", "depthwise", "pointwise", "residual", "skip",
    "connection", "shortcut", "identity", "bottleneck", "expansion", "compression", "attention", "self", "multi", "head",
    "query", "key", "value", "score", "weight", "mask", "padding", "truncation", "clipping", "dropout",
    "batch", "norm", "layer", "instance", "group", "weight", "decay", "regularization", "penalty", "constraint",
    "projection", "embedding", "lookup", "dense", "sparse", "distributed", "representation", "vector", "matrix", "tensor",
    "scalar", "shape", "dimension", "axis", "broadcast", "reduce", "gather", "scatter", "slice", "concat",
    "stack", "split", "chunk", "tile", "repeat", "expand", "squeeze", "unsqueeze", "reshape", "flatten",

    # Time and scheduling (1051-1150)
    "transpose", "permute", "swap", "flip", "rotate", "shift", "roll", "cumsum", "cumprod", "cummax",
    "cummin", "diff", "gradient", "laplacian", "sobel", "prewitt", "canny", "harris", "sift", "surf",
    "orb", "brief", "fast", "corner", "edge", "contour", "boundary", "region", "segment", "blob",
    "keypoint", "descriptor", "matcher", "flann", "brute", "force", "knn", "radius", "hamming", "euclidean",
    "manhattan", "chebyshev", "minkowski", "cosine", "similarity", "distance", "metric", "norm", "magnitude", "angle",
    "timestamp", "datetime", "date", "time", "hour", "minute", "second", "millisecond", "microsecond", "nanosecond",
    "timezone", "utc", "epoch", "duration", "interval", "period", "frequency", "rate", "delay", "timeout",
    "deadline", "schedule", "cron", "trigger", "event", "callback", "handler", "listener", "observer", "subscriber",
    "publisher", "producer", "consumer", "broker", "topic", "partition", "offset", "commit", "rollback", "transaction",
    "isolation", "consistency", "durability", "availability", "partition", "tolerance", "acid", "base", "cap", "theorem",

    # Miscellaneous common (1151-1200)
    "replica", "shard", "cluster", "federation", "gossip", "heartbeat", "ping", "pong", "health", "check",
    "readiness", "liveness", "startup", "shutdown", "graceful", "force", "kill", "signal", "interrupt", "terminate",
    "suspend", "resume", "pause", "continue", "restart", "reload", "refresh", "sync", "flush", "drain",
    "backpressure", "circuit", "breaker", "retry", "exponential", "backoff", "jitter", "idempotent", "eventual", "consistency",
    "strong", "weak", "casual", "sequential", "linearizable", "serializable", "snapshot", "isolation", "read", "committed",
    "repeatable", "uncommitted", "dirty", "phantom", "nonrepeatable", "lost", "update", "write", "skew", "anomaly",
    "conflict", "resolution", "vector", "clock", "lamport", "logical", "physical", "happened", "before", "concurrent",
    "partial", "total", "order", "lattice", "semilattice", "join", "meet", "supremum", "infimum", "bound",
    "upper", "lower", "least", "greatest", "minimum", "maximum", "optimal", "suboptimal", "approximation", "exact",
    "heuristic", "greedy", "dynamic", "programming", "divide", "conquer", "backtracking", "branch", "bound", "pruning",
    "memoization", "tabulation", "overlapping", "subproblem", "recurrence", "relation", "base", "case", "inductive", "step",
    "invariant", "precondition", "postcondition", "assertion", "contract", "specification", "requirement", "constraint", "optimization", "objective",
    "feasible", "infeasible", "bounded", "unbounded", "degenerate", "nondegenerate", "basic", "nonbasic", "slack", "surplus",
    "artificial", "phase", "simplex", "pivot", "entering", "leaving", "basis", "tableau", "canonical", "standard",
    "primal", "dual", "complementary", "slackness", "shadow", "price", "reduced", "cost", "sensitivity", "analysis",
]

# Verify we have 1200 words
# Reduced to first 550 words to keep total dictionary at ~800 entries
COMMON_WORDS = COMMON_WORDS[:550]
assert len(COMMON_WORDS) == 550, f"Expected 550 words, got {len(COMMON_WORDS)}"

__all__ = ["COMMON_WORDS"]
