from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.v1.api import api_router
from api.v1.endpoints.tracks import router as tracks_router
from api.v1.endpoints.drafts import router as drafts_router
from api.v1.endpoints.web_socket import router as web_socket_router

app = FastAPI(title="MoMu Management System")

app.include_router(api_router, prefix="/api/v1")
app.include_router(tracks_router, prefix="/api")
app.include_router(drafts_router, prefix="/api")
app.include_router(web_socket_router, prefix="/ws")

# CORS middleware must be added AFTER routers to be processed FIRST
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count"],
)

