"""IAM HTTP router composed from aggregate-oriented route modules."""

from fastapi import APIRouter

from .acl import router as acl_router
from .groups import router as groups_router
from .identity import router as identity_router
from .me import router as me_router
from .membership import router as membership_router
from .session import router as session_router
from .user import router as user_router

router = APIRouter(prefix="/iam")
router.include_router(me_router)
router.include_router(user_router)
router.include_router(membership_router)
router.include_router(acl_router)
router.include_router(groups_router)
router.include_router(identity_router)
router.include_router(session_router)
