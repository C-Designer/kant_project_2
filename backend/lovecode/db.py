import hmac
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Index,
    LargeBinary,
    MetaData,
    String,
    Table,
    create_engine,
    delete,
    func,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID, insert
from sqlalchemy.exc import IntegrityError

from .security import digest

metadata = MetaData()
results = Table(
    "shared_results",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True),
    Column("analysis_id", UUID(as_uuid=False), nullable=False, unique=True),
    Column("state", String, nullable=False),
    Column("read_token_hash", LargeBinary, unique=True),
    Column("delete_token_hash", LargeBinary),
    Column("result_payload", JSONB(none_as_null=True)),
    Column("versions", JSONB(none_as_null=True)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("ticket_expires_at", DateTime(timezone=True), nullable=False),
    Column("revoked_at", DateTime(timezone=True)),
    CheckConstraint(
        "(state='active' AND result_payload IS NOT NULL AND versions IS NOT NULL AND read_token_hash IS NOT NULL AND delete_token_hash IS NOT NULL AND revoked_at IS NULL) OR (state='revoked' AND result_payload IS NULL AND versions IS NULL AND read_token_hash IS NULL AND delete_token_hash IS NULL AND revoked_at IS NOT NULL)"
    ),
    CheckConstraint("read_token_hash IS NULL OR octet_length(read_token_hash)=32"),
    CheckConstraint("delete_token_hash IS NULL OR octet_length(delete_token_hash)=32"),
)
Index("ix_result_expiry", results.c.state, results.c.expires_at)
Index("ix_result_tombstone", results.c.state, results.c.ticket_expires_at)
audit = Table(
    "audit_events",
    metadata,
    Column("event_id", UUID(as_uuid=False), primary_key=True),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Column("action", String, nullable=False),
    Column("target_id", UUID(as_uuid=False), nullable=False),
    Column("actor_kind", String, nullable=False),
    Column("request_id", UUID(as_uuid=False), nullable=False),
    Column("policy_version", String, nullable=False),
)


class StoreError(Exception):
    def __init__(self, code, status):
        self.code, self.status = code, status


def make_engine(url):
    return create_engine(
        url,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={
            "connect_timeout": 3,
            "options": "-c statement_timeout=5000 -c lock_timeout=4000",
        },
    )


def event(c, action, id, actor):
    c.execute(
        audit.insert().values(
            event_id=str(uuid.uuid4()),
            occurred_at=func.clock_timestamp(),
            action=action,
            target_id=id,
            actor_kind=actor,
            request_id=str(uuid.uuid4()),
            policy_version="retention-v1",
        )
    )


def revoke(c, id, action, actor):
    c.execute(
        update(results)
        .where(results.c.id == id)
        .values(
            state="revoked",
            read_token_hash=None,
            delete_token_hash=None,
            result_payload=None,
            versions=None,
            revoked_at=func.clock_timestamp(),
        )
    )
    event(c, action, id, actor)


def meta(row):
    return {k: row[k] for k in ("created_at", "expires_at")} | {"result_id": row["id"]}


class Store:
    def __init__(self, engine):
        self.engine = engine

    def save(self, p, read_token, delete_token):
        rh, dh = digest(read_token), digest(delete_token)
        try:
            with self.engine.begin() as c:
                now = c.scalar(select(func.clock_timestamp()))
                if now.timestamp() >= p["expires_at"]:
                    raise StoreError("SAVE_TICKET_EXPIRED", 410)
                values = {
                    "id": str(uuid.uuid4()),
                    "analysis_id": p["analysis_id"],
                    "state": "active",
                    "read_token_hash": rh,
                    "delete_token_hash": dh,
                    "result_payload": p["result"],
                    "versions": p["versions"],
                    "created_at": now,
                    "expires_at": now + timedelta(days=7),
                    "ticket_expires_at": datetime.fromtimestamp(p["expires_at"], UTC),
                }
                new = c.execute(
                    insert(results)
                    .values(**values)
                    .on_conflict_do_nothing()
                    .returning(results.c.id)
                ).scalar_one_or_none()
                row = (
                    c.execute(
                        select(results)
                        .where(results.c.analysis_id == p["analysis_id"])
                        .with_for_update()
                    )
                    .mappings()
                    .one_or_none()
                )
                if row is None:
                    raise StoreError("SAVE_CONFLICT", 409)
                if row["state"] != "active":
                    raise StoreError("RESULT_REVOKED", 410)
                if not (
                    hmac.compare_digest(row["read_token_hash"], rh)
                    and hmac.compare_digest(row["delete_token_hash"], dh)
                ):
                    raise StoreError("SAVE_CONFLICT", 409)
                if new:
                    event(c, "result_saved", row["id"], "save_ticket_holder")
                return meta(row), bool(new)
        except IntegrityError:
            raise StoreError("SAVE_CONFLICT", 409) from None

    def get(self, token):
        with self.engine.connect() as c:
            row = (
                c.execute(
                    select(results).where(
                        results.c.read_token_hash == digest(token),
                        results.c.state == "active",
                        results.c.expires_at > func.clock_timestamp(),
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise StoreError("RESULT_UNAVAILABLE", 404)
            return meta(row) | {"result": row["result_payload"]}

    def remove(self, id, token):
        with self.engine.begin() as c:
            row = (
                c.execute(select(results).where(results.c.id == id).with_for_update())
                .mappings()
                .first()
            )
            if not row or row["state"] == "revoked":
                return
            if not hmac.compare_digest(row["delete_token_hash"], digest(token)):
                raise StoreError("RESULT_UNAVAILABLE", 404)
            revoke(c, id, "result_revoked", "delete_capability_holder")

    def cleanup(self):
        with self.engine.begin() as c:
            rows = (
                c.execute(
                    select(results.c.id)
                    .where(
                        results.c.state == "active", results.c.expires_at <= func.clock_timestamp()
                    )
                    .limit(100)
                    .with_for_update(skip_locked=True)
                )
                .scalars()
                .all()
            )
            for id in rows:
                revoke(c, id, "result_expired", "expiry_job")
            c.execute(
                delete(results).where(
                    results.c.state == "revoked",
                    results.c.ticket_expires_at <= func.clock_timestamp(),
                )
            )
            c.execute(
                delete(audit).where(
                    audit.c.occurred_at < func.clock_timestamp() - timedelta(days=7)
                )
            )
            return len(rows)
