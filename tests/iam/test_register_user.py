from __future__ import annotations

from typing import Any, cast
from uuid import UUID, uuid4

from server.iam.application import RegisterUser
from server.iam.application.handlers import RegisterUserHandler
from server.iam.domain import PasswordPolicyValidator, User, UserVerified


class _StubUserRepository:
    """Collect persisted users so the handler decision can be asserted."""

    def __init__(self) -> None:
        self.added: list[User] = []

    async def by_email(self, email: str) -> User | None:
        return None

    async def add(self, user: User) -> None:
        self.added.append(user)


class _StubUnitOfWork:
    """Stand-in transaction marker; the stub factory ignores it."""


class _StubRepositoryFactory:
    """Serve one stub repository for any transaction."""

    def __init__(self, repository: _StubUserRepository) -> None:
        self._repository = repository

    def __call__(self, uow: object) -> _StubUserRepository:
        return self._repository


class _StubHasher:
    def hash(self, password: str) -> str:
        return f"hashed:{password}"


class _StubIdGenerator:
    def new(self) -> UUID:
        return uuid4()


def _handler(repository: _StubUserRepository) -> RegisterUserHandler:
    return RegisterUserHandler(
        cast(Any, _StubRepositoryFactory(repository)),
        cast(Any, _StubHasher()),
        PasswordPolicyValidator(min_length=8),
        cast(Any, _StubIdGenerator()),
    )


async def test_register_user_leaves_account_unverified_by_default() -> None:
    repository = _StubUserRepository()

    user_id = await _handler(repository).handle(
        RegisterUser("User@Example.test", "Password1!"),
        uow=cast(Any, _StubUnitOfWork()),
    )

    (user,) = repository.added
    assert user.id == user_id
    assert user.email == "user@example.test"
    assert user.password_hash == "hashed:Password1!"
    assert user.verified is False
    assert not any(isinstance(event, UserVerified) for event in user.pull_events())


async def test_register_user_marks_account_verified_when_skipping() -> None:
    repository = _StubUserRepository()

    await _handler(repository).handle(
        RegisterUser("user@example.test", "Password1!", skip_verify=True),
        uow=cast(Any, _StubUnitOfWork()),
    )

    (user,) = repository.added
    assert user.verified is True
    events = user.pull_events()
    assert isinstance(events[-1], UserVerified)
