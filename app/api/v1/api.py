from fastapi import APIRouter

from api.v1.endpoints.catalogs import router as catalog_router
from api.v1.endpoints.catalogs_v2 import router as catalog_v2_router
from api.v1.endpoints.reports import router as report_router

api_router = APIRouter()
api_router.include_router(catalog_router, prefix="/catalog")
api_router.include_router(catalog_v2_router, prefix="/catalog_v2")
api_router.include_router(report_router, prefix="/report")