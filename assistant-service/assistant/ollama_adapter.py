"""Native Ollama protocol boundary. No API key; no cloud or heuristic fallback."""
import json
from uuid import uuid4


def to_native_messages(messages):
    names = {}
    result = []
    for original in messages:
        message = {"role": original["role"], "content": original.get("content") or ""}
        calls = original.get("tool_calls") or []
        if calls:
            native_calls = []
            for call in calls:
                function = call["function"]
                args = function["arguments"]
                if isinstance(args, str):
                    args = json.loads(args)
                if not isinstance(args, dict):
                    raise ValueError("Tool arguments must be an object")
                names[call["id"]] = function["name"]
                native_calls.append({"function": {"name": function["name"], "arguments": args}})
            message["tool_calls"] = native_calls
        if original["role"] == "tool":
            message["tool_name"] = names[original["tool_call_id"]]
        result.append(message)
    return result


def from_native_message(message):
    if message.get("role") != "assistant":
        raise ValueError("Expected assistant message")
    content = message.get("content") or ""
    if not isinstance(content, str):
        raise ValueError("Invalid message content")
    result = {"role": "assistant", "content": content}
    calls = message.get("tool_calls") or []
    if calls:
        result["tool_calls"] = []
        for call in calls:
            function = call["function"]
            args = function["arguments"]
            if isinstance(args, str):
                args = json.loads(args)
            if not isinstance(args, dict):
                raise ValueError("Tool arguments must be an object")
            result["tool_calls"].append({
                "id": "ollama_" + uuid4().hex,
                "type": "function",
                "function": {"name": function["name"], "arguments": json.dumps(args, ensure_ascii=False)},
            })
    # Reasoning content is deliberately not displayed or persisted.
    return result
