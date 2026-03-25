"""Shared utility functions for the pipeline engine."""

from __future__ import annotations

import json


def strip_markdown_fences(content: str) -> str:
    """Remove markdown code fences from LLM output."""
    if not content.startswith("```"):
        return content
    lines = content.splitlines()
    if lines[-1].strip() == "```":
        return "\n".join(lines[1:-1])
    return "\n".join(lines[1:])


def truncate_json_safe(text: str, max_chars: int) -> str:
    """Truncate text to max_chars without breaking JSON structure.

    If valid JSON, truncates values intelligently.
    If not JSON, truncates at line boundary.
    """
    if len(text) <= max_chars:
        return text

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            result = {}
            for k, v in data.items():
                if isinstance(v, str) and len(v) > 200:
                    result[k] = v[:200] + "..."
                elif isinstance(v, list) and len(json.dumps(v, ensure_ascii=False)) > 500:
                    result[k] = v[:5]
                else:
                    result[k] = v
            serialized = json.dumps(result, ensure_ascii=False, indent=2)
            if len(serialized) <= max_chars:
                return serialized
            # Last resort: keep first N keys
            result2 = {}
            for k, v in result.items():
                result2[k] = v
                if len(json.dumps(result2, ensure_ascii=False)) > max_chars - 50:
                    result2["_truncated"] = True
                    break
            return json.dumps(result2, ensure_ascii=False, indent=2)
        elif isinstance(data, list):
            result_list = []
            current_len = 2
            for item in data:
                item_str = json.dumps(item, ensure_ascii=False)
                if current_len + len(item_str) + 2 > max_chars:
                    break
                result_list.append(item)
                current_len += len(item_str) + 2
            return json.dumps(result_list, ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, TypeError):
        pass

    # Fallback: truncate at line boundary
    lines = text.splitlines(keepends=True)
    result_text = []
    current_len = 0
    for line in lines:
        if current_len + len(line) > max_chars:
            break
        result_text.append(line)
        current_len += len(line)
    truncated = "".join(result_text)
    if len(truncated) < len(text):
        truncated += f"\n... [truncated at {max_chars} chars]"
    return truncated
