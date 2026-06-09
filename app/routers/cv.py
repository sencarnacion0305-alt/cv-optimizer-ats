from fastapi import APIRouter
from app.models.schemas import AdaptarCVRequest, AdaptarCVResponse
from app.services.adaptador import adaptar_cv_mock

router = APIRouter()


@router.post("/adaptar", response_model=AdaptarCVResponse)
def adaptar_cv(request: AdaptarCVRequest):
    """
    Recibe el texto del CV y la descripción de la vacante,
    y devuelve el CV adaptado con análisis ATS.
    """
    return adaptar_cv_mock(request)
