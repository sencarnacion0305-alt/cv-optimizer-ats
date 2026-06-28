"""BUG-02: métricas apropiadas al sector (no jerga IT en perfiles no técnicos)."""
from app.services.mejorador_bullets import detectar_sector, sufijo_metrica

_JERGA_IT = ["incident", "mttr", "alert", "threat", "vulnerab", "siem", "soc", "malware"]


def test_detecta_marketing():
    assert detectar_sector(
        "Marketing Manager leading brand strategy and social media campaigns") == "marketing"


def test_detecta_seguridad():
    # Tras 4.2 "seguridad" se separa de "tech": un perfil de SOC/SIEM/malware es
    # de seguridad (y solo este recibe jerga como MTTR/incidentes).
    assert detectar_sector(
        "Security Analyst at the SOC investigating malware incidents with SIEM") == "seguridad"


def test_detecta_tech_generico():
    # Un developer genérico NO es "seguridad" (no debe recibir jerga de ciberseguridad).
    assert detectar_sector(
        "Backend Developer building APIs with Python, Docker and microservices") == "tech"


def test_detecta_ventas():
    assert detectar_sector(
        "Sales executive comercial exceeding quota and closing deals") == "ventas"


def test_marketing_no_usa_jerga_it():
    suf = sufijo_metrica("Managed social media campaigns and brand strategy", {}, "marketing")
    assert not any(w in suf.lower() for w in _JERGA_IT)


def test_finanzas_no_usa_jerga_it():
    suf = sufijo_metrica("Prepared monthly financial statements and budgets", {}, "finanzas")
    assert not any(w in suf.lower() for w in _JERGA_IT)


def test_tech_si_genera_metrica():
    suf = sufijo_metrica("Investigated security incidents and breaches", {}, "tech")
    assert "~" in suf or "%" in suf or "+" in suf


def test_sector_desconocido_usa_general():
    suf = sufijo_metrica("Did various tasks across the organization", {}, "general")
    assert not any(w in suf.lower() for w in _JERGA_IT)
