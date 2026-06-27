"""
Tracker: esquema de datos, capa de sincronización (store + analítica de embudo) y
endpoints. La sync está GATEADA por un stub de auth (501) — no se exponen datos sin
que el dueño configure la autenticación. El modo local (front) no se toca.
"""
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.models.tracker import Aplicacion
from app.services.tracker_store import analitica_embudo, MemoriaTrackerStore

client = TestClient(app)


# ── Esquema ──
def test_esquema_acepta_objeto_del_front():
    a = Aplicacion(id=1, puesto="Backend Dev", empresa="Acme",
                   estado="entrevista", score="82", link="x", notas="n", fecha="2026-06-01")
    assert a.score_ats == 82
    assert a.estado == "entrevista"


def test_esquema_score_se_normaliza_y_clampa():
    assert Aplicacion(id=1, puesto="p", empresa="e", score="").score_ats is None
    assert Aplicacion(id=1, puesto="p", empresa="e", score="250").score_ats == 100
    assert Aplicacion(id=1, puesto="p", empresa="e", score="abc").score_ats is None


def test_esquema_estado_invalido_falla():
    with pytest.raises(ValidationError):
        Aplicacion(id=1, puesto="p", empresa="e", estado="contratado")


# ── Analítica de embudo ──
def test_analitica_por_estado_y_tasa_entrevista():
    apps = [
        {"estado": "enviado", "score": 70},
        {"estado": "entrevista", "score": 88},
        {"estado": "oferta", "score": 92},
        {"estado": "rechazado", "score": 55},
        {"estado": "borrador", "score": None},
        {"estado": "enviado", "score": 81},
    ]
    emb = analitica_embudo(apps)
    assert emb["total"] == 6
    assert emb["por_estado"] == {"borrador": 1, "enviado": 2, "entrevista": 1,
                                 "oferta": 1, "rechazado": 1}
    rangos = {r["rango"]: r for r in emb["tasa_entrevista_por_rango"]}
    # 85-100: 2 enviadas (88 entrevista, 92 oferta) -> 100% entrevista
    assert rangos["85-100"]["aplicaciones"] == 2
    assert rangos["85-100"]["tasa"] == 100
    # 0-59: 1 enviada (55 rechazado) -> 0%
    assert rangos["0-59"]["tasa"] == 0
    # los borradores NO cuentan como enviadas (6 totales - 1 borrador = 5 enviadas)
    assert sum(r["aplicaciones"] for r in emb["tasa_entrevista_por_rango"]) == 5


def test_analitica_vacia():
    emb = analitica_embudo([])
    assert emb["total"] == 0
    assert all(r["tasa"] is None for r in emb["tasa_entrevista_por_rango"])


# ── Store de referencia ──
def test_store_guarda_y_obtiene_por_usuario():
    s = MemoriaTrackerStore()
    s.guardar("u1", [{"estado": "enviado", "score": 80}])
    assert len(s.obtener("u1")) == 1
    assert s.obtener("u2") == []          # aislado por usuario


# ── Endpoints gateados (seguridad: sin auth -> 501, sin exponer datos) ──
def test_sync_endpoints_gateados_501():
    assert client.get("/api/v1/tracker").status_code == 501
    assert client.put("/api/v1/tracker", json={"aplicaciones": []}).status_code == 501


def test_sync_501_explica_modo_local():
    r = client.get("/api/v1/tracker")
    assert "local" in r.json()["detail"].lower()
