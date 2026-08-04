from __future__ import annotations

import uuid

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.middleware.cors import CORSMiddleware

from app.auth import (
    CurrentUser,
    LoginRequest,
    authenticate,
    clear_session,
    create_session,
    get_current_user,
)
from app.config import Settings, get_settings
from app.dependencies import database_ready, redis_ready
from app.database import get_session
from app.models import Feed, Folder, FreshRSSConnection
from app.freshrss import GoogleReaderClient, decrypt_secret, encrypt_secret, sync_connection
from pydantic import BaseModel, Field
from app.reader import (
    EntryListOut,
    EntryOut,
    EntryStatePatch,
    FeedOut,
    FolderOut,
    ReadingPositionPatch,
    as_entry_out,
    get_entry_or_404,
    list_entries,
    save_reading_position,
)
from app.ai import DigestIn, FunctionIn, ModelIn, PolicyIn, ProviderIn, provider_out, queue_entry_job, seed_functions
from app.models import AIArtifact, AIFunction, AIJob, AIModel, AIProvider, Notification, RoutingPolicy, Workflow
import json


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    app = FastAPI(title="RSS-AI", version="0.1.0")
    app.state.settings = app_settings
    app.dependency_overrides[get_settings] = lambda: app_settings

    if app_settings.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=app_settings.allowed_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
            allow_headers=["Content-Type"],
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    async def ready() -> dict[str, str]:
        database_is_ready = await database_ready()
        redis_is_ready = await redis_ready()
        if not (database_is_ready and redis_is_ready):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"database": database_is_ready, "redis": redis_is_ready},
            )
        return {"status": "ready"}

    @app.post("/api/auth/login", response_model=CurrentUser)
    async def login(credentials: LoginRequest, response: Response) -> CurrentUser:
        user = authenticate(credentials, app_settings)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        create_session(response, user, app_settings)
        return user

    @app.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
    async def logout(response: Response) -> None:
        clear_session(response, app_settings)

    @app.get("/api/auth/me", response_model=CurrentUser)
    async def current_user(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        return user

    @app.get("/api/app/status")
    async def app_status(user: CurrentUser = Depends(get_current_user)) -> dict[str, str]:
        return {"status": "phase-2", "user": user.username}

    class FreshRSSInput(BaseModel):
        base_url: str
        username: str
        api_password: str = Field(min_length=1)
        sync_interval: int = Field(default=900, ge=60, le=86400)

    class FreshRSSOut(BaseModel):
        id: uuid.UUID; base_url: str; username: str; sync_interval: int; last_sync_at: object | None; status: str

    @app.get("/api/freshrss/status", response_model=list[FreshRSSOut])
    async def freshrss_status(user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)) -> list[FreshRSSConnection]:
        return list((await session.scalars(select(FreshRSSConnection).order_by(FreshRSSConnection.created_at))).all())

    @app.post("/api/freshrss/test")
    async def test_freshrss(payload: FreshRSSInput, user: CurrentUser = Depends(get_current_user)) -> dict[str, str]:
        client = GoogleReaderClient(payload.base_url, payload.username, payload.api_password); await client.login(); return {"status": "ok"}

    @app.post("/api/freshrss/connections", response_model=FreshRSSOut)
    async def create_freshrss_connection(payload: FreshRSSInput, user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)) -> FreshRSSConnection:
        item = FreshRSSConnection(base_url=payload.base_url.rstrip("/"), username=payload.username, encrypted_api_password=encrypt_secret(payload.api_password), sync_interval=payload.sync_interval)
        session.add(item); await session.commit(); await session.refresh(item); return item

    @app.post("/api/freshrss/sync")
    async def sync_freshrss(connection_id: uuid.UUID | None = None, max_entries: int = Query(default=2000, ge=1, le=5000), user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)) -> list[dict[str, int]]:
        query = select(FreshRSSConnection)
        if connection_id: query = query.where(FreshRSSConnection.id == connection_id)
        connections = list((await session.scalars(query)).all())
        if not connections: raise HTTPException(status_code=404, detail="FreshRSS connection not found")
        return [await sync_connection(session, item, max_entries) for item in connections]

    @app.get("/api/folders", response_model=list[FolderOut])
    async def folders(
        user: CurrentUser = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
    ) -> list[Folder]:
        return list((await session.scalars(select(Folder).order_by(Folder.name))).all())

    @app.get("/api/feeds", response_model=list[FeedOut])
    async def feeds(
        folder_id: uuid.UUID | None = None,
        user: CurrentUser = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
    ) -> list[Feed]:
        query = select(Feed).order_by(Feed.title)
        if folder_id:
            query = query.where(Feed.folder_id == folder_id)
        return list((await session.scalars(query)).all())

    @app.get("/api/entries", response_model=EntryListOut)
    async def entries(
        feed_id: uuid.UUID | None = None,
        folder_id: uuid.UUID | None = None,
        is_read: bool | None = None,
        is_starred: bool | None = None,
        cursor: uuid.UUID | None = None,
        limit: int = Query(default=50, ge=1, le=100),
        user: CurrentUser = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
    ) -> EntryListOut:
        return await list_entries(session, feed_id=feed_id, folder_id=folder_id, is_read=is_read, is_starred=is_starred, cursor=cursor, limit=limit)

    @app.get("/api/feeds/{feed_id}/entries", response_model=EntryListOut)
    async def feed_entries(
        feed_id: uuid.UUID,
        is_read: bool | None = None,
        is_starred: bool | None = None,
        cursor: uuid.UUID | None = None,
        limit: int = Query(default=50, ge=1, le=100),
        user: CurrentUser = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
    ) -> EntryListOut:
        return await list_entries(session, feed_id=feed_id, folder_id=None, is_read=is_read, is_starred=is_starred, cursor=cursor, limit=limit)

    @app.get("/api/entries/{entry_id}", response_model=EntryOut)
    async def entry(
        entry_id: uuid.UUID,
        user: CurrentUser = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
    ) -> EntryOut:
        return as_entry_out(await get_entry_or_404(session, entry_id))

    @app.patch("/api/entries/{entry_id}/state", response_model=EntryOut)
    async def patch_entry_state(
        entry_id: uuid.UUID,
        payload: EntryStatePatch,
        user: CurrentUser = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
    ) -> EntryOut:
        if not payload.model_fields_set:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No state provided")
        item = await get_entry_or_404(session, entry_id)
        if payload.is_read is not None:
            item.is_read = payload.is_read
        if payload.is_starred is not None:
            item.is_starred = payload.is_starred
        await session.commit()
        return as_entry_out(item)

    @app.patch("/api/entries/{entry_id}/reading-position", response_model=EntryOut)
    async def patch_reading_position(
        entry_id: uuid.UUID,
        payload: ReadingPositionPatch,
        user: CurrentUser = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
    ) -> EntryOut:
        return as_entry_out(await save_reading_position(session, await get_entry_or_404(session, entry_id), payload.scroll_ratio))

    @app.get("/api/ai/providers")
    async def ai_providers(user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)) -> list[dict]:
        return [provider_out(item) for item in (await session.scalars(select(AIProvider))).all()]
    @app.post("/api/ai/providers")
    async def create_provider(payload: ProviderIn, user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)) -> dict:
        item=AIProvider(name=payload.name,provider_type=payload.provider_type,base_url=payload.base_url,encrypted_api_key=encrypt_secret(payload.api_key) if payload.api_key else None,enabled=payload.enabled,timeout_seconds=payload.timeout_seconds,concurrency_limit=payload.concurrency_limit,platform_capabilities_json=json.dumps(payload.platform_capabilities_json));session.add(item);await session.commit();await session.refresh(item);return provider_out(item)
    @app.post("/api/ai/providers/{provider_id}/test")
    async def test_provider(provider_id: uuid.UUID, user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)) -> dict:
        item=await session.get(AIProvider,provider_id)
        if not item: raise HTTPException(404,"Provider not found")
        item.health_status="healthy" if item.enabled else "disabled";await session.commit();return provider_out(item)
    @app.get("/api/ai/models")
    async def ai_models(user: CurrentUser = Depends(get_current_user),session: AsyncSession = Depends(get_session)) -> list[dict]: return [{"id":str(x.id),"provider_id":str(x.provider_id),"model_key":x.model_key,"display_name":x.display_name,"capabilities_json":json.loads(x.capabilities_json),"enabled":x.enabled} for x in (await session.scalars(select(AIModel))).all()]
    @app.post("/api/ai/models")
    async def create_model(payload:ModelIn,user:CurrentUser=Depends(get_current_user),session:AsyncSession=Depends(get_session))->dict:
        x=AIModel(**payload.model_dump(exclude={"capabilities_json","cost_config_json"}),capabilities_json=json.dumps(payload.capabilities_json),cost_config_json=json.dumps(payload.cost_config_json));session.add(x);await session.commit();return {"id":str(x.id)}
    @app.get("/api/ai/functions")
    async def ai_functions(user:CurrentUser=Depends(get_current_user),session:AsyncSession=Depends(get_session))->list[dict]:
        await seed_functions(session);return [{"id":str(x.id),"name":x.name,"function_key":x.function_key,"capability":x.capability,"prompt_version":x.prompt_version,"enabled":x.enabled} for x in (await session.scalars(select(AIFunction))).all()]
    @app.post("/api/ai/functions")
    async def create_function(payload:FunctionIn,user:CurrentUser=Depends(get_current_user),session:AsyncSession=Depends(get_session))->dict:
        x=AIFunction(**payload.model_dump());session.add(x);await session.commit();return {"id":str(x.id)}
    @app.get("/api/routing-policies")
    async def policies(user:CurrentUser=Depends(get_current_user),session:AsyncSession=Depends(get_session))->list[dict]: return [{"id":str(x.id),"name":x.name,"capability":x.capability,"strategy":x.strategy,"fallback_chain_json":json.loads(x.fallback_chain_json)} for x in (await session.scalars(select(RoutingPolicy))).all()]
    @app.post("/api/routing-policies")
    async def create_policy(payload:PolicyIn,user:CurrentUser=Depends(get_current_user),session:AsyncSession=Depends(get_session))->dict:
        x=RoutingPolicy(name=payload.name,capability=payload.capability,strategy=payload.strategy,fallback_chain_json=json.dumps(payload.fallback_chain_json));session.add(x);await session.commit();return {"id":str(x.id)}
    @app.post("/api/entries/{entry_id}/summarize")
    async def summarize(entry_id:uuid.UUID,user:CurrentUser=Depends(get_current_user),session:AsyncSession=Depends(get_session))->dict: return {"job_id":str((await queue_entry_job(session,await get_entry_or_404(session,entry_id),"single_article_summary")).id)}
    @app.post("/api/entries/{entry_id}/translate")
    async def translate(entry_id:uuid.UUID,user:CurrentUser=Depends(get_current_user),session:AsyncSession=Depends(get_session))->dict: return {"job_id":str((await queue_entry_job(session,await get_entry_or_404(session,entry_id),"single_article_translation","zh")).id)}
    @app.get("/api/ai/jobs")
    async def jobs(user:CurrentUser=Depends(get_current_user),session:AsyncSession=Depends(get_session))->list[dict]: return [{"id":str(x.id),"status":x.status,"progress":x.progress,"estimated_cost":x.estimated_cost,"error_json":x.error_json} for x in (await session.scalars(select(AIJob).order_by(AIJob.created_at.desc()))).all()]
    @app.get("/api/ai/jobs/{job_id}")
    async def job(job_id:uuid.UUID,user:CurrentUser=Depends(get_current_user),session:AsyncSession=Depends(get_session))->dict:
        x=await session.get(AIJob,job_id)
        if not x: raise HTTPException(404,"Job not found")
        return {"id":str(x.id),"status":x.status,"progress":x.progress,"error_json":x.error_json}
    @app.post("/api/ai/jobs/{job_id}/cancel")
    async def cancel(job_id:uuid.UUID,user:CurrentUser=Depends(get_current_user),session:AsyncSession=Depends(get_session))->dict:
        x=await session.get(AIJob,job_id)
        if not x: raise HTTPException(404,"Job not found")
        x.status="cancelled";await session.commit();return {"status":x.status}
    @app.get("/api/entries/{entry_id}/artifacts")
    async def artifacts(entry_id:uuid.UUID,user:CurrentUser=Depends(get_current_user),session:AsyncSession=Depends(get_session))->list[dict]: return [{"id":str(x.id),"artifact_type":x.artifact_type,"language":x.language,"content_markdown":x.content_markdown,"content_json":x.content_json} for x in (await session.scalars(select(AIArtifact).where(AIArtifact.entry_id==entry_id,AIArtifact.is_current==True))).all()]
    @app.get("/api/notifications")
    async def notifications(user:CurrentUser=Depends(get_current_user),session:AsyncSession=Depends(get_session))->list[dict]: return [{"id":str(x.id),"title":x.title,"body":x.body,"is_read":x.is_read} for x in (await session.scalars(select(Notification).order_by(Notification.created_at.desc()))).all()]

    return app


app = create_app()
