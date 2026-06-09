from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.routers import cv
import os

app = FastAPI(
    title="CV Optimizer ATS",
    description="API para adaptar currículums a vacantes y optimizarlos para sistemas ATS.",
    version="0.2.0",
)

# Archivos estáticos (frontend)
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Registrar rutas de la API
app.include_router(cv.router, prefix="/api/v1", tags=["CV"])


@app.get("/", include_in_schema=False)
def root():
    """Sirve el frontend."""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
