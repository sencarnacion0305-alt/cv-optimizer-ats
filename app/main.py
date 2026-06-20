from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from app.routers import cv
import os

app = FastAPI(
    title="CV Optimizer ATS",
    description="API para adaptar currículums a vacantes y optimizarlos para sistemas ATS.",
    version="0.2.0",
)

# Content-Security-Policy: permite el propio origen + los CDN que usa el frontend
# (Google Fonts y Tabler Icons). 'unsafe-inline' es necesario por el CSS/JS embebido.
_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
    "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'self'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


@app.middleware("http")
async def cabeceras_seguridad(request: Request, call_next):
    """Añade cabeceras de seguridad a todas las respuestas."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = _CSP
    return response

@app.exception_handler(Exception)
async def error_global(request: Request, exc: Exception):
    """
    Garantiza que CUALQUIER error no controlado devuelva JSON (no HTML), para que
    el frontend nunca falle al hacer .json() sobre una página de error.
    """
    return JSONResponse(
        status_code=500,
        content={"detail": "No se pudo procesar la solicitud. Intenta de nuevo o "
                           "verifica que el archivo sea un PDF/DOCX válido.",
                 "tipo": type(exc).__name__},
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
