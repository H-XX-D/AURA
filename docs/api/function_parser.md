# Function Parser API Reference

## Overview

The `function_parser.py` module provides advanced function parsing and analysis capabilities for AURA compression, enabling intelligent code understanding and optimization of function-based data structures.

## Classes

### FunctionParser

Main function parsing and analysis class.

#### Constructor

```python
FunctionParser(
    language: str = "python",
    enable_caching: bool = True,
    max_cache_size: int = 1000,
    enable_ast_analysis: bool = True
)
```

**Parameters:**
- `language`: Programming language ("python", "javascript", "java")
- `enable_caching`: Enable parse result caching (default: True)
- `max_cache_size`: Maximum cache entries (default: 1000)
- `enable_ast_analysis`: Enable AST-based analysis (default: True)

## Methods

### parse_function(function_code)

Parse function code and extract metadata.

```python
def parse_function(self, function_code: str) -> FunctionMetadata:
```

**Parameters:**
- `function_code`: Function source code

**Returns:**
- `FunctionMetadata`: Parsed function information

### extract_signature(function_code)

Extract function signature information.

```python
def extract_signature(self, function_code: str) -> FunctionSignature:
```

**Parameters:**
- `function_code`: Function source code

**Returns:**
- `FunctionSignature`: Function signature details

### analyze_complexity(function_code)

Analyze function complexity metrics.

```python
def analyze_complexity(self, function_code: str) -> ComplexityMetrics:
```

**Parameters:**
- `function_code`: Function source code

**Returns:**
- `ComplexityMetrics`: Complexity analysis results

### extract_dependencies(function_code)

Extract function dependencies and imports.

```python
def extract_dependencies(self, function_code: str) -> DependencyInfo:
```

**Parameters:**
- `function_code`: Function source code

**Returns:**
- `DependencyInfo`: Function dependencies

### optimize_for_compression(function_code)

Optimize function code for better compression.

```python
def optimize_for_compression(self, function_code: str) -> OptimizedFunction:
```

**Parameters:**
- `function_code`: Original function code

**Returns:**
- `OptimizedFunction`: Optimized version with metadata

### detect_patterns(function_code)

Detect common code patterns in function.

```python
def detect_patterns(self, function_code: str) -> List[CodePattern]:
```

**Parameters:**
- `function_code`: Function source code

**Returns:**
- `List[CodePattern]`: Detected patterns

## FunctionMetadata Class

```python
@dataclass
class FunctionMetadata:
    name: str
    signature: FunctionSignature
    complexity: ComplexityMetrics
    dependencies: DependencyInfo
    patterns: List[CodePattern]
    language: str
    line_count: int
    token_count: int
    estimated_compression_ratio: float
```

## FunctionSignature Class

```python
@dataclass
class FunctionSignature:
    name: str
    parameters: List[ParameterInfo]
    return_type: Optional[str]
    decorators: List[str]
    is_async: bool
    is_generator: bool
```

## ComplexityMetrics Class

```python
@dataclass
class ComplexityMetrics:
    cyclomatic_complexity: int
    cognitive_complexity: int
    nesting_depth: int
    halstead_volume: float
    maintainability_index: float
```

## Usage Examples

### Basic Function Parsing

```python
from aura_compression.function_parser import FunctionParser

parser = FunctionParser(language="python")

# Parse a function
code = '''
def calculate_total(items: List[float], tax_rate: float = 0.08) -> float:
    """Calculate total with tax."""
    subtotal = sum(items)
    tax = subtotal * tax_rate
    return subtotal + tax
'''

metadata = parser.parse_function(code)

print(f"Function: {metadata.name}")
print(f"Parameters: {len(metadata.signature.parameters)}")
print(f"Complexity: {metadata.complexity.cyclomatic_complexity}")
print(f"Estimated compression ratio: {metadata.estimated_compression_ratio:.2f}")
```

### Signature Extraction

```python
signature = parser.extract_signature(code)

print(f"Name: {signature.name}")
print(f"Async: {signature.is_async}")
print(f"Return type: {signature.return_type}")

print("Parameters:")
for param in signature.parameters:
    print(f"  {param.name}: {param.type_hint} = {param.default_value}")
```

### Complexity Analysis

```python
complexity = parser.analyze_complexity(code)

print("Complexity Metrics:")
print(f"  Cyclomatic: {complexity.cyclomatic_complexity}")
print(f"  Cognitive: {complexity.cognitive_complexity}")
print(f"  Nesting depth: {complexity.nesting_depth}")
print(f"  Halstead volume: {complexity.halstead_volume:.2f}")
print(f"  Maintainability: {complexity.maintainability_index:.2f}")
```

### Dependency Extraction

```python
deps = parser.extract_dependencies(code)

print("Dependencies:")
print(f"  Imports: {deps.imports}")
print(f"  Functions called: {deps.function_calls}")
print(f"  Classes used: {deps.class_usage}")
print(f"  External modules: {deps.external_modules}")
```

### Compression Optimization

```python
optimized = parser.optimize_for_compression(code)

print("Optimization Results:")
print(f"  Original size: {optimized.original_size} chars")
print(f"  Optimized size: {optimized.optimized_size} chars")
print(f"  Improvement: {optimized.compression_improvement:.1%}")
print(f"  Applied optimizations: {optimized.applied_optimizations}")

print("Optimized code:")
print(optimized.code)
```

### Pattern Detection

```python
patterns = parser.detect_patterns(code)

print("Detected Patterns:")
for pattern in patterns:
    print(f"  {pattern.name}: {pattern.confidence:.2f} confidence")
    print(f"    Description: {pattern.description}")
    print(f"    Location: lines {pattern.start_line}-{pattern.end_line}")
```

## Language Support

### Python Support

```python
python_parser = FunctionParser(language="python")

# Supports all Python features
python_code = '''
async def process_data(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    @lru_cache(maxsize=128)
    def validate_item(item: Dict) -> bool:
        return all(k in item for k in ['id', 'value'])

    results = []
    for item in data.values():
        if validate_item(item):
            processed = await process_item(item)
            results.append(processed)

    return results
'''

metadata = python_parser.parse_function(python_code)
```

### JavaScript Support

```python
js_parser = FunctionParser(language="javascript")

js_code = '''
async function processData(data) {
    const validateItem = memoize((item) => {
        return item.id && item.value;
    });

    const results = [];
    for (const item of Object.values(data)) {
        if (validateItem(item)) {
            const processed = await processItem(item);
            results.push(processed);
        }
    }

    return results;
}
'''

metadata = js_parser.parse_function(js_code)
```

### Java Support

```python
java_parser = FunctionParser(language="java")

java_code = '''
public CompletableFuture<List<Map<String, Object>>> processData(
        Map<String, Object> data) {

    Function<Map<String, Object>, Boolean> validateItem = memoize(item ->
        item.containsKey("id") && item.containsKey("value")
    );

    List<CompletableFuture<Map<String, Object>>> futures = data.values()
        .stream()
        .filter(validateItem::apply)
        .map(this::processItem)
        .collect(Collectors.toList());

    return CompletableFuture.allOf(futures.toArray(new CompletableFuture[0]))
        .thenApply(v -> futures.stream()
            .map(CompletableFuture::join)
            .collect(Collectors.toList()));
}
'''

metadata = java_parser.parse_function(java_code)
```

## Advanced Analysis Features

### AST-Based Analysis

```python
# Enable deep AST analysis
parser = FunctionParser(enable_ast_analysis=True)

# Analyze control flow
flow_analysis = parser.analyze_control_flow(code)
print(f"Control flow paths: {flow_analysis.paths}")
print(f"Loop structures: {flow_analysis.loops}")
print(f"Conditional branches: {flow_analysis.branches}")

# Analyze data flow
data_flow = parser.analyze_data_flow(code)
print(f"Variable definitions: {data_flow.definitions}")
print(f"Variable usages: {data_flow.usages}")
print(f"Data dependencies: {data_flow.dependencies}")
```

### Performance Profiling

```python
# Profile function execution patterns
profile = parser.profile_function(code)

print("Performance Profile:")
print(f"  Estimated execution time: {profile.estimated_time_ms:.2f} ms")
print(f"  Memory allocation: {profile.memory_allocation_kb:.1f} KB")
print(f"  I/O operations: {profile.io_operations}")
print(f"  External calls: {profile.external_calls}")
```

### Security Analysis

```python
# Analyze security implications
security = parser.analyze_security(code)

print("Security Analysis:")
print(f"  Risk level: {security.risk_level}")
print(f"  Vulnerabilities: {security.vulnerabilities}")
print(f"  Input validation: {security.input_validation}")
print(f"  Data exposure: {security.data_exposure}")
```

## Optimization Strategies

### Code Minification

```python
# Remove unnecessary whitespace and comments
minified = parser.minify_code(code)
print(f"Minified from {len(code)} to {len(minified)} characters")
```

### Variable Renaming

```python
# Rename variables for better compression
renamed = parser.optimize_variable_names(code)
print("Variable optimization applied")
print(renamed)
```

### Dead Code Elimination

```python
# Remove unreachable code
optimized = parser.eliminate_dead_code(code)
print("Dead code removed")
```

### Constant Folding

```python
# Pre-compute constant expressions
folded = parser.fold_constants(code)
print("Constants folded")
```

## Caching and Performance

### Parse Result Caching

```python
# Enable caching for repeated parsing
parser = FunctionParser(enable_caching=True, max_cache_size=2000)

# First parse (cached)
metadata1 = parser.parse_function(code)

# Second parse (from cache - faster)
metadata2 = parser.parse_function(code)

print(f"Cache hit rate: {parser.get_cache_stats()['hit_rate']:.1%}")
```

### Batch Processing

```python
# Parse multiple functions efficiently
functions = [func1_code, func2_code, func3_code]
results = parser.parse_functions_batch(functions)

for i, metadata in enumerate(results):
    print(f"Function {i+1}: {metadata.name}, complexity: {metadata.complexity.cyclomatic_complexity}")
```

### Parallel Processing

```python
import concurrent.futures

# Parse functions in parallel
with concurrent.futures.ThreadPoolExecutor() as executor:
    futures = [executor.submit(parser.parse_function, code) for code in function_codes]
    results = [future.result() for future in concurrent.futures.as_completed(futures)]
```

## Integration with Compression Engine

### Function-Aware Compression

```python
from aura_compression.compression_engine import CompressionEngine

class FunctionAwareCompressor(CompressionEngine):
    def __init__(self):
        super().__init__()
        self.parser = FunctionParser()

    def compress_function_code(self, code: str) -> bytes:
        # Parse function first
        metadata = self.parser.parse_function(code)

        # Choose compression strategy based on analysis
        if metadata.complexity.cyclomatic_complexity > 10:
            strategy = "high_compression"
        elif metadata.language == "python":
            strategy = "python_optimized"
        else:
            strategy = "standard"

        # Optimize code for compression
        optimized = self.parser.optimize_for_compression(code)

        # Compress with chosen strategy
        return self.compress_with_strategy(optimized.code, strategy, metadata)
```

### Template Generation

```python
# Generate compression templates from function analysis
def generate_function_templates(parser: FunctionParser, functions: List[str]):
    templates = []

    for code in functions:
        metadata = parser.parse_function(code)
        patterns = parser.detect_patterns(code)

        # Create templates from common patterns
        for pattern in patterns:
            if pattern.confidence > 0.8:
                template = parser.create_template_from_pattern(pattern)
                templates.append(template)

    return templates
```

## Error Handling

### Parse Errors

```python
try:
    metadata = parser.parse_function(malformed_code)
except ParseError as e:
    print(f"Parse error: {e}")
    print(f"Line {e.line}: {e.message}")
except SyntaxError as e:
    print(f"Syntax error: {e}")
except UnsupportedLanguageError as e:
    print(f"Unsupported language: {e}")
```

### Analysis Errors

```python
try:
    complexity = parser.analyze_complexity(code)
except AnalysisError as e:
    print(f"Analysis failed: {e}")
    # Fall back to basic metrics
    complexity = parser.basic_complexity_analysis(code)
```

## Configuration

### Language-Specific Settings

```python
# Python-specific configuration
python_config = {
    "enable_type_hints": True,
    "enable_decorator_analysis": True,
    "enable_async_analysis": True,
    "max_nesting_depth": 5
}

# JavaScript configuration
js_config = {
    "enable_es6_analysis": True,
    "enable_jsx_support": False,
    "enable_typescript": True,
    "max_chain_length": 10
}

parser.configure_language("python", python_config)
```

### Performance Tuning

```python
# High-performance configuration
parser = FunctionParser(
    enable_caching=True,
    max_cache_size=5000,
    enable_ast_analysis=True,
    parallel_processing=True,
    cache_ttl_seconds=3600
)

# Memory-optimized configuration
parser = FunctionParser(
    enable_caching=False,
    enable_ast_analysis=False,
    max_parse_depth=3
)
```

## Monitoring and Metrics

### Parser Statistics

```python
stats = parser.get_statistics()

print("Parser Statistics:")
print(f"  Functions parsed: {stats['functions_parsed']}")
print(f"  Cache hit rate: {stats['cache_hit_rate']:.1%}")
print(f"  Average parse time: {stats['avg_parse_time_ms']:.2f} ms")
print(f"  Error rate: {stats['error_rate']:.2%}")
print(f"  Memory usage: {stats['memory_usage_mb']:.1f} MB")
```

### Performance Monitoring

```python
# Monitor parsing performance
with parser.performance_monitor():
    for code in function_codes:
        metadata = parser.parse_function(code)

performance_report = parser.get_performance_report()
print(f"Total parse time: {performance_report.total_time:.2f} s")
print(f"Functions per second: {performance_report.functions_per_second:.1f}")
```

## Dependencies

- `ast`: Python AST parsing
- `esprima`: JavaScript parsing (optional)
- `javalang`: Java parsing (optional)
- `lru_cache`: Caching functionality
- `concurrent.futures`: Parallel processing
- `dataclasses`: Data structures
- `typing`: Type hints

## Best Practices

### Parsing Strategy

1. **Enable caching** for repeated function parsing
2. **Use batch processing** for multiple functions
3. **Configure language-specific settings** appropriately
4. **Handle parse errors gracefully** with fallbacks

### Performance Optimization

1. **Parse once, cache results** for frequently used functions
2. **Use parallel processing** for large codebases
3. **Limit AST analysis depth** for complex functions
4. **Monitor memory usage** and adjust cache size

### Code Quality

1. **Validate function syntax** before detailed analysis
2. **Use appropriate complexity metrics** for different languages
3. **Handle language-specific features** correctly
4. **Provide meaningful error messages** for debugging

### Integration

1. **Integrate with IDEs** for real-time analysis
2. **Use with CI/CD pipelines** for code quality checks
3. **Combine with compression** for function-aware optimization
4. **Export analysis results** for reporting and monitoring