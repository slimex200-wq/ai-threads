"""LLM backend abstraction for AI Threads.

Default policy is CLI-first:
- Claude CLI first
- Anthropic API fallback
- Codex CLI last fallback

This matches the project's goals better than API-first:
- lower direct API cost when a local subscription-backed CLI exists
- resilience against transient Anthropic API overloads
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import anthropic

from config import ANTHROPIC_API_KEY, MODEL, THREADS_LLM_BACKEND


def has_claude_cli() -> bool:
    return bool(shutil.which("claude"))


def has_codex_cli() -> bool:
    return bool(shutil.which("codex.cmd") or shutil.which("codex"))


def build_backend_order(
    preferred: str = "claude_cli",
    *,
    has_anthropic_api: bool | None = None,
    has_claude_cli: bool | None = None,
    has_codex_cli: bool | None = None,
) -> list[str]:
    has_anthropic_api = bool(ANTHROPIC_API_KEY) if has_anthropic_api is None else has_anthropic_api
    has_claude_cli = globals()["has_claude_cli"]() if has_claude_cli is None else has_claude_cli
    has_codex_cli = globals()["has_codex_cli"]() if has_codex_cli is None else has_codex_cli

    available = {
        "anthropic_api": has_anthropic_api,
        "claude_cli": has_claude_cli,
        "codex_cli": has_codex_cli,
    }

    if preferred == "auto":
        preferred_order = ["anthropic_api", "claude_cli", "codex_cli"]
    elif preferred == "anthropic_api":
        preferred_order = ["anthropic_api", "claude_cli", "codex_cli"]
    elif preferred == "codex_cli":
        preferred_order = ["codex_cli", "claude_cli", "anthropic_api"]
    else:
        preferred_order = ["claude_cli", "anthropic_api", "codex_cli"]

    return [backend for backend in preferred_order if available.get(backend)]


def is_overloaded_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "529" in text or "overloaded" in text or "overload" in text


def build_prompt_transcript(messages: list[dict[str, str]]) -> str:
    parts: list[str] = []
    for message in messages:
        role = message.get("role", "user").upper()
        content = message.get("content", "")
        parts.append(f"[{role}]\n{content}")
    return "\n\n".join(parts)


def _parse_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    match = None
    if text.startswith("{") and text.endswith("}"):
        match = text
    else:
        import re

        code_block = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
        if code_block:
            match = code_block.group(1).strip()
        else:
            brace_match = re.search(r"\{.*\}", text, re.DOTALL)
            if brace_match:
                match = brace_match.group(0)
    if not match:
        raise ValueError("No JSON object found in backend response")
    return json.loads(match)


def _request_via_anthropic_api(messages: list[dict[str, str]], *, max_tokens: int, model: str | None = None) -> dict[str, Any]:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=model or MODEL,
        max_tokens=max_tokens,
        messages=messages,
    )
    return _parse_json_object(response.content[0].text)


def _request_via_claude_cli(
    messages: list[dict[str, str]],
    *,
    schema: dict[str, Any],
    cwd: str | None = None,
) -> dict[str, Any]:
    prompt = build_prompt_transcript(messages)
    cmd = [
        "claude",
        "-p",
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(schema, ensure_ascii=False),
        prompt,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=180)
    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI failed: {result.stderr[:500] or result.stdout[:500]}")

    payload = json.loads(result.stdout)
    content = payload.get("result", "")
    if isinstance(content, dict):
        return content
    return _parse_json_object(str(content))


def _request_via_codex_cli(
    messages: list[dict[str, str]],
    *,
    schema: dict[str, Any],
    cwd: str | None = None,
) -> dict[str, Any]:
    codex_cmd = shutil.which("codex.cmd") or shutil.which("codex")
    if not codex_cmd:
        raise RuntimeError("Codex CLI not available")

    prompt = build_prompt_transcript(messages)
    with tempfile.TemporaryDirectory() as tmpdir:
        schema_path = Path(tmpdir) / "schema.json"
        output_path = Path(tmpdir) / "last_message.txt"
        schema_path.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")

        cmd = [
            codex_cmd,
            "exec",
            "--json",
            "--output-schema",
            str(schema_path),
            "-o",
            str(output_path),
            prompt,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=180)
        if result.returncode != 0:
            raise RuntimeError(f"Codex CLI failed: {result.stderr[:500] or result.stdout[:500]}")
        return _parse_json_object(output_path.read_text(encoding="utf-8"))


def request_structured_json(
    messages: list[dict[str, str]],
    *,
    schema: dict[str, Any],
    max_tokens: int,
    preferred_backend: str | None = None,
    cwd: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    preferred_backend = preferred_backend or THREADS_LLM_BACKEND
    backends = build_backend_order(preferred_backend)
    if not backends:
        raise RuntimeError("No available LLM backend")

    errors: list[str] = []
    for backend in backends:
        try:
            if backend == "claude_cli":
                return _request_via_claude_cli(messages, schema=schema, cwd=cwd)
            if backend == "anthropic_api":
                return _request_via_anthropic_api(messages, max_tokens=max_tokens, model=model)
            if backend == "codex_cli":
                return _request_via_codex_cli(messages, schema=schema, cwd=cwd)
        except Exception as exc:
            errors.append(f"{backend}: {exc}")
            # CLI / fallback path: continue through all backends.
            if backend == "anthropic_api" and not is_overloaded_error(exc):
                continue
            continue

    raise RuntimeError("All LLM backends failed: " + " | ".join(errors))
