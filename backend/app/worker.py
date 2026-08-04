from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime

import httpx
from celery import Celery
from sqlalchemy import select

from app.config import get_settings
from app.database import session_factory
from app.freshrss import decrypt_secret
from app.models import AIArtifact, AIFunction, AIJob, AIJobEntry, AIModel, AIProvider, Entry, FreshRSSConnection, Notification
from app.freshrss import sync_connection

settings = get_settings()
celery = Celery("rss_ai", broker=settings.redis_url, backend=settings.redis_url)
celery.conf.update(
    task_default_queue="rss_ai",
    timezone="UTC",
    broker_connection_retry_on_startup=True,
    beat_schedule={"sync-due-freshrss-connections": {"task": "rss_ai.sync_due_connections", "schedule": 60.0}},
)


@celery.task(name="rss_ai.health_ping")
def health_ping() -> str:
    """Minimal task proving the Phase 0 worker can process a safe task."""

    return "ok"


async def _call_provider(provider: AIProvider, model: AIModel, prompt: str) -> tuple[str, dict]:
    key = decrypt_secret(provider.encrypted_api_key) if provider.encrypted_api_key else None
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    base = (provider.base_url or "").rstrip("/")
    async with httpx.AsyncClient(timeout=provider.timeout_seconds) as client:
        if provider.provider_type in {"openai_compatible", "openai"}:
            response = await client.post(f"{base}/v1/chat/completions", headers=headers, json={"model": model.model_key, "messages": [{"role":"user","content":prompt}], "temperature":0.2})
            response.raise_for_status(); data=response.json(); return data["choices"][0]["message"]["content"], data.get("usage", {})
        if provider.provider_type == "ollama":
            response = await client.post(f"{base}/api/generate", json={"model": model.model_key,"prompt":prompt,"stream":False})
            response.raise_for_status(); data=response.json(); return data["response"], {"prompt_tokens":data.get("prompt_eval_count",0),"completion_tokens":data.get("eval_count",0)}
    raise RuntimeError(f"Provider type {provider.provider_type} does not support generative AI")


async def _execute(job_id: str) -> None:
    async with session_factory() as session:
        job = await session.get(AIJob, job_id)
        if not job or job.status == "cancelled": return
        job.status="running";job.started_at=datetime.now(UTC);job.progress=5;await session.commit()
        try:
            function=await session.get(AIFunction,job.function_id)
            entries=list((await session.scalars(select(Entry).join(AIJobEntry,AIJobEntry.entry_id==Entry.id).where(AIJobEntry.job_id==job.id).order_by(Entry.published_at.desc()))).all())
            models=list((await session.scalars(select(AIModel).where(AIModel.enabled==True).order_by(AIModel.priority))).all())
            if not models: raise RuntimeError("No enabled AI model is configured")
            failures=[]; result=None; usage={}
            content="\n\n".join(f"# {x.title}\n{x.content_text or x.content_html or ''}" for x in entries)
            prompt=function.prompt_template.replace("{content}",content)
            for model in models:
                provider=await session.get(AIProvider,model.provider_id)
                if not provider or not provider.enabled or provider.health_status=="unhealthy": continue
                try: result,usage=await _call_provider(provider,model,prompt);job.provider_id=provider.id;job.model_id=model.id;break
                except Exception as error: failures.append(str(error))
            if result is None: raise RuntimeError("; ".join(failures) or "No healthy provider")
            cfg=hashlib.sha256(f"{function.id}:{function.prompt_version}".encode()).hexdigest(); digest=hashlib.sha256(result.encode()).hexdigest()
            session.add(AIArtifact(job_id=job.id,entry_id=entries[0].id if len(entries)==1 else None,artifact_type=function.function_key,language="zh",content_markdown=result,content_hash=digest,prompt_version=function.prompt_version,model_id=job.model_id,configuration_hash=cfg))
            job.status="succeeded";job.progress=100;job.usage_json=json.dumps(usage);job.finished_at=datetime.now(UTC);session.add(Notification(title="AI 任务完成",body=f"{function.name} 已完成"));await session.commit()
        except Exception as error:
            job.status="failed";job.error_json=json.dumps({"message":str(error)});job.finished_at=datetime.now(UTC);session.add(Notification(title="AI 任务失败",body=str(error)[:500]));await session.commit()


@celery.task(name="rss_ai.execute_ai_job")
def execute_ai_job(job_id: str) -> None:
    asyncio.run(_execute(job_id))


async def _sync_due_connections() -> int:
    async with session_factory() as session:
        connections = list((await session.scalars(select(FreshRSSConnection))).all())
        now = datetime.now(UTC); count = 0
        for connection in connections:
            if connection.last_sync_at and (now - connection.last_sync_at).total_seconds() < connection.sync_interval:
                continue
            try:
                await sync_connection(session, connection, 500)
                count += 1
            except Exception:
                # sync_connection records the connection error state; the scheduler keeps running.
                continue
        return count


@celery.task(name="rss_ai.sync_due_connections")
def sync_due_connections() -> int:
    return asyncio.run(_sync_due_connections())
