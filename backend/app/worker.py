from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime

import httpx
from celery import Celery
from sqlalchemy import select

from app.ai import _cost
from app.config import get_settings
from app.database import session_factory
from app.freshrss import decrypt_secret, sync_connection
from app.models import AIArtifact, AIFunction, AIJob, AIJobEntry, AIModel, AIProvider, Entry, FreshRSSConnection, Notification

settings = get_settings()
celery = Celery("rss_ai", broker=settings.redis_url, backend=settings.redis_url)
celery.conf.update(task_default_queue="rss_ai", timezone="UTC", broker_connection_retry_on_startup=True, beat_schedule={"sync-due-freshrss-connections": {"task": "rss_ai.sync_due_connections", "schedule": 60.0}})

@celery.task(name="rss_ai.health_ping")
def health_ping() -> str: return "ok"

async def _call_provider(provider: AIProvider, model: AIModel, prompt: str) -> tuple[str, dict]:
    key = decrypt_secret(provider.encrypted_api_key) if provider.encrypted_api_key else None
    base = (provider.base_url or "").rstrip("/")
    async with httpx.AsyncClient(timeout=provider.timeout_seconds) as client:
        if provider.provider_type in {"openai_compatible", "openai"}:
            response = await client.post(f"{base}/v1/chat/completions", headers={"Authorization": f"Bearer {key}"} if key else {}, json={"model": model.model_key, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2})
            response.raise_for_status(); data = response.json(); return data["choices"][0]["message"]["content"], data.get("usage", {})
        if provider.provider_type == "ollama":
            response = await client.post(f"{base}/api/generate", json={"model": model.model_key, "prompt": prompt, "stream": False})
            response.raise_for_status(); data = response.json(); return data["response"], {"prompt_tokens": data.get("prompt_eval_count", 0), "completion_tokens": data.get("eval_count", 0)}
        if provider.provider_type == "libretranslate":
            response = await client.post(f"{base}/translate", json={"q": prompt, "source": "auto", "target": "zh", "format": "text", "api_key": key or ""})
            response.raise_for_status(); data = response.json(); return data["translatedText"], {"prompt_tokens": len(prompt) // 4, "completion_tokens": len(data["translatedText"]) // 4}
        if provider.provider_type == "deepl":
            response = await client.post(f"{base}/v2/translate", headers={"Authorization": f"DeepL-Auth-Key {key}"} if key else {}, data={"text": prompt, "target_lang": "ZH"})
            response.raise_for_status(); data = response.json(); result = data["translations"][0]["text"]; return result, {"prompt_tokens": len(prompt) // 4, "completion_tokens": len(result) // 4}
        if provider.provider_type == "google_cloud_translation":
            response = await client.post(f"{base}/v2", params={"key": key}, json={"q": prompt, "target": "zh"})
            response.raise_for_status(); data = response.json(); result = data["data"]["translations"][0]["translatedText"]; return result, {"prompt_tokens": len(prompt) // 4, "completion_tokens": len(result) // 4}
    raise RuntimeError(f"Provider type {provider.provider_type} does not support this AI function")

async def _execute(job_id: str) -> None:
    async with session_factory() as session:
        job = await session.get(AIJob, job_id)
        if not job or job.status == "cancelled": return
        job.status = "running"; job.started_at = datetime.now(UTC); job.progress = 5; await session.commit()
        try:
            function = await session.get(AIFunction, job.function_id)
            entries = list((await session.scalars(select(Entry).join(AIJobEntry, AIJobEntry.entry_id == Entry.id).where(AIJobEntry.job_id == job.id).order_by(Entry.published_at.desc()))).all())
            if not function or not entries: raise RuntimeError("AI job has no function or source articles")
            models = list((await session.scalars(select(AIModel).where(AIModel.enabled.is_(True)).order_by(AIModel.priority))).all())
            if not models: raise RuntimeError("No enabled AI model is configured")
            result: str | None = None; usage: dict = {}; failures: list[str] = []
            content = "\n\n".join(f"# {entry.title}\n{entry.content_text or entry.content_html or ''}" for entry in entries)
            prompt = function.prompt_template.replace("{content}", content)
            for model in models:
                provider = await session.get(AIProvider, model.provider_id)
                if not provider or not provider.enabled or provider.health_status == "unhealthy": continue
                try:
                    result, usage = await _call_provider(provider, model, prompt); job.provider_id = provider.id; job.model_id = model.id; break
                except Exception as error: failures.append(str(error))
            if result is None: raise RuntimeError("; ".join(failures) or "No healthy provider")
            config = hashlib.sha256(f"{function.id}:{function.prompt_version}".encode()).hexdigest()
            session.add(AIArtifact(job_id=job.id, entry_id=entries[0].id if len(entries) == 1 else None, artifact_type=function.function_key, language="zh", content_markdown=result, content_hash=hashlib.sha256(result.encode()).hexdigest(), prompt_version=function.prompt_version, model_id=job.model_id, configuration_hash=config))
            model = await session.get(AIModel, job.model_id)
            if model: job.estimated_cost = _cost(model, int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0)))
            job.status = "succeeded"; job.progress = 100; job.usage_json = json.dumps(usage); job.finished_at = datetime.now(UTC); session.add(Notification(title="AI 任务完成", body=f"{function.name} 已完成")); await session.commit()
        except Exception as error:
            job.status = "failed"; job.error_json = json.dumps({"message": str(error)}); job.finished_at = datetime.now(UTC); session.add(Notification(title="AI 任务失败", body=str(error)[:500])); await session.commit()

@celery.task(name="rss_ai.execute_ai_job")
def execute_ai_job(job_id: str) -> None: asyncio.run(_execute(job_id))

async def _sync_due_connections() -> int:
    async with session_factory() as session:
        connections = list((await session.scalars(select(FreshRSSConnection))).all()); now = datetime.now(UTC); count = 0
        for connection in connections:
            if connection.last_sync_at and (now - connection.last_sync_at).total_seconds() < connection.sync_interval: continue
            try: await sync_connection(session, connection, 500); count += 1
            except Exception: continue
        return count

@celery.task(name="rss_ai.sync_due_connections")
def sync_due_connections() -> int: return asyncio.run(_sync_due_connections())
