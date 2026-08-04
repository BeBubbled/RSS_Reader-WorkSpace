"""AI configuration, cache-aware job submission and budget reservation."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AIArtifact, AIFunction, AIJob, AIJobEntry, AIModel, AIProvider, AppSetting, Entry, Notification, RoutingPolicy, Workflow

BUILT_INS = {
    "single_article_summary": ("单篇总结", "summarize", "用中文简洁总结以下文章：\n{content}"),
    "single_article_translation": ("单篇翻译", "translate.en_to_zh", "将以下文章翻译为中文：\n{content}"),
    "structured_article_summary": ("结构化总结", "summarize", "提取事实、观点和行动项：\n{content}"),
    "keyword_extraction": ("关键词提取", "extract.keywords", "提取关键词：\n{content}"),
    "article_classification": ("文章分类", "classify", "为文章分类：\n{content}"),
    "selected_articles_summary": ("多文章简报", "summarize", "将以下多篇文章整理成中文 Markdown 简报；每条结论标明来源标题：\n{content}"),
}
DEFAULT_WORKFLOWS = ("selected_articles_summary", "recent_articles_digest", "feed_digest", "folder_digest", "event_digest")

class ProviderIn(BaseModel):
    name: str; provider_type: str; base_url: str | None = None; api_key: str | None = None; enabled: bool = True; timeout_seconds: int = 60; concurrency_limit: int = Field(default=2, ge=1, le=32); platform_capabilities_json: dict = Field(default_factory=dict)
class ModelIn(BaseModel):
    provider_id: uuid.UUID; model_key: str; display_name: str; capabilities_json: list[str] = Field(default_factory=list); context_limit: int = 8192; max_output: int = 2048; is_local: bool = False; cost_config_json: dict = Field(default_factory=dict); priority: int = 100; enabled: bool = True
class FunctionIn(BaseModel):
    name: str; function_key: str; description: str = ""; input_scope: str = "single"; capability: str; prompt_template: str; enabled: bool = True
class PolicyIn(BaseModel):
    name: str; capability: str; strategy: str = "priority"; fallback_chain_json: list[str] = Field(default_factory=list)
class DigestIn(BaseModel):
    entry_ids: list[uuid.UUID] = Field(default_factory=list); feed_id: uuid.UUID | None = None; folder_id: uuid.UUID | None = None; limit: int = Field(default=20, ge=1, le=100); workflow_name: str = "selected_articles_summary"

def provider_out(provider: AIProvider) -> dict:
    """The encrypted key is deliberately omitted from every response."""
    return {"id": str(provider.id), "name": provider.name, "provider_type": provider.provider_type, "base_url": provider.base_url, "enabled": provider.enabled, "health_status": provider.health_status, "timeout_seconds": provider.timeout_seconds, "concurrency_limit": provider.concurrency_limit, "platform_capabilities_json": json.loads(provider.platform_capabilities_json or "{}")}

async def seed_functions(session: AsyncSession) -> None:
    for key, (name, capability, prompt) in BUILT_INS.items():
        if not await session.scalar(select(AIFunction).where(AIFunction.function_key == key)):
            session.add(AIFunction(name=name, function_key=key, capability=capability, prompt_template=prompt))
    for name in DEFAULT_WORKFLOWS:
        if not await session.scalar(select(Workflow).where(Workflow.name == name)):
            session.add(Workflow(name=name, pipeline_config_json=json.dumps({"function_key": "selected_articles_summary" if name != "event_digest" else "structured_article_summary"})))
    await session.commit()

def _cost(model: AIModel, input_tokens: int, output_tokens: int) -> float:
    config = json.loads(model.cost_config_json or "{}")
    return max(0.0, (input_tokens * float(config.get("input_per_million", 0)) + output_tokens * float(config.get("output_per_million", 0))) / 1_000_000)

async def _reserve_budget(session: AsyncSession, content: str) -> float:
    setting = await session.get(AppSetting, "monthly_ai_budget")
    budget = float(json.loads(setting.value_json)) if setting else 0.0
    if budget <= 0:
        return 0.0
    models = list((await session.scalars(select(AIModel).where(AIModel.enabled.is_(True)).order_by(AIModel.priority))).all())
    estimate = min((_cost(model, max(1, len(content) // 4), model.max_output) for model in models), default=0.0)
    month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    spent = float((await session.scalar(select(func.coalesce(func.sum(AIJob.estimated_cost), 0.0)).where(AIJob.created_at >= month_start, AIJob.status.in_(("queued", "running", "succeeded"))))) or 0.0)
    if spent + estimate > budget:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=f"Monthly AI budget reached (${spent:.4f} reserved of ${budget:.2f})")
    return estimate

async def queue_entry_job(session: AsyncSession, entry: Entry, function_key: str, language: str | None = None) -> AIJob:
    await seed_functions(session)
    function = await session.scalar(select(AIFunction).where(AIFunction.function_key == function_key, AIFunction.enabled.is_(True)))
    if not function:
        raise HTTPException(status_code=422, detail="AI function is disabled or missing")
    config = hashlib.sha256(f"{function.id}:{function.prompt_version}:{language or ''}".encode()).hexdigest()
    existing = await session.scalar(select(AIArtifact).where(AIArtifact.entry_id == entry.id, AIArtifact.artifact_type == function_key, AIArtifact.content_hash == entry.content_hash, AIArtifact.configuration_hash == config, AIArtifact.is_current.is_(True)))
    if existing:
        return await session.scalar(select(AIJob).where(AIJob.id == existing.job_id))
    job = AIJob(function_id=function.id, status="queued", entry_set_hash=hashlib.sha256(str(entry.id).encode()).hexdigest(), estimated_cost=await _reserve_budget(session, entry.content_text or entry.content_html or ""))
    session.add(job); await session.flush(); session.add(AIJobEntry(job_id=job.id, entry_id=entry.id)); await session.commit(); await session.refresh(job)
    from app.worker import execute_ai_job
    execute_ai_job.delay(str(job.id)); return job

async def queue_digest_job(session: AsyncSession, entries: list[Entry], function_key: str = "selected_articles_summary") -> AIJob:
    await seed_functions(session)
    function = await session.scalar(select(AIFunction).where(AIFunction.function_key == function_key, AIFunction.enabled.is_(True)))
    if not function:
        function = await session.scalar(select(AIFunction).where(AIFunction.function_key == "selected_articles_summary"))
    ids = sorted(str(entry.id) for entry in entries); content = "\n".join(entry.content_text or entry.content_html or "" for entry in entries)
    job = AIJob(function_id=function.id, status="queued", input_article_count=len(entries), entry_set_hash=hashlib.sha256("|".join(ids).encode()).hexdigest(), estimated_cost=await _reserve_budget(session, content))
    session.add(job); await session.flush(); session.add_all([AIJobEntry(job_id=job.id, entry_id=entry.id) for entry in entries]); await session.commit(); await session.refresh(job)
    from app.worker import execute_ai_job
    execute_ai_job.delay(str(job.id)); return job

async def create_notification(session: AsyncSession, title: str, body: str) -> None:
    session.add(Notification(title=title, body=body)); await session.commit()
