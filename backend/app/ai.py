from __future__ import annotations
import hashlib, json, uuid
from datetime import UTC, datetime
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.freshrss import encrypt_secret
from app.models import AIArtifact, AIFunction, AIJob, AIJobEntry, AIModel, AIProvider, AppSetting, Entry, Notification, RoutingPolicy, Workflow

BUILT_INS={
 "single_article_summary":("单篇总结","summarize","用中文简洁总结以下文章：\n{content}"),
 "single_article_translation":("单篇翻译","translate.en_to_zh","将以下文章翻译为中文：\n{content}"),
 "structured_article_summary":("结构化总结","summarize","提取事实、观点和行动项：\n{content}"),
 "keyword_extraction":("关键词提取","extract.keywords","提取关键词：\n{content}"),
 "article_classification":("文章分类","classify","为文章分类：\n{content}"),
}
class ProviderIn(BaseModel): name:str; provider_type:str; base_url:str|None=None; api_key:str|None=None; enabled:bool=True; timeout_seconds:int=60; concurrency_limit:int=2; platform_capabilities_json:dict={}
class ModelIn(BaseModel): provider_id:uuid.UUID; model_key:str; display_name:str; capabilities_json:list[str]=[]; context_limit:int=8192; max_output:int=2048; is_local:bool=False; cost_config_json:dict={}; priority:int=100; enabled:bool=True
class FunctionIn(BaseModel): name:str; function_key:str; description:str=""; input_scope:str="single"; capability:str; prompt_template:str; enabled:bool=True
class PolicyIn(BaseModel): name:str; capability:str; strategy:str="priority"; fallback_chain_json:list[str]=[]
class DigestIn(BaseModel): entry_ids:list[uuid.UUID]=[]; feed_id:uuid.UUID|None=None; folder_id:uuid.UUID|None=None; limit:int=20; workflow_name:str="selected_articles_summary"
def provider_out(p:AIProvider)->dict: return {"id":str(p.id),"name":p.name,"provider_type":p.provider_type,"base_url":p.base_url,"enabled":p.enabled,"health_status":p.health_status,"timeout_seconds":p.timeout_seconds,"concurrency_limit":p.concurrency_limit,"platform_capabilities_json":json.loads(p.platform_capabilities_json or "{}")}
async def seed_functions(session:AsyncSession)->None:
 for key,(name,cap,prompt) in BUILT_INS.items():
  if not await session.scalar(select(AIFunction).where(AIFunction.function_key==key)): session.add(AIFunction(name=name,function_key=key,capability=cap,prompt_template=prompt))
 await session.commit()
async def queue_entry_job(session:AsyncSession,entry:Entry,function_key:str,language:str|None=None)->AIJob:
 function=await session.scalar(select(AIFunction).where(AIFunction.function_key==function_key,AIFunction.enabled==True)); assert function
 cfg=hashlib.sha256(f"{function.id}:{function.prompt_version}:{language or ''}".encode()).hexdigest(); existing=await session.scalar(select(AIArtifact).where(AIArtifact.entry_id==entry.id,AIArtifact.artifact_type==function_key,AIArtifact.content_hash==entry.content_hash,AIArtifact.configuration_hash==cfg,AIArtifact.is_current==True))
 if existing: return await session.scalar(select(AIJob).where(AIJob.id==existing.job_id))
 job=AIJob(function_id=function.id,status="queued",entry_set_hash=hashlib.sha256(str(entry.id).encode()).hexdigest()); session.add(job); await session.flush(); session.add(AIJobEntry(job_id=job.id,entry_id=entry.id)); await session.commit(); await session.refresh(job)
 from app.worker import execute_ai_job
 execute_ai_job.delay(str(job.id)); return job
async def queue_digest_job(session:AsyncSession, entries:list[Entry], function_key:str="selected_articles_summary") -> AIJob:
 function=await session.scalar(select(AIFunction).where(AIFunction.function_key==function_key))
 if not function: await seed_functions(session); function=await session.scalar(select(AIFunction).where(AIFunction.function_key==function_key))
 ids=sorted(str(x.id) for x in entries); job=AIJob(function_id=function.id,status="queued",input_article_count=len(entries),entry_set_hash=hashlib.sha256("|".join(ids).encode()).hexdigest());session.add(job);await session.flush();session.add_all([AIJobEntry(job_id=job.id,entry_id=x.id) for x in entries]);await session.commit()
 from app.worker import execute_ai_job
 execute_ai_job.delay(str(job.id));return job
async def create_notification(session:AsyncSession,title:str,body:str)->None: session.add(Notification(title=title,body=body)); await session.commit()
