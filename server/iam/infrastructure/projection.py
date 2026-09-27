"""Idempotent IAM ACL projection handler."""
# mypy: ignore-errors

from __future__ import annotations

from sqlalchemy import delete, select

from ...kernel.application.event.handler import EventHandler
from ...kernel.application.event.integration import IntegrationEvent
from ...kernel.infrastructure.projection import claim_projection_event
from .persistence.sqlalchemy.models import AclDecisionRecord


class IamAclProjection(EventHandler[IntegrationEvent]):
    """Project ACL integration events into the decision read model."""

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    async def handle(self, event: IntegrationEvent) -> None:
        if not event.event_type.startswith(
            "iam.Acl"
        ) and not event.event_type.startswith("iam.Access"):
            return
        async with self.session_factory() as session:
            if not await claim_projection_event(session, "iam_acl", event.event_id):
                return
            payload = event.payload
            scope = payload.get("scope", {})
            entry = payload.get("entry", {})
            subject = entry.get("subject", {})
            action = entry.get("action", {})
            if event.event_type == "iam.AclDeleted":
                await session.execute(
                    delete(AclDecisionRecord).where(
                        AclDecisionRecord.tenant_id == str(scope.get("tenant_id")),
                        AclDecisionRecord.resource_type == scope.get("resource_type"),
                        AclDecisionRecord.resource_id == scope.get("resource_id"),
                    )
                )
            elif event.event_type == "iam.AccessRemoved":
                await session.execute(
                    delete(AclDecisionRecord).where(
                        AclDecisionRecord.tenant_id == str(scope.get("tenant_id")),
                        AclDecisionRecord.resource_type == scope.get("resource_type"),
                        AclDecisionRecord.resource_id == scope.get("resource_id"),
                        AclDecisionRecord.subject_id == str(subject.get("subject_id")),
                        AclDecisionRecord.action == action.get("value"),
                    )
                )
            elif entry:
                query = select(AclDecisionRecord).where(
                    AclDecisionRecord.tenant_id == str(scope.get("tenant_id")),
                    AclDecisionRecord.resource_type == scope.get("resource_type"),
                    AclDecisionRecord.resource_id == scope.get("resource_id"),
                    AclDecisionRecord.subject_id == str(subject.get("subject_id")),
                    AclDecisionRecord.action == action.get("value"),
                )
                row = await session.scalar(query)
                if row is None:
                    session.add(
                        AclDecisionRecord(
                            tenant_id=str(scope.get("tenant_id")),
                            resource_type=scope.get("resource_type"),
                            resource_id=scope.get("resource_id"),
                            subject_type=subject.get("subject_type", "USER"),
                            subject_id=str(subject.get("subject_id")),
                            action=action.get("value"),
                            effect=entry.get("effect"),
                            source_event_id=event.event_id,
                        )
                    )
                else:
                    row.effect, row.source_event_id = (
                        entry.get("effect"),
                        event.event_id,
                    )
            await session.commit()
