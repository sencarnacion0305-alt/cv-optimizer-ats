"""
Cliente LLM OPCIONAL (Claude Sonnet 4.6) para generar bullets y recomendaciones
contextuales al rol/vacante.

Principios:
- OPT-IN total: si no existe ANTHROPIC_API_KEY (o el SDK no está instalado), este
  módulo se considera "no disponible" y el caller usa el fallback por reglas. La app
  funciona igual sin key. La key se configura en el entorno (Render), nunca en el front.
- FALLBACK robusto: cualquier fallo (sin key, rate limit, 5xx, timeout, refusal, JSON
  inválido) devuelve None → el caller cae a reglas. El usuario SIEMPRE obtiene resultado.
- COSTE/LATENCIA: una sola llamada batched por análisis; system prompt cacheado;
  max_tokens acotado; caché en memoria del proceso para entradas idénticas.
- CIFRAS: el modelo debe usar marcadores editables ([number], [% estimado], [$ amount])
  y NO inventar cifras reales. La validación final la hace el caller.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

MODELO = "claude-sonnet-4-6"
_TIMEOUT = 25.0          # segundos; cubre cold-start de Render sin colgar al usuario
_MAX_TOKENS = 1500       # salida corta (bullets + consejos); no requiere streaming

_cache: Dict[str, Any] = {}      # hash(prompt) -> resultado parseado
_cliente: Any = None
_intentado = False

_SYSTEM = (
    "Eres un experto en redacción de CVs optimizados para sistemas ATS y en "
    "selección de personal. Reescribes viñetas (bullets) de experiencia para que "
    "empiecen con un verbo de acción fuerte y comuniquen impacto medible, y "
    "propones recomendaciones específicas al rol y a la vacante.\n"
    "Reglas estrictas:\n"
    "1. NUNCA inventes cifras reales. Cuando sugieras una métrica usa EXACTAMENTE "
    "uno de estos marcadores editables: [number], [% estimado] o [$ amount].\n"
    "2. Mantén el idioma del CV original.\n"
    "3. Usa métricas y vocabulario propios del rol detectado; no apliques jerga de "
    "otro dominio (p. ej. no menciones MTTR, incidentes o alertas si el perfil no "
    "es de ciberseguridad).\n"
    "4. Conserva la veracidad: no agregues tecnologías ni logros que el bullet "
    "original no insinúe.\n"
    "5. Responde ÚNICAMENTE con un objeto JSON válido, sin texto adicional ni "
    "markdown, con esta forma: "
    '{"bullets":[{"original":"...","mejorado":"..."}],"consejos":["...","..."]}'
)


def disponible() -> bool:
    """True si hay key configurada y el SDK de Anthropic se puede inicializar."""
    return _get_cliente() is not None


def _get_cliente() -> Any:
    global _cliente, _intentado
    if _intentado:
        return _cliente
    _intentado = True
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic  # import diferido: dependencia opcional
        _cliente = anthropic.Anthropic(timeout=_TIMEOUT)
    except Exception as e:  # SDK ausente o init fallido
        log.warning("LLM no disponible (%s); se usarán reglas", type(e).__name__)
        _cliente = None
    return _cliente


def _parse_json(texto: str) -> Optional[dict]:
    """Extrae el primer objeto JSON del texto (tolerante a fences ```), o None."""
    if not texto:
        return None
    t = texto.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", t).strip()
    ini, fin = t.find("{"), t.rfind("}")
    if ini == -1 or fin == -1 or fin <= ini:
        return None
    try:
        datos = json.loads(t[ini:fin + 1])
        return datos if isinstance(datos, dict) else None
    except (ValueError, TypeError):
        return None


def _completar(user: str) -> Optional[dict]:
    """Llama al modelo y devuelve el dict JSON, o None ante cualquier problema."""
    cli = _get_cliente()
    if cli is None:
        return None
    clave = hashlib.sha256(user.encode("utf-8")).hexdigest()
    if clave in _cache:
        return _cache[clave]
    try:
        resp = cli.messages.create(
            model=MODELO,
            max_tokens=_MAX_TOKENS,
            system=[{"type": "text", "text": _SYSTEM,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
        )
        if getattr(resp, "stop_reason", None) == "refusal":
            log.info("LLM rechazó la solicitud; se usan reglas")
            return None
        texto = "".join(
            getattr(b, "text", "") for b in (resp.content or [])
            if getattr(b, "type", "") == "text"
        )
        datos = _parse_json(texto)
        if datos is not None:
            _cache[clave] = datos
        return datos
    except Exception as e:  # rate limit, 5xx, timeout, conexión, etc. -> reglas
        log.warning("LLM falló (%s); se usan reglas", type(e).__name__)
        return None


def generar_bullets(
    bullets: List[str], rol: str = "", vacante: str = "",
) -> Optional[Dict[str, List]]:
    """
    Reescribe una lista de bullets y propone consejos, en UNA sola llamada.
    Devuelve {"bullets":[{"original","mejorado"}], "consejos":[...]} o None.
    El caller valida placeholders y jerga antes de mostrar el resultado.
    """
    bullets = [b.strip() for b in bullets if b and b.strip()]
    if not bullets:
        return None
    partes = [f"Rol/perfil detectado: {rol or 'no especificado'}."]
    if vacante.strip():
        partes.append("Descripción de la vacante objetivo:\n" + vacante.strip()[:1500])
    partes.append(
        "Reescribe estos bullets (devuelve uno por cada original, en el mismo orden) "
        "y añade 2-4 consejos accionables para este perfil:\n"
        + "\n".join(f"- {b}" for b in bullets[:20])
    )
    datos = _completar("\n\n".join(partes))
    if not datos:
        return None
    items = datos.get("bullets")
    if not isinstance(items, list) or not items:
        return None
    limpios: List[Dict[str, str]] = []
    for it in items:
        if isinstance(it, dict) and it.get("mejorado"):
            limpios.append({
                "original": str(it.get("original", "")).strip(),
                "mejorado": str(it["mejorado"]).strip(),
            })
    if not limpios:
        return None
    consejos = [str(c).strip() for c in datos.get("consejos", [])
                if isinstance(c, (str, int)) and str(c).strip()]
    return {"bullets": limpios, "consejos": consejos[:4]}
