from fastapi import APIRouter
from fastapi import Depends
from api.deps import get_current_user

from api.v1.endpoints.catalogs import router as catalog_router
from api.v1.endpoints.catalogs_v2 import router as catalog_v2_router
from api.v1.endpoints.reports import router as report_router
from api.v1.endpoints.users import router as users_router
from api.v1.endpoints.auth import router as auth_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["Auth"])

api_router.include_router(
    catalog_router, 
    prefix="/catalog", 
    dependencies=[Depends(get_current_user)]
)
api_router.include_router(
    catalog_v2_router, 
    prefix="/catalog_v2", 
    dependencies=[Depends(get_current_user)]
)
api_router.include_router(
    report_router, 
    prefix="/report", 
    dependencies=[Depends(get_current_user)]
)
api_router.include_router(
    users_router, 
    prefix="", 
    dependencies=[Depends(get_current_user)]
)
api_router.include_router(catalog_router, prefix="/catalog")
api_router.include_router(catalog_v2_router, prefix="/catalog_v2")
api_router.include_router(report_router, prefix="/report")
api_router.include_router(users_router, prefix="")