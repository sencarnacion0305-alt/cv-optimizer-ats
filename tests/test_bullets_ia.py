"""
Tarea 4.1: generación de bullets/recomendaciones con LLM (Sonnet 4.6) con FALLBACK
por reglas. El LLM se mockea (sin red en CI). Se verifica:
- Sin key/no disponible -> reglas (comportamiento actual intacto).
- Éxito IA -> fuente "ia", bullets reescritos + recomendaciones.
- Fallo IA (None) o salida no válida -> cae a reglas, el usuario siempre obtiene algo.
- Las cifras inventadas por el modelo se convierten en marcadores editables.
- La jerga de seguridad en un perfil no-seguridad descarta esa salida (garantía 4.2).
"""
import re

import pytest

from app.services import llm_client, mejorador_bullets
from app.services.mejorador_bullets import mejorar_bullets

CV = (
    "Backend Developer\n"
    "- Responsable del backend de la plataforma de pagos en Python\n"
    "- Encargado de la integración de APIs con terceros\n"
    "- Ayudé al diseño de la arquitectura de microservicios"
)

_PH = re.compile(r"\[(number|% estimado|\$ amount)\]")


def _gen_ok(bullets, rol="", vacante=""):
    return {
        "bullets": [
            {"original": b, "mejorado": f"Lideré {b[2:]} logrando una mejora del ~35%"}
            for b in bullets
        ],
        "consejos": ["Cuantifica cada logro", "Incluye keywords de la vacante"],
    }


def test_sin_ia_disponible_usa_reglas(monkeypatch):
    monkeypatch.setattr(llm_client, "disponible", lambda: False)
    r = mejorar_bullets(CV, usar_ia=True)
    assert r["fuente"] == "reglas"
    assert r["ia_disponible"] is False
    assert r["mejoras"]


def test_usar_ia_false_no_llama_al_modelo(monkeypatch):
    # Aunque el modelo esté disponible, sin opt-in no se usa.
    monkeypatch.setattr(llm_client, "disponible", lambda: True)
    monkeypatch.setattr(llm_client, "generar_bullets",
                        lambda *a, **k: pytest.fail("no debía llamar a la IA"))
    r = mejorar_bullets(CV, usar_ia=False)
    assert r["fuente"] == "reglas"


def test_exito_ia(monkeypatch):
    monkeypatch.setattr(llm_client, "disponible", lambda: True)
    monkeypatch.setattr(llm_client, "generar_bullets", _gen_ok)
    r = mejorar_bullets(CV, usar_ia=True)
    assert r["fuente"] == "ia"
    assert r["mejoras"]
    assert r["recomendaciones"]
    # Toda cifra del modelo quedó como marcador editable (sin números crudos).
    for m in r["mejoras"]:
        assert _PH.search(m["mejorado"])
        sin_ph = re.sub(r"\[[^\]]*\]", "", m["mejorado"])
        assert not re.search(r"\d", sin_ph)


def test_ia_falla_cae_a_reglas(monkeypatch):
    monkeypatch.setattr(llm_client, "disponible", lambda: True)
    monkeypatch.setattr(llm_client, "generar_bullets", lambda *a, **k: None)
    r = mejorar_bullets(CV, usar_ia=True)
    assert r["fuente"] == "reglas"
    assert r["mejoras"]


def test_ia_con_jerga_seguridad_en_perfil_no_seg_cae_a_reglas(monkeypatch):
    # Si el modelo mete MTTR/incidentes en un perfil que no es de seguridad,
    # esas salidas se descartan; si no queda nada, se usan reglas.
    def _gen_jerga(bullets, rol="", vacante=""):
        return {"bullets": [{"original": b, "mejorado": f"Reduje el MTTR un ~20% en {b}"}
                            for b in bullets], "consejos": []}
    monkeypatch.setattr(llm_client, "disponible", lambda: True)
    monkeypatch.setattr(llm_client, "generar_bullets", _gen_jerga)
    r = mejorar_bullets(CV, usar_ia=True)
    assert r["fuente"] == "reglas"
    blob = " ".join(m["mejorado"] for m in r["mejoras"]).lower()
    assert "mttr" not in blob


def test_ia_salida_vacia_cae_a_reglas(monkeypatch):
    monkeypatch.setattr(llm_client, "disponible", lambda: True)
    monkeypatch.setattr(llm_client, "generar_bullets",
                        lambda *a, **k: {"bullets": [], "consejos": []})
    r = mejorar_bullets(CV, usar_ia=True)
    assert r["fuente"] == "reglas"


def test_validar_ia_bullet_sanea_y_filtra():
    # Convierte cifras reales en marcadores.
    out = mejorador_bullets._validar_ia_bullet("Aumenté ventas en 30% y 5000 clientes", "ventas")
    assert out is not None and not re.search(r"\d", re.sub(r"\[[^\]]*\]", "", out))
    # Filtra jerga de seguridad en perfil no-seguridad.
    assert mejorador_bullets._validar_ia_bullet("Reduje el MTTR un 40%", "marketing") is None
    # La permite en perfil de seguridad.
    assert mejorador_bullets._validar_ia_bullet("Reduje el MTTR un 40%", "seguridad") is not None


@pytest.mark.parametrize("texto,esperado", [
    ('{"bullets":[{"original":"a","mejorado":"b"}],"consejos":["c"]}', True),
    ('```json\n{"bullets":[],"consejos":[]}\n```', True),
    ('Aquí tienes: {"bullets":[],"consejos":[]} fin', True),
    ('no es json', False),
    ('', False),
])
def test_parse_json_robusto(texto, esperado):
    assert (llm_client._parse_json(texto) is not None) is esperado


class _FakeBlock:
    type = "text"
    text = ('{"bullets":[{"original":"Responsable de X","mejorado":'
            '"Lideré X logrando una mejora del 30%"}],"consejos":["Cuantifica"]}')


class _FakeResp:
    stop_reason = "end_turn"
    content = [_FakeBlock()]


class _FakeMessages:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return _FakeResp()


class _FakeClient:
    def __init__(self):
        self.messages = _FakeMessages()


def test_completar_parsea_respuesta_del_sdk(monkeypatch):
    # Ejercita _completar/generar_bullets de punta a punta con un cliente falso
    # (sin red): valida la forma de la llamada y el parseo del JSON.
    fake = _FakeClient()
    llm_client._cache.clear()
    monkeypatch.setattr(llm_client, "_intentado", True)
    monkeypatch.setattr(llm_client, "_cliente", fake)
    out = llm_client.generar_bullets(["Responsable de X"], rol="tech", vacante="Backend")
    assert out and out["bullets"][0]["mejorado"]
    assert out["consejos"] == ["Cuantifica"]
    # Se llamó al modelo correcto, con system cacheado y sin streaming.
    assert fake.messages.kwargs["model"] == "claude-sonnet-4-6"
    assert fake.messages.kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}


def test_completar_refusal_devuelve_none(monkeypatch):
    class _Refuse(_FakeClient):
        def __init__(self):
            super().__init__()
            self.messages.create = lambda **k: type("R", (), {"stop_reason": "refusal", "content": []})()
    llm_client._cache.clear()
    monkeypatch.setattr(llm_client, "_intentado", True)
    monkeypatch.setattr(llm_client, "_cliente", _Refuse())
    assert llm_client.generar_bullets(["Responsable de X"]) is None


def test_completar_excepcion_devuelve_none(monkeypatch):
    fake = _FakeClient()
    def _boom(**k):
        raise RuntimeError("network")
    fake.messages.create = _boom
    llm_client._cache.clear()
    monkeypatch.setattr(llm_client, "_intentado", True)
    monkeypatch.setattr(llm_client, "_cliente", fake)
    assert llm_client.generar_bullets(["Responsable de X"]) is None


def test_disponible_false_sin_key(monkeypatch):
    # Sin ANTHROPIC_API_KEY el cliente no se inicializa (estado por defecto en CI).
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(llm_client, "_intentado", False)
    monkeypatch.setattr(llm_client, "_cliente", None)
    assert llm_client.disponible() is False
