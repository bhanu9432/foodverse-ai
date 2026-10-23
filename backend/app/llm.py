"""Thin wrapper around the Claude API: vision + reasoning, always returning validated JSON."""
import json
import re
import urllib.error
import urllib.request

from fastapi import HTTPException

from . import config

_client = None


def client():
    """Create the Anthropic client lazily so the app can start without a key."""
    global _client
    if _client is None:
        if not config.ANTHROPIC_API_KEY:
            raise HTTPException(
                503, "ANTHROPIC_API_KEY is not set (or set GEMINI_API_KEY for the free option). Add it to the server settings and restart."
            )
        import anthropic

        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def provider() -> str:
    """Claude if its key is set, otherwise Gemini if its key is set."""
    if config.ANTHROPIC_API_KEY:
        return "claude"
    if config.GEMINI_API_KEY:
        return "gemini"
    return "none"


def configured() -> bool:
    return provider() != "none"


def active_model() -> str:
    return config.GEMINI_MODEL if provider() == "gemini" else config.MODEL


def image_block(b64: str) -> dict:
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}}


def _extract_json(text: str):
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = min([i for i in (text.find("{"), text.find("[")) if i != -1], default=-1)
    if start == -1:
        raise ValueError("no JSON found")
    depth, in_str, esc = 0, False, False
    open_c = text[start]
    close_c = "}" if open_c == "{" else "]"
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == open_c:
            depth += 1
        elif ch == close_c:
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError("unterminated JSON")


def _gemini_parts(content) -> list[dict]:
    """Convert our Claude-style content (string or list of blocks) into Gemini parts."""
    if isinstance(content, str):
        return [{"text": content or " "}]
    parts = []
    for b in content:
        if b.get("type") == "image":
            src = b["source"]
            parts.append({"inline_data": {"mime_type": src["media_type"], "data": src["data"]}})
        else:
            parts.append({"text": b.get("text", "") or " "})
    return parts


def _gemini_complete(system: str, msgs: list[dict], max_tokens: int) -> str:
    contents = [
        {"role": "model" if m["role"] == "assistant" else "user", "parts": _gemini_parts(m["content"])} for m in msgs
    ]
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": contents,
        # thinkingBudget 0: otherwise hidden "thinking" tokens can eat the output budget and cut the JSON short.
        "generationConfig": {"maxOutputTokens": max_tokens, "thinkingConfig": {"thinkingBudget": 0}},
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": config.GEMINI_API_KEY},
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise HTTPException(429, "The free Gemini limit was reached. Wait a minute and try again.")
        raise HTTPException(502, f"The AI service returned an error ({e.code}). Check GEMINI_API_KEY and try again.")
    except Exception as e:
        raise HTTPException(502, f"The AI service could not be reached: {type(e).__name__}.")
    cands = data.get("candidates") or []
    parts = (cands[0].get("content") or {}).get("parts", []) if cands else []
    return "".join(p.get("text", "") for p in parts)


def complete(system: str, content: list[dict] | str, max_tokens: int = 2048, messages: list[dict] | None = None) -> str:
    """One model call. `content` is the user turn; pass `messages` for multi-turn chat."""
    msgs = messages if messages is not None else [{"role": "user", "content": content}]
    if provider() == "gemini":
        return _gemini_complete(system, msgs, max_tokens)
    try:
        resp = client().messages.create(model=config.MODEL, max_tokens=max_tokens, system=system, messages=msgs)
    except HTTPException:
        raise
    except Exception as e:  # network, auth, rate limit
        raise HTTPException(502, f"The AI service returned an error: {type(e).__name__}. Check your API key and try again.")
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")


def complete_json(system: str, content: list[dict] | str, validate, max_tokens: int = 2048, retries: int = 1):
    """Ask for JSON, parse it, and run `validate(obj)` (which returns the cleaned object or raises ValueError)."""
    system = system + "\n\nReply with a single JSON object only. No prose, no markdown fences."
    last = ""
    for attempt in range(retries + 1):
        prompt = content
        if attempt and isinstance(content, list):
            prompt = content + [{"type": "text", "text": f"Your previous reply was invalid ({last}). Return corrected JSON only."}]
        elif attempt:
            prompt = f"{content}\n\nYour previous reply was invalid ({last}). Return corrected JSON only."
        raw = complete(system, prompt, max_tokens)
        try:
            return validate(_extract_json(raw))
        except (ValueError, KeyError, TypeError) as e:
            last = str(e)[:200]
    raise HTTPException(502, "The AI response could not be understood. Please try again.")
