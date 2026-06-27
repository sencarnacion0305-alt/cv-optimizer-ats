"""
Densidad/recuento de keywords (estilo Jobscan): frecuencia esperada (vacante) vs.
real (CV), normalización por sinónimos (JS=JavaScript, K8s=Kubernetes, AWS=Amazon
Web Services), clasificación por tipo y marca de sobreoptimización.
"""
from fastapi.testclient import TestClient

from app.main import app
from app.core.cv_analyzer import analizar_keywords
from app.services.keyword_aliases import frecuencia, canonicalizar_texto

client = TestClient(app)


# ── Conteo con sinónimos ──
def test_sinonimos_cuentan_como_la_misma_keyword():
    cv = canonicalizar_texto("Despliego en k8s sobre AWS. Sé JS y node.js.")
    assert frecuencia("Kubernetes", cv) == 1      # k8s
    assert frecuencia("Amazon Web Services", cv) == 1   # AWS
    assert frecuencia("JavaScript", cv) == 1      # JS
    # node.js NO se cuenta como JavaScript (set de sinónimos distinto)
    assert frecuencia("Node.js", cv) == 1


def test_frecuencia_esperada_vs_real():
    vac = "Python, Python y Python. Kubernetes."
    cv = "Solo uso Python una vez. k8s."
    r = analizar_keywords(cv, vac)
    py = next(i for i in r["items"] if i["keyword"].lower() == "python")
    assert py["freq_vacante"] == 3
    assert py["freq_cv"] == 1
    assert py["cubierta"] is True


# ── Clasificación por tipo ──
def test_clasificacion_por_tipo():
    vac = ("Backend Developer. Requisitos: Python, FastAPI, Jira, Docker. "
           "Liderazgo y comunicación.")
    cv = "Backend Developer con Python, FastAPI, Jira, Docker, liderazgo, comunicación."
    r = analizar_keywords(cv, vac)
    tipos = {i["keyword"]: i["tipo"] for i in r["items"]}
    assert r["por_tipo"].get("title")               # hay título
    assert any(t == "soft" for t in tipos.values())  # liderazgo/comunicación
    assert any(t == "tool" for t in tipos.values())  # jira/docker
    assert any(t == "hard" for t in tipos.values())  # python/fastapi
    # el cargo se clasifica como title
    assert tipos.get("Backend Developer") == "title"


# ── Sobreoptimización (keyword stuffing) ──
def test_marca_sobreoptimizacion():
    vac = "Python developer."
    cv = "Python Python Python Python Python Python developer."
    r = analizar_keywords(cv, vac)
    py = next(i for i in r["items"] if i["keyword"].lower() == "python")
    assert py["freq_cv"] >= 5
    assert py["sobreoptimizada"] is True
    assert any(i["keyword"].lower() == "python" for i in r["sobreoptimizadas"])


def test_uso_normal_no_es_sobreoptimizacion():
    r = analizar_keywords("Uso Python y Docker a diario.", "Python Docker developer.")
    assert all(not i["sobreoptimizada"] for i in r["items"])


# ── Sin vacante / endpoint ──
def test_sin_vacante_no_hay_items():
    r = analizar_keywords("Backend Developer con Python.", "")
    assert r["items"] == []


def test_endpoint_metricas_incluye_keywords_detalle():
    r = client.post("/api/v1/metricas",
                    data={"cv_texto": "Backend dev con Python y Docker.",
                          "vacante_texto": "Python Python Docker. Liderazgo."})
    assert r.status_code == 200
    kd = r.json()["keywords_detalle"]
    assert kd["items"]
    assert all({"keyword", "tipo", "freq_vacante", "freq_cv", "cubierta",
                "densidad", "sobreoptimizada"} <= set(i) for i in kd["items"])
