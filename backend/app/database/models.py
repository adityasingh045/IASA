"""
ISA database models.

PostgreSQL via SQLAlchemy async. Alembic migrations manage schema changes.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import String, Boolean, DateTime, Float, ForeignKey, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
try:
    from sqlalchemy.dialects.postgresql import JSONB
except ImportError:
    JSONB = dict  # fallback for non-PostgreSQL

try:
    from sqlalchemy import Uuid as UUID  # SQLAlchemy 2.0+ generic Uuid
except ImportError:
    from sqlalchemy.dialects.postgresql import UUID  # fallback for older SQLAlchemy

from app.database.session import Base


# ── Enums (as Python enums for type safety; stored as strings in Postgres) ─────

class PermissionLevel:
    READ = "READ"
    CONTROLLED = "CONTROLLED"
    RESTRICTED = "RESTRICTED"


class WorkspaceRole:
    MEMBER = "member"
    ADMIN = "admin"


# ── Users ───────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    identity_provider: Mapped[str] = mapped_column(String(64), default="isa-local")
    identity_sub: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=dt.datetime.now(dt.timezone.utc))
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=dt.datetime.now(dt.timezone.utc), onupdate=dt.datetime.now(dt.timezone.utc))

    # ── Relationships ──────────────────────────────────────────────────────────
    memberships: Mapped[list["WorkspaceMembership"]] = relationship(back_populates="user")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="owner")
    approvals: Mapped[list["Approval"]] = relationship(back_populates="approver")
    tool_executions: Mapped[list["ToolExecution"]] = relationship(back_populates="user")


# ── Workspaces ──────────────────────────────────────────────────────────────────

class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=dt.datetime.now(dt.timezone.utc))
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=dt.datetime.now(dt.timezone.utc), onupdate=dt.datetime.now(dt.timezone.utc))

    owner: Mapped["User"] = relationship("User", backref="owned_workspaces")
    memberships: Mapped[list["WorkspaceMembership"]] = relationship(back_populates="workspace")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="workspace")
    memories: Mapped[list["Memory"]] = relationship(back_populates="workspace")


# ── Workspace membership ────────────────────────────────────────────────────────

class WorkspaceMembership(Base):
    __tablename__ = "workspace_memberships"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    workspace_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), index=True)
    role: Mapped[str] = mapped_column(String(32), default=WorkspaceRole.MEMBER)
    joined_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=dt.datetime.now(dt.timezone.utc))

    user: Mapped["User"] = relationship("User", back_populates="memberships")
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="memberships")


# ── Conversations ───────────────────────────────────────────────────────────────

class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    owner_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    workspace_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), default="New conversation")
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=dt.datetime.now(dt.timezone.utc))
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=dt.datetime.now(dt.timezone.utc), onupdate=dt.datetime.now(dt.timezone.utc))

    owner: Mapped["User"] = relationship("User", back_populates="conversations")
    workspace: Mapped["Workspace | None"] = relationship("Workspace", back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", order_by="Message.created_at")


# ── Messages ─────────────────────────────────────────────────────────────────────

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))  # user | assistant | system
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(32), default="user")  # user | llm | tool
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=dt.datetime.now(dt.timezone.utc))

    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
    tool_results: Mapped[list["ToolResult"]] = relationship(back_populates="message")


# ── Tool definitions (registered in IASA, not from upstream projects) ───────────

class ToolRegistration(Base):
    __tablename__ = "tool_registrations"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    description: Mapped[str] = mapped_column(Text)
    input_schema: Mapped[dict] = mapped_column(JSONB)
    output_schema: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    permission: Mapped[str] = mapped_column(String(32))  # READ | CONTROLLED | RESTRICTED
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, default=False)
    timeout_seconds: Mapped[float] = mapped_column(Float(53), default=30.0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=dt.datetime.now(dt.timezone.utc))
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=dt.datetime.now(dt.timezone.utc), onupdate=dt.datetime.now(dt.timezone.utc))


# ── Tool executions (audit trail) ────────────────────────────────────────────────

class ToolExecution(Base):
    __tablename__ = "tool_executions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    tool_name: Mapped[str] = mapped_column(String(128), index=True)
    project_id: Mapped[str] = mapped_column(String(64))
    arguments: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(32))  # pending | approved | running | completed | failed | denied
    result_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=dt.datetime.now(dt.timezone.utc))

    user: Mapped["User"] = relationship("User", back_populates="tool_executions")
    approval: Mapped["Approval | None"] = relationship(back_populates="execution")


# ── Approvals ────────────────────────────────────────────────────────────────────

class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    execution_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("tool_executions.id"), unique=True, index=True)
    requested_by: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    approved_by: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(128))
    project_id: Mapped[str] = mapped_column(String(64))
    arguments: Mapped[dict] = mapped_column(JSONB)
    action_description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32))  # pending | approved | denied | expired
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=dt.datetime.now(dt.timezone.utc))
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    execution: Mapped["ToolExecution"] = relationship("ToolExecution", back_populates="approval")
    approver: Mapped["User | None"] = relationship("User", back_populates="approvals", foreign_keys=[approved_by])
    requester: Mapped["User"] = relationship("User", foreign_keys=[requested_by])


# ── Memory ───────────────────────────────────────────────────────────────────────

class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    owner_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    workspace_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=True, index=True)
    scope: Mapped[str] = mapped_column(String(32))  # personal | conversation | project | shared | operational
    category: Mapped[str] = mapped_column(String(128))
    content: Mapped[str] = mapped_column(Text)
    provenance: Mapped[str] = mapped_column(String(128))  # where this memory came from
    metadata_: Mapped[dict | None] = mapped_column(JSONB, nullable=True, name="metadata")
    is_public_in_workspace: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=dt.datetime.now(dt.timezone.utc))
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=dt.datetime.now(dt.timezone.utc), onupdate=dt.datetime.now(dt.timezone.utc))
    expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workspace: Mapped["Workspace | None"] = relationship("Workspace", back_populates="memories")


# ── Events (operational history) ────────────────────────────────────────────────

class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    workspace_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=dt.datetime.now(dt.timezone.utc))
