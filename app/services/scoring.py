"""
Compat shim — el motor de scoring vive ahora en `app.core.cv_analyzer`,
la ÚNICA fuente de verdad. Este módulo solo re-exporta los nombres que otros
módulos/tests ya importaban, para no romper sus imports.

No añadas lógica aquí: edita `app/core/cv_analyzer.py` y `app/core/constantes.py`.
"""

from app.core.constantes import SOFT_SKILLS
from app.core.cv_analyzer import (
    calcular_score_compuesto,
    _dim_formato,
    _peso_posicion,
    _hay_keyword_stuffing,
)

__all__ = [
    "calcular_score_compuesto", "SOFT_SKILLS",
    "_dim_formato", "_peso_posicion", "_hay_keyword_stuffing",
]
