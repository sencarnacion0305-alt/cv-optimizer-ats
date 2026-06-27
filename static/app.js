
  const NOTA_ICON = '<i class="ti ti-bulb" aria-hidden="true"></i>';

  async function analizar() {
    const cv      = document.getElementById("cv").value.trim();
    const vacante = document.getElementById("vacante").value.trim();
    const errBox  = document.getElementById("error-box");
    const btn     = document.getElementById("analizar");

    // Validar
    errBox.style.display = "none";
    if (!cv || !vacante) {
      mostrarError("Por favor completa ambos campos antes de analizar.");
      return;
    }

    // Estado cargando
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>Analizando…';
    document.getElementById("resultados").style.display = "none";

    try {
      const res = await fetch("/api/v1/adaptar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cv_texto: cv, vacante_texto: vacante }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Error ${res.status}`);
      }

      const data = await res.json();
      renderResultados(data);

    } catch (e) {
      mostrarError(e.message || "Error desconocido. Revisa que el servidor esté corriendo.");
    } finally {
      btn.disabled = false;
      btn.innerHTML = "Analizar CV";
    }
  }

  // ════════════ Diagnóstico de contenido (cliente, sin API) ════════════
  function checkContactInfo(cvText) {
    return {
      email:    /[\w.+-]+@[\w-]+\.\w{2,}/i.test(cvText),
      phone:    /(?:\+?\d[\s\-.]?){7,15}/.test(cvText),
      linkedin: /linkedin\.com\/in\//i.test(cvText),
      name:     cvText.trim().split("\n")[0].trim().length > 3,
    };
  }

  function checkDates(cvText) {
    const goodDatePattern = /(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\.?\s+\d{4}/gi;
    const vaguePatterns = [
      /hace\s+\w+\s+años/gi, /sin\s+fecha/gi, /no\s+recuerdo/gi, /\(periodo:/gi,
    ];
    const goodDates = cvText.match(goodDatePattern) || [];
    const vagueMatches = vaguePatterns.flatMap(p => cvText.match(p) || []);
    return { goodDatesCount: goodDates.length, vagueFound: vagueMatches };
  }

  function checkLength(cvText) {
    const words = cvText.trim().split(/\s+/).filter(Boolean).length;
    const pages = Math.round((words / 400) * 10) / 10;
    if (words < 250) return { status: "warning", words,
      msg: `CV muy corto (~${pages} pág). Añade más detalle en experiencia.` };
    if (words > 900) return { status: "warning", words,
      msg: `CV muy largo (~${pages} pág). Condénsalo a 2 páginas máximo.` };
    return { status: "ok", words, msg: `Longitud ideal (~${pages} pág, ${words} palabras)` };
  }

  function checkRepetition(cvText) {
    const stop = new Set(["de","la","el","en","y","a","que","los","las","con","por","para","un","una","su","sus","se","es","son","fue","era","al","del","lo","le","me","mi","tu","te","si","no","ya","the","and","for","with","that","this","from","were","was"]);
    const words = cvText.toLowerCase().match(/\b[a-záéíóúñü]{4,}\b/g) || [];
    const freq = {};
    words.forEach(w => { if (!stop.has(w)) freq[w] = (freq[w] || 0) + 1; });
    return Object.entries(freq).filter(([, c]) => c >= 4).sort((a, b) => b[1] - a[1])
      .map(([w, c]) => `"${w}" ×${c}`);
  }

  const WEAK_PHRASES = [
    "responsable de", "ayudé a", "ayude a", "participé en", "participe en",
    "colaboré en", "colabore en", "trabajé en", "trabaje en", "me encargué de",
    "fui parte de", "apoyé en", "estuve involucrado", "contribuí a", "asistí en",
    "realicé tareas", "responsible for", "helped to", "helped with", "worked on",
    "in charge of", "assisted with", "involved in",
  ];
  function checkWeakPhrases(cvText) {
    const lower = cvText.toLowerCase();
    return WEAK_PHRASES.filter(p => lower.includes(p));
  }

  function checkKeywordStuffing(cvText) {
    const lines = cvText.split("\n");
    const stuffed = lines.filter(line => {
      const words = line.trim().split(/[\s,;|]+/).filter(w => w.length > 2);
      const hasVerb = /^(lider|gest|desar|implement|optim|diseñ|constru|analiz|coordin|led|managed|built|developed)/i.test(line.trim());
      return words.length >= 6 && !hasVerb && line.includes(",");
    });
    return stuffed.length > 2;
  }

  function renderDiagnostico(cvText) {
    const cont = document.getElementById("cv-diagnostico");
    if (!cont) return;
    if (!cvText || cvText.trim().length < 20) { cont.style.display = "none"; return; }

    const items = [];
    const c = checkContactInfo(cvText);
    const piezas = [
      (c.email ? "✓" : "✗") + " Email",
      (c.phone ? "✓" : "✗") + " Teléfono",
      (c.linkedin ? "✓" : "✗") + " LinkedIn",
    ];
    items.push({ estado: (c.email && c.phone && c.linkedin) ? "ok" : "warning",
      t: "Información de contacto", d: piezas.join("   ") });

    const len = checkLength(cvText);
    items.push({ estado: len.status, t: "Longitud del CV", d: len.msg });

    const dt = checkDates(cvText);
    if (dt.vagueFound.length)
      items.push({ estado: "warning", t: "Fechas ambiguas",
        d: `${dt.vagueFound.length} expresión(es): ${dt.vagueFound.slice(0, 3).join(", ")}` });

    const weak = checkWeakPhrases(cvText);
    if (weak.length)
      items.push({ estado: "warning", t: "Frases débiles de relleno",
        d: `${weak.length} detectada(s): ${weak.slice(0, 4).join(", ")} — usa verbos de acción + resultado` });

    const rep = checkRepetition(cvText);
    if (rep.length)
      items.push({ estado: "warning", t: "Palabras muy repetidas",
        d: `${rep.slice(0, 5).join(", ")} — considera sinónimos` });

    if (checkKeywordStuffing(cvText))
      items.push({ estado: "warning", t: "Keyword stuffing",
        d: "Tienes keywords listadas sin contexto. Intégralas en bullets de experiencia con resultados." });

    let html = `<div class="section-title" style="margin-bottom:.5rem"><i class="ti ti-list-check" aria-hidden="true"></i> Diagnóstico del CV</div>`;
    items.forEach(it => {
      const icono = it.estado === "ok" ? "circle-check" : "alert-triangle";
      html += `<div class="ats-check ${it.estado}" style="margin-bottom:.4rem">
          <span class="ico"><i class="ti ti-${icono}" aria-hidden="true"></i></span>
          <div class="body"><div class="t" style="font-size:.84rem">${escapeHtml(it.t)}</div>
          <div class="d">${escapeHtml(it.d)}</div></div>
        </div>`;
    });
    cont.innerHTML = html;
    cont.style.display = "block";
  }

  // ════════════ Señales de riesgo (Bloque 7) ════════════
  function detectarSenalesRiesgo(cvText, d) {
    const s = [];
    if (d && d.score_desglose && d.score_desglose.dimensiones) {
      const cargo = d.score_desglose.dimensiones.find(x => x.nombre === "Cargo objetivo");
      if (cargo && cargo.puntos < 5)
        s.push({ icono: "ti-target-arrow",
          mensaje: "El cargo objetivo de la vacante casi no aparece en tu CV.",
          accion: "Añade el título exacto del puesto en tu titular o resumen." });
    }
    const weak = checkWeakPhrases(cvText);
    if (weak.length >= 3)
      s.push({ icono: "ti-pencil",
        mensaje: `${weak.length} frases genéricas detectadas. Los reclutadores buscan logros concretos, no responsabilidades.`,
        accion: 'Reemplaza "responsable de X" por "Lideré X logrando Y resultado".' });
    const len = checkLength(cvText);
    if (len.status !== "ok")
      s.push({ icono: "ti-ruler-2", mensaje: len.msg,
        accion: len.words > 900 ? "Elimina información irrelevante de hace más de 10 años."
                                : "Expande las descripciones de tus roles con logros y contexto." });
    const dt = checkDates(cvText);
    if (dt.vagueFound.length)
      s.push({ icono: "ti-calendar", mensaje: `${dt.vagueFound.length} fecha(s) ambigua(s) o ausente(s).`,
        accion: 'Usa el formato "Mes AAAA - Mes AAAA" en todas las posiciones.' });
    const c = checkContactInfo(cvText);
    if (!c.email || !c.phone) {
      const faltan = [!c.email ? "email" : null, !c.phone ? "teléfono" : null].filter(Boolean).join(" y ");
      s.push({ icono: "ti-phone", mensaje: `Faltan datos de contacto: ${faltan}.`,
        accion: "Añade email y teléfono en la cabecera del CV." });
    }
    return s;
  }

  function renderSenales(cvText, d) {
    const box = document.getElementById("senales-riesgo");
    if (!box) return;
    const senales = detectarSenalesRiesgo(cvText, d);
    if (!senales.length) { box.style.display = "none"; return; }
    document.getElementById("senales-count").textContent = senales.length;
    document.getElementById("senales-lista").innerHTML = senales.map(s =>
      `<div class="ats-check warning" style="margin-bottom:.5rem">
         <span class="ico"><i class="ti ${s.icono}" aria-hidden="true"></i></span>
         <div class="body"><div class="t" style="font-size:.86rem">${escapeHtml(s.mensaje)}</div>
         <div class="d"><strong>Acción:</strong> ${escapeHtml(s.accion)}</div></div>
       </div>`).join("");
    box.style.display = "block";
    box.open = true;
  }

  // ════════════ Requisitos de la vacante (métricas 10-13) ════════════
  function renderRequisitos(req) {
    const box = document.getElementById("requisitos-box");
    if (!box) return;
    if (!req) { box.style.display = "none"; return; }

    let filas = "";
    const fila = (ok, label, detalle) => {
      const estado = ok === true ? "ok" : ok === false ? "error" : "warning";
      const ico = ok === true ? "circle-check" : ok === false ? "circle-x" : "minus";
      const col = ok === true ? "var(--green)" : ok === false ? "var(--red)" : "var(--muted)";
      filas += `<div class="ats-check ${estado}" style="margin-bottom:.4rem">
          <span class="ico"><i class="ti ti-${ico}" style="color:${col}" aria-hidden="true"></i></span>
          <div class="body"><div class="t" style="font-size:.85rem">${escapeHtml(label)}</div>
          <div class="d">${escapeHtml(detalle)}</div></div></div>`;
    };

    if (req.anios) {
      const a = req.anios;
      const det = a.detectados != null ? `${a.detectados} año(s)` : "no detectados";
      fila(a.cumple, `Experiencia: pide ${a.requeridos}+ años`, `Tu CV: ${det}`);
    }
    if (req.seniority) {
      const s = req.seniority;
      fila(s.coincide, `Seniority objetivo: ${s.vacante}`,
        s.cv ? `Tu CV refleja: ${s.cv}` : "No detectamos el nivel en tu CV");
    }
    (req.idiomas || []).forEach(i =>
      fila(i.en_cv, `Idioma: ${i.idioma}`,
        i.en_cv ? "Mencionado en tu CV" : "No aparece en tu CV"));
    if (req.educacion) {
      const e = req.educacion;
      fila(e.cumple, `Educación: ${e.requerido}`,
        e.cv ? `Tu CV: ${e.cv}` : "No detectamos formación en tu CV");
    }
    (req.certificaciones || []).forEach(c =>
      fila(c.en_cv, `Certificación: ${c.cert}`,
        c.en_cv ? "Presente en tu CV" : "Falta en tu CV"));

    if (!filas) { box.style.display = "none"; return; }
    box.innerHTML = `<div class="section-title" style="margin-bottom:.5rem"><i class="ti ti-checklist" aria-hidden="true"></i> Requisitos de la vacante</div>` + filas;
    box.style.display = "block";
  }

  function renderResultados(d) {
    // ── Score circular ──────────────────────────────────────────
    const score = d.score_match;
    const circumference = 2 * Math.PI * 54; // 339.3
    const offset = circumference - (score / 100) * circumference;

    const fill = document.getElementById("score-fill");
    fill.style.strokeDashoffset = offset;

    // Color según score (alineado al umbral recomendado de 75)
    const color = score >= 75 ? "#16A34A" : score >= 50 ? "#D97706" : "#DC2626";
    fill.style.stroke = color;

    const numEl = document.getElementById("score-number");
    numEl.style.color = color;

    // Animación del número
    animarNumero(numEl, 0, score, 1000);

    // Veredicto en 4 niveles (SCORE-02)
    const desc = document.getElementById("score-desc");
    let dTxt, dCol, dIco;
    if      (score >= 90) { dTxt = "Match excelente";                   dCol = "#15803D"; dIco = "trophy"; }
    else if (score >= 75) { dTxt = "Buen match — aplica con confianza"; dCol = "#16A34A"; dIco = "circle-check"; }
    else if (score >= 50) { dTxt = "Puede pasar, sigue optimizando";    dCol = "#D97706"; dIco = "alert-circle"; }
    else                  { dTxt = "Alto riesgo de ser filtrado";       dCol = "#DC2626"; dIco = "alert-triangle"; }
    desc.innerHTML = `<i class="ti ti-${dIco}" style="margin-right:.35rem" aria-hidden="true"></i>${dTxt}`;
    desc.style.color = dCol;

    // ── Desglose del score (5 dimensiones) ──────────────────────
    const desg = document.getElementById("score-desglose");
    if (d.score_desglose && d.score_desglose.dimensiones) {
      let html = `<div class="section-title" style="margin-bottom:.5rem"><i class="ti ti-chart-bar" aria-hidden="true"></i> Desglose del score <span style="font-weight:400;text-transform:none;letter-spacing:normal;color:var(--muted);font-size:.72rem">(clic para ver detalle)</span></div>`;
      d.score_desglose.dimensiones.forEach(dim => {
        const pct = dim.max ? Math.round(dim.puntos / dim.max * 100) : 0;
        const c = pct >= 80 ? "#16A34A" : pct >= 50 ? "#D97706" : "#DC2626";
        const checksHtml = dim.checks.map(ch => {
          const col = ch.ok ? "var(--green)" : (ch.pts > 0 ? "var(--orange)" : "var(--red)");
          const ico = ch.ok ? "circle-check" : (ch.pts > 0 ? "alert-triangle" : "circle-x");
          return `<div class="chk-item"><i class="ti ti-${ico}" style="color:${col}" aria-hidden="true"></i><span>${escapeHtml(ch.label)} <span style="color:var(--muted)">(${ch.pts}/${ch.max})</span></span></div>`;
        }).join("");
        html += `<details class="score-dim">
            <summary>
              <div class="dim-head"><span class="dim-name">${escapeHtml(dim.nombre)}</span><span class="chk-cat-pts">${dim.puntos}/${dim.max}</span></div>
              <div class="ats-cat-bar"><span style="width:${pct}%;background:${c}"></span></div>
            </summary>
            <div style="margin-top:.6rem">${checksHtml}</div>
          </details>`;
      });
      desg.innerHTML = html;
      desg.style.display = "block";
    } else {
      desg.style.display = "none";
    }

    // ── Job title match ─────────────────────────────────────────
    const jt = document.getElementById("job-title-box");
    if (d.titulo_vacante) {
      const ok = d.titulo_cubierto;
      jt.className = "job-title-box " + (ok ? "ok" : "miss");
      jt.style.display = "block";
      jt.innerHTML =
        `<div class="jt-label"><i class="ti ti-target-arrow" aria-hidden="true"></i> Cargo objetivo de la vacante</div>` +
        `<div class="jt-value">${escapeHtml(d.titulo_vacante)}</div>` +
        `<div class="jt-status">${ok
          ? "✓ Tu CV ya menciona este cargo"
          : "⚠ No aparece en tu CV — al adaptar el DOCX lo añadiremos a tu titular"}</div>`;
    } else {
      jt.style.display = "none";
    }

    // ── Keywords ────────────────────────────────────────────────
    renderChipsHardSoft("chips-cubiertas", d.keywords_hard_skills_cubiertas, d.keywords_soft_skills_cubiertas, d.keywords_cubiertas);
    renderChipsHardSoft("chips-sugeridas", d.keywords_hard_skills_faltantes, d.keywords_soft_skills_faltantes, d.keywords_sugeridas);

    // ── Diagnóstico de contenido (FEAT-01..06, en el cliente) ───
    renderDiagnostico((document.getElementById("cv") || {}).value || "");

    // ── Señales de riesgo (Bloque 7) ────────────────────────────
    renderSenales((document.getElementById("cv") || {}).value || "", d);

    // ── Requisitos de la vacante (métricas 10-13) ───────────────
    renderRequisitos(d.requisitos);

    // ── CV adaptado ──────────────────────────────────────────────
    document.getElementById("cv-resumen").innerHTML =
      resaltarKeywords(d.cv_adaptado.resumen, d.keywords_cubiertas, d.keywords_sugeridas);

    renderExperiencia(d.cv_adaptado);
    renderLista("cv-habilidades", d.cv_adaptado.habilidades);

    // ── Notas ────────────────────────────────────────────────────
    const notasEl = document.getElementById("notas-list");
    notasEl.innerHTML = "";
    d.notas_para_usuario.forEach((nota, i) => {
      const div = document.createElement("div");
      div.className = "nota-item";
      div.innerHTML = `<span class="nota-icon">${NOTA_ICON}</span><span>${nota}</span>`;
      notasEl.appendChild(div);
    });

    // Mostrar sección
    const sec = document.getElementById("resultados");
    sec.style.display = "block";
    sec.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function renderChips(containerId, items, className) {
    const el = document.getElementById(containerId);
    el.innerHTML = "";
    if (!items || items.length === 0) {
      el.innerHTML = '<span style="color:var(--muted);font-size:.8rem">Ninguna detectada</span>';
      return;
    }
    items.forEach(kw => {
      const span = document.createElement("span");
      span.className = `chip ${className}`;
      span.textContent = kw;
      el.appendChild(span);
    });
  }

  // Chips separados en Hard skills (azul) y Soft skills (verde) — SCORE-03
  function renderChipsHardSoft(containerId, hard, soft, fallback) {
    const el = document.getElementById(containerId);
    hard = hard || []; soft = soft || [];
    if (!hard.length && !soft.length && fallback && fallback.length) hard = fallback;
    if (!hard.length && !soft.length) {
      el.innerHTML = '<span style="color:var(--muted);font-size:.8rem">Ninguna detectada</span>';
      return;
    }
    const grupo = (lista, cls, ico, lbl) => !lista.length ? "" :
      `<div class="kw-grupo"><div class="kw-grupo-lbl"><i class="ti ${ico}" aria-hidden="true"></i> ${lbl}</div>` +
      `<div class="chips">${lista.map(k => `<span class="chip ${cls}">${escapeHtml(k)}</span>`).join("")}</div></div>`;
    el.innerHTML = grupo(hard, "chip-hard", "ti-tool", "Hard skills") +
                   grupo(soft, "chip-soft", "ti-users", "Soft skills");
  }

  function renderLista(id, items) {
    const ul = document.getElementById(id);
    ul.innerHTML = "";
    (items || []).forEach(item => {
      const li = document.createElement("li");
      li.textContent = item;
      ul.appendChild(li);
    });
  }

  // Experiencia con jerarquía puesto → logros (Bug #4)
  function renderExperiencia(cva) {
    const cont = document.getElementById("cv-experiencia");
    cont.innerHTML = "";
    const est = cva.experiencia_estructurada;
    if (est && est.length) {
      est.forEach(p => {
        const div = document.createElement("div");
        div.className = "cv-puesto";
        let html = `<div class="cv-puesto-titulo">${escapeHtml(p.titulo)}</div>`;
        if (p.bullets && p.bullets.length) {
          html += `<ul>${p.bullets.map(b => `<li>${escapeHtml(b)}</li>`).join("")}</ul>`;
        }
        div.innerHTML = html;
        cont.appendChild(div);
      });
    } else {
      const ul = document.createElement("ul");
      (cva.experiencia || []).forEach(item => {
        const li = document.createElement("li");
        li.textContent = item;
        ul.appendChild(li);
      });
      cont.appendChild(ul);
    }
  }

  function animarNumero(el, desde, hasta, duracion) {
    const inicio = performance.now();
    function tick(ahora) {
      const t = Math.min((ahora - inicio) / duracion, 1);
      const ease = 1 - Math.pow(1 - t, 3); // ease-out cubic
      el.textContent = Math.round(desde + (hasta - desde) * ease);
      if (t < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  let _vacanteOriginal = null;
  function restaurarVacante() {
    if (_vacanteOriginal === null) return;
    document.getElementById("vacante").value = _vacanteOriginal;
    _vacanteOriginal = null;
    document.getElementById("btn-restaurar").style.display = "none";
    const st = document.getElementById("limpiar-status");
    st.className = "upload-status"; st.textContent = "Original restaurado";
    actualizarContador("vacante", "vacante-counter");
  }

  async function limpiarVacante() {
    const textarea = document.getElementById("vacante");
    const status   = document.getElementById("limpiar-status");
    const texto    = textarea.value.trim();

    if (!texto) {
      status.className = "upload-status err";
      status.textContent = "❌ Pega primero la descripción de la vacante";
      return;
    }

    _vacanteOriginal = textarea.value;
    status.className = "upload-status";
    status.innerHTML = '<span class="spinner-sm"></span>Limpiando…';

    try {
      const res = await fetch("/api/v1/limpiar-vacante", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ texto }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `Error ${res.status}`);

      const original = texto.split(/\s+/).length;
      const limpio   = data.texto.split(/\s+/).length;
      const reduccion = Math.round((1 - limpio / original) * 100);

      textarea.value = data.texto;
      document.getElementById("btn-restaurar").style.display = "inline-flex";
      actualizarContador("vacante", "vacante-counter");
      status.className = "upload-status ok";
      status.textContent = reduccion > 0
        ? `✅ Listo — se eliminó el ${reduccion}% de ruido`
        : "✅ Texto ya estaba limpio";
    } catch (e) {
      status.className = "upload-status err";
      status.textContent = "❌ " + (e.message || "Error al limpiar");
    }
  }

  async function subirArchivo(input) {
    const archivo = input.files[0];
    if (!archivo) return;

    const status = document.getElementById("upload-status");
    status.className = "upload-status";
    status.innerHTML = '<span class="spinner-sm"></span>Leyendo archivo…';

    const form = new FormData();
    form.append("archivo", archivo);

    try {
      const res = await fetch("/api/v1/extraer-cv", { method: "POST", body: form });
      if (!(res.headers.get("content-type") || "").includes("application/json"))
        throw new Error("El servidor devolvió una respuesta inesperada. Verifica que el archivo sea un PDF o DOCX válido y no esté protegido con contraseña.");
      const data = await res.json();

      if (!res.ok) throw new Error(data.detail || `Error ${res.status}`);

      document.getElementById("cv").value = data.texto;
      status.className = "upload-status ok";
      status.textContent = `✅ ${data.nombre} cargado`;
    } catch (e) {
      status.className = "upload-status err";
      status.textContent = "❌ " + (e.message || "No se pudo leer el archivo");
    }

    // Limpiar el input para permitir subir el mismo archivo de nuevo
    input.value = "";
  }

  function mostrarNombreDocx(input) {
    const nombre = input.files[0] ? input.files[0].name : "ningún archivo seleccionado";
    document.getElementById("docx-nombre").textContent = nombre;
    document.getElementById("docx-nombre").className = input.files[0] ? "upload-status ok" : "upload-status";
  }

  async function adaptarDocxOriginal() {
    const input   = document.getElementById("docx-original");
    const vacante = document.getElementById("vacante").value.trim();
    const status  = document.getElementById("adaptar-docx-status");

    if (!input.files[0]) {
      status.className = "upload-status err";
      status.textContent = "Selecciona tu CV en DOCX primero";
      return;
    }
    if (!vacante) {
      status.className = "upload-status err";
      status.textContent = "Pega la vacante arriba primero";
      return;
    }

    status.className = "upload-status";
    status.innerHTML = '<span class="spinner-sm"></span>Adaptando…';

    const form = new FormData();
    form.append("archivo", input.files[0]);
    form.append("vacante_texto", vacante);

    try {
      const res = await fetch("/api/v1/adaptar-docx-original", { method: "POST", body: form });
      if (!(res.headers.get("content-type") || "").includes("application/json"))
        throw new Error("El servidor devolvió una respuesta inesperada. Verifica que el archivo sea un PDF o DOCX válido y no esté protegido con contraseña.");
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Error ${res.status}`);
      }
      const data = await res.json();

      // 1. Descargar el DOCX adaptado
      const bytes  = Uint8Array.from(atob(data.archivo_base64), c => c.charCodeAt(0));
      const blob   = new Blob([bytes], { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" });
      const url    = URL.createObjectURL(blob);
      const a      = document.createElement("a");
      a.href       = url;
      a.download   = data.nombre;
      a.click();
      URL.revokeObjectURL(url);

      // 2. Actualizar el textarea del CV con el texto adaptado
      document.getElementById("cv").value = data.texto;

      status.className = "upload-status ok";
      status.textContent = "✅ Descargado — re-analizando...";

      // 3. Re-analizar automáticamente con el CV adaptado
      await analizar();

      status.textContent = "✅ Listo";

    } catch(e) {
      status.className = "upload-status err";
      status.textContent = "Error: " + e.message;
    }
  }

  async function generarCVAdaptado() {
    const cv      = document.getElementById("cv").value.trim();
    const vacante = document.getElementById("vacante").value.trim();
    const status  = document.getElementById("generar-status");
    const section = document.getElementById("cv-generado-section");

    if (!cv || !vacante) {
      mostrarError("Completa el CV y la vacante antes de generar.");
      return;
    }

    status.innerHTML = '<span class="spinner-sm"></span>Generando CV adaptado…';
    section.style.display = "block";
    section.scrollIntoView({ behavior: "smooth", block: "start" });

    try {
      const res = await fetch("/api/v1/generar-cv", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cv_texto: cv, vacante_texto: vacante }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `Error ${res.status}`);

      document.getElementById("cv-generado-texto").value = data.texto_completo;

      // Mostrar keywords incorporadas
      const kwWrap = document.getElementById("kw-incorporadas-wrap");
      if (data.keywords_incorporadas && data.keywords_incorporadas.length > 0) {
        kwWrap.style.display = "flex";
        // Limpiar chips previos (conservar el label)
        const chips = kwWrap.querySelectorAll(".chip");
        chips.forEach(c => c.remove());
        data.keywords_incorporadas.forEach(kw => {
          const span = document.createElement("span");
          span.className = "chip chip-purple";
          span.textContent = kw;
          kwWrap.appendChild(span);
        });
      }

      status.textContent = `✅ CV adaptado para: "${data.titulo_puesto}"`;
      status.style.color = "#15803D";

    } catch (e) {
      status.textContent = "❌ " + (e.message || "Error al generar el CV");
      status.style.color = "#DC2626";
    }
  }

  function copiarCV() {
    const texto = document.getElementById("cv-generado-texto").value;
    if (!texto) return;
    navigator.clipboard.writeText(texto).then(() => {
      const status = document.getElementById("generar-status");
      const prev = status.textContent;
      status.textContent = "📋 ¡Copiado al portapapeles!";
      status.style.color = "#15803D";
      setTimeout(() => { status.textContent = prev; }, 2000);
    });
  }

  async function descargarCV(formato) {
    const cv      = document.getElementById("cv").value.trim();
    const vacante = document.getElementById("vacante").value.trim();
    const status  = document.getElementById("generar-status");

    if (!cv || !vacante) {
      mostrarError("Completa el CV y la vacante antes de descargar.");
      return;
    }

    const prevStatus = status.textContent;
    status.innerHTML = `<span class="spinner-sm"></span>Generando ${formato.toUpperCase()}…`;
    status.style.color = "";

    try {
      const res = await fetch(`/api/v1/exportar-cv?formato=${formato}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cv_texto: cv, vacante_texto: vacante }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Error ${res.status}`);
      }

      const blob     = await res.blob();
      const url      = URL.createObjectURL(blob);
      const nombre   = cv.split("\n")[0].trim().replace(/\s+/g, "_") || "CV_Adaptado";
      const a        = document.createElement("a");
      a.href         = url;
      a.download     = `${nombre}_Adaptado.${formato}`;
      a.click();
      URL.revokeObjectURL(url);

      status.textContent = `✅ ${formato.toUpperCase()} descargado`;
      status.style.color = "#15803D";
      setTimeout(() => { status.textContent = prevStatus; status.style.color = ""; }, 3000);

    } catch (e) {
      status.textContent = "❌ " + (e.message || "Error al generar el archivo");
      status.style.color = "#DC2626";
    }
  }

  // ── Tabs ──────────────────────────────────────────────────────
  // ════════════ Checklist ATS — 20 checks (cliente) ════════════
  async function runChecklist() {
    const cv = (document.getElementById("checklist-cv").value.trim())
             || (document.getElementById("cv") ? document.getElementById("cv").value.trim() : "");
    const status = document.getElementById("checklist-status");
    const cont = document.getElementById("checklist-resultado");
    if (!cv || cv.length < 30) {
      status.className = "upload-status err";
      status.textContent = "Pega tu CV (o complétalo en «Adaptar a vacante») para analizarlo.";
      cont.style.display = "none";
      return;
    }
    status.textContent = "";

    // Fuente única: secciones y calidad vienen del backend (core.cv_analyzer),
    // para no contradecir a las otras pestañas. Si la red falla, se usa el
    // cálculo local como respaldo (modo offline).
    let core = null;
    try {
      const _f = new FormData();
      _f.append("cv_texto", cv);
      const _r = await fetch("/api/v1/analyze", { method: "POST", body: _f });
      if (_r.ok && (_r.headers.get("content-type") || "").includes("application/json")) {
        core = await _r.json();
      }
    } catch (e) { core = null; }

    const lower = cv.toLowerCase();
    const lineas = cv.split("\n").map(l => l.trim()).filter(Boolean);
    const bullets = lineas.filter(l => l.length > 20);

    const c = checkContactInfo(cv);
    const dt = checkDates(cv);
    const len = checkLength(cv);
    const weak = checkWeakPhrases(cv);
    const rep = checkRepetition(cv);
    const stuffing = checkKeywordStuffing(cv);

    const tieneUbic = /(location|ubicaci[oó]n|address|direcci[oó]n)\s*[:\-]/i.test(cv)
      || /\b(remote|remoto|madrid|barcelona|m[eé]xico|bogot[aá]|lima|santiago|buenos aires|new york|london|miami)\b/i.test(cv);
    let secResumen = /\b(professional\s+summary|summary|perfil|resumen|objetivo|about\s+me)\b/i.test(cv);
    let secExp = /\b(work\s+experience|experience|experiencia|employment|trayectoria|historial\s+laboral)\b/i.test(cv);
    let secEdu = /\b(education|educaci[oó]n|formaci[oó]n|academic)\b/i.test(cv);
    let secSkills = /\b(technical\s+skills?|skills?|habilidades|competencias?|conocimientos)\b/i.test(cv);
    if (core && core.secciones) {
      secResumen = !!core.secciones.resumen; secExp = !!core.secciones.experiencia;
      secEdu = !!core.secciones.educacion;   secSkills = !!core.secciones.habilidades;
    }
    const idxRes = lower.search(/\b(summary|resumen|perfil|profile|objetivo)\b/);
    const idxExp = lower.search(/\b(experience|experiencia|employment)\b/);
    const ordenOk = idxRes === -1 || idxExp === -1 || idxRes < idxExp;

    const _lineasPipe = cv.split("\n").filter(l => (l.match(/\|/g) || []).length >= 2).length;
    const sinTabla = !/[│┃]|[─━]{3,}|\t{2,}/.test(cv) && _lineasPipe < 3;
    const sinChars = !/[‘’“”•▪●—\u{1F300}-\u{1FAFF}]/u.test(cv);
    const tieneVinetas = /^[\s]*[-•*–·]\s+/m.test(cv);
    let conMetrica = lineas.filter(l => /\d+\s*%|\$\s*\d|\b\d[\d.,]*\s*\+|\bx\s?\d|\d{2,}/.test(l)).length;
    const verboRe = /^[\s\-•*–·]*(led|managed|built|created|designed|developed|implemented|reduced|increased|improved|launched|delivered|drove|optimized|achieved|resolved|analyzed|coordinated|automated|spearheaded|streamlined|lider|gestion|desarroll|implement|dise|reduj|aument|mejor|cre|coordin|logr|dirig|ejecut|analic)/i;
    let conVerbo = bullets.filter(l => verboRe.test(l)).length;
    let ratioVerbo = bullets.length ? conVerbo / bullets.length : 0;
    // Contenido desde el core (fuente única) cuando hay backend; si no, lo local.
    let nBullets = bullets.length, nWeak = weak.length, repList = rep, stuff = stuffing;
    if (core && core.calidad) {
      const cal = core.calidad;
      conMetrica = cal.con_metrica; conVerbo = cal.con_verbo; ratioVerbo = cal.ratio_verbo;
      nBullets = cal.bullets_total; nWeak = cal.relleno;
      repList = cal.repetidas || []; stuff = cal.stuffing;
    }

    const ok = "ok", warn = "warning", err = "error";
    // Estado de sección (3 estados del core): encabezado / contenido / ausente.
    const _estadoSec = (core && core.secciones_estado) || null;
    const _boolSec = { resumen: secResumen, experiencia: secExp, educacion: secEdu, habilidades: secSkills };
    const _secChk = (key, name, absentState) => {
      const st = _estadoSec ? _estadoSec[key] : null;
      if (st === "encabezado") return { label: `Sección ${name}`, estado: ok };
      if (st === "contenido")  return { label: `Sección ${name}: añade el encabezado «${name}»`, estado: warn };
      if (st === "ausente")    return { label: `Falta la sección ${name}`, estado: absentState };
      return { label: `Sección ${name}`, estado: _boolSec[key] ? ok : absentState };  // respaldo offline
    };
    const categorias = [
      { nombre: "Información de contacto", checks: [
        { label: "Email presente", estado: c.email ? ok : err },
        { label: "Teléfono presente", estado: c.phone ? ok : err },
        { label: "Perfil de LinkedIn", estado: c.linkedin ? ok : warn },
        { label: "Nombre al inicio del CV", estado: c.name ? ok : warn },
        { label: "Ubicación / ciudad indicada", estado: tieneUbic ? ok : warn },
      ]},
      { nombre: "Estructura y secciones", checks: [
        _secChk("resumen", "Resumen / Perfil", warn),
        _secChk("experiencia", "Experiencia", err),
        _secChk("educacion", "Educación", warn),
        _secChk("habilidades", "Habilidades", warn),
        { label: "Orden lógico (resumen → experiencia)", estado: ordenOk ? ok : warn },
      ]},
      { nombre: "Formato ATS", checks: [
        { label: `Longitud adecuada (${len.words} palabras)`, estado: len.status === "ok" ? ok : warn },
        { label: "Fechas en formato estándar (Mes AAAA)",
          estado: dt.goodDatesCount > 0 ? (dt.vagueFound.length ? warn : ok) : warn },
        { label: "Sin tablas ni columnas", estado: sinTabla ? ok : err },
        { label: "Sin caracteres especiales problemáticos", estado: sinChars ? ok : warn },
        { label: "Usa viñetas estándar (- •)", estado: tieneVinetas ? ok : warn },
      ]},
      { nombre: "Calidad de contenido", checks: [
        { label: `Logros con métricas numéricas (${conMetrica})`,
          estado: conMetrica >= 2 ? ok : (conMetrica === 1 ? warn : err) },
        { label: `Verbos de acción al inicio (${conVerbo}/${nBullets})`,
          estado: ratioVerbo >= 0.4 ? ok : warn },
        { label: nWeak ? `Frases débiles de relleno (${nWeak})` : "Sin frases débiles de relleno",
          estado: nWeak === 0 ? ok : warn },
        { label: repList.length ? `Palabras muy repetidas (${repList.slice(0, 3).join(", ")})` : "Sin palabras muy repetidas",
          estado: repList.length === 0 ? ok : warn },
        { label: "Sin keyword stuffing", estado: stuff ? err : ok },
      ]},
    ];
    renderChecklist(categorias);
    cont.style.display = "block";
    cont.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function renderChecklist(categorias) {
    const PTS = { ok: 5, warning: 2, error: 0 };
    const COL = { ok: "var(--green)", warning: "var(--orange)", error: "var(--red)" };
    const ICO = { ok: "circle-check", warning: "alert-triangle", error: "circle-x" };
    let total = 0;
    let cats = "";
    categorias.forEach(cat => {
      const cp = cat.checks.reduce((s, ch) => s + PTS[ch.estado], 0);
      total += cp;
      const pct = Math.round(cp / 25 * 100);
      const barC = pct >= 80 ? "#16A34A" : pct >= 50 ? "#D97706" : "#DC2626";
      const items = cat.checks.map(ch =>
        `<div class="chk-item"><i class="ti ti-${ICO[ch.estado]}" style="color:${COL[ch.estado]}" aria-hidden="true"></i><span>${escapeHtml(ch.label)}</span></div>`).join("");
      cats += `<details class="chk-cat" open>
          <summary><span class="chk-cat-name">${escapeHtml(cat.nombre)}</span><span class="chk-cat-pts">${cp}/25</span></summary>
          <div class="ats-cat-bar" style="margin:.5rem 0 .6rem"><span style="width:${pct}%;background:${barC}"></span></div>
          ${items}
        </details>`;
    });
    const tc = total >= 80 ? "#16A34A" : total >= 50 ? "#D97706" : "#DC2626";
    const veredicto = total >= 80 ? "Tu CV está bien preparado para ATS"
      : total >= 50 ? "Tu CV pasa lo básico, pero hay margen de mejora"
      : "Tu CV necesita ajustes importantes para los ATS";
    document.getElementById("checklist-resultado").innerHTML =
      `<div class="card chk-score"><div class="n" style="color:${tc}">${total}/100</div>` +
      `<div class="l">${escapeHtml(veredicto)}</div></div>` +
      `<div style="margin-top:1rem">${cats}</div>`;
  }

  function cambiarTab(tab) {
    document.querySelectorAll(".tab-content").forEach(el => el.classList.remove("active"));
    document.querySelectorAll(".tab-btn").forEach(el => el.classList.remove("active"));
    document.getElementById("tab-" + tab).classList.add("active");
    document.getElementById("tabbtn-" + tab).classList.add("active");
    // Checklist: pre-rellenar con el CV ya pegado en "Adaptar a vacante"
    if (tab === "checklist") {
      const dst = document.getElementById("checklist-cv");
      const src = document.getElementById("cv");
      if (dst && src && !dst.value.trim() && src.value.trim()) dst.value = src.value;
    }
    // 15 Métricas: heredar la descripción de la vacante pegada en "Adaptar"
    if (tab === "metricas") {
      const dv = document.getElementById("metricas-vacante");
      const sv = document.getElementById("vacante");
      if (dv && sv && !dv.value.trim() && sv.value.trim()) dv.value = sv.value;
    }
  }

  // ── Análisis ATS standalone (sin vacante) ─────────────────────
  // ── Entrada unificada (Bug #7): <input file> o {texto} del CV pegado ──
  const _GUARD_CT = "El servidor devolvió una respuesta inesperada. Verifica que el CV sea un PDF/DOCX válido (sin contraseña) o pega el texto.";
  function _fuenteCV(fuente) {
    const form = new FormData();
    if (fuente && fuente.files) {
      const archivo = fuente.files[0];
      if (!archivo) return null;
      form.append("archivo", archivo);
      return { form, nombre: archivo.name, reset: () => { fuente.value = ""; } };
    }
    if (fuente && fuente.texto) {
      form.append("cv_texto", fuente.texto);
      return { form, nombre: "tu CV pegado", reset: () => {} };
    }
    return null;
  }
  function usarCVPegado(pestana) {
    const t = (document.getElementById("cv").value || "").trim();
    if (!t) {
      alert("Primero pega tu CV en la pestaña «Adaptar a vacante» (campo «Tu CV»).");
      cambiarTab("adaptar");
      return;
    }
    // 15 Métricas: el botón importa también la vacante del estado de "Adaptar"
    // (no solo el CV) para que recalcule Match/Skills con la job description.
    if (pestana === "metricas") {
      const sv = (document.getElementById("vacante").value || "").trim();
      const dv = document.getElementById("metricas-vacante");
      if (dv && sv) dv.value = sv;
    }
    const fn = { ats: analizarATS, parsing: analizarParsing, bullets: analizarBullets, plantilla: optimizarCV, metricas: analizarMetricas }[pestana];
    if (fn) fn({ texto: t });
  }

  // ── 15 Métricas competitivas ──────────────────────────────────
  function _colMetrica(s) { return s >= 80 ? "#16A34A" : s >= 60 ? "#D97706" : "#DC2626"; }

  function _shortCat(c) {
    return ({ "Compatibilidad ATS": "ATS", "Match con Vacante": "Match",
              "Skills y Requisitos": "Skills", "Calidad del Contenido": "Calidad",
              "Formato y Riesgo": "Formato" })[c] || c;
  }

  function _radarMetricas(cats) {
    const N = cats.length;
    if (N < 3) return "";              // un radar necesita al menos 3 ejes
    const cx = 170, cy = 150, R = 95;
    const ang = i => (-90 + i * 360 / N) * Math.PI / 180;
    const pt = (i, r) => [cx + r * Math.cos(ang(i)), cy + r * Math.sin(ang(i))];
    let grid = "";
    [0.25, 0.5, 0.75, 1].forEach(f => {
      const pts = cats.map((_, i) => pt(i, R * f).map(n => n.toFixed(1)).join(",")).join(" ");
      grid += `<polygon points="${pts}" fill="none" stroke="#e2e8f0" stroke-width="1"/>`;
    });
    let axes = "";
    cats.forEach((_, i) => {
      const [x, y] = pt(i, R);
      axes += `<line x1="${cx}" y1="${cy}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}" stroke="#e2e8f0" stroke-width="1"/>`;
    });
    const dpts = cats.map((c, i) => pt(i, R * (c.score / 100)).map(n => n.toFixed(1)).join(",")).join(" ");
    let labels = "", dots = "";
    cats.forEach((c, i) => {
      const [lx, ly] = pt(i, R + 24);
      const anchor = Math.abs(lx - cx) < 12 ? "middle" : (lx > cx ? "start" : "end");
      labels += `<text x="${lx.toFixed(1)}" y="${ly.toFixed(1)}" text-anchor="${anchor}" dominant-baseline="middle" font-size="11" fill="#475569">${escapeHtml(c.label)}</text>`;
      labels += `<text x="${lx.toFixed(1)}" y="${(ly + 14).toFixed(1)}" text-anchor="${anchor}" dominant-baseline="middle" font-size="12" font-weight="700" fill="${_colMetrica(c.score)}">${c.score}</text>`;
      const [dx, dy] = pt(i, R * (c.score / 100));
      dots += `<circle cx="${dx.toFixed(1)}" cy="${dy.toFixed(1)}" r="3" fill="#2563eb"/>`;
    });
    return `<svg viewBox="0 0 340 300" width="100%" style="max-width:420px" xmlns="http://www.w3.org/2000/svg">
      ${grid}${axes}
      <polygon points="${dpts}" fill="rgba(37,99,235,0.18)" stroke="#2563eb" stroke-width="2"/>
      ${dots}${labels}
    </svg>`;
  }

  async function analizarMetricas(fuente) {
    const src = _fuenteCV(fuente);
    if (!src) return;
    // Lee la vacante del campo propio o, si está vacío, del estado compartido
    // ("Adaptar a vacante"), para no perder el match cuando se usa "usar CV pegado".
    const vac = (document.getElementById("metricas-vacante").value || "").trim()
             || (document.getElementById("vacante").value || "").trim();
    if (vac) {
      src.form.append("vacante_texto", vac);
      const dv = document.getElementById("metricas-vacante");
      if (dv && !dv.value.trim()) dv.value = vac;   // reflejarla en el campo
    }
    const status    = document.getElementById("metricas-file-status");
    const resultado = document.getElementById("metricas-resultado");
    status.className = "upload-status";
    status.innerHTML = '<span class="spinner-sm"></span>Calculando métricas de ' + src.nombre + "…";
    try {
      const res  = await fetch("/api/v1/metricas", { method: "POST", body: src.form });
      if (!(res.headers.get("content-type") || "").includes("application/json")) throw new Error(_GUARD_CT);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `Error ${res.status}`);
      status.className = "upload-status ok";
      status.textContent = "✅ " + src.nombre + " analizado";
      renderMetricas(data);
      resultado.style.display = "block";
      resultado.scrollIntoView({ behavior: "smooth", block: "start" });
      if (src.reset) src.reset();
    } catch (e) {
      status.className = "upload-status err";
      status.textContent = "⚠️ " + e.message;
    }
  }

  function _barKw(it) {
    const exp = Math.max(1, it.freq_vacante);
    const pct = Math.min(100, Math.round(it.freq_cv / exp * 100));
    const col = it.sobreoptimizada ? "#DC2626" : (it.cubierta ? "#16A34A" : "#D97706");
    return `<div style="height:6px;background:#eef2f7;border-radius:6px;overflow:hidden"><div style="height:100%;width:${pct}%;background:${col}"></div></div>`;
  }

  function renderKeywordsDetalle(kd) {
    const card = document.getElementById("metricas-keywords-card");
    const box = document.getElementById("metricas-keywords");
    const items = (kd && kd.items) || [];
    if (!items.length) { card.style.display = "none"; box.innerHTML = ""; return; }

    const TIPO = {
      title: { l: "Cargo / Título", c: "#db2777" },
      hard:  { l: "Hard skills", c: "#2563eb" },
      tool:  { l: "Herramientas / Plataformas", c: "#0d9488" },
      soft:  { l: "Soft skills", c: "#7c3aed" },
    };
    const porTipo = kd.por_tipo || {};

    const fila = it => {
      const falta = Math.max(0, it.freq_vacante - it.freq_cv);
      const estadoCol = it.sobreoptimizada ? "#DC2626" : (it.cubierta ? "#16A34A" : "#D97706");
      const badge = it.sobreoptimizada
        ? `<span style="font-size:.7rem;font-weight:700;color:#DC2626;background:#fee2e2;border-radius:999px;padding:.05rem .5rem">sobreoptimizada</span>`
        : (it.cubierta
            ? `<span style="font-size:.7rem;color:#166534;background:#dcfce7;border-radius:999px;padding:.05rem .5rem">✓ cubierta</span>`
            : `<span style="font-size:.7rem;color:#92400e;background:#fef3c7;border-radius:999px;padding:.05rem .5rem">falta ${falta}</span>`);
      return `<div style="display:flex;align-items:center;gap:.6rem;padding:.4rem 0;border-top:1px solid #eef2f7">
        <div style="flex:1;min-width:0;font-size:.86rem;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escapeHtml(it.keyword)}</div>
        <div style="font-size:.78rem;color:var(--muted);white-space:nowrap">vacante <strong style="color:var(--text)">${it.freq_vacante}</strong> · CV <strong style="color:${estadoCol}">${it.freq_cv}</strong></div>
        <div style="width:80px;flex-shrink:0">${_barKw(it)}</div>
        <div style="width:108px;flex-shrink:0;text-align:right">${badge}</div>
      </div>`;
    };

    box.innerHTML = ["title", "hard", "tool", "soft"]
      .filter(t => porTipo[t] && porTipo[t].length)
      .map(t => `<div style="margin-bottom:.7rem">
        <div style="font-size:.74rem;font-weight:700;color:${TIPO[t].c};text-transform:uppercase;letter-spacing:.03em;margin-bottom:.15rem">${TIPO[t].l}</div>
        ${porTipo[t].map(fila).join("")}
      </div>`).join("");
    card.style.display = "block";
  }

  function renderMetricas(d) {
    const score = d.score_global || 0;
    const circumference = 2 * Math.PI * 54;
    const fill = document.getElementById("metricas-score-fill");
    fill.style.strokeDashoffset = circumference - (score / 100) * circumference;
    const color = _colMetrica(score);
    fill.style.stroke = color;
    const numEl = document.getElementById("metricas-score-number");
    numEl.style.color = color;
    animarNumero(numEl, 0, score, 1000);
    const cg = d.cobertura_global;
    const baseG = cg ? ` Basado en ${cg.aplicables} de ${cg.total} métricas aplicables; las N/A se excluyen (nunca cuentan como 100).` : "";
    document.getElementById("metricas-resumen").textContent =
      "Media de las métricas aplicables." + baseG;

    const pc = document.getElementById("metricas-prioritarias-card");
    const ol = document.getElementById("metricas-prioritarias");
    const pr = d.prioritarias || [];
    if (pr.length) {
      ol.innerHTML = pr.map(p =>
        `<li style="margin-bottom:.5rem"><strong style="color:${_colMetrica(p.score)}">${escapeHtml(p.nombre)} (${p.score})</strong> — ${escapeHtml(p.recomendacion)}</li>`
      ).join("");
      pc.style.display = "block";
    } else {
      pc.style.display = "none";
    }

    // Agregado por categoría con la regla de N/A (excluye no aplicables) + cobertura.
    const _cov = cat => (d.resumen_categorias && d.resumen_categorias[cat]) || null;
    const catAvg = cat => {
      const c = _cov(cat);
      if (c) return c.score == null ? 0 : c.score;
      const items = (d.por_categoria && d.por_categoria[cat]) || [];   // respaldo
      const ap = items.filter(m => m.aplica).map(m => m.score);
      return ap.length ? Math.round(ap.reduce((a, b) => a + b, 0) / ap.length) : 0;
    };
    const radarCats = (d.categorias || []).map(cat => ({ label: _shortCat(cat), score: catAvg(cat) }));
    document.getElementById("metricas-radar").innerHTML = _radarMetricas(radarCats);

    renderKeywordsDetalle(d.keywords_detalle);

    const cont = document.getElementById("metricas-grupos");
    cont.innerHTML = (d.categorias || []).map(cat => {
      const items = (d.por_categoria && d.por_categoria[cat]) || [];
      if (!items.length) return "";
      const avg = catAvg(cat);
      const filas = items.map(m => {
        const sep = 'padding:.7rem 0;border-top:1px solid #e8edf3';
        if (!m.aplica) {
          return `<div style="${sep}">
            <div style="display:flex;justify-content:space-between;align-items:center">
              <strong style="font-size:.92rem">${escapeHtml(m.nombre)}</strong>
              <span style="color:var(--muted);font-size:.8rem">N/A</span>
            </div>
            <div style="font-size:.82rem;color:var(--muted);margin-top:.25rem">${escapeHtml(m.explicacion)}</div>
          </div>`;
        }
        const col = _colMetrica(m.score);
        return `<div style="${sep}">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <strong style="font-size:.92rem">${escapeHtml(m.nombre)}</strong>
            <span style="color:${col};font-weight:600">${m.score}</span>
          </div>
          <div style="height:7px;background:#eef2f7;border-radius:6px;margin:.4rem 0;overflow:hidden">
            <div style="height:100%;width:${m.score}%;background:${col};border-radius:6px"></div>
          </div>
          <div style="font-size:.82rem;color:var(--muted)">${escapeHtml(m.explicacion)}</div>
          <div style="font-size:.82rem;margin-top:.2rem"><strong>Sugerencia:</strong> ${escapeHtml(m.recomendacion)}</div>
        </div>`;
      }).join("");
      const cov = _cov(cat);
      const base = (cov && cov.aplicables < cov.total)
        ? ` <span style="color:var(--muted);font-weight:400;font-size:.76rem">· ${cov.aplicables} de ${cov.total} métricas</span>`
        : "";
      const scoreTxt = (cov && cov.score == null) ? "—" : avg;
      return `<div class="card" style="margin-bottom:1rem">
        <div class="section-title" style="display:flex;justify-content:space-between;align-items:center">
          <span>${escapeHtml(cat)}</span>
          <span style="font-size:.85rem;font-weight:700;color:${_colMetrica(avg)}">${scoreTxt}<span style="color:var(--muted);font-weight:400">/100</span>${base}</span>
        </div>
        ${filas}
      </div>`;
    }).join("");
  }

  async function analizarATS(fuente) {
    const src = _fuenteCV(fuente);
    if (!src) return;
    const status    = document.getElementById("ats-file-status");
    const resultado = document.getElementById("ats-resultado");
    status.className = "upload-status";
    status.innerHTML = '<span class="spinner-sm"></span>Analizando ' + src.nombre + "…";
    try {
      const res  = await fetch("/api/v1/analizar-ats", { method: "POST", body: src.form });
      if (!(res.headers.get("content-type") || "").includes("application/json")) throw new Error(_GUARD_CT);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `Error ${res.status}`);
      status.className = "upload-status ok";
      status.textContent = "✅ " + src.nombre + " analizado";
      renderATS(data);
      resultado.style.display = "block";
      resultado.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) {
      status.className = "upload-status err";
      status.textContent = "❌ " + (e.message || "No se pudo analizar el CV");
    }
    src.reset();
  }

  function renderATS(d) {
    // Círculo de score
    const score = d.score;
    const circumference = 2 * Math.PI * 54;
    const fill = document.getElementById("ats-score-fill");
    fill.style.strokeDashoffset = circumference - (score / 100) * circumference;
    const color = score >= 70 ? "#16A34A" : score >= 50 ? "#D97706" : "#DC2626";
    fill.style.stroke = color;
    const numEl = document.getElementById("ats-score-number");
    numEl.style.color = color;
    animarNumero(numEl, 0, score, 1000);

    // Nivel + resumen
    const nivelEl = document.getElementById("ats-nivel");
    nivelEl.textContent = d.nivel;
    nivelEl.style.color = color;
    document.getElementById("ats-resumen").textContent = d.resumen;

    // Badges
    const badges = document.getElementById("ats-badges");
    badges.innerHTML = "";
    if (d.n_errores > 0)
      badges.innerHTML += `<span class="ats-badge err">${d.n_errores} crítico(s)</span>`;
    if (d.n_advertencias > 0)
      badges.innerHTML += `<span class="ats-badge warn">${d.n_advertencias} mejora(s)</span>`;
    if (d.n_errores === 0 && d.n_advertencias === 0)
      badges.innerHTML += `<span class="ats-badge ok">Sin problemas</span>`;

    // Categorías
    const cont = document.getElementById("ats-categorias");
    cont.innerHTML = "";
    const ICO = { ok: '<i class="ti ti-circle-check" aria-hidden="true"></i>', warning: '<i class="ti ti-alert-triangle" aria-hidden="true"></i>', error: '<i class="ti ti-circle-x" aria-hidden="true"></i>' };
    d.categorias.forEach(cat => {
      const tienePts = cat.max_puntos > 0;
      const pct = tienePts ? Math.round(cat.puntos / cat.max_puntos * 100) : 0;
      const barColor = pct >= 80 ? "#16A34A" : pct >= 50 ? "#D97706" : "#DC2626";

      let checksHtml = "";
      cat.checks.forEach(ch => {
        checksHtml += `
          <div class="ats-check ${ch.estado}">
            <span class="ico">${ICO[ch.estado] || "•"}</span>
            <div class="body">
              <div class="t">${escapeHtml(ch.titulo)}</div>
              <div class="d">${escapeHtml(ch.detalle)}</div>
            </div>
          </div>`;
      });

      cont.innerHTML += `
        <div class="ats-cat">
          <div class="ats-cat-header">
            <span class="name">${cat.icono} ${escapeHtml(cat.nombre)}</span>
            <span class="pts">${tienePts ? cat.puntos + "/" + cat.max_puntos : "N/A"}</span>
          </div>
          ${tienePts ? `<div class="ats-cat-bar"><span style="width:${pct}%;background:${barColor}"></span></div>` : ""}
          ${checksHtml}
        </div>`;
    });
  }

  function escapeHtml(s) {
    return (s || "").replace(/[&<>"']/g, c => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c]));
  }

  // ════════════ Vista del reclutador (Parsing ATS) ════════════
  async function analizarParsing(fuente) {
    const src = _fuenteCV(fuente);
    if (!src) return;
    const status    = document.getElementById("parsing-file-status");
    const resultado = document.getElementById("parsing-resultado");
    status.className = "upload-status";
    status.innerHTML = '<span class="spinner-sm"></span>Analizando ' + src.nombre + "…";
    try {
      const res  = await fetch("/api/v1/parsing-ats", { method: "POST", body: src.form });
      if (!(res.headers.get("content-type") || "").includes("application/json")) throw new Error(_GUARD_CT);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `Error ${res.status}`);
      status.className = "upload-status ok";
      status.textContent = "✅ " + src.nombre + " analizado";
      renderParsing(data);
      resultado.style.display = "block";
      resultado.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) {
      status.className = "upload-status err";
      status.textContent = "❌ " + (e.message || "No se pudo analizar el CV");
    }
    src.reset();
  }

  function renderParsing(d) {
    const score = d.score;
    const circ = 2 * Math.PI * 54;
    const fill = document.getElementById("parsing-score-fill");
    fill.style.strokeDashoffset = circ - (score / 100) * circ;
    const color = score >= 80 ? "#16A34A" : score >= 60 ? "#D97706" : "#DC2626";
    fill.style.stroke = color;
    const numEl = document.getElementById("parsing-score-number");
    numEl.style.color = color;
    animarNumero(numEl, 0, score, 1000);
    document.getElementById("parsing-resumen").textContent = d.resumen;

    const badges = document.getElementById("parsing-badges");
    badges.innerHTML = d.no_detectados.length
      ? `<span class="ats-badge err">${d.no_detectados.length} campo(s) no detectado(s)</span>`
      : `<span class="ats-badge ok">Datos completos</span>`;

    // Campos
    const etiquetas = {
      nombre: "Nombre", email: "Email", telefono: "Teléfono",
      linkedin: "LinkedIn", ubicacion: "Ubicación", experiencia: "Años de experiencia"
    };
    const cont = document.getElementById("parsing-campos");
    cont.innerHTML = "";
    Object.keys(etiquetas).forEach(k => {
      const val = d.campos[k];
      cont.innerHTML += `
        <div class="parse-field ${val ? "" : "missing"}">
          <div class="label">${etiquetas[k]}</div>
          <div class="value">${val ? escapeHtml(val) : "✗ No detectado"}</div>
        </div>`;
    });

    // Puestos
    const pc = document.getElementById("parsing-puestos");
    pc.innerHTML = d.puestos.length
      ? d.puestos.map(p => `
          <div class="parse-job">
            <div class="role">${escapeHtml(p.titulo)}</div>
            ${p.empresa ? `<div class="org">${escapeHtml(p.empresa)}</div>` : ""}
            <div class="per">${escapeHtml(p.periodo)}</div>
          </div>`).join("")
      : `<p style="color:#DC2626;font-size:.85rem">✗ El ATS no detectó experiencia laboral con fechas claras.</p>`;

    // Gaps en el historial (#15)
    const gc = document.getElementById("parsing-gaps");
    if (gc) {
      const gaps = d.gaps || [];
      gc.innerHTML = gaps.length
        ? `<div class="ats-check warning"><span class="ico"><i class="ti ti-calendar-off" aria-hidden="true"></i></span>`
          + `<div class="body"><div class="t" style="font-size:.84rem">Huecos en el historial laboral</div>`
          + `<div class="d">${gaps.map(g => `${g.meses} mes(es) entre ${g.desde} y ${g.hasta}`).join("; ")}`
          + ` — prepárate para explicarlos o añade formación/proyectos del periodo.</div></div></div>`
        : "";
    }

    // Educación
    const ec = document.getElementById("parsing-educacion");
    ec.innerHTML = d.educacion.length
      ? d.educacion.map(e => `<li>${escapeHtml(e)}</li>`).join("")
      : `<li style="color:#DC2626">✗ No detectada</li>`;

    // Skills
    const sc = document.getElementById("parsing-skills");
    sc.innerHTML = d.skills.length
      ? d.skills.map(s => `<span class="chip chip-purple">${escapeHtml(s)}</span>`).join("")
      : `<span style="color:#DC2626;font-size:.85rem">✗ No detectadas</span>`;
  }

  // ════════════ Comparar vacantes ════════════
  function agregarVacante() {
    const cont = document.getElementById("comparar-inputs");
    if (cont.querySelectorAll(".vac-input").length >= 5) return;
    const ta = document.createElement("textarea");
    ta.className = "vac-input";
    ta.placeholder = "Vacante " + (cont.querySelectorAll(".vac-input").length + 1) + ": pega aquí la descripción...";
    cont.appendChild(ta);
  }

  async function compararVacantes() {
    const inputs = document.querySelectorAll("#comparar-inputs .vac-input");
    const vacantes = Array.from(inputs).map(t => t.value.trim()).filter(Boolean);
    const cv = document.getElementById("comparar-cv").value.trim();
    const status = document.getElementById("comparar-status");

    if (vacantes.length < 2) {
      status.className = "upload-status err";
      status.textContent = "Pega al menos 2 vacantes";
      return;
    }
    status.className = "upload-status";
    status.innerHTML = '<span class="spinner-sm"></span>Comparando…';

    try {
      const res = await fetch("/api/v1/comparar-vacantes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ vacantes, cv_texto: cv })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `Error ${res.status}`);
      status.className = "upload-status ok";
      status.textContent = `✅ ${data.total_vacantes} vacantes analizadas`;
      renderComparar(data);
      document.getElementById("comparar-resultado").style.display = "block";
    } catch (e) {
      status.className = "upload-status err";
      status.textContent = "❌ " + (e.message || "Error al comparar");
    }
  }

  function renderComparar(d) {
    document.getElementById("comparar-resumen").textContent = d.resumen;
    const grupos = {
      imprescindible: { el: "comparar-imp", bg: "rgba(239,68,68,.15)",  col: "#DC2626" },
      muy_pedida:     { el: "comparar-muy", bg: "rgba(245,158,11,.12)", col: "#B45309" },
      ocasional:      { el: "comparar-oca", bg: "var(--bg)",            col: "var(--muted)" },
    };
    Object.values(grupos).forEach(g => document.getElementById(g.el).innerHTML = "");
    d.keywords.forEach(k => {
      const g = grupos[k.categoria];
      if (!g) return;
      const incv = k.en_cv ? " chip-incv" : "";
      const check = k.en_cv ? " ✓" : "";
      document.getElementById(g.el).innerHTML +=
        `<span class="chip${incv}" style="background:${g.bg};color:${g.col}">` +
        `${escapeHtml(k.keyword)}${check}<span class="chip-count">${k.frecuencia}/${k.total}</span></span>`;
    });
    Object.values(grupos).forEach(g => {
      const el = document.getElementById(g.el);
      if (!el.innerHTML) el.innerHTML = `<span style="color:var(--muted);font-size:.82rem">—</span>`;
    });
  }

  // ════════════ Mejorar bullets ════════════
  async function analizarBullets(fuente) {
    const src = _fuenteCV(fuente);
    if (!src) return;
    const status    = document.getElementById("bullets-file-status");
    const resultado = document.getElementById("bullets-resultado");
    status.className = "upload-status";
    status.innerHTML = '<span class="spinner-sm"></span>Analizando ' + src.nombre + "…";
    try {
      const res  = await fetch("/api/v1/mejorar-bullets", { method: "POST", body: src.form });
      if (!(res.headers.get("content-type") || "").includes("application/json")) throw new Error(_GUARD_CT);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `Error ${res.status}`);
      status.className = "upload-status ok";
      status.textContent = "✅ " + src.nombre + " analizado";
      renderBullets(data);
      resultado.style.display = "block";
      resultado.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) {
      status.className = "upload-status err";
      status.textContent = "❌ " + (e.message || "No se pudo analizar el CV");
    }
    src.reset();
  }

  function renderBullets(d) {
    document.getElementById("bullets-resumen").textContent = d.resumen;
    const cont = document.getElementById("bullets-lista");
    cont.innerHTML = "";
    if (!d.mejoras || !d.mejoras.length) {
      cont.innerHTML = `<div style="color:var(--muted);font-size:.85rem">No hay bullets que mejorar — ¡tus logros ya usan verbos de acción y métricas!</div>`;
      return;
    }
    d.mejoras.forEach(m => {
      const badges = (m.tipos || []).map(t =>
        t === "verbo"
          ? `<span class="bullet-badge b-verbo">Verbo de acción</span>`
          : `<span class="bullet-badge b-metrica">Métrica añadida</span>`
      ).join(" ");
      const nota = m.metrica_agregada
        ? `<div class="bullet-metric">⚠ Ajusta el número marcado con « ~ » a tu cifra real.</div>`
        : "";
      cont.innerHTML += `
        <div class="bullet-card">
          <div class="bullet-badges">${badges}</div>
          <div class="bullet-row old">
            <span class="tag before">Antes</span>
            <span class="txt">${escapeHtml(m.original)}</span>
          </div>
          <div class="bullet-row">
            <span class="tag after">Después</span>
            <span class="txt">${escapeHtml(m.mejorado)}</span>
          </div>
          ${nota}
        </div>`;
    });
  }

  // ════════════ Optimizador ATS (pipeline completo) ════════════
  // ── Vista previa del Optimizador ATS (antes/después con resaltado) ──
  const _OPTIM_TIPO = {
    estructura: { c: "#64748b", l: "Estructura" },
    secciones:  { c: "#2563eb", l: "Secciones renombradas" },
    fechas:     { c: "#D97706", l: "Fechas normalizadas" },
    orden:      { c: "#0d9488", l: "Orden cronológico" },
    verbos:     { c: "#7c3aed", l: "Verbos de acción" },
    metricas:   { c: "#7c3aed", l: "Métricas de impacto" },
    cargo:      { c: "#db2777", l: "Cargo objetivo" },
    keywords:   { c: "#16A34A", l: "Keywords inyectadas" },
    acronimos:  { c: "#0ea5e9", l: "Acrónimos expandidos" },
  };

  function _resaltarOptim(texto, keywords) {
    const headerRe = /^[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ &/]{3,}$/;
    const dateRe = /\b((?:ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic|jan|apr|aug|dec|enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|january|february|march|april|june|july|august|september|october|november|december)[a-zá-ú]*\.?\s+\d{4})\b/gi;
    const kw = (keywords || []).map(k => (k || "").trim()).filter(Boolean).sort((a, b) => b.length - a.length);
    const kwRe = kw.length ? new RegExp("(" + kw.map(k => k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|") + ")", "gi") : null;
    return texto.split("\n").map(raw => {
      const esc = escapeHtml(raw);
      if (headerRe.test(raw.trim())) return `<span style="color:#2563eb;font-weight:700">${esc}</span>`;
      let l = esc;
      if (kwRe) l = l.replace(kwRe, m => `<mark style="background:#dcfce7;color:#166534;padding:0 2px;border-radius:3px">${m}</mark>`);
      l = l.replace(dateRe, m => `<span style="background:#fef3c7;color:#92400e;border-radius:3px;padding:0 2px">${m}</span>`);
      return l;
    }).join("\n");
  }

  function renderOptimPreview(data) {
    const cambios = (data.cambios || []).map(c => typeof c === "string" ? { tipo: "secciones", texto: c } : c);

    const tipos = [...new Set(cambios.map(c => c.tipo))];
    document.getElementById("optimizador-leyenda").innerHTML = tipos.map(t => {
      const m = _OPTIM_TIPO[t] || { c: "#64748b", l: t };
      return `<span style="display:inline-flex;align-items:center;gap:.3rem;font-size:.74rem;font-weight:600;color:${m.c};background:${m.c}1a;border:1px solid ${m.c}55;border-radius:999px;padding:.15rem .6rem"><span style="width:8px;height:8px;border-radius:50%;background:${m.c}"></span>${escapeHtml(m.l)}</span>`;
    }).join("");

    document.getElementById("optimizador-cambios").innerHTML = cambios.map(c => {
      const m = _OPTIM_TIPO[c.tipo] || { c: "#16A34A" };
      return `<li><i class="ti ti-point-filled" style="color:${m.c};margin-right:.35rem" aria-hidden="true"></i>${escapeHtml(c.texto)}</li>`;
    }).join("");

    const kws = data.keywords_inyectadas || [];
    document.getElementById("optimizador-keywords").innerHTML = kws.length
      ? `<div style="font-size:.82rem"><strong>Keywords de la vacante inyectadas:</strong> ` +
        kws.map(k => `<mark style="background:#dcfce7;color:#166534;padding:0 4px;border-radius:3px;margin:0 2px">${escapeHtml(k)}</mark>`).join("") + `</div>`
      : "";

    document.getElementById("optimizador-original").textContent = data.texto_original || "";
    document.getElementById("optimizador-optimizado").innerHTML = _resaltarOptim(data.texto_optimizado || "", kws);

    // La descarga aparece SOLO después de pintar la vista previa.
    const btn = document.getElementById("plantilla-download");
    btn.onclick = () => {
      const bytes = Uint8Array.from(atob(data.archivo_base64), c => c.charCodeAt(0));
      const blob = new Blob([bytes], { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = data.nombre; a.click();
      URL.revokeObjectURL(url);
    };
    document.getElementById("optimizador-descarga").style.display = "block";
  }

  async function optimizarCV(fuente) {
    const src = _fuenteCV(fuente);
    if (!src) return;
    const status = document.getElementById("plantilla-status");
    const resultado = document.getElementById("plantilla-resultado");
    const vacante = document.getElementById("optimizador-vacante").value.trim();
    if (vacante) src.form.append("vacante_texto", vacante);
    status.className = "upload-status";
    status.innerHTML = '<span class="spinner-sm"></span>Optimizando ' + src.nombre + "…";
    try {
      const res = await fetch("/api/v1/optimizar-cv", { method: "POST", body: src.form });
      if (!(res.headers.get("content-type") || "").includes("application/json")) throw new Error(_GUARD_CT);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `Error ${res.status}`);

      document.getElementById("plantilla-antes").textContent = data.score_antes != null ? data.score_antes : "—";
      document.getElementById("plantilla-despues").textContent = data.score_despues != null ? data.score_despues : "—";
      renderOptimPreview(data);
      resultado.style.display = "block";
      status.className = "upload-status ok";
      status.textContent = "✅ " + src.nombre + " optimizado";
      resultado.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) {
      status.className = "upload-status err";
      status.textContent = "❌ " + (e.message || "No se pudo optimizar el CV");
    }
    src.reset();
  }

  // ════════════ Tracker de aplicaciones (localStorage) ════════════
  const TRK_KEY = "cvats_aplicaciones";
  let trkFiltroActual = "todas";
  const TRK_ESTADOS = { borrador:"Borrador", enviado:"Enviado", entrevista:"Entrevista", oferta:"Oferta", rechazado:"Rechazado" };

  function trkCargar() {
    try { return JSON.parse(localStorage.getItem(TRK_KEY)) || []; }
    catch (e) { return []; }
  }
  function trkGuardar(apps) { localStorage.setItem(TRK_KEY, JSON.stringify(apps)); }

  function trkAgregar() {
    const puesto  = document.getElementById("trk-puesto").value.trim();
    const empresa = document.getElementById("trk-empresa").value.trim();
    const status  = document.getElementById("trk-form-status");
    if (!puesto || !empresa) {
      status.className = "upload-status err";
      status.textContent = "Completa al menos puesto y empresa";
      return;
    }
    const apps = trkCargar();
    apps.unshift({
      id: Date.now(),
      puesto, empresa,
      estado: document.getElementById("trk-estado").value,
      score: document.getElementById("trk-score").value,
      link:  document.getElementById("trk-link").value.trim(),
      notas: document.getElementById("trk-notas").value.trim(),
      fecha: new Date().toISOString(),
    });
    trkGuardar(apps);
    ["trk-puesto","trk-empresa","trk-score","trk-link","trk-notas"].forEach(id => document.getElementById(id).value = "");
    document.getElementById("trk-estado").value = "borrador";
    status.className = "upload-status ok";
    status.textContent = "Guardada";
    setTimeout(() => { status.textContent = ""; }, 2000);
    trkRender();
  }

  function trkEliminar(id) {
    if (!confirm("¿Eliminar esta aplicación?")) return;
    trkGuardar(trkCargar().filter(a => a.id !== id));
    trkRender();
  }

  function trkCambiarEstado(id, estado) {
    const apps = trkCargar();
    const a = apps.find(x => x.id === id);
    if (a) { a.estado = estado; trkGuardar(apps); trkRender(); }
  }

  function trkFiltrar(f, btn) {
    trkFiltroActual = f;
    document.querySelectorAll(".trk-filter").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    trkRender();
  }

  function trkStatCard(n, label, color) {
    return `<div class="trk-stat"><div class="n" style="color:${color}">${n}</div><div class="l">${label}</div></div>`;
  }

  // Embudo: tasa de entrevista por rango de score ATS (mismo cálculo que el backend).
  const _TRK_RANGOS = [["0-59", 0, 59], ["60-74", 60, 74], ["75-84", 75, 84], ["85-100", 85, 100]];
  const _ENVIADAS = ["enviado", "entrevista", "oferta", "rechazado"];
  function _trkScore(a) { const n = parseInt(a.score, 10); return isNaN(n) ? 0 : Math.max(0, Math.min(100, n)); }

  function renderTrkFunnel(apps) {
    const card = document.getElementById("trk-funnel-card");
    const box = document.getElementById("trk-funnel");
    if (!card || !box) return;
    const enviadas = apps.filter(a => _ENVIADAS.includes(a.estado));
    if (!enviadas.length) { card.style.display = "none"; box.innerHTML = ""; return; }
    box.innerHTML = _TRK_RANGOS.map(([label, lo, hi]) => {
      const en = enviadas.filter(a => { const s = _trkScore(a); return s >= lo && s <= hi; });
      const ent = en.filter(a => a.estado === "entrevista" || a.estado === "oferta");
      const tasa = en.length ? Math.round(ent.length / en.length * 100) : null;
      const col = tasa == null ? "#94a3b8" : tasa >= 50 ? "#16A34A" : tasa >= 25 ? "#D97706" : "#DC2626";
      return `<div style="display:flex;align-items:center;gap:.7rem;padding:.35rem 0">
        <div style="width:62px;font-size:.82rem;font-weight:600">${label}</div>
        <div style="flex:1;height:8px;background:#eef2f7;border-radius:6px;overflow:hidden"><div style="height:100%;width:${tasa == null ? 0 : tasa}%;background:${col}"></div></div>
        <div style="width:120px;text-align:right;font-size:.8rem;color:var(--muted)">${tasa == null ? "—" : `<strong style="color:${col}">${tasa}%</strong>`} · ${ent.length}/${en.length}</div>
      </div>`;
    }).join("");
    card.style.display = "block";
  }

  async function trkSyncTest() {
    const st = document.getElementById("trk-sync-status");
    if (!st) return;
    st.textContent = "Probando…";
    try {
      const r = await fetch("/api/v1/tracker");
      const j = await r.json().catch(() => ({}));
      if (r.ok) st.innerHTML = `<span style="color:#166534">✓ Sincronización activa.</span>`;
      else st.innerHTML = `<span style="color:#92400e">⚙️ ${escapeHtml(j.detail || ("Sync no configurada (modo local activo). Error " + r.status))}</span>`;
    } catch (e) {
      st.innerHTML = `<span style="color:#DC2626">No se pudo contactar el servidor.</span>`;
    }
  }

  function trkRender() {
    const apps = trkCargar();
    const conteo = { borrador:0, enviado:0, entrevista:0, oferta:0, rechazado:0 };
    apps.forEach(a => { conteo[a.estado] = (conteo[a.estado] || 0) + 1; });

    const stats = document.getElementById("trk-stats");
    if (stats) stats.innerHTML =
      trkStatCard(apps.length, "Total", "#0F172A") +
      trkStatCard(conteo.enviado, "Enviadas", "#1D4ED8") +
      trkStatCard(conteo.entrevista, "Entrevistas", "#B45309") +
      trkStatCard(conteo.oferta, "Ofertas", "#15803D");

    renderTrkFunnel(apps);

    const lista = document.getElementById("trk-lista");
    if (!lista) return;
    const filtradas = trkFiltroActual === "todas" ? apps : apps.filter(a => a.estado === trkFiltroActual);

    if (!filtradas.length) {
      lista.innerHTML = `<div class="trk-empty"><i class="ti ti-inbox" style="font-size:1.7rem;display:block;margin-bottom:.4rem" aria-hidden="true"></i>` +
        (apps.length ? "No hay aplicaciones con este estado." : "Aún no registras aplicaciones. Añade la primera arriba.") + `</div>`;
      return;
    }

    lista.innerHTML = "";
    filtradas.forEach(a => {
      const fecha = new Date(a.fecha).toLocaleDateString("es", { day:"2-digit", month:"short" });
      const opts = Object.keys(TRK_ESTADOS).map(e =>
        `<option value="${e}" ${e===a.estado?"selected":""}>${TRK_ESTADOS[e]}</option>`).join("");
      const linkHtml = a.link ? `<a href="${escapeHtml(a.link)}" target="_blank" rel="noopener" style="color:var(--accent);text-decoration:none">ver vacante</a> · ` : "";
      const scoreHtml = a.score ? `<span class="score-pill">${parseInt(a.score, 10)}%</span>` : "";
      const notasHtml = a.notas ? " · " + escapeHtml(a.notas) : "";
      const div = document.createElement("div");
      div.className = "trk-row";
      div.innerHTML =
        `<div class="main">
           <div class="role">${escapeHtml(a.puesto)}</div>
           <div class="meta">${escapeHtml(a.empresa)} · ${linkHtml}${fecha}${notasHtml}</div>
         </div>
         ${scoreHtml}
         <select class="trk-estado e-${a.estado}" data-chg="trk-estado" data-arg="${a.id}" aria-label="Estado">${opts}</select>
         <button class="trk-del" data-act="trk-eliminar" data-arg="${a.id}" aria-label="Eliminar"><i class="ti ti-trash" aria-hidden="true"></i></button>`;
      lista.appendChild(div);
    });
  }

  // ════════════ UX polish (Bloque 5) ════════════
  function actualizarContador(textareaId, counterId) {
    const ta = document.getElementById(textareaId);
    const c  = document.getElementById(counterId);
    if (!ta || !c) return;
    const words = ta.value.trim().split(/\s+/).filter(Boolean).length;
    c.textContent = words > 0 ? `${words} palabras · ~${(words / 400).toFixed(1)} pág` : "";
  }

  function exportarCSV() {
    const apps = (typeof trkCargar === "function") ? trkCargar() : [];
    if (!apps.length) { alert("No hay aplicaciones que exportar todavía."); return; }
    const headers = ["Puesto", "Empresa", "Estado", "Score ATS", "Fecha", "Link", "Notas"];
    const rows = apps.map(a => [
      a.puesto, a.empresa, (TRK_ESTADOS && TRK_ESTADOS[a.estado]) || a.estado, a.score,
      a.fecha ? new Date(a.fecha).toLocaleDateString("es") : "", a.link, a.notas,
    ]);
    const esc = c => `"${String(c == null ? "" : c).replace(/"/g, '""')}"`;
    const csv = [headers, ...rows].map(r => r.map(esc).join(",")).join("\n");
    const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "mis-aplicaciones.csv"; a.click();
    URL.revokeObjectURL(url);
  }

  function resaltarKeywords(texto, cubiertas, sugeridas) {
    let html = escapeHtml(texto || "");
    const marcar = (lista, cls) => (lista || []).forEach(kw => {
      if (!kw || kw.length < 2) return;
      const re = new RegExp("(?<![\\w-])(" + kw.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")(?![\\w-])", "gi");
      html = html.replace(re, m => m.includes("<") ? m : `<mark class="${cls}">${m}</mark>`);
    });
    marcar(cubiertas, "kw-found");
    marcar((sugeridas || []).slice(0, 6), "kw-missing");
    return html;
  }

  function iniciarCargaArchivo(statusEl, dropEl, nombre) {
    const fases = ["Extrayendo texto…", "Analizando contenido…", "Generando resultados…"];
    let i = 0;
    statusEl.className = "upload-status";
    statusEl.innerHTML = `<span class="spinner-sm"></span>${fases[0]}`;
    if (dropEl) dropEl.classList.add("cargando");
    const timer = setInterval(() => {
      i = (i + 1) % fases.length;
      statusEl.innerHTML = `<span class="spinner-sm"></span>${fases[i]}`;
    }, 1100);
    return () => { clearInterval(timer); if (dropEl) dropEl.classList.remove("cargando"); };
  }

  function _wireUX() {
    [["cv", "cv-counter"], ["vacante", "vacante-counter"]].forEach(([t, c]) => {
      const ta = document.getElementById(t);
      if (ta) { ta.addEventListener("input", () => actualizarContador(t, c)); actualizarContador(t, c); }
    });
    document.querySelectorAll(".ats-dropzone").forEach(zone => {
      const input = document.getElementById(zone.getAttribute("for"));
      if (!input) return;
      zone.addEventListener("dragover", e => { e.preventDefault(); zone.classList.add("drag-active"); });
      zone.addEventListener("dragleave", () => zone.classList.remove("drag-active"));
      zone.addEventListener("drop", e => {
        e.preventDefault(); zone.classList.remove("drag-active");
        const file = e.dataTransfer.files[0];
        if (file) {
          const dt = new DataTransfer(); dt.items.add(file); input.files = dt.files;
          input.dispatchEvent(new Event("change"));
        }
      });
    });
  }
  _wireUX();

  function mostrarError(msg) {
    const el = document.getElementById("error-box");
    el.textContent = "❌ " + msg;
    el.style.display = "block";
  }

  // Mostrar las aplicaciones guardadas al cargar
  trkRender();


  // ── Delegación de eventos (CSP sin 'unsafe-inline' en script-src) ──
  (function () {
    const ACT = {
      "tab": (el) => cambiarTab(el.dataset.arg),
      "usarcv": (el) => usarCVPegado(el.dataset.arg),
      "analizar": () => analizar(),
      "limpiar-vacante": () => limpiarVacante(),
      "restaurar-vacante": () => restaurarVacante(),
      "adaptar-docx": () => adaptarDocxOriginal(),
      "run-checklist": () => runChecklist(),
      "agregar-vacante": () => agregarVacante(),
      "comparar-vacantes": () => compararVacantes(),
      "trk-agregar": () => trkAgregar(),
      "trk-sync-test": () => trkSyncTest(),
      "trk-filtrar": (el) => trkFiltrar(el.dataset.arg, el),
      "export-csv": () => exportarCSV(),
      "trk-eliminar": (el) => trkEliminar(Number(el.dataset.arg)),
    };
    const CHG = {
      "subir-archivo": (el) => subirArchivo(el),
      "docx-nombre": (el) => mostrarNombreDocx(el),
      "ats": (el) => analizarATS(el),
      "parsing": (el) => analizarParsing(el),
      "bullets": (el) => analizarBullets(el),
      "optimizar": (el) => optimizarCV(el),
      "metricas": (el) => analizarMetricas(el),
      "trk-estado": (el) => trkCambiarEstado(Number(el.dataset.arg), el.value),
    };
    document.addEventListener("click", (e) => {
      const el = e.target.closest("[data-act]");
      if (el && ACT[el.dataset.act]) ACT[el.dataset.act](el);
    });
    document.addEventListener("change", (e) => {
      const el = e.target.closest("[data-chg]");
      if (el && CHG[el.dataset.chg]) CHG[el.dataset.chg](el);
    });
  })();
