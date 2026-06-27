"""
Endpoints de sincronización del tracker (arquitectura lista, NO activa por defecto).

SEGURIDAD — leer:
  El alta de cuentas y el manejo de contraseñas/sesiones NO se implementan aquí, a
  propósito. La sincronización necesita identificar al usuario; esa identidad la debe
  proveer TU capa de autenticación. Mientras no la configures, `usuario_actual` lanza
  501 y estos endpoints NO exponen ni guardan datos de nadie. El tracker sigue
  funcionando 100% en modo local (localStorage) en el navegador.

Para activar la nube:
  1. Implementa tu auth (signup/login/hash de contraseñas o un proveedor OAuth/JWT).
  2. Sustituye el cuerpo de `usuario_actual` para validar la sesión y devolver el user_id.
  3. Cambia `tracker_store.store` por una implementación con base de datos real.
"""
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException

from app.models.tracker import TrackerSync
from app.services.tracker_store import store, analitica_embudo

router = APIRouter()


def usuario_actual() -> str:
    """
    STUB de autenticación — sin implementar a propósito (ver cabecera del módulo).
    Devuelve el user_id del usuario autenticado. Hasta que configures auth, gatea la
    sync con 501 para no exponer datos.
    """
    raise HTTPException(
        status_code=501,
        detail=("Sincronización en la nube no configurada. El tracker funciona en modo "
                "local (privado). Para sincronizar, configura la autenticación de cuenta "
                "(ver app/routers/tracker.py)."),
    )


@router.get("/tracker")
def tracker_descargar(user_id: str = Depends(usuario_actual)) -> Dict:
    """Sincronización (bajar): aplicaciones del usuario + analítica del embudo."""
    apps = store.obtener(user_id)
    return {"aplicaciones": apps, "analitica": analitica_embudo(apps)}


@router.put("/tracker")
def tracker_subir(payload: TrackerSync, user_id: str = Depends(usuario_actual)) -> Dict:
    """Sincronización (subir): reemplaza el tracker del usuario por el enviado."""
    apps = [a.dict(by_alias=False) for a in payload.aplicaciones]
    store.guardar(user_id, apps)
    return {"ok": True, "n": len(apps), "analitica": analitica_embudo(apps)}
