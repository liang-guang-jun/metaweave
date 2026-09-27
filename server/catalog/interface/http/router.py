from fastapi import APIRouter

# Router composition is deliberately kept free of application logic.
# ruff: noqa

from .node import router as node_router
from .membership import router as membership_router
from .permission import router as permission_router
from .workspace import router as workspace_router

router = APIRouter(prefix="/catalog")
router.include_router(workspace_router)
router.include_router(node_router)
router.include_router(membership_router)
router.include_router(permission_router)
