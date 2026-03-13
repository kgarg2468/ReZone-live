"""HomeX Backend — FastAPI application."""

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_routes.router)
