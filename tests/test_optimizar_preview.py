"""
El Optimizador ATS expone una vista previa antes/después: texto optimizado,
cambios tipados y las keywords concretas de la vacante inyectadas. La UI las usa
para que el usuario vea qué cambió ANTES de descargar.
"""
from fastapi.testclient import TestClient

from app.main import app
from app.services.optimizador_ats import optimizar_cv

client = TestClient(app)

CV = (
    "Carlos Méndez\n"
    "carlos@example.com | Madrid\n"
    "Experiencia\n"
    "Backend Developer en Acme, 03/2020 - 05/2023.\n"
    "Trabajé en la API y los despliegues con Docker.\n"
    "Educación\n"
    "Grado en Informática, 2019."
)
VAC = "Backend Developer con Python, FastAPI, Kubernetes, PostgreSQL y CI/CD."


def test_optimizar_devuelve_texto_y_cambios_tipados():
    r = optimizar_cv(CV, VAC)
    assert r["texto_optimizado"].strip()                 # hay vista previa
    assert isinstance(r["cambios"], list) and r["cambios"]
    for c in r["cambios"]:
        assert set(c) == {"tipo", "texto"}               # cambios tipados
        assert c["texto"]


def test_keywords_inyectadas_aparecen_en_la_preview():
    r = optimizar_cv(CV, VAC)
    kws = r["keywords_inyectadas"]
    assert kws                                            # se inyectó al menos una
    low = r["texto_optimizado"].lower()
    # cada keyword reportada como inyectada debe estar en el texto optimizado
    assert all(k.lower() in low for k in kws)
    # y deben venir de la vacante (no inventadas)
    assert any(k.lower() in VAC.lower() for k in kws)


def test_sin_vacante_no_inyecta_keywords():
    r = optimizar_cv(CV, "")
    assert r["keywords_inyectadas"] == []
    assert r["texto_optimizado"].strip()                 # igual hay preview


def test_endpoint_expone_preview():
    r = client.post("/api/v1/optimizar-cv", data={"cv_texto": CV, "vacante_texto": VAC})
    assert r.status_code == 200
    j = r.json()
    assert j["texto_original"].strip()
    assert j["texto_optimizado"].strip()
    assert isinstance(j["keywords_inyectadas"], list) and j["keywords_inyectadas"]
    assert j["archivo_base64"]                            # descarga disponible
