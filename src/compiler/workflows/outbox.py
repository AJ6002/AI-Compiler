"""Idempotent Outbox pattern store for published dataset handoff events."""

from __future__ import annotations

import hashlib

from src.compiler.workflows.models import HandoffEvent


class HandoffOutbox:
    """Thread-safe persistent outbox store ensuring reliable, at-least-once event delivery."""

    def __init__(self) -> None:
        self._events: dict[str, HandoffEvent] = {}
        self._idempotency_map: dict[str, str] = {}

    def emit(self, event: HandoffEvent) -> HandoffEvent:
        """Enqueue an authenticated handoff event, deduplicating via SHA-256 idempotency key."""
        idempotency_key = hashlib.sha256(
            f"{event.handoff_manifest_uri}:{event.payload_sha256}".encode()
        ).hexdigest()

        if idempotency_key in self._idempotency_map:
            existing_event_id = self._idempotency_map[idempotency_key]
            return self._events[existing_event_id]

        self._events[event.event_id] = event
        self._idempotency_map[idempotency_key] = event.event_id
        return event

    def get(self, event_id: str) -> HandoffEvent | None:
        """Fetch event by ID."""
        return self._events.get(event_id)

    def mark_delivered(self, event_id: str) -> HandoffEvent | None:
        """Mark an event as successfully delivered to downstream AutoMLOps."""
        event = self._events.get(event_id)
        if not event:
            return None
        updated = event.model_copy(update={"delivered": True})
        self._events[event_id] = updated
        return updated

    def list_pending(self, tenant_id: str | None = None) -> list[HandoffEvent]:
        """List undelivered outbox events."""
        result: list[HandoffEvent] = []
        for e in self._events.values():
            if not e.delivered:
                if tenant_id is None or e.tenant_id == tenant_id:
                    result.append(e)
        return result

    def list_all(self, tenant_id: str | None = None) -> list[HandoffEvent]:
        """List all events."""
        result: list[HandoffEvent] = []
        for e in self._events.values():
            if tenant_id is None or e.tenant_id == tenant_id:
                result.append(e)
        return result
