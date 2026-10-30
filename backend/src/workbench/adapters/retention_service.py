"""Retention adapter service exposing policy management, legal holds, and approved purges."""

from __future__ import annotations

from workbench.adapters.domain_store import DomainStore
from workbench.adapters.object_storage import ObjectStorage
from workbench.adapters.retention_application_service import (
    RetentionService as CoreRetentionService,
)


class RetentionService(CoreRetentionService):
    """Adapter service for retention policy enforcement, legal holds, and purges."""

    def __init__(self, store: DomainStore, storage: ObjectStorage | None = None) -> None:
        super().__init__(store=store, storage=storage)


__all__ = ["RetentionService"]
