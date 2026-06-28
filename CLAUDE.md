# CLAUDE.md — CV Optimizer ATS

## Qué es el producto
Web app (FastAPI + frontend) que optimiza CVs para filtros ATS. Compite con Jobscan
y Enhancv. Mercado objetivo: hispanohablante / bilingüe ES-EN.

## Funcionalidades actuales (9 módulos)
Adaptar a vacante · Análisis ATS · Checklist ATS · Vista del reclutador ·
Comparar vacantes · Mejorar bullets · Optimizador ATS · 15 Métricas · Mis aplicaciones.

## Activos diferenciadores (NO romper, potenciar)
- Transparencia del score: desglose con sub-puntuaciones expandibles.
- "Vista del reclutador": extracción visual de datos como los lee un ATS.
- "Comparar vacantes": cobertura de mercado ponderada por demanda + gap priorizado.

## Reglas de trabajo
- Antes de codificar: leer el código relevante y proponer un PLAN; esperar aprobación.
- Todo cambio en el motor de scoring debe incluir tests unitarios.
- No exponer rutas de archivos ni detalles internos en mensajes al usuario final.
- Mantener formato ATS en plantillas: una columna, sin tablas/columnas/gráficos.
- Soporte ES/EN: normalizar texto (lowercase + sin acentos) antes de comparar keywords.

## Arquitectura: fuente única de verdad (YA implementada)
La deuda técnica raíz —"cada módulo calculaba su propio matching → resultados
inconsistentes entre vistas"— **ya está resuelta**. Hoy:
- `app/core/cv_analyzer.py` = ÚNICO motor de análisis (`analizar_cv`, secciones,
  calidad, formato, 5 dimensiones del score, densidad de keywords). Las 4 vistas
  (Adaptar, Análisis ATS, Checklist, 15 Métricas) PROYECTAN este objeto, no recalculan.
- `app/core/constantes.py` = pesos, umbrales, patrones de sección y SOFT_SKILLS.
- `app/services/keyword_aliases.py` = diccionario canónico de skills/sinónimos
  (k8s=Kubernetes, JS=JavaScript, AWS=Amazon Web Services) + `frecuencia()` sinónimo-aware.
- `app/services/scoring.py` es solo un SHIM que reexporta desde el core — NO poner
  lógica ahí; editar el core.
- Endpoint `POST /api/v1/analyze` devuelve el objeto normalizado.
- Tests de coherencia entre vistas: `tests/test_fuente_unica.py`.
Regla: cualquier detector nuevo (secciones, calidad, keywords) va en el core y las
vistas lo consumen; no duplicar lógica por módulo.

## Despliegue y caché (importante)
- `git push origin main` = deploy automático en Render (cv-optimizer-ats.onrender.com).
  El usuario prueba contra producción: "sigue roto" suele ser deploy en curso o caché.
- Estáticos con `Cache-Control: no-cache` + `app.js?v=YYYY-MM-DD` versionado para
  evitar caché vieja tras un deploy. Repo: github.com/sencarnacion0305-alt/cv-optimizer-ats.

## Prioridad de fases
1. Quick wins  2. Refactor del núcleo  3. UX/flujo  4. IA contextual
5. Features nuevas  6. Datos/diferenciación
