from datetime import datetime, timezone
from sqlalchemy import ForeignKey, String, Text, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class PacketImport(Base):
    __tablename__ = 'packet_imports'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # SHA-256 of original bytes
    original: Mapped[str] = mapped_column(Text)
    report: Mapped[dict] = mapped_column(JSONB)

class Record(Base):
    __tablename__ = 'records'
    __table_args__ = (UniqueConstraint('packet_id', 'ref'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    packet_id: Mapped[str] = mapped_column(ForeignKey('packet_imports.id'), index=True)
    ref: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    revision: Mapped[int] = mapped_column(Integer, default=1)

class Edge(Base):
    __tablename__ = 'evidence_edges'
    __table_args__ = (UniqueConstraint('packet_id', 'source', 'target', 'kind'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    packet_id: Mapped[str] = mapped_column(ForeignKey('packet_imports.id'), index=True)
    source: Mapped[str] = mapped_column(Text, index=True)
    target: Mapped[str] = mapped_column(Text, index=True)
    kind: Mapped[str] = mapped_column(String(30))
    resolved: Mapped[bool]

class DemoSession(Base):
    __tablename__ = 'demo_sessions'
    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(30))

class AuditEvent(Base):
    __tablename__ = 'audit_events'
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(30))
    action: Mapped[str] = mapped_column(String(60))
    subject: Mapped[str] = mapped_column(Text)
    at: Mapped[str] = mapped_column(String(40), default=lambda: datetime.now(timezone.utc).isoformat())
