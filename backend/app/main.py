"""HomeX Backend — FastAPI application."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .services.geodata import GeoDataService
from .routes import api as api_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load geo data
    geo = GeoDataService()
    geo.load()
    api_routes.init(geo)
    print(f"[HomeX] Loaded layers: {geo.layer_counts()}")
    yield
    # Shutdown: nothing to clean up


app = FastAPI(
    title="HomeX API",
    description="Spatial Intelligence for Office-to-Housing Conversion",
    version="0.1.0",
    lifespan=lifespan,
)

raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
allow_origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_routes.router)
