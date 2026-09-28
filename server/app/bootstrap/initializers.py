"""Context-specific composition-root initializers."""
# mypy: ignore-errors

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from ...catalog.application.events import CatalogDomainEventMapper
from ...catalog.application.handlers import (
    AcceptWorkspaceInvitationHandler,
    ChangeWorkspaceMemberRoleHandler,
    CreateNodeHandler,
    CreateWorkspaceHandler,
    DeleteNodeHandler,
    DisableWorkspaceHandler,
    DisableWorkspaceMemberHandler,
    GetNodeHandler,
    GetNodePathHandler,
    GetNodePermissionsHandler,
    GetWorkspaceHandler,
    GrantNodeAccessHandler,
    GrantWorkspaceAccessHandler,
    InviteWorkspaceMemberHandler,
    ListNodesHandler,
    ListWorkspaceMembersHandler,
    ListWorkspacesHandler,
    MoveNodeHandler,
    RemoveWorkspaceMemberHandler,
    RenameNodeHandler,
    RenameWorkspaceHandler,
    RestoreWorkspaceHandler,
    RestoreWorkspaceMemberHandler,
    RevokeNodeAccessHandler,
    RevokeWorkspaceAccessHandler,
    UpdateNodeHandler,
)
from ...catalog.application.messages import (
    AcceptWorkspaceInvitation,
    ChangeWorkspaceMemberRole,
    CreateNode,
    CreateWorkspace,
    DeleteNode,
    DisableWorkspace,
    DisableWorkspaceMember,
    GetNode,
    GetNodePath,
    GetNodePermissions,
    GetWorkspace,
    GrantNodeAccess,
    GrantWorkspaceAccess,
    InviteWorkspaceMember,
    ListNodes,
    ListWorkspaceMembers,
    ListWorkspaces,
    MoveNode,
    RemoveWorkspaceMember,
    RenameNode,
    RenameWorkspace,
    RestoreWorkspace,
    RestoreWorkspaceMember,
    RevokeNodeAccess,
    RevokeWorkspaceAccess,
    UpdateNode,
)
from ...catalog.application.ports import (
    CatalogAclAuthorizationService,
    NodeReadStore,
    NodeRepository,
    WorkspaceMembershipReadStore,
    WorkspaceMembershipRepository,
    WorkspaceReadStore,
    WorkspaceRepository,
)
from ...iam.application.events import IamDomainEventMapper
from ...iam.application.handlers import (
    AcceptInvitationHandler,
    AddGroupMemberHandler,
    AddSSOProviderMembershipHandler,
    BatchCheckAccessHandler,
    BootstrapSystemAdminHandler,
    ChangePasswordHandler,
    CheckAccessHandler,
    ConfigureSSOProviderHandler,
    CreateGroupHandler,
    CreateServicePrincipalHandler,
    CreateTenantHandler,
    DeleteAclHandler,
    DemoteAdminHandler,
    DisableMembershipHandler,
    DisablePrincipalHandler,
    GetAclHandler,
    GetCurrentUserHandler,
    GetSessionHandler,
    GrantAccessHandler,
    GrantSystemAdminHandler,
    InviteMemberHandler,
    IsPrincipalActiveHandler,
    IssueApiKeyHandler,
    IssuePreAuthTokenHandler,
    LinkExternalSSOIdentityHandler,
    ListAvailableTenantsHandler,
    ListTenantMembershipsHandler,
    ListUserMembershipsHandler,
    LoginWithDatabricksAppsHandler,
    LoginWithOidcHandler,
    LoginWithPasswordHandler,
    PromoteMemberHandler,
    RegisterAclHandler,
    RegisterUserHandler,
    RemoveGroupMemberHandler,
    RemoveMemberHandler,
    RestoreGroupMemberHandler,
    RestoreMembershipHandler,
    RestorePrincipalHandler,
    RevokeAccessHandler,
    RevokeApiKeyHandler,
    RevokeSessionHandler,
    RevokeSystemAdminHandler,
    SearchGroupMembershipsHandler,
    SearchGroupsHandler,
    SearchTenantMembershipsHandler,
    SearchUsersHandler,
    SelectTenantAndIssueTokensHandler,
    VerifyUserHandler,
)
from ...iam.application.messages import (
    AcceptInvitation,
    AddGroupMember,
    AddSSOProviderMembership,
    BatchCheckAccess,
    BootstrapSystemAdmin,
    ChangePassword,
    CheckAccess,
    ConfigureSSOProvider,
    CreateGroup,
    CreateServicePrincipal,
    CreateTenant,
    DeleteAcl,
    DemoteAdmin,
    DisableMembership,
    DisablePrincipal,
    GetAcl,
    GetCurrentUser,
    GetSession,
    GrantAccess,
    GrantSystemAdmin,
    InviteMember,
    IsPrincipalActive,
    IssueApiKey,
    IssuePreAuthToken,
    LinkExternalSSOIdentity,
    ListAvailableTenants,
    ListTenantMemberships,
    ListUserMemberships,
    LoginWithDatabricksApps,
    LoginWithOidc,
    LoginWithPassword,
    PromoteMember,
    RegisterAcl,
    RegisterUser,
    RemoveGroupMember,
    RemoveMember,
    RestoreGroupMember,
    RestoreMembership,
    RestorePrincipal,
    RevokeAccess,
    RevokeApiKey,
    RevokeSession,
    RevokeSystemAdmin,
    SearchGroupMemberships,
    SearchGroups,
    SearchTenantMemberships,
    SearchUsers,
    SelectTenantAndIssueTokens,
    VerifyUser,
)
from ...iam.application.permissions import RelationshipAclSynchronizer
from ...iam.application.ports import (
    AccessControlListRepository,
    MembershipRepository,
    TenantRepository,
    UserRepository,
)
from ...iam.domain.services import AccessDecisionEvaluator, PasswordPolicyValidator
from ...iam.infrastructure.persistence.sqlalchemy.repositories import (
    SqlAlchemyAccessDecisionReadStore,
    SqlAlchemyAclReadStore,
    SqlAlchemyApiKeyRepository,
    SqlAlchemyDirectoryReadStore,
    SqlAlchemyExternalSSOIdentityRepository,
    SqlAlchemyGroupMembershipReadStore,
    SqlAlchemyMembershipReadStore,
    SqlAlchemyPrincipalStatusReadStore,
    SqlAlchemyServicePrincipalRepository,
    SqlAlchemySessionReadStore,
    SqlAlchemySSOProviderRepository,
)
from ...iam.infrastructure.security import (
    PyJwtTokenIssuer,
    SecureApiKeySecretGenerator,
    StaticOidcTokenVerifier,
)
from ...kernel.application.messaging.transaction import TransactionBehavior
from ...kernel.application.unit_of_work import UnitOfWork
from ...kernel.infrastructure.logging import LoggingBehavior
from ...kernel.infrastructure.persistence.sqlalchemy.unit_of_work import (
    SqlAlchemyUnitOfWork,
)
from .config import AppConfig
from .container import Container


@dataclass(frozen=True, slots=True)
class IamContextDependencies:
    """Infrastructure services shared by IAM handlers."""

    user_factory: Callable[[UnitOfWork], UserRepository]
    tenant_factory: Callable[[UnitOfWork], TenantRepository]
    membership_factory: Callable[[UnitOfWork], MembershipRepository]
    acl_factory: Callable[[UnitOfWork], AccessControlListRepository]
    principal_groups: object
    session_factory: object
    group_factory: object
    group_membership_factory: object
    group_graph: object
    clock: object
    ids: object
    password_hasher: object


@dataclass(frozen=True, slots=True)
class CatalogContextDependencies:
    """Infrastructure services shared by Catalog handlers."""

    workspace_factory: Callable[[UnitOfWork], WorkspaceRepository]
    membership_factory: Callable[[UnitOfWork], WorkspaceMembershipRepository]
    node_factory: Callable[[UnitOfWork], NodeRepository]
    workspace_read_store: WorkspaceReadStore
    membership_read_store: WorkspaceMembershipReadStore
    node_read_store: NodeReadStore
    acl: CatalogAclAuthorizationService
    clock: object
    ids: object


class KernelContextInitializer:
    """Register behaviors common to every bounded context."""

    def initialize(self, container: Container) -> None:
        container.behaviors().register_global(LoggingBehavior())


class IamContextInitializer:
    """Register IAM repositories, handlers and command transactions."""

    def __init__(self, config: AppConfig, dependencies: IamContextDependencies) -> None:
        self.config = config
        self.dependencies = dependencies

    def initialize(self, container: Container) -> None:
        d = self.dependencies
        permissions = RelationshipAclSynchronizer(
            d.acl_factory, d.ids, d.principal_groups
        )
        mapper = IamDomainEventMapper()
        transaction = TransactionBehavior(
            lambda: SqlAlchemyUnitOfWork(container.session_factory()), mapper
        )
        command_types = (
            RegisterUser,
            BootstrapSystemAdmin,
            VerifyUser,
            ChangePassword,
            DisablePrincipal,
            RestorePrincipal,
            CreateTenant,
            GrantSystemAdmin,
            RevokeSystemAdmin,
            InviteMember,
            AcceptInvitation,
            CreateGroup,
            AddGroupMember,
            RemoveGroupMember,
            RestoreGroupMember,
            DisableMembership,
            RestoreMembership,
            ConfigureSSOProvider,
            AddSSOProviderMembership,
            LinkExternalSSOIdentity,
            CreateServicePrincipal,
            IssueApiKey,
            RevokeApiKey,
            RemoveMember,
            PromoteMember,
            DemoteAdmin,
            RegisterAcl,
            GrantAccess,
            RevokeAccess,
            DeleteAcl,
            LoginWithPassword,
            LoginWithDatabricksApps,
            IssuePreAuthToken,
            LoginWithOidc,
            SelectTenantAndIssueTokens,
            RevokeSession,
        )
        for message_type in command_types:
            container.behaviors().register_for(message_type, transaction)

        handlers = container.handlers()
        policy = PasswordPolicyValidator(
            self.config.iam.password.min_length,
            self.config.iam.password.require_upper,
            self.config.iam.password.require_digit,
            self.config.iam.password.require_symbol,
        )
        handlers.register(
            RegisterUser,
            RegisterUserHandler(d.user_factory, d.password_hasher, policy, d.ids),
        )
        handlers.register(
            BootstrapSystemAdmin,
            BootstrapSystemAdminHandler(
                d.user_factory,
                d.password_hasher,
                policy,
                d.ids,
                permissions,
            ),
        )
        handlers.register(VerifyUser, VerifyUserHandler(d.user_factory))
        handlers.register(
            ChangePassword,
            ChangePasswordHandler(d.user_factory, d.password_hasher, policy),
        )
        handlers.register(
            CreateTenant,
            CreateTenantHandler(
                d.tenant_factory, d.membership_factory, d.ids, d.clock, permissions
            ),
        )
        handlers.register(
            GrantSystemAdmin,
            GrantSystemAdminHandler(permissions),
        )
        handlers.register(
            RevokeSystemAdmin,
            RevokeSystemAdminHandler(permissions),
        )
        handlers.register(
            InviteMember,
            InviteMemberHandler(d.membership_factory, d.ids, permissions),
        )
        handlers.register(
            AcceptInvitation,
            AcceptInvitationHandler(d.membership_factory, d.clock, permissions),
        )
        handlers.register(
            CreateGroup,
            CreateGroupHandler(
                d.group_factory, d.ids, d.membership_factory, permissions
            ),
        )
        handlers.register(
            AddGroupMember,
            AddGroupMemberHandler(
                d.group_factory,
                d.group_membership_factory,
                d.ids,
                d.group_graph,
                d.membership_factory,
                permissions,
            ),
        )
        handlers.register(
            RemoveGroupMember,
            RemoveGroupMemberHandler(
                d.group_membership_factory,
                d.group_factory,
                d.membership_factory,
                permissions,
            ),
        )
        handlers.register(
            RestoreGroupMember,
            RestoreGroupMemberHandler(
                d.group_membership_factory,
                d.group_factory,
                d.membership_factory,
                permissions,
            ),
        )
        provider_factory = SqlAlchemySSOProviderRepository
        identity_factory = SqlAlchemyExternalSSOIdentityRepository
        principal_factory = SqlAlchemyServicePrincipalRepository
        api_key_factory = SqlAlchemyApiKeyRepository
        handlers.register(
            DisablePrincipal,
            DisablePrincipalHandler(
                d.user_factory,
                principal_factory,
                d.membership_factory,
                permissions,
            ),
        )
        handlers.register(
            RestorePrincipal,
            RestorePrincipalHandler(
                d.user_factory,
                principal_factory,
                d.membership_factory,
                permissions,
            ),
        )
        handlers.register(
            ConfigureSSOProvider,
            ConfigureSSOProviderHandler(
                provider_factory, d.membership_factory, d.ids, permissions
            ),
        )
        handlers.register(
            AddSSOProviderMembership,
            AddSSOProviderMembershipHandler(
                provider_factory, d.membership_factory, permissions
            ),
        )
        handlers.register(
            LinkExternalSSOIdentity,
            LinkExternalSSOIdentityHandler(
                provider_factory,
                identity_factory,
                d.membership_factory,
                d.ids,
                permissions,
            ),
        )
        handlers.register(
            CreateServicePrincipal,
            CreateServicePrincipalHandler(
                principal_factory, d.membership_factory, d.ids, permissions
            ),
        )
        handlers.register(
            IssueApiKey,
            IssueApiKeyHandler(
                principal_factory,
                api_key_factory,
                d.membership_factory,
                d.password_hasher,
                SecureApiKeySecretGenerator(),
                d.ids,
                permissions,
            ),
        )
        handlers.register(
            RevokeApiKey,
            RevokeApiKeyHandler(
                principal_factory, api_key_factory, d.membership_factory, permissions
            ),
        )
        handlers.register(
            RemoveMember, RemoveMemberHandler(d.membership_factory, permissions)
        )
        handlers.register(
            DisableMembership,
            DisableMembershipHandler(d.membership_factory, permissions),
        )
        handlers.register(
            RestoreMembership,
            RestoreMembershipHandler(d.membership_factory, d.clock, permissions),
        )
        handlers.register(
            PromoteMember, PromoteMemberHandler(d.membership_factory, permissions)
        )
        handlers.register(
            DemoteAdmin, DemoteAdminHandler(d.membership_factory, permissions)
        )
        handlers.register(
            RegisterAcl,
            RegisterAclHandler(d.acl_factory, d.membership_factory, d.ids, permissions),
        )
        handlers.register(
            GrantAccess,
            GrantAccessHandler(d.acl_factory, d.membership_factory, permissions),
        )
        handlers.register(
            RevokeAccess,
            RevokeAccessHandler(d.acl_factory, d.membership_factory, permissions),
        )
        handlers.register(
            DeleteAcl,
            DeleteAclHandler(d.acl_factory, d.membership_factory, permissions),
        )
        read_memberships = SqlAlchemyMembershipReadStore(container.session_factory())
        directory = SqlAlchemyDirectoryReadStore(container.session_factory())
        group_memberships = SqlAlchemyGroupMembershipReadStore(
            container.session_factory()
        )
        handlers.register(
            LoginWithPassword,
            LoginWithPasswordHandler(
                d.user_factory, read_memberships, d.password_hasher, d.clock
            ),
        )
        handlers.register(
            LoginWithDatabricksApps,
            LoginWithDatabricksAppsHandler(
                d.user_factory,
                provider_factory,
                identity_factory,
                read_memberships,
                d.password_hasher,
                d.ids,
            ),
        )
        handlers.register(
            IssuePreAuthToken,
            IssuePreAuthTokenHandler(
                PyJwtTokenIssuer(self.config.iam.token.secret),
                self.config.iam.token.issuer,
                self.config.iam.token.audience,
                timedelta(seconds=self.config.iam.token.access_ttl_seconds),
                d.clock,
            ),
        )
        handlers.register(
            LoginWithOidc,
            LoginWithOidcHandler(
                StaticOidcTokenVerifier({}), d.user_factory, read_memberships
            ),
        )
        handlers.register(
            SelectTenantAndIssueTokens,
            SelectTenantAndIssueTokensHandler(
                d.membership_factory,
                d.session_factory,
                PyJwtTokenIssuer(self.config.iam.token.secret),
                self.config.iam.token.issuer,
                self.config.iam.token.audience,
                ttl=timedelta(seconds=self.config.iam.token.access_ttl_seconds),
                clock=d.clock,
                ids=d.ids,
            ),
        )
        handlers.register(RevokeSession, RevokeSessionHandler(d.session_factory))
        handlers.register(
            ListUserMemberships, ListUserMembershipsHandler(read_memberships)
        )
        handlers.register(
            ListTenantMemberships, ListTenantMembershipsHandler(read_memberships)
        )
        handlers.register(
            SearchTenantMemberships, SearchTenantMembershipsHandler(read_memberships)
        )
        handlers.register(
            SearchGroupMemberships,
            SearchGroupMembershipsHandler(group_memberships),
        )
        handlers.register(SearchUsers, SearchUsersHandler(directory))
        handlers.register(GetCurrentUser, GetCurrentUserHandler(directory))
        handlers.register(ListAvailableTenants, ListAvailableTenantsHandler(directory))
        handlers.register(SearchGroups, SearchGroupsHandler(directory))
        check_access = CheckAccessHandler(
            read_memberships,
            SqlAlchemyAccessDecisionReadStore(container.session_factory()),
            AccessDecisionEvaluator(),
            d.principal_groups,
        )
        handlers.register(CheckAccess, check_access)
        handlers.register(BatchCheckAccess, BatchCheckAccessHandler(check_access))
        handlers.register(
            GetAcl, GetAclHandler(SqlAlchemyAclReadStore(container.session_factory()))
        )
        handlers.register(
            GetSession,
            GetSessionHandler(SqlAlchemySessionReadStore(container.session_factory())),
        )
        handlers.register(
            IsPrincipalActive,
            IsPrincipalActiveHandler(
                SqlAlchemyPrincipalStatusReadStore(container.session_factory())
            ),
        )


class CatalogContextInitializer:
    """Register Catalog handlers on the application's shared message bus."""

    def __init__(
        self, config: AppConfig, dependencies: CatalogContextDependencies
    ) -> None:
        self.config = config
        self.dependencies = dependencies

    def initialize(self, container: Container) -> None:
        d = self.dependencies
        transaction = TransactionBehavior(
            lambda: SqlAlchemyUnitOfWork(container.session_factory()),
            CatalogDomainEventMapper(),
        )
        command_types = (
            CreateWorkspace,
            RenameWorkspace,
            DisableWorkspace,
            RestoreWorkspace,
            InviteWorkspaceMember,
            AcceptWorkspaceInvitation,
            ChangeWorkspaceMemberRole,
            DisableWorkspaceMember,
            RestoreWorkspaceMember,
            RemoveWorkspaceMember,
            CreateNode,
            UpdateNode,
            RenameNode,
            MoveNode,
            DeleteNode,
            GrantNodeAccess,
            RevokeNodeAccess,
            GrantWorkspaceAccess,
            RevokeWorkspaceAccess,
        )
        behaviors = container.behaviors()
        for message_type in command_types:
            behaviors.register_for(message_type, transaction)

        handlers = container.handlers()
        handlers.register(
            CreateWorkspace,
            CreateWorkspaceHandler(
                d.workspace_factory, d.membership_factory, d.acl, d.ids, d.clock
            ),
        )
        handlers.register(
            RenameWorkspace,
            RenameWorkspaceHandler(d.workspace_factory, d.membership_factory),
        )
        handlers.register(
            DisableWorkspace,
            DisableWorkspaceHandler(d.workspace_factory, d.membership_factory),
        )
        handlers.register(
            RestoreWorkspace,
            RestoreWorkspaceHandler(d.workspace_factory, d.membership_factory),
        )
        handlers.register(
            InviteWorkspaceMember,
            InviteWorkspaceMemberHandler(
                d.workspace_factory, d.membership_factory, d.ids
            ),
        )
        handlers.register(
            AcceptWorkspaceInvitation,
            AcceptWorkspaceInvitationHandler(d.membership_factory, d.clock, d.acl),
        )
        handlers.register(
            ChangeWorkspaceMemberRole,
            ChangeWorkspaceMemberRoleHandler(d.membership_factory, d.acl),
        )
        handlers.register(
            DisableWorkspaceMember,
            DisableWorkspaceMemberHandler(d.membership_factory, d.acl),
        )
        handlers.register(
            RestoreWorkspaceMember,
            RestoreWorkspaceMemberHandler(d.membership_factory, d.acl),
        )
        handlers.register(
            RemoveWorkspaceMember,
            RemoveWorkspaceMemberHandler(d.membership_factory, d.acl),
        )
        handlers.register(
            CreateNode,
            CreateNodeHandler(
                d.workspace_factory,
                d.membership_factory,
                d.node_factory,
                d.acl,
                d.ids,
            ),
        )
        handlers.register(
            RenameNode,
            RenameNodeHandler(
                d.workspace_factory, d.membership_factory, d.node_factory, d.acl
            ),
        )
        handlers.register(
            UpdateNode,
            UpdateNodeHandler(
                d.workspace_factory, d.membership_factory, d.node_factory, d.acl
            ),
        )
        handlers.register(
            MoveNode,
            MoveNodeHandler(
                d.workspace_factory, d.membership_factory, d.node_factory, d.acl
            ),
        )
        handlers.register(
            DeleteNode,
            DeleteNodeHandler(
                d.workspace_factory, d.membership_factory, d.node_factory, d.acl
            ),
        )
        handlers.register(
            GrantNodeAccess,
            GrantNodeAccessHandler(
                d.workspace_factory, d.membership_factory, d.node_factory, d.acl
            ),
        )
        handlers.register(
            RevokeNodeAccess,
            RevokeNodeAccessHandler(
                d.workspace_factory, d.membership_factory, d.node_factory, d.acl
            ),
        )
        handlers.register(
            GrantWorkspaceAccess,
            GrantWorkspaceAccessHandler(
                d.workspace_factory, d.membership_factory, d.node_factory, d.acl
            ),
        )
        handlers.register(
            RevokeWorkspaceAccess,
            RevokeWorkspaceAccessHandler(
                d.workspace_factory, d.membership_factory, d.node_factory, d.acl
            ),
        )

        handlers.register(ListWorkspaces, ListWorkspacesHandler(d.workspace_read_store))
        handlers.register(GetWorkspace, GetWorkspaceHandler(d.workspace_read_store))
        handlers.register(
            ListWorkspaceMembers,
            ListWorkspaceMembersHandler(d.membership_read_store),
        )
        handlers.register(ListNodes, ListNodesHandler(d.node_read_store, d.acl))
        handlers.register(GetNode, GetNodeHandler(d.node_read_store, d.acl))
        handlers.register(GetNodePath, GetNodePathHandler(d.node_read_store))
        handlers.register(
            GetNodePermissions,
            GetNodePermissionsHandler(d.node_read_store, d.acl),
        )
