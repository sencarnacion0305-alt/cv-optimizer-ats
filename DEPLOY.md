# 🚀 Desplegar CV Optimizer ATS (gratis, 24/7)

Tu app es FastAPI (Python) + frontend estático. Estos archivos ya están listos
para desplegarla en un host gratuito con una **URL pública** accesible desde
cualquier dispositivo, sin instalar nada.

Archivos de despliegue incluidos:
- `Dockerfile` — empaqueta la app (sirve para Render, Hugging Face, Fly.io…)
- `.dockerignore` / `.gitignore` — evitan subir el venv y archivos personales
- `render.yaml` — deploy automático en Render

---

## Paso 1 — Subir el proyecto a GitHub

> ✅ Ya está todo commiteado en tu repo local (rama `main`, sin incluir `venv/`
> ni archivos personales). Solo falta crear el repo remoto y hacer push.

1. Crea un repo vacío en https://github.com/new (por ejemplo `cv-optimizer-ats`).
   **No** marques "Add a README" (ya tienes uno).
2. Desde la carpeta del proyecto, conecta el remoto y sube:

```bash
git remote add origin https://github.com/TU_USUARIO/cv-optimizer-ats.git
git push -u origin main
```

> Si GitHub te pide credenciales, usa tu usuario y un **Personal Access Token**
> (Settings → Developer settings → Tokens) como contraseña.

---

## Opción A — Render (recomendada) 🟢

1. Entra a https://render.com y regístrate con tu cuenta de GitHub.
2. **New +** → **Blueprint**.
3. Selecciona tu repo `cv-optimizer-ats`. Render leerá `render.yaml` y configurará
   todo solo (runtime Docker, plan free, health check).
4. Pulsa **Apply**. El primer build tarda ~3–5 min.
5. Obtendrás una URL como `https://cv-optimizer-ats.onrender.com` — ábrela en
   cualquier dispositivo. ✅

> **Nota del plan free:** la app "duerme" tras ~15 min sin uso; el primer acceso
> tras dormir tarda ~30–50 s en despertar. Después va fluido.

Si no quieres usar el Blueprint: **New +** → **Web Service** → conecta el repo →
Render detecta el `Dockerfile` automáticamente → plan **Free** → **Create**.

---

## Opción B — Hugging Face Spaces 🤗

Buena alternativa (a veces más accesible según tu red).

1. Entra a https://huggingface.co/new-space
2. **SDK: Docker** (Blank). Visibilidad: Public.
3. Sube los archivos del proyecto al Space (o conéctalo a tu repo de GitHub).
4. **Importante:** el `README.md` del Space debe empezar con este encabezado
   para que HF sepa qué puerto usar:

   ```yaml
   ---
   title: CV Optimizer ATS
   emoji: ⚡
   colorFrom: indigo
   colorTo: purple
   sdk: docker
   app_port: 7860
   pinned: false
   ---
   ```

5. HF construye la imagen y te da una URL `https://huggingface.co/spaces/TU_USUARIO/...` ✅

---

## Probar la imagen en local (opcional)

Si tienes Docker instalado:

```bash
docker build -t cv-ats .
docker run -p 8000:7860 cv-ats
# abre http://localhost:8000
```

---

## Notas

- **No** se usa el mirror de PyPI de Tsinghua aquí: el build corre en los
  servidores del host (con acceso normal a PyPI), no en tu red local.
- La app no usa base de datos ni guarda archivos: todo se procesa en memoria,
  así que no hay nada más que configurar.
- Para actualizar la app: haz `git push` y el host vuelve a desplegar solo.
