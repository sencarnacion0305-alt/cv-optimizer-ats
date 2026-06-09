from app.models.schemas import AdaptarCVRequest, AdaptarCVResponse, CVAdaptado


def adaptar_cv_mock(request: AdaptarCVRequest) -> AdaptarCVResponse:
    """
    Versión mock: devuelve datos de prueba estáticos.
    Aquí se integrará la lógica con IA en pasos posteriores.
    """
    cv_adaptado = CVAdaptado(
        resumen=(
            "Profesional con experiencia en desarrollo de software, "
            "adaptado a los requerimientos de la vacante proporcionada."
        ),
        experiencia=[
            "Desarrollador Backend en Empresa X (2021-2024)",
            "Analista de Sistemas en Empresa Y (2019-2021)",
        ],
        habilidades=["Python", "FastAPI", "SQL", "Docker", "Git"],
    )

    return AdaptarCVResponse(
        cv_adaptado=cv_adaptado,
        score_match=75,
        keywords_cubiertas=["Python", "FastAPI", "Git"],
        keywords_sugeridas=["Kubernetes", "CI/CD", "AWS"],
        notas_para_usuario=[
            "Considera agregar métricas concretas a tu experiencia.",
            "Menciona proyectos relevantes alineados con la vacante.",
        ],
    )
