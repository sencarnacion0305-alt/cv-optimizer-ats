"""
Capa de sincronización del tracker (arquitectura lista; backend real a elección).

- `TrackerStore`: interfaz de almacenamiento por usuario. Sustituye la impl. de
  referencia (en memoria) por una real (PostgreSQL, SQLite, Firestore…) cuando
  configures la cuenta. La identidad del usuario la provee tu capa de auth (un
  `user_id` opaco); el alta de cuentas y las contraseñas NO se manejan aquí.
- `analitica_embudo`: analítica del embudo (nº por estado + tasa de entrevista por
  rango de score ATS). Función pura: sirve para el modo sincronizado y como
  referencia del cálculo que el front hace en local.
"""
from abc import ABC, abstractmethod
from typing import Dict, List

ESTADOS = ["borrador", "enviado", "entrevista", "oferta", "rechazado"]
# Estados que implican que la aplicación realmente se ENVIÓ (no es borrador).
_ENVIADAS = {"enviado", "entrevista", "oferta", "rechazado"}
_CON_ENTREVISTA = {"entrevista", "oferta"}
# Rangos de score ATS para cruzar calidad del CV con resultados.
_RANGOS = [("0-59", 0, 59), ("60-74", 60, 74), ("75-84", 75, 84), ("85-100", 85, 100)]


class TrackerStore(ABC):
    """Almacenamiento del tracker por usuario (sync en la nube)."""

    @abstractmethod
    def obtener(self, user_id: str) -> List[dict]:
        ...

    @abstractmethod
    def guardar(self, user_id: str, aplicaciones: List[dict]) -> None:
        ...


class MemoriaTrackerStore(TrackerStore):
    """
    Implementación de REFERENCIA en memoria — NO persiste entre reinicios y NO es
    apta para producción. Existe solo para que la arquitectura quede operativa y
    testeable. Cámbiala por una base de datos real al configurar la sincronización.
    """

    def __init__(self) -> None:
        self._datos: Dict[str, List[dict]] = {}

    def obtener(self, user_id: str) -> List[dict]:
        return list(self._datos.get(user_id, []))

    def guardar(self, user_id: str, aplicaciones: List[dict]) -> None:
        self._datos[user_id] = list(aplicaciones)


# Instancia activa (inyéctala/cámbiala por la real en tu configuración).
store: TrackerStore = MemoriaTrackerStore()


def _score(a: dict) -> int:
    v = a.get("score_ats", a.get("score"))
    try:
        return max(0, min(100, int(float(v))))
    except (ValueError, TypeError):
        return 0


def analitica_embudo(aplicaciones: List[dict]) -> Dict:
    """Embudo: nº de aplicaciones por estado + tasa de entrevista por rango de score ATS."""
    por_estado = {e: 0 for e in ESTADOS}
    for a in aplicaciones:
        e = a.get("estado")
        if e in por_estado:
            por_estado[e] += 1

    tasa = []
    for label, lo, hi in _RANGOS:
        enviadas = [a for a in aplicaciones
                    if a.get("estado") in _ENVIADAS and lo <= _score(a) <= hi]
        entrevistas = [a for a in enviadas if a.get("estado") in _CON_ENTREVISTA]
        n = len(enviadas)
        tasa.append({
            "rango": label, "aplicaciones": n, "entrevistas": len(entrevistas),
            "tasa": (round(len(entrevistas) / n * 100) if n else None),
        })

    return {
        "total": len(aplicaciones),
        "por_estado": por_estado,
        "tasa_entrevista_por_rango": tasa,
    }
