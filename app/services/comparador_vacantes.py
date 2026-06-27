"""
Radar de skills del sector: compara 2-5 vacantes del mismo rol, extrae las keywords
del MERCADO y las cruza con el CV para decir al candidato qué le falta para ser
competitivo en su nicho.

  - Frecuencia de mercado: en cuántas vacantes aparece cada skill (sinónimos
    unificados: k8s y Kubernetes cuentan como la misma — reutiliza keyword_aliases).
  - Clasificación: imprescindible / muy pedida / ocasional.
  - Con CV: % de cobertura del mercado (ponderado por frecuencia) y GAP priorizado
    por lo más pedido que el candidato NO tiene ("te falta: Kubernetes, Celery").
"""
from typing import Dict, List

from app.services.adaptador import _keywords_de
from app.services.adaptador_docx import _formato_keyword
from app.services.keyword_aliases import canonicalizar, canonicalizar_texto, frecuencia


def _clasificar(frec: int, total: int) -> str:
    if total <= 1:
        return "imprescindible"
    ratio = frec / total
    if ratio >= 0.8:
        return "imprescindible"
    if ratio >= 0.5:
        return "muy_pedida"
    return "ocasional"


def comparar_vacantes(vacantes: List[str], cv_texto: str = "") -> Dict:
    vacantes = [v.strip() for v in vacantes if v and v.strip()]
    total = len(vacantes)
    if total == 0:
        return {"total_vacantes": 0, "keywords": [], "gap": [],
                "cobertura_mercado": None, "resumen": "No se aportaron vacantes."}

    # Universo de skills: lo que el extractor encuentra en alguna vacante, canonizado.
    vac_canon = [canonicalizar_texto(v) for v in vacantes]
    display: Dict[str, str] = {}
    primera: Dict[str, int] = {}
    orden = 0
    for v in vacantes:
        for kw in _keywords_de(v):
            canon = canonicalizar(kw)
            if canon not in display:
                display[canon] = _formato_keyword(kw)
                primera[canon] = orden
                orden += 1

    # Frecuencia de mercado SINÓNIMO-AWARE: en cuántas vacantes aparece cada skill
    # (cuenta k8s en una y Kubernetes en otra como la misma).
    frec_mercado = {canon: sum(1 for vc in vac_canon if frecuencia(canon, vc) > 0)
                    for canon in display}

    items = sorted(frec_mercado.items(), key=lambda x: (-x[1], primera[x[0]]))
    cv_canon = canonicalizar_texto(cv_texto) if cv_texto.strip() else ""
    tiene_cv = bool(cv_canon)

    keywords, gap = [], []
    cob_num = cob_den = 0
    for canon, frec in items:
        en_cv = tiene_cv and frecuencia(canon, cv_canon) > 0
        categoria = _clasificar(frec, total)
        cob_den += frec
        if en_cv:
            cob_num += frec
        registro = {
            "keyword": display[canon], "frecuencia": frec, "total": total,
            "categoria": categoria, "en_cv": en_cv,
        }
        keywords.append(registro)
        if tiene_cv and not en_cv:
            gap.append(registro)           # ya ordenado por frecuencia desc

    # % de cobertura del mercado ponderado por cuánto se pide cada skill.
    cobertura = round(cob_num / cob_den * 100) if (tiene_cv and cob_den) else None

    imprescindibles = [k for k in keywords if k["categoria"] == "imprescindible"]
    cubiertas_imp = [k for k in imprescindibles if k["en_cv"]]

    if tiene_cv:
        faltan = ", ".join(g["keyword"] for g in gap[:5])
        resumen = (f"Cubres el {cobertura}% del mercado (ponderado por demanda). "
                   + (f"Lo más pedido que te falta: {faltan}." if faltan
                      else "¡No te falta ninguna skill del mercado detectada!"))
    elif imprescindibles:
        resumen = (f"{len(imprescindibles)} skills imprescindibles en {total} vacantes. "
                   "Pega tu CV para ver tu cobertura del mercado y qué te falta.")
    else:
        resumen = f"Se analizaron {total} vacantes."

    return {
        "total_vacantes": total,
        "keywords": keywords,
        "gap": gap,
        "cobertura_mercado": cobertura,
        "n_imprescindibles": len(imprescindibles),
        "n_cubiertas_imp": len(cubiertas_imp),
        "tiene_cv": tiene_cv,
        "resumen": resumen,
    }
