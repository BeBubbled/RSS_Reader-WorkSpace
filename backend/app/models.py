from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class FreshRSSConnection(Base):
    __tablename__ = "freshrss_connections"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    base_url: Mapped[str] = mapped_column(Text)
    username: Mapped[str] = mapped_column(String(512))
    encrypted_api_password: Mapped[str] = mapped_column(Text)
    sync_interval: Mapped[int] = mapped_column(Integer, default=900)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(64), default="not_synced")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Folder(Base):
    __tablename__ = "folders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("freshrss_connections.id"), index=True)
    freshrss_folder_id: Mapped[str | None] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(512))
    feeds: Mapped[list[Feed]] = relationship(back_populates="folder")


class Feed(Base):
    __tablename__ = "feeds"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("freshrss_connections.id"), index=True)
    freshrss_feed_id: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(512))
    feed_url: Mapped[str | None] = mapped_column(Text)
    site_url: Mapped[str | None] = mapped_column(Text)
    folder_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("folders.id"))
    folder: Mapped[Folder | None] = relationship(back_populates="feeds")
    entries: Mapped[list[Entry]] = relationship(back_populates="feed")


class Entry(Base):
    __tablename__ = "entries"
    __table_args__ = (UniqueConstraint("connection_id", "freshrss_entry_id", name="uq_entries_connection_freshrss_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("freshrss_connections.id"), index=True)
    freshrss_entry_id: Mapped[str | None] = mapped_column(String(255))
    feed_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("feeds.id"), index=True)
    title: Mapped[str] = mapped_column(String(2048))
    url: Mapped[str | None] = mapped_column(Text)
    canonical_url: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(512))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    content_html: Mapped[str | None] = mapped_column(Text)
    content_text: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    language: Mapped[str | None] = mapped_column(String(32))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_starred: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    feed: Mapped[Feed] = relationship(back_populates="entries")
    reading_position: Mapped[ReadingPosition | None] = relationship(back_populates="entry", uselist=False, cascade="all, delete-orphan")


class ReadingPosition(Base):
    __tablename__ = "reading_positions"

    entry_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entries.id"), primary_key=True)
    scroll_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    entry: Mapped[Entry] = relationship(back_populates="reading_position")


class AIProvider(Base):
    __tablename__ = "ai_providers"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(256), unique=True)
    provider_type: Mapped[str] = mapped_column(String(64))
    base_url: Mapped[str | None] = mapped_column(Text)
    encrypted_api_key: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    health_status: Mapped[str] = mapped_column(String(32), default="unknown")
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=60)
    concurrency_limit: Mapped[int] = mapped_column(Integer, default=2)
    platform_capabilities_json: Mapped[str] = mapped_column(Text, default="{}")


class AIModel(Base):
    __tablename__ = "ai_models"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_providers.id"), index=True)
    model_key: Mapped[str] = mapped_column(String(256))
    display_name: Mapped[str] = mapped_column(String(256))
    capabilities_json: Mapped[str] = mapped_column(Text, default="[]")
    context_limit: Mapped[int] = mapped_column(Integer, default=8192)
    max_output: Mapped[int] = mapped_column(Integer, default=2048)
    is_local: Mapped[bool] = mapped_column(Boolean, default=False)
    cost_config_json: Mapped[str] = mapped_column(Text, default="{}")
    priority: Mapped[int] = mapped_column(Integer, default=100)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class AIFunction(Base):
    __tablename__ = "ai_functions"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(256))
    function_key: Mapped[str] = mapped_column(String(256), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    input_scope: Mapped[str] = mapped_column(String(32), default="single")
    capability: Mapped[str] = mapped_column(String(128))
    prompt_template: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[int] = mapped_column(Integer, default=1)
    output_schema_json: Mapped[str | None] = mapped_column(Text)
    default_routing_policy_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("routing_policies.id"))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class RoutingPolicy(Base):
    __tablename__ = "routing_policies"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(256), unique=True)
    capability: Mapped[str] = mapped_column(String(128))
    strategy: Mapped[str] = mapped_column(String(64), default="priority")
    fallback_chain_json: Mapped[str] = mapped_column(Text, default="[]")


class AIJob(Base):
    __tablename__ = "ai_jobs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workflow_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workflows.id"))
    function_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ai_functions.id"))
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    input_article_count: Mapped[int] = mapped_column(Integer, default=1)
    entry_set_hash: Mapped[str] = mapped_column(String(64), index=True)
    provider_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ai_providers.id"))
    model_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ai_models.id"))
    usage_json: Mapped[str] = mapped_column(Text, default="{}")
    estimated_cost: Mapped[float] = mapped_column(Float, default=0)
    error_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AIArtifact(Base):
    __tablename__ = "ai_artifacts"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_jobs.id"), index=True)
    entry_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("entries.id"), index=True)
    artifact_type: Mapped[str] = mapped_column(String(128))
    language: Mapped[str | None] = mapped_column(String(32))
    content_markdown: Mapped[str | None] = mapped_column(Text)
    content_json: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[int] = mapped_column(Integer)
    model_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ai_models.id"))
    configuration_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)


class AIJobEntry(Base):
    __tablename__ = "ai_job_entries"
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_jobs.id"), primary_key=True)
    entry_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entries.id"), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    intermediate_result_json: Mapped[str | None] = mapped_column(Text)


class Workflow(Base):
    __tablename__ = "workflows"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(256), unique=True)
    scope_config_json: Mapped[str] = mapped_column(Text, default="{}")
    selection_config_json: Mapped[str] = mapped_column(Text, default="{}")
    pipeline_config_json: Mapped[str] = mapped_column(Text, default="{}")
    output_config_json: Mapped[str] = mapped_column(Text, default="{}")
    schedule_config_json: Mapped[str] = mapped_column(Text, default="{}")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AppSetting(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(256), primary_key=True)
    value_json: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(512))
    body: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
