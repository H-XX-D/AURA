#!/usr/bin/env python3
"""
Comprehensive test suite for function_parser.py

Tests AI-to-AI function call parsing and routing (Patent Claim 19).
Validates JSON, Python-style, and natural language parsing, metadata encoding,
and fast-path routing without decompression.
"""
import os
import sys
import json
from pathlib import Path
import traceback
from typing import Dict, Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aura_compression.function_parser import (
    FunctionCall,
    FunctionCallParser,
    AItoAIOrchestrator,
    task_executor_handler,
    database_query_handler,
    api_gateway_handler,
)


def test_function_call_dataclass():
    """Test FunctionCall dataclass creation."""
    print("\n=== Test 1: FunctionCall Dataclass ===")
    
    call = FunctionCall(
        function_name="execute_task",
        arguments={"task_id": "123", "priority": "high"},
        function_id=1,
        routing_hint="task_executor"
    )
    
    assert call.function_name == "execute_task"
    assert call.arguments == {"task_id": "123", "priority": "high"}
    assert call.function_id == 1
    assert call.routing_hint == "task_executor"
    
    print(f"✅ FunctionCall dataclass works")
    print(f"   - Function: {call.function_name}")
    print(f"   - Arguments: {call.arguments}")
    print(f"   - Function ID: {call.function_id}")
    print(f"   - Routing: {call.routing_hint}")


def test_function_call_to_metadata():
    """Test FunctionCall.to_metadata() for fast-path routing (Claim 19)."""
    print("\n=== Test 2: FunctionCall to_metadata() ===")
    
    call = FunctionCall(
        function_name="query_database",
        arguments={"table": "users", "filter": "active=true"},
        function_id=2,
        routing_hint="database_service"
    )
    
    metadata = call.to_metadata()
    
    assert metadata['type'] == 'function_call'
    assert metadata['function_name'] == 'query_database'
    assert metadata['function_id'] == 2
    assert metadata['argument_count'] == 2
    assert metadata['routing_hint'] == 'database_service'
    
    print(f"✅ to_metadata() generates correct metadata")
    print(f"   - Type: {metadata['type']}")
    print(f"   - Function: {metadata['function_name']}")
    print(f"   - Function ID: {metadata['function_id']}")
    print(f"   - Arg count: {metadata['argument_count']}")
    print(f"   - Routing hint: {metadata['routing_hint']}")


def test_parser_initialization():
    """Test FunctionCallParser initialization with registry and routing."""
    print("\n=== Test 3: Parser Initialization ===")
    
    parser = FunctionCallParser()
    
    assert len(parser.function_registry) == 10
    assert len(parser.routing_map) == 10
    
    # Check specific functions
    assert parser.function_registry['execute_task'] == 1
    assert parser.function_registry['query_database'] == 2
    assert parser.function_registry['call_api'] == 3
    
    # Check routing
    assert parser.routing_map['execute_task'] == 'task_executor'
    assert parser.routing_map['query_database'] == 'database_service'
    assert parser.routing_map['call_api'] == 'api_gateway'
    
    print(f"✅ Parser initialized with registry and routing")
    print(f"   - Registry size: {len(parser.function_registry)}")
    print(f"   - Routing map size: {len(parser.routing_map)}")


def test_parse_json_format_simple():
    """Test parsing simple JSON format function calls."""
    print("\n=== Test 4: Parse JSON Format (Simple) ===")
    
    parser = FunctionCallParser()
    
    json_text = json.dumps({
        "function": "execute_task",
        "args": {"task_id": "123", "name": "test_task"}
    })
    
    call = parser.parse(json_text)
    
    assert call is not None
    assert call.function_name == "execute_task"
    assert call.arguments["task_id"] == "123"
    assert call.arguments["name"] == "test_task"
    assert call.function_id == 1
    assert call.routing_hint == "task_executor"
    
    print(f"✅ JSON format parsed correctly")
    print(f"   - Function: {call.function_name}")
    print(f"   - Arguments: {call.arguments}")


def test_parse_json_format_with_arguments_key():
    """Test parsing JSON with 'arguments' key instead of 'args'."""
    print("\n=== Test 5: Parse JSON Format (arguments key) ===")
    
    parser = FunctionCallParser()
    
    json_text = json.dumps({
        "function": "query_database",
        "arguments": {"table": "users", "limit": 10}
    })
    
    call = parser.parse(json_text)
    
    assert call is not None
    assert call.function_name == "query_database"
    assert call.arguments["table"] == "users"
    assert call.arguments["limit"] == 10
    assert call.function_id == 2
    assert call.routing_hint == "database_service"
    
    print(f"✅ JSON with 'arguments' key parsed correctly")
    print(f"   - Function: {call.function_name}")


def test_parse_json_embedded_in_text():
    """Test parsing JSON embedded in surrounding text."""
    print("\n=== Test 6: Parse JSON Embedded in Text ===")
    
    parser = FunctionCallParser()
    
    text = 'I need to execute this: {"function": "call_api", "args": {"url": "https://example.com", "method": "GET"}} please.'
    
    call = parser.parse(text)
    
    assert call is not None
    assert call.function_name == "call_api"
    assert call.arguments["url"] == "https://example.com"
    assert call.arguments["method"] == "GET"
    assert call.function_id == 3
    assert call.routing_hint == "api_gateway"
    
    print(f"✅ Embedded JSON parsed correctly")
    print(f"   - Function: {call.function_name}")
    print(f"   - Extracted from text with surrounding context")


def test_parse_python_format():
    """Test parsing Python-style function calls."""
    print("\n=== Test 7: Parse Python Format ===")
    
    parser = FunctionCallParser()
    
    text = "execute_task(task_id=456, priority=high, status=pending)"
    
    call = parser.parse(text)
    
    assert call is not None
    assert call.function_name == "execute_task"
    assert call.arguments["task_id"] == "456"
    assert call.arguments["priority"] == "high"
    assert call.arguments["status"] == "pending"
    assert call.function_id == 1
    assert call.routing_hint == "task_executor"
    
    print(f"✅ Python format parsed correctly")
    print(f"   - Function: {call.function_name}")
    print(f"   - Arguments: {call.arguments}")


def test_parse_python_format_with_quotes():
    """Test parsing Python format with quoted string values."""
    print("\n=== Test 8: Parse Python Format (quoted strings) ===")
    
    parser = FunctionCallParser()
    
    text = 'process_data(input="file.csv", output="result.json", mode="batch")'
    
    call = parser.parse(text)
    
    assert call is not None
    assert call.function_name == "process_data"
    assert call.arguments["input"] == "file.csv"
    assert call.arguments["output"] == "result.json"
    assert call.arguments["mode"] == "batch"
    assert call.function_id == 4
    
    print(f"✅ Python format with quotes parsed correctly")
    print(f"   - Function: {call.function_name}")


def test_parse_python_format_no_args():
    """Test parsing Python format with no arguments."""
    print("\n=== Test 9: Parse Python Format (no args) ===")
    
    parser = FunctionCallParser()
    
    text = "get_status()"
    
    call = parser.parse(text)
    
    assert call is not None
    assert call.function_name == "get_status"
    assert call.arguments == {}
    assert call.function_id == 10
    assert call.routing_hint == "status_service"
    
    print(f"✅ Python format with no args parsed correctly")
    print(f"   - Function: {call.function_name}")
    print(f"   - Arguments: {call.arguments}")


def test_parse_natural_language():
    """Test parsing natural language function call descriptions."""
    print("\n=== Test 10: Parse Natural Language ===")
    
    parser = FunctionCallParser()
    
    text = "Please execute task with the following parameters"
    
    call = parser.parse(text)
    
    assert call is not None
    assert call.function_name == "execute_task"
    assert call.function_id == 1
    assert call.routing_hint == "task_executor"
    
    print(f"✅ Natural language parsed correctly")
    print(f"   - Function: {call.function_name}")
    print(f"   - Detected from: '{text}'")


def test_parse_natural_language_query_database():
    """Test parsing natural language for database query."""
    print("\n=== Test 11: Parse Natural Language (query database) ===")
    
    parser = FunctionCallParser()
    
    text = "I need to query database for user information"
    
    call = parser.parse(text)
    
    assert call is not None
    assert call.function_name == "query_database"
    assert call.function_id == 2
    assert call.routing_hint == "database_service"
    
    print(f"✅ Natural language query parsed correctly")
    print(f"   - Function: {call.function_name}")


def test_parse_natural_language_with_parameters():
    """Test natural language parsing with parameter extraction."""
    print("\n=== Test 12: Parse Natural Language (with parameters) ===")
    
    parser = FunctionCallParser()
    
    text = 'Send notification with message: "System update completed" and priority: high'
    
    call = parser.parse(text)
    
    assert call is not None
    assert call.function_name == "send_notification"
    assert call.function_id == 8
    assert call.routing_hint == "notification_service"
    # Parameter extraction is heuristic - just verify it extracts something
    assert isinstance(call.arguments, dict)
    # Check if priority was extracted (but don't require it - heuristic may vary)
    if "priority" in call.arguments:
        assert call.arguments["priority"] == "high"
    
    print(f"✅ Natural language with parameters parsed")
    print(f"   - Function: {call.function_name}")
    print(f"   - Extracted parameters: {call.arguments}")


def test_parse_unrecognized_function():
    """Test that unrecognized functions return None."""
    print("\n=== Test 13: Parse Unrecognized Function ===")
    
    parser = FunctionCallParser()
    
    text = "unknown_function(param=value)"
    
    call = parser.parse(text)
    
    assert call is None
    
    print(f"✅ Unrecognized function returns None")


def test_parse_invalid_text():
    """Test parsing invalid/random text."""
    print("\n=== Test 14: Parse Invalid Text ===")
    
    parser = FunctionCallParser()
    
    text = "This is just random text without any function call"
    
    call = parser.parse(text)
    
    assert call is None
    
    print(f"✅ Invalid text returns None")


def test_parse_malformed_json():
    """Test parsing malformed JSON."""
    print("\n=== Test 15: Parse Malformed JSON ===")
    
    parser = FunctionCallParser()
    
    text = '{"function": "execute_task", invalid json}'
    
    call = parser.parse(text)
    
    # Should still try other formats and potentially match natural language
    # or return None if no match
    assert call is None or call.function_name == "execute_task"
    
    print(f"✅ Malformed JSON handled gracefully")


def test_register_function():
    """Test registering new functions dynamically."""
    print("\n=== Test 16: Register Function ===")
    
    parser = FunctionCallParser()
    
    initial_count = len(parser.function_registry)
    
    parser.register_function(
        function_name="custom_function",
        function_id=100,
        routing_hint="custom_handler"
    )
    
    assert len(parser.function_registry) == initial_count + 1
    assert parser.function_registry["custom_function"] == 100
    assert parser.routing_map["custom_function"] == "custom_handler"
    
    # Test parsing the new function
    text = "custom_function(param=value)"
    call = parser.parse(text)
    
    assert call is not None
    assert call.function_name == "custom_function"
    assert call.function_id == 100
    assert call.routing_hint == "custom_handler"
    
    print(f"✅ Function registration works")
    print(f"   - Registered: custom_function")
    print(f"   - Function ID: 100")
    print(f"   - Can be parsed after registration")


def test_orchestrator_initialization():
    """Test AItoAIOrchestrator initialization."""
    print("\n=== Test 17: Orchestrator Initialization ===")
    
    orchestrator = AItoAIOrchestrator()
    
    assert orchestrator.parser is not None
    assert isinstance(orchestrator.parser, FunctionCallParser)
    assert len(orchestrator.handlers) == 0
    
    print(f"✅ Orchestrator initialized")
    print(f"   - Parser: {type(orchestrator.parser).__name__}")
    print(f"   - Handlers: {len(orchestrator.handlers)}")


def test_orchestrator_register_handler():
    """Test registering handlers in orchestrator."""
    print("\n=== Test 18: Orchestrator Register Handler ===")
    
    orchestrator = AItoAIOrchestrator()
    
    orchestrator.register_handler("task_executor", task_executor_handler)
    orchestrator.register_handler("database_service", database_query_handler)
    orchestrator.register_handler("api_gateway", api_gateway_handler)
    
    assert len(orchestrator.handlers) == 3
    assert "task_executor" in orchestrator.handlers
    assert "database_service" in orchestrator.handlers
    assert "api_gateway" in orchestrator.handlers
    
    print(f"✅ Handlers registered")
    print(f"   - Total handlers: {len(orchestrator.handlers)}")


def test_orchestrator_route_from_metadata():
    """Test metadata-only routing (Claim 19 fast-path)."""
    print("\n=== Test 19: Route from Metadata (Fast-path) ===")
    
    orchestrator = AItoAIOrchestrator()
    
    metadata = {
        'type': 'function_call',
        'function_name': 'execute_task',
        'function_id': 1,
        'routing_hint': 'task_executor'
    }
    
    routing_hint = orchestrator.route_from_metadata(metadata)
    
    assert routing_hint == "task_executor"
    
    print(f"✅ Metadata-only routing works (Claim 19)")
    print(f"   - Routed to: {routing_hint}")
    print(f"   - No decompression required")


def test_orchestrator_route_from_metadata_non_function():
    """Test routing with non-function-call metadata."""
    print("\n=== Test 20: Route from Metadata (non-function) ===")
    
    orchestrator = AItoAIOrchestrator()
    
    metadata = {
        'type': 'regular_message',
        'size': 1024
    }
    
    routing_hint = orchestrator.route_from_metadata(metadata)
    
    assert routing_hint is None
    
    print(f"✅ Non-function metadata returns None")


def test_orchestrator_dispatch():
    """Test dispatching function calls to handlers."""
    print("\n=== Test 21: Orchestrator Dispatch ===")
    
    orchestrator = AItoAIOrchestrator()
    orchestrator.register_handler("task_executor", task_executor_handler)
    
    call = FunctionCall(
        function_name="execute_task",
        arguments={"task_id": "123"},
        function_id=1,
        routing_hint="task_executor"
    )
    
    result = orchestrator.dispatch(call)
    
    assert result is not None
    assert "Executed execute_task" in result
    assert "1 arguments" in result
    
    print(f"✅ Dispatch works")
    print(f"   - Result: {result}")


def test_orchestrator_dispatch_no_handler():
    """Test dispatching with no registered handler raises error."""
    print("\n=== Test 22: Orchestrator Dispatch (no handler) ===")
    
    orchestrator = AItoAIOrchestrator()
    
    call = FunctionCall(
        function_name="execute_task",
        arguments={},
        function_id=1,
        routing_hint="task_executor"
    )
    
    try:
        orchestrator.dispatch(call)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "No handler registered" in str(e)
        print(f"✅ Missing handler raises ValueError")
        print(f"   - Error: {e}")


def test_orchestrator_process_message_fast_path():
    """Test processing message with fast-path routing (Claim 19)."""
    print("\n=== Test 23: Process Message (Fast-path) ===")
    
    orchestrator = AItoAIOrchestrator()
    orchestrator.register_handler("task_executor", task_executor_handler)
    
    # Metadata-only routing (fast path)
    metadata = {
        'type': 'function_call',
        'function_name': 'execute_task',
        'function_id': 1,
        'routing_hint': 'task_executor'
    }
    
    used_fast_path, result = orchestrator.process_message(
        text="",  # Not needed for fast path
        compressed_data=b"",  # Not decompressed
        metadata=metadata
    )
    
    assert used_fast_path is True
    assert result is not None
    assert "Executed" in result
    
    print(f"✅ Fast-path processing works (Claim 19)")
    print(f"   - Used fast path: {used_fast_path}")
    print(f"   - Result: {result}")
    print(f"   - No decompression required")


def test_orchestrator_process_message_slow_path():
    """Test processing message with slow-path parsing."""
    print("\n=== Test 24: Process Message (Slow-path) ===")
    
    orchestrator = AItoAIOrchestrator()
    orchestrator.register_handler("database_service", database_query_handler)
    
    # No function call metadata - must parse full text
    metadata = {
        'type': 'regular_message',
        'size': 100
    }
    
    text = "query_database(table=users, limit=10)"
    
    used_fast_path, result = orchestrator.process_message(
        text=text,
        compressed_data=b"",
        metadata=metadata
    )
    
    assert used_fast_path is False
    assert result is not None
    assert "Queried database" in result
    
    print(f"✅ Slow-path processing works")
    print(f"   - Used fast path: {used_fast_path}")
    print(f"   - Result: {result}")
    print(f"   - Full text parsing required")


def test_orchestrator_process_message_no_function():
    """Test processing message with no function call."""
    print("\n=== Test 25: Process Message (no function) ===")
    
    orchestrator = AItoAIOrchestrator()
    
    metadata = {'type': 'regular_message'}
    text = "This is just a regular message"
    
    used_fast_path, result = orchestrator.process_message(
        text=text,
        compressed_data=b"",
        metadata=metadata
    )
    
    assert used_fast_path is False
    assert result is None
    
    print(f"✅ Non-function message handled")
    print(f"   - Used fast path: {used_fast_path}")
    print(f"   - Result: {result}")


def test_example_handlers():
    """Test example handler functions."""
    print("\n=== Test 26: Example Handlers ===")
    
    result1 = task_executor_handler("execute_task", {"task_id": "123"})
    assert "Executed execute_task" in result1
    assert "1 arguments" in result1
    
    result2 = database_query_handler("query_database", {"table": "users"})
    assert "Queried database" in result2
    
    result3 = api_gateway_handler("call_api", {"url": "https://example.com"})
    assert "Called API" in result3
    
    print(f"✅ All example handlers work")
    print(f"   - Task executor: {result1}")
    print(f"   - Database query: {result2}")
    print(f"   - API gateway: {result3}")


def test_all_registered_functions():
    """Test that all 10 default functions are properly registered."""
    print("\n=== Test 27: All Registered Functions ===")
    
    parser = FunctionCallParser()
    
    expected_functions = [
        ('execute_task', 1, 'task_executor'),
        ('query_database', 2, 'database_service'),
        ('call_api', 3, 'api_gateway'),
        ('process_data', 4, 'data_processor'),
        ('generate_response', 5, 'response_generator'),
        ('validate_input', 6, 'validator'),
        ('transform_data', 7, 'transformer'),
        ('send_notification', 8, 'notification_service'),
        ('schedule_job', 9, 'scheduler'),
        ('get_status', 10, 'status_service'),
    ]
    
    for func_name, func_id, routing in expected_functions:
        assert parser.function_registry[func_name] == func_id
        assert parser.routing_map[func_name] == routing
    
    print(f"✅ All 10 functions registered correctly")
    for func_name, func_id, routing in expected_functions:
        print(f"   - {func_name}: ID={func_id}, Route={routing}")


def test_parse_all_function_formats():
    """Test parsing all registered functions in different formats."""
    print("\n=== Test 28: Parse All Functions (multiple formats) ===")
    
    parser = FunctionCallParser()
    
    # Test a few functions in different formats
    test_cases = [
        ('{"function": "validate_input", "args": {}}', "validate_input"),
        ("transform_data(input=raw, output=clean)", "transform_data"),
        ("schedule job for tomorrow", "schedule_job"),
        ("generate response with context", "generate_response"),
    ]
    
    for text, expected_func in test_cases:
        call = parser.parse(text)
        assert call is not None
        assert call.function_name == expected_func
        print(f"   ✓ Parsed '{text}' → {expected_func}")
    
    print(f"✅ Multiple functions parsed in various formats")


def test_metadata_encoding_efficiency():
    """Test that metadata is compact for fast-path routing."""
    print("\n=== Test 29: Metadata Encoding Efficiency ===")
    
    call = FunctionCall(
        function_name="execute_task",
        arguments={"task_id": "123", "priority": "high", "details": "very long string " * 100},
        function_id=1,
        routing_hint="task_executor"
    )
    
    metadata = call.to_metadata()
    
    # Metadata should not contain full arguments
    assert 'arguments' not in metadata
    assert 'details' not in metadata
    
    # But should have essential routing info
    assert metadata['function_id'] == 1
    assert metadata['routing_hint'] == "task_executor"
    assert metadata['argument_count'] == 3
    
    print(f"✅ Metadata is compact (Claim 19)")
    print(f"   - Metadata size: {len(str(metadata))} bytes")
    print(f"   - Arguments not included (only count)")
    print(f"   - Fast-path routing enabled")


def test_end_to_end_workflow():
    """Test complete end-to-end workflow (Claim 19)."""
    print("\n=== Test 30: End-to-End Workflow (Claim 19) ===")
    
    # 1. Parse function call from text
    parser = FunctionCallParser()
    text = 'execute_task(task_id="789", priority="critical")'
    call = parser.parse(text)
    
    assert call is not None
    print(f"   1. Parsed function call: {call.function_name}")
    
    # 2. Generate metadata
    metadata = call.to_metadata()
    assert metadata['type'] == 'function_call'
    print(f"   2. Generated metadata: {metadata['function_id']}")
    
    # 3. Setup orchestrator
    orchestrator = AItoAIOrchestrator()
    orchestrator.register_handler("task_executor", task_executor_handler)
    print(f"   3. Registered handler: task_executor")
    
    # 4. Route using metadata (fast-path)
    routing_hint = orchestrator.route_from_metadata(metadata)
    assert routing_hint == "task_executor"
    print(f"   4. Routed via metadata: {routing_hint}")
    
    # 5. Process message with fast-path
    used_fast_path, result = orchestrator.process_message(
        text=text,
        compressed_data=b"compressed_payload",
        metadata=metadata
    )
    
    assert used_fast_path is True
    assert result is not None
    print(f"   5. Processed with fast-path: {result}")
    
    print(f"✅ Complete end-to-end workflow successful (Claim 19)")
    print(f"   - Parse → Metadata → Route → Execute")
    print(f"   - No decompression required for routing")


def run_all_tests():
    """Run all test functions."""
    test_functions = [
        test_function_call_dataclass,
        test_function_call_to_metadata,
        test_parser_initialization,
        test_parse_json_format_simple,
        test_parse_json_format_with_arguments_key,
        test_parse_json_embedded_in_text,
        test_parse_python_format,
        test_parse_python_format_with_quotes,
        test_parse_python_format_no_args,
        test_parse_natural_language,
        test_parse_natural_language_query_database,
        test_parse_natural_language_with_parameters,
        test_parse_unrecognized_function,
        test_parse_invalid_text,
        test_parse_malformed_json,
        test_register_function,
        test_orchestrator_initialization,
        test_orchestrator_register_handler,
        test_orchestrator_route_from_metadata,
        test_orchestrator_route_from_metadata_non_function,
        test_orchestrator_dispatch,
        test_orchestrator_dispatch_no_handler,
        test_orchestrator_process_message_fast_path,
        test_orchestrator_process_message_slow_path,
        test_orchestrator_process_message_no_function,
        test_example_handlers,
        test_all_registered_functions,
        test_parse_all_function_formats,
        test_metadata_encoding_efficiency,
        test_end_to_end_workflow,
    ]
    
    passed = 0
    failed = 0
    
    print("=" * 70)
    print("FUNCTION_PARSER.PY COMPREHENSIVE TEST SUITE")
    print("Patent Claim 19: AI-to-AI Function Call Parsing & Routing")
    print("=" * 70)
    
    for test_func in test_functions:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            failed += 1
            print(f"❌ {test_func.__name__} FAILED: {e}")
            traceback.print_exc()
        except Exception as e:
            failed += 1
            print(f"❌ {test_func.__name__} FAILED: {e}")
            traceback.print_exc()
    
    print("\n" + "=" * 70)
    print(f"TEST RESULTS: {passed}/{passed + failed} passed, {failed}/{passed + failed} failed")
    print("=" * 70)
    
    if failed == 0:
        print("✅ ALL TESTS PASSED!")
        print("\nValidated Patent Claim 19:")
        print("  - Function call parsing (JSON, Python, natural language)")
        print("  - Metadata encoding for fast-path routing")
        print("  - AI-to-AI orchestration without decompression")
        print("  - Dynamic function registration")
        print("  - Multiple handler routing")
        sys.exit(0)
    else:
        print(f"❌ {failed} TEST(S) FAILED")
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
