from datetime import UTC, datetime
from uuid import uuid4

from server.iam.domain import (
    PrincipalDisabled,
    PrincipalRestored,
    ServicePrincipal,
    ServicePrincipalId,
    TenantId,
    User,
    UserId,
)


def test_user_principal_lifecycle_blocks_authentication_and_records_events() -> None:
    user = User.register("user@example.test", "hash", UserId(uuid4()))
    user.verify()
    user.pull_events()

    user.disable()
    assert not user.can_authenticate(datetime.now(UTC))
    assert isinstance(user.pull_events()[0], PrincipalDisabled)

    user.restore_principal()
    assert user.active
    assert user.can_authenticate(datetime.now(UTC))
    assert isinstance(user.pull_events()[0], PrincipalRestored)


def test_service_principal_lifecycle_is_idempotent() -> None:
    principal = ServicePrincipal.create(
        ServicePrincipalId(uuid4()), TenantId(uuid4()), "worker"
    )
    principal.pull_events()

    principal.disable()
    principal.disable()
    events = principal.pull_events()
    assert len(events) == 1
    assert isinstance(events[0], PrincipalDisabled)

    principal.restore_principal()
    assert principal.active
    assert isinstance(principal.pull_events()[0], PrincipalRestored)
