# CV Optimizer ATS

API para adaptar currículums a vacantes específicas y optimizarlos para sistemas ATS (Applicant Tracking Systems).

## Estructura del proyecto

```
cv-optimizer-ats/
├── app/
│   ├── main.py              # Punto de entrada de FastAPI
│   ├── routers/
│   │   └── cv.py            # Endpoints relacionados al CV
│   ├── models/
│   │   └── schemas.py       # Modelos Pydantic (request y response)
│   └── services/
│       └── adaptador.py     # Lógica de negocio (mock por ahora)
├── requirements.txt
├── .gitignore
└── README.md
```

## Configuración en Windows

### 1. Crear el entorno virtual

Abre una terminal (PowerShell o CMD) dentro de la carpeta del proyecto:

```powershell
python -m venv venv
```

### 2. Activar el entorno virtual

```powershell
venv\Scripts\activate
```

Verás `(venv)` al inicio de la línea cuando esté activo.

### 3. Instalar dependencias

```powershell
pip install -r requirements.txt
```

### 4. Levantar el servidor

```powershell
uvicorn app.main:app --reload
```

El servidor estará disponible en: `http://127.0.0.1:8000`

## Probar la API

### Opción 1: Documentación interactiva (recomendado)

Abre en tu navegador: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

Desde ahí puedes ejecutar el endpoint directamente con una interfaz visual.

### Opción 2: curl desde la terminal

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/adaptar" \
  -H "Content-Type: application/json" \
  -d "{\"cv_texto\": \"Soy desarrollador con 5 años de experiencia en Python.\", \"vacante_texto\": \"Buscamos desarrollador Backend con experiencia en FastAPI y Docker.\"}"
```

### Respuesta esperada

```json
{
  "cv_adaptado": {
    "resumen": "Profesional con experiencia en desarrollo de software...",
    "experiencia": ["Desarrollador Backend en Empresa X (2021-2024)", "..."],
    "habilidades": ["Python", "FastAPI", "SQL", "Docker", "Git"]
  },
  "score_match": 75,
  "keywords_cubiertas": ["Python", "FastAPI", "Git"],
  "keywords_sugeridas": ["Kubernetes", "CI/CD", "AWS"],
  "notas_para_usuario": [
    "Considera agregar métricas concretas a tu experiencia.",
    "Menciona proyectos relevantes alineados con la vacante."
  ]
}
```

## Endpoints disponibles

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Health check |
| POST | `/api/v1/adaptar` | Adapta un CV a una vacante |
