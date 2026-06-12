"""
Compara varias vacantes del mismo rol y extrae las keywords del MERCADO.

Clasifica cada keyword segun en cuantas vacantes aparece:
  - Imprescindibles: presentes en (casi) todas las vacantes.
  - Muy pedidas:      en la mayoria.
  - Ocasionales:      en pocas.

Si se aporta el texto del CV, marca cuales ya cubre el candidato.
"""

from typing import Dict, List

from app.services.adaptador import _keywords_de, _kw_cubierta, norm_alias


def _clasificar(frecuencia: int, total: int) -> str:
    """Devuelve la categoria segun en cuantas vacantes (de 'total') aparece."""
    if total <= 1:
        return "imprescindible"
    ratio = frecuencia / total
    if ratio >= 0.8:
        return "imprescindible"
    if ratio >= 0.5:
        return "muy_pedida"
    return "ocasional"


def comparar_vacantes(vacantes: List[str], cv_texto: str = "") -> Dict:
    """
    vacantes: lista de descripciones (texto) de puestos del mismo tipo.
    cv_texto: opcional, para marcar que keywords ya cubre el CV.
    """
    # Filtrar vacantes vacias
    vacantes = [v.strip() for v in vacantes if v and v.strip()]
    total = len(vacantes)
    if total == 0:
        return {"total_vacantes": 0, "keywords": [], "resumen": "No se aportaron vacantes."}

    # Contar en cuantas vacantes aparece cada keyword
    frecuencia: Dict[str, int] = {}
    primera_aparicion: Dict[str, int] = {}
    orden = 0
    for v in vacantes:
        kws = set(_keywords_de(v))
        for kw in kws:
            frecuencia[kw] = frecuencia.get(kw, 0) + 1
            if kw not in primera_aparicion:
                primera_aparicion[kw] = orden
                orden += 1

    cv_alias = norm_alias(cv_texto) if cv_texto else ""

    keywords = []
    for kw, freq in frecuencia.items():
        categoria = _clasificar(freq, total)
        keywords.append({
            "keyword": kw,
            "frecuencia": freq,
            "total": total,
            "categoria": categoria,
            "en_cv": bool(cv_alias) and _kw_cubierta(cv_alias, kw),
        })

    # Ordenar: por frecuencia desc, luego por orden de aparicion
    keywords.sort(key=lambda k: (-k["frecuencia"], primera_aparicion.get(k["keyword"], 999)))

    # Estadisticas de cobertura del CV
    imprescindibles = [k for k in keywords if k["categoria"] == "imprescindible"]
    cubiertas_imp = [k for k in imprescindibles if k["en_cv"]]

    resumen = ""
    if cv_alias and imprescindibles:
        resumen = (f"Tu CV cubre {len(cubiertas_imp)} de {len(imprescindibles)} "
                   "keywords imprescindibles del mercado.")
    elif imprescindibles:
        resumen = (f"Se identificaron {len(imprescindibles)} keywords imprescindibles "
                   f"a partir de {total} vacantes. Pega tu CV para ver tu cobertura.")
    else:
        resumen = f"Se analizaron {total} vacantes."

    return {
        "total_vacantes": total,
        "keywords": keywords,
        "n_imprescindibles": len(imprescindibles),
        "n_cubiertas_imp": len(cubiertas_imp),
        "tiene_cv": bool(cv_alias),
        "resumen": resumen,
    }
