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
# (Google Fonts y Tabler Icons).
#  - script-src: SIN 'unsafe-inline'. El JS vive en /static/app.js ('self') y los
#    handlers se enlazan con addEventListener (delegación por data-*), no con onclick.
#  - style-src: conserva 'unsafe-inline' porque el HTML usa ~170 atributos style=""
#    inline; migrarlos a clases sería un refactor mayor y la inyección de estilos es
#    de bajo riesgo comparada con la de scripts.
_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
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
    """Añade cabeceras de seguridad a todas las respuestas.

    Nota de privacidad: la API NO persiste CVs ni vacantes. Todo se procesa en
    memoria durante la petición y se descarta; el historial de aplicaciones vive
    solo en el localStorage del navegador del usuario (ver /privacy).
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = _CSP
    # HSTS solo cuando la conexión es HTTPS (Render termina TLS y reenvía el proto).
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    if proto == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
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


@app.get("/privacy", include_in_schema=False)
def privacy():
    """Página de Política de Privacidad (SaaS que procesa CVs)."""
    return FileResponse(os.path.join(STATIC_DIR, "privacy.html"))


@app.get("/terms", include_in_schema=False)
def terms():
    """Página de Términos del Servicio."""
    return FileResponse(os.path.join(STATIC_DIR, "terms.html"))
