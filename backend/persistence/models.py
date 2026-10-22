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

class Verification(Base):
    __tablename__ = 'verifications'
    id: Mapped[int] = mapped_column(primary_key=True)
    record_id: Mapped[int] = mapped_column(ForeignKey('records.id'), index=True)
    actor_id: Mapped[str] = mapped_column(String(30))
    method: Mapped[str] = mapped_column(String(60))
    note: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list] = mapped_column(JSONB)
    value: Mapped[str] = mapped_column(Text)
    subject_revision: Mapped[int]
    operation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    reversed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reversed_by: Mapped[str | None] = mapped_column(String(30), nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    at: Mapped[str] = mapped_column(String(40))

class Adjustment(Base):
    __tablename__ = 'adjustments'
    id: Mapped[int] = mapped_column(primary_key=True)
    record_id: Mapped[int] = mapped_column(ForeignKey('records.id'), index=True)
    actor_id: Mapped[str] = mapped_column(String(30))
    original_value: Mapped[str] = mapped_column(Text)
    proposed_value: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list] = mapped_column(JSONB)
    effect: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(30), default='proposed')
    at: Mapped[str] = mapped_column(String(40))

class AdjustmentReview(Base):
    __tablename__ = 'adjustment_reviews'
    id: Mapped[int] = mapped_column(primary_key=True)
    adjustment_id: Mapped[int] = mapped_column(ForeignKey('adjustments.id'), index=True)
    actor_id: Mapped[str] = mapped_column(String(30))
    decision: Mapped[str] = mapped_column(String(20))
    note: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list] = mapped_column(JSONB)
    fingerprint: Mapped[str] = mapped_column(String(64))
    at: Mapped[str] = mapped_column(String(40))

class LastSeen(Base):
    __tablename__ = 'last_seen'
    packet_id: Mapped[str] = mapped_column(ForeignKey('packet_imports.id'), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    cursor: Mapped[int] = mapped_column(Integer, default=0)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    at: Mapped[str] = mapped_column(String(40))

class FilingSnapshot(Base):
    __tablename__ = 'filing_snapshots'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    packet_id: Mapped[str] = mapped_column(ForeignKey('packet_imports.id'), index=True)
    branch_ref: Mapped[str] = mapped_column(Text)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey('filing_snapshots.id'), nullable=True)
    content: Mapped[dict] = mapped_column(JSONB)
    digest: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[str] = mapped_column(String(30))
    at: Mapped[str] = mapped_column(String(40))
