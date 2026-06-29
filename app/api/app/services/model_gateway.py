import json
import time
from typing import AsyncIterator

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models.audit import ModelCallAudit
from ..models.config import AppModelConfig

_FERNET_KEY: bytes | None = None


def _get_fernet():
    from cryptography.fernet import Fernet
    import base64
    import hashlib
    global _FERNET_KEY
    if _FERNET_KEY is None:
        digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        _FERNET_KEY = base64.urlsafe_b64encode(digest)
    return Fernet(_FERNET_KEY)


def encrypt_token(token: str) -> str:
    return _get_fernet().encrypt(token.encode()).decode()


def decrypt_token(enc: str) -> str:
    return _get_fernet().decrypt(enc.encode()).decode()


async def _resolve_config(db: AsyncSession) -> tuple[str, str, str, str]:
    """返回 (base_url, token, model, protocol)。

    protocol 取自 settings.AI_PROTOCOL，值为 "openai" 或 "anthropic"。
    CodePlan（智谱代码套餐）key 必须走 anthropic 兼容端点 /api/anthropic。
    """
    stmt = select(AppModelConfig).limit(1)
    cfg = (await db.execute(stmt)).scalar_one_or_none()
    if cfg and cfg.gateway_base_url and cfg.gateway_token_enc:
        base_url = cfg.gateway_base_url.rstrip("/")
        token = decrypt_token(cfg.gateway_token_enc)
        model = cfg.default_model or settings.AI_MODEL
        return base_url, token, model, settings.AI_PROTOCOL
    return (settings.AI_BASE_URL.rstrip("/"), settings.AI_API_KEY,
            settings.AI_MODEL, settings.AI_PROTOCOL)


def _split_system(messages: list[dict]) -> tuple[str | None, list[dict]]:
    """把 role=system 的消息抽出来（Anthropic 要求 system 在顶层，不在 messages 里）。"""
    sys_parts = [m["content"] for m in messages if m.get("role") == "system" and m.get("content")]
    rest = [m for m in messages if m.get("role") != "system"]
    return ("\n\n".join(sys_parts) if sys_parts else None), rest


def _normalize_anthropic_to_openai(data: dict) -> dict:
    """把 Anthropic Messages 响应归一化为 OpenAI chat/completions 形状。

    统一返回 {"choices":[{"message":{"content": ...}}], "usage": {...}, "model": ...}
    让所有调用方继续读 resp["choices"][0]["message"]["content"]。
    """
    blocks = data.get("content") or []
    text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    usage = data.get("usage") or {}
    in_tok = usage.get("input_tokens", 0)
    out_tok = usage.get("output_tokens", 0)
    return {
        "choices": [{"message": {"content": text, "role": "assistant"}, "finish_reason": data.get("stop_reason")}],
        "usage": {"prompt_tokens": in_tok, "completion_tokens": out_tok,
                  "total_tokens": in_tok + out_tok},
        "model": data.get("model", ""),
    }


async def chat_completion(
    db: AsyncSession,
    messages: list[dict],
    *,
    scene: str = "review",
    user_id: int | None = None,
    model_override: str | None = None,
) -> dict:
    base_url, token, model, protocol = await _resolve_config(db)
    if model_override:
        model = model_override
    t0 = time.time()

    if protocol == "anthropic":
        # 智谱 CodePlan / Anthropic 兼容端点：POST {base}/v1/messages
        system, rest = _split_system(messages)
        body: dict = {"model": model, "max_tokens": 4096,
                      "messages": rest, "temperature": 0.3}
        if system:
            body["system"] = system
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(
                f"{base_url}/v1/messages",
                headers={"x-api-key": token, "anthropic-version": "2023-06-01",
                         "Content-Type": "application/json"},
                json=body,
            )
            resp.raise_for_status()
            data = _normalize_anthropic_to_openai(resp.json())
    else:
        # OpenAI 兼容端点：POST {base}/chat/completions
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"model": model, "messages": messages, "temperature": 0.3},
            )
            resp.raise_for_status()
            data = resp.json()

    latency = int((time.time() - t0) * 1000)
    usage = data.get("usage", {})
    audit = ModelCallAudit(
        scene=scene, model_used=model,
        tokens=usage.get("total_tokens"),
        latency_ms=latency, status="ok", user_id=user_id,
    )
    db.add(audit)
    await db.flush()
    return data


async def chat_completion_stream(
    db: AsyncSession,
    messages: list[dict],
    *,
    scene: str = "review",
    user_id: int | None = None,
) -> AsyncIterator[str]:
    """流式（OpenAI 协议）。Anthropic 协议暂不支持流式（应用审查走非流式 chat_completion）。"""
    base_url, token, model, protocol = await _resolve_config(db)
    if protocol == "anthropic":
        # 回退为非流式：一次性取完，再伪造成单个 chunk yield
        data = await chat_completion(db, messages, scene=scene, user_id=user_id)
        yield json.dumps(data)
        return
    t0 = time.time()
    total_tokens = 0
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "POST",
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages, "temperature": 0.3, "stream": True},
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    chunk = line[6:]
                    if chunk.strip() == "[DONE]":
                        break
                    yield chunk
    latency = int((time.time() - t0) * 1000)
    audit = ModelCallAudit(
        scene=scene, model_used=model,
        tokens=total_tokens, latency_ms=latency,
        status="ok", user_id=user_id,
    )
    db.add(audit)
    await db.flush()
