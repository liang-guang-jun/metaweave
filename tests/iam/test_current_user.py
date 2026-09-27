from __future__ import annotations

from uuid import uuid4

from server.iam.application import GetCurrentUser, UserDTO
from server.iam.application.handlers import GetCurrentUserHandler
from server.iam.domain import UserId


class _StubDirectory:
    """Minimal DirectoryReadStore stub exposing only the self-service lookup."""

    def __init__(self, user: UserDTO | None) -> None:
        self._user = user

    async def get_user(self, user_id: UserId) -> UserDTO | None:
        if self._user is not None and self._user.user_id == user_id:
            return self._user
        return None


async def test_get_current_user_handler_returns_profile() -> None:
    user_id = UserId(uuid4())
    user = UserDTO(user_id, "user@example.test", True)
    handler = GetCurrentUserHandler(_StubDirectory(user))  # type: ignore[arg-type]

    result = await handler.handle(GetCurrentUser(user_id))

    assert result is not None
    assert result.user_id == user_id
    assert result.email == "user@example.test"
    assert result.active is True


async def test_get_current_user_handler_returns_none_for_unknown_user() -> None:
    handler = GetCurrentUserHandler(_StubDirectory(None))  # type: ignore[arg-type]

    assert await handler.handle(GetCurrentUser(UserId(uuid4()))) is None
