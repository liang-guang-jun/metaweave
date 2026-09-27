"""Application composition root."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.engine import make_url

from ...catalog.infrastructure.acl import IamCatalogAclAuthorizationService
from ...catalog.infrastructure.persistence.sqlalchemy.repositories import (
    SqlAlchemyCatalogReadStore,
    SqlAlchemyNodeRepository,
    SqlAlchemyWorkspaceMembershipReadStore,
    SqlAlchemyWorkspaceMembershipRepository,
    SqlAlchemyWorkspaceReadStore,
    SqlAlchemyWorkspaceRepository,
)
from ...iam.infrastructure.persistence.sqlalchemy.repositories import (
    SqlAlchemyAccessControlListRepository,
    SqlAlchemyGroupGraph,
    SqlAlchemyGroupMembershipRepository,
    SqlAlchemyGroupRepository,
    SqlAlchemyMembershipRepository,
    SqlAlchemyPrincipalGroupResolver,
    SqlAlchemySessionRepository,
    SqlAlchemyTenantRepository,
    SqlAlchemyUserRepository,
)
from ...iam.infrastructure.projection import IamAclProjection
from ...iam.infrastructure.security import PwdlibPasswordHasher
from ...kernel.infrastructure.common import SystemClock, UuidGenerator
from ...kernel.infrastructure.logging import configure_logging
from ...kernel.infrastructure.messaging import (
    InMemoryIntegrationEventPublisher,
    OutboxDispatcher,
)
from ...kernel.infrastructure.persistence.sqlalchemy import (
    create_async_engine,
    create_session_factory,
)
from ...kernel.infrastructure.persistence.sqlalchemy.unit_of_work import (
    SqlAlchemyUnitOfWork,
)
from .config import AppConfig, repository_root
from .container import Container
from .initializers import (
    CatalogContextDependencies,
    CatalogContextInitializer,
    IamContextDependencies,
    IamContextInitializer,
    KernelContextInitializer,
)
from .loader import load_config


def create_factory(config: AppConfig | None = None) -> Container:
    """Build infrastructure, then initialize each bounded context."""
    resolved_config = config or load_config()
    configure_logging(resolved_config.logging)
    engine = create_async_engine(
        _resolve_database_url(resolved_config.database.url),
        echo=resolved_config.database.echo,
        sqlite_busy_timeout_ms=resolved_config.database.busy_timeout_ms,
    )
    session_factory = create_session_factory(engine)
    container = Container()
    container.config.override(resolved_config)
    container.engine.override(engine)
    container.session_factory.override(session_factory)
    KernelContextInitializer().initialize(container)

    publisher = InMemoryIntegrationEventPublisher([IamAclProjection(session_factory)])
    container.publisher.override(publisher)
    container.dispatcher.override(
        OutboxDispatcher(lambda: SqlAlchemyUnitOfWork(session_factory), publisher)
    )
    dependencies = IamContextDependencies(
        user_factory=SqlAlchemyUserRepository,
        tenant_factory=SqlAlchemyTenantRepository,
        membership_factory=SqlAlchemyMembershipRepository,
        acl_factory=SqlAlchemyAccessControlListRepository,
        principal_groups=SqlAlchemyPrincipalGroupResolver(session_factory),
        session_factory=SqlAlchemySessionRepository,
        group_factory=SqlAlchemyGroupRepository,
        group_membership_factory=SqlAlchemyGroupMembershipRepository,
        group_graph=SqlAlchemyGroupGraph(session_factory),
        clock=SystemClock(),
        ids=UuidGenerator(),
        password_hasher=PwdlibPasswordHasher(),
    )
    IamContextInitializer(resolved_config, dependencies).initialize(container)
    catalog_dependencies = CatalogContextDependencies(
        workspace_factory=SqlAlchemyWorkspaceRepository,
        membership_factory=SqlAlchemyWorkspaceMembershipRepository,
        node_factory=SqlAlchemyNodeRepository,
        workspace_read_store=SqlAlchemyWorkspaceReadStore(session_factory),
        membership_read_store=SqlAlchemyWorkspaceMembershipReadStore(session_factory),
        node_read_store=SqlAlchemyCatalogReadStore(session_factory),
        acl=IamCatalogAclAuthorizationService(
            SqlAlchemyAccessControlListRepository, session_factory
        ),
        clock=SystemClock(),
        ids=UuidGenerator(),
    )
    CatalogContextInitializer(resolved_config, catalog_dependencies).initialize(
        container
    )
    return container


def create_container(config: AppConfig | None = None) -> Container:
    """Backward-compatible alias for callers using the previous factory name."""
    return create_factory(config)


def _resolve_database_url(url: str) -> str:
    """Anchor a relative SQLite file path to the repository root.

    A relative SQLite path is resolved against the process working directory, so
    running the server from another folder (for example ``client/``) would
    silently create a second database file there. Pinning the file keeps the
    single database managed by ``mw db`` and Alembic.
    """
    parsed = make_url(url)
    database = parsed.database
    if parsed.get_backend_name() != "sqlite" or not database:
        return url
    if database == ":memory:":
        return url
    path = Path(database)
    if path.is_absolute():
        return url
    return str(parsed.set(database=str(repository_root() / path)))
