from fastapi import FastAPI
from app.routers import cv

app = FastAPI(
    title="CV Optimizer ATS",
    description="API para adaptar currículums a vacantes y optimizarlos para sistemas ATS.",
    version="0.1.0",
)

# Registrar rutas
app.include_router(cv.router, prefix="/api/v1", tags=["CV"])


@app.get("/")
def root():
    return {"mensaje": "CV Optimizer ATS activo. Ve a /docs para explorar la API."}
