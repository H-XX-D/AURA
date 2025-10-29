#!/usr/bin/env python3
"""
Function Call Parser - Patent Claim 19
Parse and route AI-to-AI function calls using metadata
"""
import json
import re
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple


@dataclass
class FunctionCall:
    """
    Parsed function call from AI traffic (Claim 19)
    """
    function_name: str
    arguments: Dict[str, Any]
    function_id: Optional[int] = None  # For metadata encoding
    routing_hint: Optional[str] = None  # Handler/service to route to

    def to_metadata(self) -> Dict[str, Any]:
        """Convert to metadata for fast-path routing (Claim 19)"""
        return {
            'type': 'function_call',
            'function_name': self.function_name,
            'function_id': self.function_id,
            'argument_count': len(self.arguments),
            'routing_hint': self.routing_hint,
        }


class FunctionCallParser:
    """
    Parser for AI-to-AI function calls (Claim 19)
    Detects and extracts function calls from AI messages for metadata encoding
    """

    def __init__(self):
        # Function ID registry (for metadata encoding)
        self.function_registry: Dict[str, int] = {
            'execute_task': 1,
            'query_database': 2,
            'call_api': 3,
            'process_data': 4,
            'generate_response': 5,
            'validate_input': 6,
            'transform_data': 7,
            'send_notification': 8,
            'schedule_job': 9,
            'get_status': 10,
        }

        # Routing hints (which service handles which function)
        self.routing_map: Dict[str, str] = {
            'execute_task': 'task_executor',
            'query_database': 'database_service',
            'call_api': 'api_gateway',
            'process_data': 'data_processor',
            'generate_response': 'response_generator',
            'validate_input': 'validator',
            'transform_data': 'transformer',
            'send_notification': 'notification_service',
            'schedule_job': 'scheduler',
            'get_status': 'status_service',
        }

    def parse(self, text: str) -> Optional[FunctionCall]:
        """
        Parse function call from AI message (Claim 19)

        Supports multiple formats:
        1. JSON: {"function": "name", "args": {...}}
        2. Python-style: function_name(arg1=value1, arg2=value2)
        3. Natural language: "Execute task with parameters..."

        Args:
            text: AI message text

        Returns:
            FunctionCall if detected, None otherwise
        """
        # Try JSON format first
        function_call = self._parse_json_format(text)
        if function_call:
            return function_call

        # Try Python-style format
        function_call = self._parse_python_format(text)
        if function_call:
            return function_call

        # Try natural language format
        function_call = self._parse_natural_language(text)
        if function_call:
            return function_call

        return None

    def _parse_json_format(self, text: str) -> Optional[FunctionCall]:
        """Parse JSON function call format"""
        try:
            # Try parsing the entire text as JSON first
            data = json.loads(text.strip())
            function_name = data.get('function')
            arguments = data.get('args', data.get('arguments', {}))

            if function_name:
                return FunctionCall(
                    function_name=function_name,
                    arguments=arguments,
                    function_id=self.function_registry.get(function_name),
                    routing_hint=self.routing_map.get(function_name),
                )
        except json.JSONDecodeError:
            # Try extracting JSON from text
            try:
                json_match = re.search(r'\{.*"function".*\}', text, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(0))
                    function_name = data.get('function')
                    arguments = data.get('args', data.get('arguments', {}))

                    if function_name:
                        return FunctionCall(
                            function_name=function_name,
                            arguments=arguments,
                            function_id=self.function_registry.get(function_name),
                            routing_hint=self.routing_map.get(function_name),
                        )
            except Exception:
                pass

        return None

    def _parse_python_format(self, text: str) -> Optional[FunctionCall]:
        """Parse Python-style function call format"""
        # Match: function_name(arg1=value1, arg2=value2)
        pattern = r'(\w+)\s*\((.*?)\)'
        match = re.search(pattern, text)

        if match:
            function_name = match.group(1)
            args_str = match.group(2)

            # Parse arguments
            arguments = {}
            if args_str:
                # Simple key=value parsing
                for arg in args_str.split(','):
                    if '=' in arg:
                        key, value = arg.split('=', 1)
                        arguments[key.strip()] = value.strip().strip('"\'')

            # Only return if it's a recognized function
            if function_name in self.function_registry:
                return FunctionCall(
                    function_name=function_name,
                    arguments=arguments,
                    function_id=self.function_registry.get(function_name),
                    routing_hint=self.routing_map.get(function_name),
                )

        return None

    def _parse_natural_language(self, text: str) -> Optional[FunctionCall]:
        """Parse natural language function call description"""
        text_lower = text.lower()

        # Look for action keywords
        for function_name in self.function_registry.keys():
            # Convert function_name to natural language (e.g., execute_task -> "execute task")
            natural_form = function_name.replace('_', ' ')

            if natural_form in text_lower:
                # Extract parameters (very simple heuristic)
                arguments = self._extract_parameters(text)

                return FunctionCall(
                    function_name=function_name,
                    arguments=arguments,
                    function_id=self.function_registry.get(function_name),
                    routing_hint=self.routing_map.get(function_name),
                )

        return None

    def _extract_parameters(self, text: str) -> Dict[str, Any]:
        """Extract parameters from natural language text"""
        # Very simple parameter extraction
        # Look for patterns like: "with X", "using Y", "for Z"
        params = {}

        # Extract quoted strings as parameters
        quotes = re.findall(r'"([^"]*)"', text)
        for i, quote in enumerate(quotes):
            params[f'param_{i}'] = quote

        # Extract key: value patterns
        kv_pattern = r'(\w+):\s*([^,;.\n]+)'
        for match in re.finditer(kv_pattern, text):
            key, value = match.groups()
            params[key] = value.strip()

        return params

    def register_function(self, function_name: str, function_id: int, routing_hint: str):
        """
        Register new function for parsing (Claim 19)

        Args:
            function_name: Name of function
            function_id: Unique ID for metadata encoding
            routing_hint: Service/handler to route to
        """
        self.function_registry[function_name] = function_id
        self.routing_map[function_name] = routing_hint


class AItoAIOrchestrator:
    """
    Orchestration layer for AI-to-AI communication (Claim 19)
    Routes function calls without decompressing argument payloads
    """

    def __init__(self):
        self.parser = FunctionCallParser()
        self.handlers: Dict[str, Any] = {}

    def register_handler(self, routing_hint: str, handler):
        """Register handler for routing hint"""
        self.handlers[routing_hint] = handler

    def route_from_metadata(self, metadata: Dict[str, Any]) -> Optional[str]:
        """
        Route message based on metadata without decompression (Claim 19)

        Args:
            metadata: Extracted metadata from compressed message

        Returns:
            Routing hint (handler name) or None
        """
        if metadata.get('type') == 'function_call':
            return metadata.get('routing_hint')

        return None

    def dispatch(self, function_call: FunctionCall) -> Any:
        """
        Dispatch function call to appropriate handler (Claim 19)

        Args:
            function_call: Parsed function call

        Returns:
            Result from handler
        """
        routing_hint = function_call.routing_hint

        if routing_hint in self.handlers:
            handler = self.handlers[routing_hint]
            return handler(function_call.function_name, function_call.arguments)

        raise ValueError(f"No handler registered for: {routing_hint}")

    def process_message(self, text: str, compressed_data: bytes, metadata: Dict[str, Any]) -> Tuple[bool, Any]:
        """
        Process AI-to-AI message with fast-path routing (Claim 19)

        Args:
            text: Decompressed message (only if needed)
            compressed_data: Compressed message
            metadata: Extracted metadata

        Returns:
            (used_fast_path, result)
        """
        # Try metadata-only routing first (Claim 19)
        routing_hint = self.route_from_metadata(metadata)

        if routing_hint and routing_hint in self.handlers:
            # Fast path: route without full parsing
            # Reconstruct function call from metadata
            function_call = FunctionCall(
                function_name=metadata.get('function_name', 'unknown'),
                arguments={},  # Would extract from compressed payload if needed
                function_id=metadata.get('function_id'),
                routing_hint=routing_hint,
            )

            result = self.dispatch(function_call)
            return True, result  # Used fast path

        # Slow path: parse full message
        function_call = self.parser.parse(text)

        if function_call:
            result = self.dispatch(function_call)
            return False, result  # Did not use fast path

        return False, None


# Example handlers for demonstration
def task_executor_handler(function_name: str, arguments: Dict[str, Any]) -> str:
    """Example handler for task execution"""
    return f"Executed {function_name} with {len(arguments)} arguments"


def database_query_handler(function_name: str, arguments: Dict[str, Any]) -> str:
    """Example handler for database queries"""
    return f"Queried database: {function_name}"


def api_gateway_handler(function_name: str, arguments: Dict[str, Any]) -> str:
    """Example handler for API calls"""
    return f"Called API: {function_name}"
