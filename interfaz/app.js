/* app.js - Interfaz de OptiFin. Llama a la API local (src/api.py) y muestra los resultados. */

const E = {                          // estado de la interfaz
  redes: [], archivos: [], reportes: {},
  gestion: { red: "enrutamiento", pestana: "nodos" },
  fraude: { pestana: "proximidad", cuenta: "CTA_A" },
  rutas: { red: "enrutamiento", criterio: "friccion", origen: "A", destino: "X", monto: 100, vista: "ruta" },
  liquidez: { red: "liquidez", pestana: "distribucion" },
  evaluacion: { pestana: "verificaciones", densidad: "dispersa" },
  nodosRed: {},
};

/* ============================================================ utilidades */
const $ = (s, c = document) => c.querySelector(s);
const $$ = (s, c = document) => [...c.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
const pct = (a, b) => b ? Math.round(100 * a / b) : 0;

async function api(accion, params = {}) {
  const r = await fetch(`/api/${accion}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(params) });
  const d = await r.json().catch(() => ({ error: "Respuesta inválida del servidor" }));
  if (!r.ok) throw new Error(d.error || `Error ${r.status}`);
  return d;
}

function aviso(texto, tipo = "") {
  const t = document.createElement("div");
  t.className = `toast ${tipo}`;
  t.textContent = texto;
  $("#avisos").appendChild(t);
  setTimeout(() => t.remove(), tipo === "error" ? 6500 : 3500);
}

async function conCarga(nodo, fn) {
  nodo?.classList.add("cargando");
  try { return await fn(); }
  catch (e) { aviso(e.message, "error"); throw e; }
  finally { nodo?.classList.remove("cargando"); }
}

function kpi(etq, valor, det = "", color = "", unidad = "") {
  return `<div class="tarjeta kpi ${color}"><div class="etq"><span class="punto"></span>${etq}</div>
    <div class="valor">${valor}${unidad ? `<small>${unidad}</small>` : ""}</div><div class="det">${det}</div></div>`;
}
function tarjeta(titulo, cuerpo, nota = "", acciones = "", clase = "") {
  return `<div class="tarjeta ${clase}"><div class="tarjeta-cab"><div><h3>${titulo}</h3>${nota ? `<div class="nota">${nota}</div>` : ""}</div><div>${acciones}</div></div>${cuerpo}</div>`;
}
function rutaChips(ruta, nombres = {}) {
  return `<span class="ruta-chips">${ruta.map((n, i) => `${i ? '<span class="flecha">→</span>' : ""}<span class="nodo-chip">${esc(nombres[n] || n)}</span>`).join("")}</span>`;
}
function tablaHTML(cab, filas, clasesCol = []) {
  return `<div class="tabla-cont"><table><thead><tr>${cab.map((h, i) => `<th class="${clasesCol[i] || ""}">${h}</th>`).join("")}</tr></thead>
    <tbody>${filas.join("") || `<tr><td colspan="${cab.length}" class="vacio">Sin resultados</td></tr>`}</tbody></table></div>`;
}
const sinLimite = html => html.replace('class="tabla-cont"', 'class="tabla-cont" style="max-height:none"');
function segmentado(id, opciones, activo) {
  return `<div class="segmentado" id="${id}">${opciones.map(([v, t]) => `<button data-v="${v}" class="${v === activo ? "activo" : ""}">${t}</button>`).join("")}</div>`;
}
function onSegmentado(id, fn) {
  $$(`#${id} button`).forEach(b => b.onclick = () => {
    $$(`#${id} button`).forEach(x => x.classList.remove("activo"));
    b.classList.add("activo");
    fn(b.dataset.v);
  });
}
function botonReporte(clave) {
  return `<button class="btn chico" data-reporte="${clave}" title="Descargar el reporte en texto">⭳ Reporte .txt</button>`;
}
function activarReportes(ctx = document) {
  $$("[data-reporte]", ctx).forEach(b => b.onclick = () => {
    const txt = E.reportes[b.dataset.reporte];
    if (txt) descargar(`reporte_${b.dataset.reporte}.txt`, txt); else aviso("Ejecute primero el análisis.");
  });
}
function visorHTML(id, titulo = "Visor de la red", bajo = false) {
  return `<div class="tarjeta sin-relleno"><div class="visor-cab"><h3 id="${id}-tit">${titulo}</h3><div class="visor-herr">
    <button class="btn chico icono" data-v="${id}" data-acc="mas" title="Acercar">＋</button>
    <button class="btn chico icono" data-v="${id}" data-acc="menos" title="Alejar">－</button>
    <button class="btn chico" data-v="${id}" data-acc="ajustar" title="Restablecer vista">Ajustar</button>
    <button class="btn chico" data-v="${id}" data-acc="etq" title="Mostrar u ocultar valores de las aristas">Etiquetas</button>
    <button class="btn chico" data-v="${id}" data-acc="svg" title="Descargar imagen SVG">⭳ SVG</button>
    <span class="chip" title="Rueda del mouse: zoom · Arrastrar el fondo: mover · Arrastrar un nodo: reubicarlo · Pasar el mouse: ver atributos">?</span>
    </div></div><div id="${id}" class="${bajo ? "visor bajo" : "visor"}"></div></div>`;
}
const VISORES = {};
function pintarVisor(id, datos) {
  const cont = document.getElementById(id);
  if (!cont) return;
  const v = new VisorGrafo(cont);
  v.mostrarEtiquetas = datos.aristas.length <= 60;
  v.dibujar(datos);
  VISORES[id] = v;
  const tit = document.getElementById(`${id}-tit`);
  if (tit && datos.titulo) tit.textContent = datos.titulo;
  $$(`[data-v="${id}"]`).forEach(b => b.onclick = () => {
    const acc = b.dataset.acc;
    if (acc === "mas") v.zoom(1.25); else if (acc === "menos") v.zoom(0.8);
    else if (acc === "ajustar") v.ajustar(); else if (acc === "etq") v.alternarEtiquetas();
    else if (acc === "svg") v.descargarSVG(`${(datos.titulo || "red").replace(/[^\w]+/g, "_")}.svg`);
  });
}
function barra(valor, total, color = "") {
  return `<div class="barra-prog ${color}"><div style="width:${Math.max(0, Math.min(100, pct(valor, total)))}%"></div></div>`;
}
async function nodosDe(red) {
  if (!E.nodosRed[red]) {
    const d = await api("red", { clave: red });
    E.nodosRed[red] = d.nodos.map(n => ({ id: n.id, nombre: n.atributos.nombre || n.id, tipo: n.tipo }));
  }
  return E.nodosRed[red];
}
async function refrescarEstado() {
  const d = await api("estado");
  E.redes = d.redes; E.archivos = d.archivos;
  const n = d.alertas_ruleteo.length;
  $("#cabecera-der").innerHTML = `<span class="chip verde">● Servidor local activo</span>${n ? `<span class="chip rojo">${n} alerta(s) de ruleteo</span>` : ""}`;
}

/* ============================================================ navegación */
const PAGINAS = {
  inicio: { miga: "Inicio", titulo: "Panel general", sub: "Falta de control sobre el flujo del dinero en la red financiera: tres escenarios, un grafo común y algoritmos elegidos para cada pregunta.", render: paginaInicio },
  gestion: { miga: "Módulo 1", titulo: "Gestión y modelamiento de redes", sub: "Cree, cargue (CSV, TXT, JSON), modifique, valide y visualice las redes que usan todos los módulos.", render: paginaGestion },
  fraude: { miga: "Módulo 2", titulo: "Análisis de transacciones y detección de operaciones sospechosas", sub: "Rastreo de fondos, circulación, fraccionamiento y cercanía entre cuentas. Los patrones son indicadores para revisión, no prueba de delito.", render: paginaFraude },
  rutas: { miga: "Módulo 3", titulo: "Enrutamiento de operaciones y cálculo de comisiones", sub: "Compare todas las rutas entre dos entidades, elija la de menor costo y detecte promociones que generan ruleteo.", render: paginaRutas },
  liquidez: { miga: "Módulo 4", titulo: "Planificación de la distribución de liquidez", sub: "Cuánto efectivo puede llegar a cada agencia, qué tramos lo limitan y cuál es el plan de traslado más barato.", render: paginaLiquidez },
  evaluacion: { miga: "Módulo 5", titulo: "Evaluación, comparación y validación", sub: "Verificaciones cruzadas entre algoritmos, desempeño empírico frente a la complejidad teórica y pruebas automatizadas.", render: paginaEvaluacion },
};

async function navegar() {
  const clave = (location.hash.replace("#/", "") || "inicio").split("?")[0];
  const p = PAGINAS[clave] || PAGINAS.inicio;
  $$("#menu a").forEach(a => a.classList.toggle("activo", a.dataset.pagina === (PAGINAS[clave] ? clave : "inicio")));
  $("#miga").textContent = p.miga;
  $("#titulo").textContent = p.titulo;
  $("#subtitulo").textContent = p.sub;
  const c = $("#contenido");
  c.innerHTML = `<div class="tarjeta" style="height:240px"></div>`;
  c.firstChild.classList.add("cargando");
  $("main").scrollTop = 0;
  try { await p.render(c); } catch (e) { c.innerHTML = `<div class="aviso rojo"><span class="simbolo">!</span><div><b>No se pudo cargar la página</b>${esc(e.message)}</div></div>`; }
  activarReportes(c);
}

/* ============================================================ PANEL GENERAL */
async function paginaInicio(c) {
  const d = await api("inicio");
  const f = d.fraude, r = d.rutas, l = d.liquidez;
  const ahorro = pct(r.menos_saltos - r.mejor, r.menos_saltos);
  c.innerHTML = `
  <div class="portada">
    <div><h2>Control del flujo del dinero</h2>
      <p>Las entidades financieras mueven dinero por una red de cuentas, plataformas de pago, bancos y bóvedas, pero no controlan ese flujo:
      no detectan el dinero que circula de forma sospechosa, no eligen la ruta más barata y no distribuyen el efectivo según la capacidad real de transporte.
      OptiFin modela esa red como un <b>grafo</b> y aplica el algoritmo adecuado a cada pregunta.</p>
      <div class="chips" style="margin-top:14px">${["Recorridos", "Componentes fuertemente conexas", "Rutas más cortas", "Ciclos negativos", "Flujo máximo y corte mínimo", "Árbol de expansión mínima"].map(t => `<span class="chip" style="background:rgba(255,255,255,.14);color:#fff">${t}</span>`).join("")}</div>
    </div>
    <div class="preguntas">
      <div class="pregunta"><b>¿Por dónde pasó el dinero?</b> — recorrido (Módulo 2)</div>
      <div class="pregunta"><b>¿Cuánto cuesta enviarlo?</b> — costo (Módulo 3)</div>
      <div class="pregunta"><b>¿Cuánto efectivo puede llegar?</b> — capacidad (Módulo 4)</div>
    </div>
  </div>
  <div class="fila c4">
    ${kpi("Cuentas en circulación de fondos", f.cuentas_en_ciclo, `${f.grupos} grupo(s) detectados · ${f.abanicos} abanicos de fraccionamiento`, "rojo")}
    ${kpi("Mejor ruta Yape → Comercio", r.mejor, `La ruta con menos saltos cuesta ${r.menos_saltos}: ${ahorro} % más cara`, "verde", "puntos de fricción")}
    ${kpi("Ruleteo con cashback", r.costo_ciclo ?? "—", r.ciclos_cashback.length ? `Ciclo ${esc(r.ciclos_cashback[0])} por vuelta` : "Sin ciclos negativos", "morado")}
    ${kpi("Efectivo que puede llegar", fmtNum(l.flujo), `de ${fmtNum(l.demanda)} demandados (${pct(l.flujo, l.demanda)} %) · corte mínimo = ${fmtNum(l.corte)}`, "naranja", "miles de S/")}
  </div>
  <div class="fila c3">
    ${escenario("2", "#FBEAE8", "#C0392B", "Prevención de fraude y lavado", "Rastrea el dinero en orden cronológico, encuentra grupos donde circula, detecta operaciones fraccionadas y prioriza las cuentas a revisar.", ["BFS", "DFS temporal", "Tarjan / Kosaraju", "Suma de subconjuntos", "Heap"], "fraude")}
    ${escenario("3", "#FDF1E3", "#D9822B", "Enrutamiento y comisiones", "Lista todas las rutas entre dos entidades, calcula su costo en fricción, soles o minutos, aplica restricciones de servicio y detecta ruleteo.", ["Backtracking", "Dijkstra", "Bellman-Ford", "Floyd-Warshall", "Johnson"], "rutas")}
    ${escenario("4", "#E3F4EC", "#1F8A5B", "Distribución de liquidez", "Calcula cuánto efectivo llega a cada agencia, identifica los cuellos de botella y encuentra el plan de traslado más barato.", ["Edmonds-Karp", "Corte mínimo", "Costo mínimo", "Prim / Kruskal"], "liquidez")}
  </div>
  <div class="fila c-principal">
    ${tarjeta("Redes cargadas", tablaHTML(["Red", "Tipo", "Nodos", "Aristas", "Archivo"], d.redes.map(x =>
      `<tr><td class="negrita">${esc(x.nombre)}</td><td>${x.dirigido ? "Dirigida" : "No dirigida"}${x.multiarista ? " · aristas múltiples" : ""}</td><td class="num">${x.nodos}</td><td class="num">${x.aristas}</td><td><code>${esc(x.archivo)}</code></td></tr>`), ["", "", "num", "num", ""]),
      "Representación común: lista de adyacencia con atributos por arista", `<a class="btn chico" href="#/gestion">Gestionar →</a>`)}
    ${tarjeta("Agencias con faltante de efectivo", l.pendientes.length ? `<div class="barras-h">${l.pendientes.map(a => `
      <div class="fila-b"><b>${esc(a.agencia)}</b><div class="pista"><div style="width:${pct(a.recibe, a.demanda)}%;background:#D9822B"></div></div><span class="num">${fmtNum(a.recibe)} / ${fmtNum(a.demanda)}</span></div>`).join("")}</div>
      <div class="aviso naranja" style="margin:14px 0 0"><span class="simbolo">!</span><div><b>Cuellos de botella</b>Los tramos saturados que alimentan a estas agencias se identifican con el corte mínimo (Guía 11).</div></div>` : `<div class="vacio">Todas las agencias están cubiertas.</div>`,
      "Red de la Figura 5 · miles de S/", `<a class="btn chico" href="#/liquidez">Planificar →</a>`)}
  </div>
  <div class="fila c-principal">
    ${tarjeta("Cuentas a revisar primero", tablaHTML(["#", "Cuenta", "Puntaje", "Motivos"], f.top.map((t, i) => `<tr><td class="num">${i + 1}</td><td class="negrita">${esc(t.cuenta)}</td><td><span class="chip rojo">${t.puntaje} pts</span></td><td><div class="chips">${t.motivos.map(m => `<span class="chip">${esc(m)}</span>`).join("")}</div></td></tr>`), ["num", "", "", ""]),
      "Puntaje combinado de los indicadores del Módulo 2", `<a class="btn chico" href="#/fraude">Ver análisis →</a>`)}
    ${tarjeta("Arquitectura del sistema", `<div class="arquitectura">
      <div class="caja" style="border-color:#2F5D8C;background:#E8F0F9"><b>Módulo 1 · Gestión de la red</b>Grafo común con atributos por arista</div>
      <div class="tres">
        <div class="caja" style="border-color:#C0392B;background:#FBEAE8"><b>Módulo 2</b>RECORRIDO</div>
        <div class="caja" style="border-color:#D9822B;background:#FDF1E3"><b>Módulo 3</b>COSTO</div>
        <div class="caja" style="border-color:#1F8A5B;background:#E3F4EC"><b>Módulo 4</b>CAPACIDAD</div>
      </div>
      <div class="caja" style="border-color:#7651C2;background:#EFEAFA"><b>Módulo 5 · Evaluación</b>Verificación, tiempos y pruebas</div></div>`)}
  </div>`;
}
function escenario(num, fondo, color, titulo, texto, algs, pagina) {
  return `<div class="tarjeta escenario"><div class="icono" style="background:${fondo};color:${color}">${num}</div><h3>${titulo}</h3><p>${texto}</p>
    <div class="chips">${algs.map(a => `<span class="chip azul">${a}</span>`).join("")}</div>
    <div class="pie"><span class="texto-tenue mini">Módulo ${num}</span><a class="btn primario chico" href="#/${pagina}">Abrir módulo →</a></div></div>`;
}

/* ============================================================ MÓDULO 1 · GESTIÓN */
const TIPOS = ["cuenta", "cliente", "billetera", "banco", "compensacion", "comercio", "boveda_central", "boveda_regional", "agencia", "atm", "generico"];

async function paginaGestion(c) {
  await refrescarEstado();
  const d = await api("red", { clave: E.gestion.red });
  renderGestion(c, d);
}

function renderGestion(c, d) {
  const g = E.gestion;
  const opcionesRed = E.redes.map(r => [r.clave, r.nombre]);
  const v = d.validacion, errores = v.filter(x => x.startsWith("ERROR")).length;
  const nombres = Object.fromEntries(d.nodos.map(n => [n.id, n.atributos.nombre || n.id]));
  c.innerHTML = `
  <div class="tarjeta" style="margin-bottom:18px"><div class="controles"><div class="campo"><label>Red de trabajo</label>${segmentado("seg-red", opcionesRed, g.red)}</div></div></div>
  <div class="fila c-principal">
    ${visorHTML("v-gestion", d.nombre)}
    <div style="display:flex;flex-direction:column;gap:18px">
      ${tarjeta("Resumen de la red", `
        <div class="fila c2" style="margin:0">
          <div><div class="texto-tenue mini">Nodos</div><div class="negrita" style="font-size:22px">${d.resumen.nodos}</div></div>
          <div><div class="texto-tenue mini">Aristas</div><div class="negrita" style="font-size:22px">${d.resumen.aristas}</div></div>
        </div>
        <div class="chips" style="margin-top:10px"><span class="chip azul">${d.resumen.dirigido ? "Dirigida" : "No dirigida"}</span><span class="chip azul">${d.resumen.ponderado ? "Ponderada" : "No ponderada"}</span>${d.resumen.multiarista ? '<span class="chip azul">Aristas múltiples</span>' : ""}</div>
        <div class="chips" style="margin-top:8px">${Object.entries(d.resumen.tipos).map(([t, n]) => `<span class="chip">${NOMBRE_TIPO[t] || t}: ${n}</span>`).join("")}</div>
        <div class="aviso ${errores ? "rojo" : v.length ? "naranja" : "verde"}" style="margin:14px 0 0"><span class="simbolo">${errores ? "!" : "✓"}</span>
          <div><b>${errores ? `${errores} error(es) de consistencia` : v.length ? `${v.length} aviso(s)` : "Red consistente"}</b>${v.length ? "Vea la pestaña Validación." : "Sin nodos inexistentes, duplicados ni valores inválidos."}</div></div>`,
        "", botonReporte("red"))}
      ${tarjeta("Cargar red desde archivo", `
        <div class="campo ancho"><label>Archivo de la carpeta data/</label><select id="g-archivo">${E.archivos.map(a => `<option>${esc(a)}</option>`).join("")}</select></div>
        <div class="controles" style="margin-top:10px">
          <label class="chk"><input type="checkbox" id="g-dir" checked> Dirigida</label>
          <label class="chk"><input type="checkbox" id="g-multi"> Aristas múltiples</label>
          <button class="btn primario chico derecha" id="g-cargar">Cargar</button></div>
        <div class="separador"></div>
        <div class="campo ancho"><label>O subir un archivo propio (CSV, TXT o JSON)</label><input type="file" id="g-sub" accept=".csv,.txt,.json"></div>
        <div class="campo ancho" style="margin-top:8px"><label>Archivo de nodos (opcional, CSV con id,tipo,...)</label><input type="file" id="g-sub-n" accept=".csv"></div>
        <button class="btn chico" id="g-subir" style="margin-top:10px">Subir y cargar como "Red del usuario"</button>`,
        "Se carga en la red seleccionada arriba")}
      ${tarjeta("Guardar red", `<div class="controles"><div class="campo" style="flex:1"><label>Nombre del archivo (.json o .csv)</label><input type="text" id="g-nombre" value="${esc(d.resumen.nombre)}_editada.json" style="width:100%"></div>
        <button class="btn" id="g-guardar">Guardar y descargar</button></div>`)}
    </div>
  </div>
  <div class="tarjeta">
    <div class="pestanas" id="g-pest">${[["nodos", `Nodos <span class="alg">${d.nodos.length}</span>`], ["aristas", `Aristas <span class="alg">${d.aristas.length}</span>`], ["editar", "Agregar / modificar"], ["validacion", `Validación <span class="alg">${v.length}</span>`]]
      .map(([k, t]) => `<button data-p="${k}" class="${g.pestana === k ? "activo" : ""}">${t}</button>`).join("")}</div>
    <div id="g-cuerpo"></div>
  </div>`;

  const cuerpo = {
    nodos: () => `<input type="text" id="g-filtro" placeholder="Filtrar nodos..." style="margin-bottom:10px;width:260px">` + tablaHTML(["Id", "Nombre", "Tipo", "Grado de salida", "Atributos", ""], d.nodos.map(n => `
      <tr data-f="${esc(n.id + " " + (n.atributos.nombre || "") + " " + n.tipo).toLowerCase()}"><td class="negrita">${esc(n.id)}</td><td>${esc(n.atributos.nombre || "")}</td><td><span class="chip">${NOMBRE_TIPO[n.tipo] || esc(n.tipo)}</span></td>
      <td class="num">${n.grado_salida}</td><td class="mini texto-tenue">${Object.entries(n.atributos).filter(([k]) => !["nombre", "x", "y"].includes(k)).map(([k, x]) => `${esc(k)}=${esc(x)}`).join(", ")}</td>
      <td class="nowrap"><button class="btn chico" data-edn="${esc(n.id)}">Editar</button> <button class="btn chico peligro" data-deln="${esc(n.id)}">Eliminar</button></td></tr>`), ["", "", "", "num", "", ""]),
    aristas: () => `<input type="text" id="g-filtro" placeholder="Filtrar aristas..." style="margin-bottom:10px;width:260px">` + tablaHTML(["Origen", "", "Destino", "Atributos", ""], d.aristas.map(a => `
      <tr data-f="${esc(a.origen + " " + a.destino).toLowerCase()}"><td class="negrita">${esc(nombres[a.origen])}</td><td class="texto-tenue">${d.resumen.dirigido ? "→" : "—"}</td><td class="negrita">${esc(nombres[a.destino])}</td>
      <td class="mini">${Object.entries(a.atributos).map(([k, x]) => `<span class="chip">${esc(k)}: ${esc(typeof x === "number" ? fmtNum(x) : x)}</span>`).join(" ")}</td>
      <td class="nowrap"><button class="btn chico" data-eda="${esc(a.origen)}|${esc(a.destino)}|${a.indice}">Editar</button> <button class="btn chico peligro" data-dela="${esc(a.origen)}|${esc(a.destino)}|${a.indice}">Eliminar</button></td></tr>`)),
    editar: () => `<div class="fila c2" style="margin:0">
      <div><h4 style="margin-top:0">Nodo</h4><div class="controles">
        <div class="campo"><label>Id</label><input type="text" id="n-id" placeholder="ej. ATM5" style="width:130px"></div>
        <div class="campo"><label>Tipo</label><select id="n-tipo">${TIPOS.map(t => `<option value="${t}">${NOMBRE_TIPO[t]}</option>`).join("")}</select></div>
        <div class="campo" style="flex:1"><label>Atributos (clave=valor, separados por coma)</label><input type="text" id="n-at" placeholder="nombre=ATM Centro, oferta=500"></div></div>
        <div class="controles" style="margin-top:10px"><button class="btn primario" data-accn="agregar">Agregar</button><button class="btn" data-accn="modificar">Modificar</button><button class="btn peligro" data-accn="eliminar">Eliminar</button></div></div>
      <div><h4 style="margin-top:0">Arista</h4><div class="controles">
        <div class="campo"><label>Origen</label><select id="a-o">${d.nodos.map(n => `<option value="${esc(n.id)}">${esc(nombres[n.id])}</option>`).join("")}</select></div>
        <div class="campo"><label>Destino</label><select id="a-d">${d.nodos.map(n => `<option value="${esc(n.id)}">${esc(nombres[n.id])}</option>`).join("")}</select></div>
        <div class="campo"><label>Índice</label><input type="number" id="a-i" value="0" min="0" style="width:70px"></div>
        <div class="campo" style="flex:1"><label>Atributos</label><input type="text" id="a-at" placeholder="comision=2.5, tiempo=10"></div></div>
        <div class="controles" style="margin-top:10px"><button class="btn primario" data-acca="agregar">Agregar</button><button class="btn" data-acca="modificar">Modificar</button><button class="btn peligro" data-acca="eliminar">Eliminar</button></div></div></div>
      <div class="aviso azul" style="margin:16px 0 0"><span class="simbolo">i</span><div><b>Validación al editar</b>No se aceptan nodos inexistentes, valores negativos (los bonos van en <code>cashback</code>), ni aristas duplicadas sin justificación. Las aristas múltiples solo se permiten en redes de transferencias.</div></div>`,
    validacion: () => v.length ? `<div class="lista">${v.map(x => `<div class="item-lista ${x.startsWith("ERROR") ? "rojo" : ""}">${esc(x)}</div>`).join("")}</div>` : `<div class="aviso verde" style="margin:0"><span class="simbolo">✓</span><div><b>Sin observaciones</b>Todos los nodos existen, no hay duplicados y los valores son válidos.</div></div>`,
  };
  const pintarCuerpo = () => {
    $("#g-cuerpo").innerHTML = cuerpo[g.pestana]();
    const filtro = $("#g-filtro");
    if (filtro) filtro.oninput = () => $$("#g-cuerpo tbody tr").forEach(tr => tr.style.display = (tr.dataset.f || "").includes(filtro.value.toLowerCase()) ? "" : "none");
    $$("[data-deln]").forEach(b => b.onclick = () => accion("nodo", { accion: "eliminar", nodo: b.dataset.deln }));
    $$("[data-dela]").forEach(b => b.onclick = () => { const [o, de, i] = b.dataset.dela.split("|"); accion("arista", { accion: "eliminar", origen: o, destino: de, indice: +i }); });
    $$("[data-edn]").forEach(b => b.onclick = () => {
      const n = d.nodos.find(x => x.id === b.dataset.edn);
      g.pestana = "editar"; marcarPestana(); pintarCuerpo();
      $("#n-id").value = n.id; $("#n-tipo").value = n.tipo;
      $("#n-at").value = Object.entries(n.atributos).filter(([k]) => !["x", "y"].includes(k)).map(([k, x]) => `${k}=${x}`).join(", ");
    });
    $$("[data-eda]").forEach(b => b.onclick = () => {
      const [o, de, i] = b.dataset.eda.split("|");
      const a = d.aristas.find(x => x.origen === o && x.destino === de && x.indice === +i);
      g.pestana = "editar"; marcarPestana(); pintarCuerpo();
      $("#a-o").value = o; $("#a-d").value = de; $("#a-i").value = i;
      $("#a-at").value = Object.entries(a.atributos).map(([k, x]) => `${k}=${x}`).join(", ");
    });
    $$("[data-accn]").forEach(b => b.onclick = () => accion("nodo", { accion: b.dataset.accn, nodo: $("#n-id").value.trim(), tipo: $("#n-tipo").value, atributos: $("#n-at").value }));
    $$("[data-acca]").forEach(b => b.onclick = () => accion("arista", { accion: b.dataset.acca, origen: $("#a-o").value, destino: $("#a-d").value, indice: +$("#a-i").value, atributos: $("#a-at").value }));
  };
  const marcarPestana = () => $$("#g-pest button").forEach(b => b.classList.toggle("activo", b.dataset.p === g.pestana));
  $$("#g-pest button").forEach(b => b.onclick = () => { g.pestana = b.dataset.p; marcarPestana(); pintarCuerpo(); });
  pintarCuerpo();
  pintarVisor("v-gestion", d.grafo);
  E.reportes.red = d.reporte;
  activarReportes(c);

  async function accion(tipo, params) {
    try {
      const nd = await api(tipo, { clave: g.red, ...params });
      delete E.nodosRed[g.red];
      aviso(`${tipo === "nodo" ? "Nodo" : "Arista"}: operación "${params.accion}" realizada.`, "ok");
      const pest = g.pestana;
      await refrescarEstado();
      renderGestion(c, nd);
      g.pestana = pest;
    } catch (e) { aviso(e.message, "error"); }
  }
  onSegmentado("seg-red", async red => { g.red = red; renderGestion(c, await api("red", { clave: red })); });
  $("#g-cargar").onclick = async () => {
    try {
      const r = await api("cargar", { clave: g.red, archivo: $("#g-archivo").value, dirigido: $("#g-dir").checked, multiarista: $("#g-multi").checked });
      delete E.nodosRed[g.red];
      aviso(r.errores.length ? `Cargada con ${r.errores.length} registro(s) rechazado(s).` : "Red cargada correctamente.", r.errores.length ? "error" : "ok");
      await refrescarEstado(); renderGestion(c, r.red);
      if (r.errores.length) { g.pestana = "validacion"; $("#g-cuerpo").innerHTML = `<div class="lista">${r.errores.map(x => `<div class="item-lista rojo">${esc(x)}</div>`).join("")}</div>`; }
    } catch (e) { aviso(e.message, "error"); }
  };
  $("#g-subir").onclick = async () => {
    const f = $("#g-sub").files[0], fn = $("#g-sub-n").files[0];
    if (!f) return aviso("Seleccione un archivo.", "error");
    try {
      const r = await api("subir", { clave: "personal", nombre: f.name, contenido: await f.text(), contenido_nodos: fn ? await fn.text() : null,
        dirigido: $("#g-dir").checked, multiarista: $("#g-multi").checked });
      g.red = "personal"; delete E.nodosRed.personal;
      await refrescarEstado(); renderGestion(c, r.red);
      aviso(r.errores.length ? `Cargada con ${r.errores.length} registro(s) rechazado(s).` : `"${f.name}" cargado.`, r.errores.length ? "error" : "ok");
    } catch (e) { aviso(e.message, "error"); }
  };
  $("#g-guardar").onclick = async () => {
    try { const r = await api("guardar", { clave: g.red, nombre: $("#g-nombre").value }); descargar(r.archivo, r.contenido); aviso(`Guardado en data/${r.archivo}`, "ok"); }
    catch (e) { aviso(e.message, "error"); }
  };
}

/* ============================================================ MÓDULO 2 · FRAUDE */
const PEST_FRAUDE = [
  ["proximidad", "Proximidad", "BFS"], ["rastreo", "Rastreo de fondos", "DFS temporal"], ["circulacion", "Circulación", "Tarjan · Kosaraju"],
  ["fraccionamiento", "Fraccionamiento", "Ventana · PD"], ["ranking", "Cuentas a revisar", "Heap"],
];

async function paginaFraude(c) {
  const nodos = await nodosDe("transacciones");
  const f = E.fraude;
  c.innerHTML = `
  <div class="tarjeta" style="margin-bottom:18px">
    <div class="controles">
      <div class="campo"><label>Cuenta</label><input type="text" id="f-cuenta" list="f-lista" value="${esc(f.cuenta)}" style="width:130px"><datalist id="f-lista">${nodos.map(n => `<option value="${esc(n.id)}">`).join("")}</datalist></div>
      <div class="campo"><label>Saltos (BFS)</label><input type="number" id="f-saltos" value="2" min="1" max="6"></div>
      <div class="campo"><label>Ventana rastreo (días)</label><input type="number" id="f-ventana" value="7" min="1"></div>
      <div class="campo"><label>Umbral de reporte (S/)</label><input type="number" id="f-umbral" value="10000" step="500"></div>
      <div class="campo"><label>Ventana abanicos (días)</label><input type="number" id="f-vab" value="3" min="1"></div>
      <div class="campo"><label>Top k</label><input type="number" id="f-k" value="10" min="1"></div>
      <div class="campo"><label>Cuentas ya marcadas</label><input type="text" id="f-marc" placeholder="ej. CTA_A" style="width:140px"></div>
      <button class="btn primario derecha" id="f-ir">Analizar</button>
    </div>
  </div>
  <div class="pestanas" id="f-pest">${PEST_FRAUDE.map(([k, t, a]) => `<button data-p="${k}" class="${f.pestana === k ? "activo" : ""}">${t} <span class="alg">${a}</span></button>`).join("")}</div>
  <div id="f-res"></div>
  <div class="aviso azul"><span class="simbolo">i</span><div><b>Indicadores para revisión</b>La detección computacional de un patrón no constituye, por sí sola, prueba de fraude o lavado de activos; la decisión corresponde a auditoría.</div></div>`;
  $$("#f-pest button").forEach(b => b.onclick = () => { f.pestana = b.dataset.p; $$("#f-pest button").forEach(x => x.classList.toggle("activo", x === b)); analizarFraude(); });
  $("#f-ir").onclick = analizarFraude;
  $("#f-cuenta").onkeydown = e => { if (e.key === "Enter") analizarFraude(); };
  await analizarFraude();
}

async function analizarFraude() {
  const f = E.fraude, cont = $("#f-res");
  f.cuenta = $("#f-cuenta").value.trim();
  const p = {
    proximidad: ["proximidad", { cuenta: f.cuenta, saltos: +$("#f-saltos").value }],
    rastreo: ["rastreo", { cuenta: f.cuenta, ventana: +$("#f-ventana").value }],
    circulacion: ["circulacion", { cuenta: f.cuenta }],
    fraccionamiento: ["fraccionamiento", { umbral: +$("#f-umbral").value, ventana: +$("#f-vab").value }],
    ranking: ["ranking", { k: +$("#f-k").value, marcadas: $("#f-marc").value }],
  }[f.pestana];
  cont.innerHTML = `<div class="fila c-principal">${visorHTML("v-fraude")}<div id="f-panel" class="tarjeta" style="min-height:300px"></div></div><div id="f-detalle"></div>`;
  let d;
  try { d = await conCarga($("#f-panel"), () => api(p[0], p[1])); } catch { return; }
  E.reportes.fraude = d.reporte;
  pintarVisor("v-fraude", d.grafo);
  const panel = $("#f-panel"), det = $("#f-detalle");
  const cab = (t, n = "") => `<div class="tarjeta-cab"><div><h3>${t}</h3><div class="nota">${n}</div></div>${botonReporte("fraude")}</div>`;
  if (f.pestana === "proximidad") {
    const niveles = Object.entries(d.por_nivel);
    panel.innerHTML = cab("Cuentas relacionadas", `BFS desde ${esc(f.cuenta)} · ${fmtNum(d.tiempo_ms, 3)} ms`) + `
      <div class="fila c2" style="margin:0 0 10px">${kpi("Relacionadas", d.filas.length, "directa o indirectamente")}${kpi("Más lejana", niveles.length ? Math.max(...niveles.map(([k]) => +k)) : 0, "saltos")}</div>
      <h4>Cuentas por nivel</h4><div class="barras-h">${niveles.map(([k, n]) => `<div class="fila-b"><span>${k} salto(s)</span><div class="pista"><div style="width:${pct(n, d.filas.length)}%;background:#3B74B0"></div></div><span class="num">${n}</span></div>`).join("")}</div>
      <p class="texto-tenue mini">El nivel BFS es el número de saltos: a menor nivel, más cercana la relación con la cuenta analizada. El número sobre cada nodo del visor es su nivel.</p>`;
    det.innerHTML = tarjeta("Detalle de la proximidad", tablaHTML(["Cuenta", "Saltos", "Camino más corto (en saltos)"], d.filas.map(r => `<tr><td class="negrita">${esc(r.cuenta)}</td><td class="num">${r.saltos}</td><td>${rutaChips(r.camino)}</td></tr>`), ["", "num", ""]));
  } else if (f.pestana === "rastreo") {
    panel.innerHTML = cab("Rastreo de fondos", `DFS con restricción temporal · ${fmtNum(d.tiempo_ms, 3)} ms`) + `
      <div class="fila c2" style="margin:0 0 10px">${kpi("Cadenas encontradas", d.total, "secuencias de transferencias")}${kpi("Vuelven al origen", d.con_ciclo, "circulación de fondos", d.con_ciclo ? "rojo" : "verde")}</div>
      <div class="aviso azul" style="margin:0"><span class="simbolo">i</span><div><b>Orden cronológico</b>Desde una transferencia solo se continúa por otra con fecha igual o posterior, dentro de la ventana de días. Así se evita encadenar dinero que todavía no había llegado.</div></div>`;
    det.innerHTML = tarjeta("Cadenas de transferencias", d.cadenas.length ? `<div class="fila c2" style="margin:0">${d.cadenas.map((cad, i) => `
      <div class="item-lista ${cad.ciclo ? "rojo" : ""}"><div class="cab"><b>Cadena ${i + 1} · ${cad.pasos.length} transferencia(s)</b>${cad.ciclo ? '<span class="chip rojo">Vuelve al origen</span>' : ""}</div>
      ${cad.pasos.map(s => `<div class="paso"><span class="fecha">${esc(s.fecha)}</span><span>${esc(s.origen)} <span class="flecha">→</span> ${esc(s.destino)}</span><span class="monto">S/ ${fmtNum(s.monto)}</span></div>`).join("")}</div>`).join("")}</div>`
      : `<div class="vacio">La cuenta no tiene transferencias salientes con fecha.</div>`, d.total > d.cadenas.length ? `Se muestran ${d.cadenas.length} de ${d.total}` : "");
  } else if (f.pestana === "circulacion") {
    panel.innerHTML = cab("Grupos con circulación de fondos", "Componentes fuertemente conexas") + `
      <div class="fila c2" style="margin:0 0 10px">${kpi("Grupos con circulación", d.grupos.length, `${d.componentes} componentes en total`, d.grupos.length ? "rojo" : "verde")}
      ${kpi("Tarjan = Kosaraju", d.coinciden ? "Sí" : "No", `${fmtNum(d.tiempo_tarjan_ms, 3)} ms vs ${fmtNum(d.tiempo_kosaraju_ms, 3)} ms`, d.coinciden ? "verde" : "rojo")}</div>
      <h4>Grupos detectados</h4>${d.grupos.length ? d.grupos.map((gr, i) => `<div class="item-lista rojo" style="margin-bottom:8px"><div class="cab"><b>Grupo ${i + 1}</b><span class="chip rojo">${gr.length} cuentas</span></div><div class="chips">${gr.map(x => `<span class="chip">${esc(x)}</span>`).join("")}</div></div>`).join("") : '<div class="vacio">Sin grupos</div>'}
      <p class="texto-tenue mini">En un grupo de más de una cuenta, desde cualquiera se puede llegar a cualquier otra: el dinero puede volver a su origen.</p>`;
    det.innerHTML = tarjeta(`Capas del recorrido desde ${esc(f.cuenta)}`, d.capas.length ? `<div class="capas">${d.capas.map((capa, i) => `<div class="capa"><div class="tit">Capa ${i}</div><div class="chips">${capa.map(comp => `<span class="chip ${comp.length > 1 ? "rojo" : ""}">${comp.length > 1 ? "{" + comp.map(esc).join(", ") + "}" : esc(comp[0])}</span>`).join("")}</div></div>`).join("")}</div>
      <p class="texto-tenue mini" style="margin-bottom:0">Cada grupo se comprime en un nodo (condensación); el grafo resultante no tiene ciclos y se ordena en capas con el orden topológico (algoritmo de Kahn).</p>` : `<div class="vacio">Ingrese una cuenta existente para ver las capas.</div>`, "Condensación + orden topológico · pruebe con N05 o L1");
  } else if (f.pestana === "fraccionamiento") {
    panel.innerHTML = cab("Operaciones fragmentadas", `Montos entre 80 % y 100 % del umbral · ${fmtNum(d.tiempo_ms, 3)} ms`) + `
      <div class="fila c2" style="margin:0 0 10px">${kpi("Abanicos detectados", d.alertas.length, "entrada o salida", d.alertas.length ? "rojo" : "verde")}${kpi("Montos reconstruidos", d.reconstrucciones.length, "suma de subconjuntos", d.reconstrucciones.length ? "naranja" : "")}</div>
      <h4>Cómo se detecta</h4><p class="texto-tenue mini" style="margin-top:0">Las transferencias se ordenan por fecha (Guía 2) y una ventana deslizante cuenta cuántas cuentas distintas envían a una sola (abanico de entrada) o reciben de una sola (abanico de salida). Luego la programación dinámica (Guía 5) verifica si esos montos pequeños suman la transferencia grande que sale después.</p>`;
    det.innerHTML = tarjeta("Alertas de fraccionamiento", d.alertas.length ? `<div class="fila c2" style="margin:0">${d.alertas.map(a => `
      <div class="item-lista ${a.reconstruccion ? "rojo" : ""}"><div class="cab"><b>${esc(a.cuenta)}</b><span class="chip ${a.tipo === "entrada" ? "naranja" : "morado"}">Abanico de ${a.tipo}</span></div>
      <div class="mini texto-tenue">${a.montos.length} transferencias · total S/ ${fmtNum(a.total)} · ${esc(a.desde)} a ${esc(a.hasta)}</div>
      <div class="chips" style="margin-top:6px">${a.contrapartes.map(x => `<span class="chip">${esc(x)}</span>`).join("")}</div>
      ${a.reconstruccion ? `<div class="formula"><b>Suma de subconjuntos:</b> envía S/ ${fmtNum(a.reconstruccion.monto_salida)} a ${esc(a.reconstruccion.destino)} el ${esc(a.reconstruccion.fecha)} =<br>${a.reconstruccion.montos_usados.map(m => fmtNum(m)).join(" + ")} = <b>${fmtNum(a.reconstruccion.suma)}</b>${a.reconstruccion.suma === a.reconstruccion.monto_salida ? ' <span class="chip rojo">coincidencia exacta</span>' : ` <span class="chip naranja">retiene S/ ${fmtNum(a.reconstruccion.suma - a.reconstruccion.monto_salida)}</span>`}</div>` : ""}</div>`).join("")}</div>` : `<div class="vacio">No se detectaron abanicos con estos parámetros.</div>`);
  } else {
    panel.innerHTML = cab("Alertas recibidas del Módulo 3", "Ruleteo detectado en la red de pagos") + (d.alertas_ruleteo.length
      ? `<div class="lista">${d.alertas_ruleteo.map(a => `<div class="item-lista rojo mini">${esc(a)}</div>`).join("")}</div>`
      : `<div class="aviso verde" style="margin:0"><span class="simbolo">✓</span><div><b>Sin alertas de ruleteo</b>Ejecute el Módulo 3 con la red de cashback para generarlas.</div></div>`) + `
      <h4>Cómo se calcula el puntaje</h4><div class="chips"><span class="chip rojo">Ciclo +3</span><span class="chip naranja">Abanico +2</span><span class="chip naranja">Monto reconstruido +2</span><span class="chip morado">Estratificación +2</span><span class="chip">Contraparte de abanico +1</span><span class="chip azul">Cerca de cuenta marcada +1</span></div>
      <p class="texto-tenue mini">Las k cuentas de mayor puntaje se obtienen con un heap (heapq.nlargest), en O(V log k).</p>`;
    det.innerHTML = tarjeta("Cuentas a revisar primero", tablaHTML(["#", "Cuenta", "Puntaje", "", "Motivos"], d.filas.map((r, i) => `
      <tr><td class="num">${i + 1}</td><td class="negrita">${esc(r.cuenta)}</td><td class="num negrita">${r.puntaje}</td><td style="width:140px">${barra(r.relativo * 100, 100, "rojo")}</td>
      <td><div class="chips">${r.motivos.map(m => `<span class="chip">${esc(m)}</span>`).join("")}</div></td></tr>`), ["num", "", "num", "", ""]), `${fmtNum(d.tiempo_ms, 3)} ms`);
  }
  activarReportes(cont);
}

/* ============================================================ MÓDULO 3 · RUTAS */
const CRITERIOS = [["friccion", "Fricción (Guía 10)"], ["comision", "Comisión en S/"], ["tiempo", "Tiempo (min)"]];

async function paginaRutas(c) {
  const r = E.rutas;
  const nodos = await nodosDe(r.red);
  const opc = sel => nodos.map(n => `<option value="${esc(n.id)}" ${n.id === sel ? "selected" : ""}>${esc(n.nombre)}</option>`).join("");
  c.innerHTML = `
  <div class="tarjeta" style="margin-bottom:18px"><div class="controles">
    <div class="campo"><label>Red de pagos</label>${segmentado("r-red", [["enrutamiento", "Guía 10"], ["cashback", "Campaña CyberDays (cashback)"]], r.red)}</div>
    <div class="campo"><label>Origen</label><select id="r-o">${opc(r.origen)}</select></div>
    <div class="campo"><label>Destino</label><select id="r-d">${opc(r.destino)}</select></div>
    <div class="campo"><label>Criterio de costo</label>${segmentado("r-crit", CRITERIOS, r.criterio)}</div>
    <div class="campo"><label>Monto (S/)</label><input type="number" id="r-monto" value="${r.monto}" min="0" step="50"></div>
  </div><div class="controles" style="margin-top:14px">
    <button class="btn primario" data-vista="ruta">Calcular mejor ruta</button>
    <button class="btn" data-vista="pares">Matriz de todos los pares</button>
    <button class="btn" data-vista="ciclos">Detectar ruleteo (ciclos negativos)</button>
    <span class="texto-tenue mini derecha">Los canales no disponibles o con límite menor que el monto se excluyen automáticamente.</span>
  </div></div>
  <div id="r-res"></div>`;
  onSegmentado("r-red", async v => { r.red = v; await paginaRutas(c); });
  onSegmentado("r-crit", v => { r.criterio = v; calcularRutas(); });
  $$("[data-vista]").forEach(b => b.onclick = () => { r.vista = b.dataset.vista; calcularRutas(); });
  $("#r-o").onchange = $("#r-d").onchange = $("#r-monto").onchange = () => calcularRutas();
  await calcularRutas();
}

async function calcularRutas() {
  const r = E.rutas, cont = $("#r-res");
  r.origen = $("#r-o").value; r.destino = $("#r-d").value; r.monto = +$("#r-monto").value || 0;
  const base = { red: r.red, criterio: r.criterio, monto: r.monto };
  const nombres = Object.fromEntries((E.nodosRed[r.red] || []).map(n => [n.id, n.nombre]));
  cont.innerHTML = `<div class="tarjeta" style="height:200px"></div>`;
  let d;
  try {
    d = await conCarga(cont.firstChild, () => r.vista === "ruta" ? api("ruta", { ...base, origen: r.origen, destino: r.destino })
      : r.vista === "pares" ? api("todos_los_pares", base) : api("ciclos", base));
  } catch { return; }
  E.reportes.rutas = d.reporte;
  refrescarEstado();
  if (r.vista === "ruta") {
    const ciclos = d.ciclos.length ? `<div class="aviso rojo"><span class="simbolo">!</span><div><b>Ruleteo detectado: ${d.ciclos.length} ciclo(s) negativo(s)</b>
      ${d.ciclos.map(cc => `Ciclo ${rutaChips(cc.ciclo, nombres)} con costo <b>${fmtNum(cc.costo)}</b> por vuelta. Se retiran las promociones ${cc.retiradas.join(", ")} y se recalcula con Bellman-Ford. La alerta se envió al Módulo 2.`).join("<br>")}</div></div>` : "";
    if (!d.mejor) {
      cont.innerHTML = ciclos + `<div class="aviso naranja"><span class="simbolo">!</span><div><b>No existe ruta</b>Ninguna ruta de ${esc(nombres[r.origen])} a ${esc(nombres[r.destino])} cumple las restricciones para un monto de S/ ${fmtNum(r.monto)}.</div></div>`
        + `<div class="fila">${visorHTML("v-rutas")}</div>`;
      pintarVisor("v-rutas", d.grafo); return;
    }
    const ms = d.menos_saltos, sobre = ms ? ms.costo - d.mejor.costo : 0;
    const maxC = Math.max(...d.alternativas.map(a => a.costo));
    cont.innerHTML = ciclos + `
      <div class="fila c4">
        ${kpi("Costo de la mejor ruta", fmtNum(d.mejor.costo), `${d.mejor.ruta.length - 1} tramos`, "verde", d.unidad)}
        ${kpi("Ruta con menos saltos", ms ? fmtNum(ms.costo) : "—", ms ? (sobre > 0 ? `Sobrecosto de ${fmtNum(sobre)} (${pct(sobre, ms.costo)} %)` : "Coincide con la mejor") : "", sobre > 0 ? "rojo" : "")}
        ${kpi("Alternativas evaluadas", d.total_alternativas, "enumeradas con backtracking")}
        ${kpi("Algoritmo elegido", d.algoritmo.split(" ")[0], d.algoritmo.includes("negativos") ? "hay pesos negativos" : "todos los pesos ≥ 0", "morado")}
      </div>
      <div class="fila c-principal">${visorHTML("v-rutas")}
        <div class="tarjeta"><div class="tarjeta-cab"><h3>Ruta recomendada</h3>${botonReporte("rutas")}</div>
          <div style="margin-bottom:12px">${rutaChips(d.mejor.ruta, nombres)}</div>
          ${ms ? `<h4>Ruta con menos saltos (BFS)</h4>${rutaChips(ms.ruta, nombres)}` : ""}
          <h4>Canales excluidos</h4>${d.excluidas.length ? `<div class="lista">${d.excluidas.map(x => `<div class="item-lista mini"><b>${esc(nombres[x.origen])} → ${esc(nombres[x.destino])}</b><br><span class="texto-tenue">${esc(x.motivo)}</span></div>`).join("")}</div>` : '<div class="texto-tenue mini">Ninguno para este monto.</div>'}
          <h4>Por qué este algoritmo</h4><p class="mini texto-tenue" style="margin:0">${d.algoritmo.startsWith("Dijkstra") ? "Comisiones, tiempos y fricción no son negativos: Dijkstra (voraz, Guía 9) es correcto y más rápido que Bellman-Ford." : "Hay aristas con costo negativo (cashback): Dijkstra podría fallar, por eso se usa Bellman-Ford (programación dinámica, Guía 9), que además detecta ciclos negativos."}</p>
          <p class="mini texto-tenue">Tiempo total del análisis: ${fmtNum(d.tiempo_ms, 3)} ms</p></div></div>
      ${tarjeta("Todas las alternativas", tablaHTML(["#", "Ruta", "Tramos", "Costo", "", "Diferencia"], d.alternativas.map((a, i) => `
        <tr class="${i === 0 ? "destacada" : ""}"><td class="num">${i + 1}</td><td>${rutaChips(a.ruta, nombres)}</td><td class="num">${a.tramos}</td><td class="num negrita">${fmtNum(a.costo)}</td>
        <td style="width:160px">${barra(a.costo, maxC, i === 0 ? "verde" : "")}</td><td class="num">${i === 0 ? '<span class="chip verde">mejor</span>' : `+${fmtNum(a.sobrecosto)}`}</td></tr>`), ["num", "", "num", "num", "", "num"]),
        `Backtracking con poda (Guía 6) · ${d.unidad}`)}`;
    pintarVisor("v-rutas", d.grafo);
  } else if (r.vista === "pares") {
    if (d.ciclo_negativo.length) {
      cont.innerHTML = `<div class="aviso rojo"><span class="simbolo">!</span><div><b>La matriz no está definida</b>Floyd-Warshall encontró dist[i][i] &lt; 0 para ${d.ciclo_negativo.map(esc).join(", ")}: hay un ciclo negativo y el costo mínimo puede bajar sin límite. Use "Detectar ruleteo".</div></div>`;
      return;
    }
    const vals = d.matriz.flat().filter(x => x !== null && x > 0), vmax = Math.max(...vals, 1);
    const color = v => v === null ? "#F6F7F9" : v === 0 ? "#fff" : `rgba(47,93,140,${0.08 + 0.55 * v / vmax})`;
    cont.innerHTML = `<div class="fila c4">
      ${kpi("Floyd-Warshall", fmtNum(d.tiempo_fw_ms, 3), "programación dinámica · O(V³)", "", "ms")}
      ${kpi("Johnson", fmtNum(d.tiempo_johnson_ms, 3), "Bellman-Ford + Dijkstra · O(VE + V(V+E) log V)", "", "ms")}
      ${kpi("Resultados iguales", d.iguales ? "Sí" : "No", "verificación cruzada", d.iguales ? "verde" : "rojo")}
      ${kpi("Pares conectados", vals.length, `de ${d.orden.length * (d.orden.length - 1)} pares posibles`)}</div>
      ${tarjeta(`Costo mínimo entre todos los pares · ${esc(d.unidad)}`, `<div class="tabla-cont" style="max-height:none"><table class="mapa-calor"><thead><tr><th>Desde \\ hacia</th>${d.orden.map(n => `<th title="${esc(d.nombres[n])}">${esc(n)}</th>`).join("")}</tr></thead><tbody>
        ${d.orden.map((n, i) => `<tr><td class="negrita">${esc(d.nombres[n])}</td>${d.matriz[i].map(v => `<td style="background:${color(v)}">${v === null ? '<span class="texto-tenue">∞</span>' : fmtNum(v)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>
        <p class="texto-tenue mini">∞ = no existe ruta. En redes dispersas y grandes Johnson escala mejor; Floyd-Warshall itera sobre conexiones inexistentes.</p>`, "", botonReporte("rutas"))}`;
  } else {
    cont.innerHTML = (d.ciclos.length ? `<div class="aviso rojo"><span class="simbolo">!</span><div><b>${d.ciclos.length} ciclo(s) negativo(s): posible ruleteo</b>Cada vuelta deja ganancia al usuario a costa de la entidad. Un cashback real tiene tope por usuario; el ciclo infinito revela un defecto en el diseño de la promoción.</div></div>`
      : d.negativas.length ? `<div class="aviso verde"><span class="simbolo">✓</span><div><b>Hay pesos negativos, pero ningún ciclo negativo</b>Las rutas siguen bien definidas; se calculan con Bellman-Ford.</div></div>`
        : `<div class="aviso verde"><span class="simbolo">✓</span><div><b>Sin aristas de costo negativo</b>Con pesos no negativos no puede existir un ciclo negativo. Cambie a la red "Campaña CyberDays".</div></div>`) + `
      <div class="fila c-principal">${visorHTML("v-rutas")}
        <div class="tarjeta"><div class="tarjeta-cab"><h3>Resultado</h3>${botonReporte("rutas")}</div>
          <h4 style="margin-top:0">Aristas con costo neto negativo</h4>${d.negativas.length ? `<div class="lista">${d.negativas.map(x => `<div class="item-lista mini"><b>${esc(nombres[x.origen])} → ${esc(nombres[x.destino])}</b> <span class="chip morado">${fmtNum(x.costo)}</span></div>`).join("")}</div>` : '<div class="texto-tenue mini">Ninguna.</div>'}
          <h4>Ciclos encontrados (Bellman-Ford)</h4>${d.ciclos.length ? d.ciclos.map(cc => `<div class="item-lista rojo"><div style="margin-bottom:6px">${rutaChips(cc.ciclo, nombres)}</div><span class="chip rojo">${fmtNum(cc.costo)} por vuelta</span></div>`).join("") : '<div class="texto-tenue mini">Ninguno.</div>'}
          <h4>Floyd-Warshall: nodos con dist[i][i] &lt; 0</h4><div class="chips">${d.en_floyd_warshall.length ? d.en_floyd_warshall.map(n => `<span class="chip rojo">${esc(nombres[n] || n)}</span>`).join("") : '<span class="texto-tenue mini">Ninguno</span>'}</div>
          <p class="texto-tenue mini">Incluye los nodos que pueden salir y volver pasando por el ciclo.</p></div></div>`;
    pintarVisor("v-rutas", d.grafo);
  }
  activarReportes(cont);
}

/* ============================================================ MÓDULO 4 · LIQUIDEZ */
const PEST_LIQ = [["distribucion", "Distribución", "Edmonds-Karp"], ["costo", "Plan de costo mínimo", "Bellman-Ford"], ["voraz", "Voraz vs óptimo", "Guía 3"], ["arbol", "Red mínima de rutas", "Prim · Kruskal"]];

async function paginaLiquidez(c) {
  const l = E.liquidez;
  c.innerHTML = `
  <div class="tarjeta" style="margin-bottom:18px"><div class="controles">
    <div class="campo"><label>Red de bóvedas y agencias</label>${segmentado("l-red", [["liquidez", "Figura 5 (con déficit)"], ["liquidez_ampliada", "Red ampliada (dos bóvedas)"]], l.red)}</div>
    <span class="texto-tenue mini derecha" style="max-width:480px">Modelo de flujo: superfuente S* → bóvedas (capacidad = oferta) y agencias → supersumidero T* (capacidad = demanda). Cantidades en miles de S/.</span>
  </div></div>
  <div class="pestanas" id="l-pest">${PEST_LIQ.map(([k, t, a]) => `<button data-p="${k}" class="${l.pestana === k ? "activo" : ""}">${t} <span class="alg">${a}</span></button>`).join("")}</div>
  <div id="l-res"></div>`;
  onSegmentado("l-red", v => { l.red = v; calcularLiquidez(); });
  $$("#l-pest button").forEach(b => b.onclick = () => { l.pestana = b.dataset.p; $$("#l-pest button").forEach(x => x.classList.toggle("activo", x === b)); calcularLiquidez(); });
  await calcularLiquidez();
}

async function calcularLiquidez(previo = null) {
  const l = E.liquidez, cont = $("#l-res");
  cont.innerHTML = `<div class="tarjeta" style="height:200px"></div>`;
  let d;
  try {
    d = previo || await conCarga(cont.firstChild, () => api({ distribucion: "distribucion", costo: "costo_minimo", voraz: "voraz", arbol: "arbol" }[l.pestana], { red: l.red }));
  } catch { return; }
  E.reportes.liquidez = d.reporte;
  if (l.pestana === "distribucion") {
    const cob = pct(d.flujo, d.demanda);
    cont.innerHTML = `
      <div class="fila c5">
        ${kpi("Flujo máximo", fmtNum(d.flujo), "Edmonds-Karp", "verde", "miles S/")}
        ${kpi("Demanda total", fmtNum(d.demanda), `oferta disponible ${fmtNum(d.oferta)}`)}
        ${kpi("Cobertura", cob, d.factible ? "toda la demanda cubierta" : `faltan ${fmtNum(d.demanda - d.flujo)}`, d.factible ? "verde" : "rojo", "%")}
        ${kpi("Corte mínimo", fmtNum(d.capacidad_corte), d.capacidad_corte === d.flujo ? "= flujo máximo ✓ (teorema)" : "no coincide", "morado")}
        ${kpi("Costo del plan", fmtNum(d.costo), "S/ · sin optimizar costos", "naranja")}
      </div>
      <div class="aviso ${d.factible ? "verde" : "naranja"}"><span class="simbolo">${d.factible ? "✓" : "!"}</span><div><b>${d.factible ? "Plan factible" : "Plan no factible"}</b>${d.factible ? "Las capacidades permiten cubrir la demanda de todas las agencias." : `Aunque haya efectivo disponible, las capacidades de transporte solo permiten entregar ${fmtNum(d.flujo)} de ${fmtNum(d.demanda)}.`} Verificación de capacidad y conservación del flujo: <b>${d.verificacion.length ? "con problemas" : "correcta"}</b>.</div></div>
      <div class="fila c-principal">${visorHTML("v-liq")}
        <div class="tarjeta"><div class="tarjeta-cab"><h3>Abastecimiento por agencia</h3>${botonReporte("liquidez")}</div>
          <div class="barras-h">${d.agencias.map(a => `<div class="fila-b"><b>${esc(a.agencia)}</b><div class="pista"><div style="width:${pct(a.recibe, a.demanda)}%;background:${a.falta ? "#D9822B" : "#1F8A5B"}"></div></div><span class="num">${fmtNum(a.recibe)}/${fmtNum(a.demanda)}</span></div>`).join("")}</div>
          <h4>Corte mínimo</h4><div class="chips">${d.corte.map(x => `<span class="chip rojo">${esc(x.origen)} → ${esc(x.destino)} (${fmtNum(x.capacidad)})</span>`).join("")}</div>
          <h4>Cuellos de botella relevantes</h4>${d.cuellos.length ? `<div class="lista">${d.cuellos.map(x => `<div class="item-lista mini"><b>${esc(x.origen)} → ${esc(x.destino)}</b> limita a <b>${esc(x.agencia)}</b></div>`).join("")}</div>` : '<div class="texto-tenue mini">Ninguno: no hay agencias con déficit.</div>'}
          <p class="texto-tenue mini">El corte mínimo puede no ser único. Los cuellos relevantes son los tramos saturados que alimentan agencias con faltante.</p></div></div>
      <div class="fila c2">
        ${tarjeta("Caminos aumentantes (BFS)", `<div class="lista">${d.caminos.map((p, i) => `<div class="item-lista"><div class="cab"><b>${i + 1}.</b><span class="chip verde">+${fmtNum(p.delta)}</span></div>${rutaChips(p.ruta)}</div>`).join("")}</div>`, "Cada BFS encuentra el camino con menos tramos en la red residual")}
        ${tarjeta("Escenario: modificar oferta y demanda", tablaHTML(["Nodo", "Tipo", "Oferta", "Demanda", ""], d.nodos.filter(n => n.tipo !== "boveda_regional").map(n => `
          <tr><td class="negrita">${esc(n.nombre)}</td><td class="mini">${NOMBRE_TIPO[n.tipo] || esc(n.tipo)}</td>
          <td><input type="number" data-of="${esc(n.id)}" value="${n.oferta || 0}" style="width:90px"></td><td><input type="number" data-de="${esc(n.id)}" value="${n.demanda || 0}" style="width:90px"></td>
          <td><button class="btn chico" data-rec="${esc(n.id)}">Recalcular</button></td></tr>`)), "Pruebe qué pasa si cambia la demanda de una agencia")}
      </div>`;
    pintarVisor("v-liq", d.grafo);
    $$("[data-rec]").forEach(b => b.onclick = async () => {
      const id = b.dataset.rec;
      try {
        const nd = await api("editar_liquidez", { red: l.red, nodo: id, oferta: $(`[data-of="${id}"]`).value, demanda: $(`[data-de="${id}"]`).value });
        aviso(`Recalculado: flujo máximo ${fmtNum(nd.flujo)}.`, "ok");
        calcularLiquidez(nd);
      } catch (e) { aviso(e.message, "error"); }
    });
  } else if (l.pestana === "costo") {
    cont.innerHTML = `<div class="fila c4">
      ${kpi("Flujo enviado", fmtNum(d.flujo), "igual al flujo máximo", "verde", "miles S/")}
      ${kpi("Costo plan Edmonds-Karp", fmtNum(d.costo_ek), "rutas elegidas por número de tramos", "", "S/")}
      ${kpi("Costo plan óptimo", fmtNum(d.costo), "caminos aumentantes de menor costo", "verde", "S/")}
      ${kpi("Ahorro", fmtNum(d.ahorro), d.costo_ek ? `${(100 * d.ahorro / d.costo_ek).toFixed(1)} % menos` : "", d.ahorro > 0 ? "verde" : "", "S/")}</div>
      <div class="aviso azul"><span class="simbolo">i</span><div><b>Por qué hace falta</b>El flujo máximo solo maximiza la cantidad enviada; no considera el costo (Guía 11). El plan de costo mínimo busca cada camino aumentante con Bellman-Ford sobre la red residual, que tiene costos negativos en las aristas inversas.</div></div>
      <div class="fila c-principal">${visorHTML("v-liq")}
        ${tarjeta("Comparación por ruta", tablaHTML(["Ruta", "Cap.", "Costo/u", "Edmonds-Karp", "Costo mínimo"], d.rutas.map(x => `
          <tr><td class="negrita nowrap">${esc(x.origen)} → ${esc(x.destino)}</td><td class="num">${fmtNum(x.capacidad)}</td><td class="num">${fmtNum(x.costo)}</td><td class="num">${fmtNum(x.flujo_ek)}</td>
          <td class="num ${x.flujo !== x.flujo_ek ? "negrita" : ""}" style="${x.flujo !== x.flujo_ek ? "color:#1F8A5B" : ""}">${fmtNum(x.flujo)}</td></tr>`), ["", "num", "num", "num", "num"]), "En verde, rutas que cambian", botonReporte("liquidez"))}</div>`;
    pintarVisor("v-liq", d.grafo);
  } else if (l.pestana === "voraz") {
    const max = Math.max(...d.filas.map(f => f.demanda), 1);
    cont.innerHTML = `<div class="fila c3">
      ${kpi("Voraz: agencia más cercana primero", fmtNum(d.total_voraz), "decisiones irrevocables", d.total_voraz < d.total_flujo ? "rojo" : "", "miles S/")}
      ${kpi("Flujo máximo (Edmonds-Karp)", fmtNum(d.total_flujo), "corrige decisiones con aristas inversas", "verde", "miles S/")}
      ${kpi("Diferencia", fmtNum(d.total_flujo - d.total_voraz), d.total_flujo > d.total_voraz ? "efectivo que el voraz deja de entregar" : "en esta red el voraz alcanza el óptimo", d.total_flujo > d.total_voraz ? "naranja" : "verde", "miles S/")}</div>
      ${d.total_flujo > d.total_voraz ? `<div class="aviso naranja"><span class="simbolo">!</span><div><b>Por qué falla el voraz</b>Atiende primero a la agencia más barata de alcanzar y usa su ruta más barata, aunque esa capacidad la necesitaba otra agencia que no tiene alternativa. Como no puede deshacer decisiones (no usa aristas inversas), termina entregando menos. Ejemplo de que una elección localmente óptima no garantiza el óptimo global (Guía 3).</div></div>` : `<div class="aviso azul"><span class="simbolo">i</span><div><b>Pruebe la red ampliada</b>En la Figura 5 cada agencia tiene una sola ruta, por eso el voraz coincide con el óptimo.</div></div>`}
      ${tarjeta("Entrega por agencia (en orden de atención del voraz)", `<div class="agrupadas">${d.filas.map((f, i) => `<div class="grupo"><div class="nombre">${i + 1}. ${esc(f.agencia)}</div>
        <div class="linea-b"><span class="texto-tenue">Demanda</span><div class="pista"><div style="width:${pct(f.demanda, max)}%;background:#A9B4C4"></div></div><span class="num">${fmtNum(f.demanda)}</span></div>
        <div class="linea-b"><span class="texto-tenue">Voraz</span><div class="pista"><div style="width:${pct(f.voraz, max)}%;background:#D9822B"></div></div><span class="num">${fmtNum(f.voraz)}</span></div>
        <div class="linea-b"><span class="texto-tenue">Flujo máximo</span><div class="pista"><div style="width:${pct(f.flujo, max)}%;background:#1F8A5B"></div></div><span class="num">${fmtNum(f.flujo)}</span></div></div>`).join("")}</div>`, "", botonReporte("liquidez"))}`;
  } else {
    const perdida = d.flujo_completo - d.flujo_arbol;
    cont.innerHTML = `<div class="fila c4">
      ${kpi("Costo de habilitación (Prim)", fmtNum(d.costo_prim), `${fmtNum(d.tiempo_prim_ms, 3)} ms`)}
      ${kpi("Costo de habilitación (Kruskal)", fmtNum(d.costo_kruskal), d.costo_prim === d.costo_kruskal ? "igual a Prim ✓" : "distinto", d.costo_prim === d.costo_kruskal ? "verde" : "rojo")}
      ${kpi("Flujo con la red completa", fmtNum(d.flujo_completo), "todas las rutas", "verde", "miles S/")}
      ${kpi("Flujo solo con el árbol", fmtNum(d.flujo_arbol), perdida > 0 ? `pierde ${fmtNum(perdida)} (${pct(perdida, d.flujo_completo)} %)` : "sin pérdida", perdida > 0 ? "rojo" : "verde", "miles S/")}</div>
      <div class="aviso azul"><span class="simbolo">i</span><div><b>Qué aporta y qué no</b>El árbol de expansión mínima responde qué rutas habilitar para conectar todos los puntos al menor costo fijo. No considera capacidades ni la dirección de los traslados, y deja un solo camino entre cada par: por eso el flujo con el árbol puede ser menor. Ilustra el compromiso entre costo de la red y capacidad.</div></div>
      <div class="fila c-principal">${visorHTML("v-liq")}
        ${tarjeta("Rutas del árbol (Kruskal)", tablaHTML(["Ruta", "Costo de habilitación"], d.aristas.map(a => `<tr><td class="negrita">${esc(a.a)} — ${esc(a.b)}</td><td class="num">${fmtNum(a.costo)}</td></tr>`), ["", "num"]), "Union-find evita ciclos", botonReporte("liquidez"))}</div>`;
    pintarVisor("v-liq", d.grafo);
  }
  activarReportes(cont);
}

/* ============================================================ MÓDULO 5 · EVALUACIÓN */
const PEST_EV = [["verificaciones", "Verificaciones cruzadas"], ["desempeno", "Desempeño empírico"], ["complejidad", "Complejidad teórica"], ["pruebas", "Pruebas automatizadas"]];
const GRUPOS_BENCH = [
  ["Rutas: todos los pares", ["Floyd-Warshall (todos los pares)", "Johnson (todos los pares)"]],
  ["Rutas: un origen", ["Dijkstra (1 origen)", "Bellman-Ford (1 origen)"]],
  ["Recorridos y componentes", ["BFS", "Tarjan", "Kosaraju"]],
  ["Flujo y árbol de expansión", ["Edmonds-Karp", "Ford-Fulkerson DFS", "Prim", "Kruskal"]],
];

async function paginaEvaluacion(c) {
  const ev = E.evaluacion;
  c.innerHTML = `<div class="pestanas" id="e-pest">${PEST_EV.map(([k, t]) => `<button data-p="${k}" class="${ev.pestana === k ? "activo" : ""}">${t}</button>`).join("")}</div><div id="e-res"></div>`;
  $$("#e-pest button").forEach(b => b.onclick = () => { ev.pestana = b.dataset.p; $$("#e-pest button").forEach(x => x.classList.toggle("activo", x === b)); vistaEvaluacion(); });
  await vistaEvaluacion();
}

async function vistaEvaluacion() {
  const ev = E.evaluacion, cont = $("#e-res");
  if (ev.pestana === "verificaciones") {
    cont.innerHTML = `<div class="tarjeta" style="height:200px"></div>`;
    let d; try { d = await conCarga(cont.firstChild, () => api("verificaciones")); } catch { return; }
    E.reportes.evaluacion = d.reporte;
    const ok = d.filas.filter(f => f.ok).length;
    const esc_ = [...new Set(d.filas.map(f => f.escenario))];
    cont.innerHTML = `<div class="fila c3">
      ${kpi("Verificaciones correctas", `${ok}/${d.filas.length}`, ok === d.filas.length ? "todos los resultados coinciden" : "revise las fallas", ok === d.filas.length ? "verde" : "rojo")}
      ${kpi("Escenarios cubiertos", esc_.length, esc_.join(" · "))}
      ${kpi("Tiempo de ejecución", fmtNum(d.tiempo_ms, 1), "datos simulados + redes aleatorias", "", "ms")}</div>
      ${tarjeta("Algoritmos distintos que deben dar el mismo resultado", sinLimite(tablaHTML(["Escenario", "Comparación", "Resultado", "Detalle"], d.filas.map(f => `
        <tr><td><span class="chip azul">${esc(f.escenario)}</span></td><td>${esc(f.comparacion)}</td><td>${f.ok ? '<span class="chip verde">✓ Correcto</span>' : '<span class="chip rojo">✗ Falla</span>'}</td><td class="mini texto-tenue">${esc(f.detalle)}</td></tr>`))),
        "Si dos métodos independientes coinciden, el resultado es confiable", botonReporte("evaluacion"))}`;
  } else if (ev.pestana === "desempeno") {
    cont.innerHTML = `<div class="tarjeta" style="margin-bottom:18px"><div class="controles">
      <div class="campo"><label>Tamaños V (separados por coma)</label><input type="text" id="e-tam" value="${ev.tamanos || "10,50,100,200"}" style="width:200px"></div>
      <div class="campo"><label>Densidad</label>${segmentado("e-dens", [["dispersa", "Dispersa (E ≈ 3V)"], ["densa", "Densa (E ≈ V²/4)"]], ev.densidad)}</div>
      <button class="btn primario" id="e-medir">Medir tiempos y memoria</button>
      <span class="texto-tenue mini derecha" style="max-width:380px">Redes aleatorias con semilla fija (reproducibles). Floyd-Warshall es O(V³): más de 300 nodos tarda varios segundos.</span></div></div><div id="e-bench"></div>`;
    onSegmentado("e-dens", v => ev.densidad = v);
    $("#e-medir").onclick = medir;
    if (ev.bench) pintarBench(ev.bench); else medir();
  } else if (ev.pestana === "complejidad") {
    const d = await api("complejidad");
    E.reportes.evaluacion = d.reporte;
    cont.innerHTML = tarjeta("Complejidad teórica de los algoritmos seleccionados", tablaHTML(["Módulo", "Algoritmo", "Guía", "Paradigma", "Tiempo", "Espacio"], d.filas.map(f => `
      <tr><td><span class="chip ${{ 2: "rojo", 3: "naranja", 4: "verde" }[f.modulo] || ""}">Módulo ${f.modulo}</span></td><td class="negrita">${esc(f.algoritmo)}</td><td><span class="chip azul">Guía ${esc(f.guia)}</span></td><td>${esc(f.paradigma)}</td><td><code>${esc(f.tiempo)}</code></td><td><code>${esc(f.espacio)}</code></td></tr>`)),
      "V = nodos, E = aristas, F = flujo total, S = monto objetivo, k = cuentas del ranking", botonReporte("evaluacion"));
  } else {
    cont.innerHTML = `<div class="tarjeta"><div class="tarjeta-cab"><div><h3>Pruebas automatizadas (pytest)</h3><div class="nota">Carga, validación, algoritmos y casos de prueba de cada módulo</div></div><button class="btn primario" id="e-pytest">Ejecutar pruebas</button></div><div id="e-salida"><div class="vacio">Presione "Ejecutar pruebas".</div></div></div>`;
    $("#e-pytest").onclick = async () => {
      const caja = $("#e-salida");
      let d; try { d = await conCarga(caja.parentElement, () => api("pruebas")); } catch { return; }
      const html = esc(d.salida).replace(/(\d+ passed[^\n]*)/g, '<span class="ok">$1</span>').replace(/(\d+ failed[^\n]*|FAILED[^\n]*|Error[^\n]*)/g, '<span class="err">$1</span>');
      caja.innerHTML = `<div class="aviso ${d.ok ? "verde" : "rojo"}"><span class="simbolo">${d.ok ? "✓" : "!"}</span><div><b>${d.ok ? "Todas las pruebas pasaron" : "Hay pruebas que fallan"}</b>${esc(d.resumen)} · ${d.tiempo_s.toFixed(1)} s</div></div><pre class="consola">${html}</pre>`;
    };
  }
  activarReportes(cont);
}

async function medir() {
  const ev = E.evaluacion;
  ev.tamanos = $("#e-tam").value;
  const caja = $("#e-bench");
  caja.innerHTML = `<div class="tarjeta" style="height:240px"></div>`;
  try { ev.bench = await conCarga(caja.firstChild, () => api("benchmark", { tamanos: ev.tamanos, densidad: ev.densidad })); } catch { return; }
  pintarBench(ev.bench);
}

function pintarBench(d) {
  E.reportes.evaluacion = d.reporte;
  const caja = $("#e-bench");
  caja.innerHTML = `<div class="fila c2">${GRUPOS_BENCH.map(([t], i) => `<div class="tarjeta"><div class="tarjeta-cab"><h3>${t}</h3><span class="nota">tiempo (ms, escala log) vs V · ${esc(d.densidad)}</span></div><div class="grafico" id="gb-${i}"></div></div>`).join("")}</div>
    ${tarjeta("Tabla de mediciones", tablaHTML(["Algoritmo", "V", "E", "Tiempo (ms)", "Memoria pico (KB)"], Object.entries(d.series).flatMap(([alg, ps]) => ps.map(p => `<tr><td class="negrita">${esc(alg)}</td><td class="num">${p.n}</td><td class="num">${p.e}</td><td class="num">${fmtNum(p.ms, 3)}</td><td class="num">${fmtNum(p.kb, 1)}</td></tr>`)), ["", "num", "num", "num", "num"]),
      "Promedio de repeticiones · time.perf_counter y tracemalloc", botonReporte("evaluacion"))}`;
  GRUPOS_BENCH.forEach(([_, algs], i) => graficoLineas($(`#gb-${i}`), algs.filter(a => d.series[a]).map(a => ({ nombre: a.replace(" (todos los pares)", "").replace(" (1 origen)", ""), puntos: d.series[a].map(p => ({ x: p.n, y: p.ms })) })), { xEtiqueta: "número de nodos V", yEtiqueta: "ms" }));
  activarReportes(caja);
}

/* ============================================================ arranque */
window.addEventListener("hashchange", navegar);
window.addEventListener("resize", () => { clearTimeout(window._rs); window._rs = setTimeout(() => Object.values(VISORES).forEach(v => v.datos && v.dibujar(v.datos)), 250); });
(async () => {
  try { await refrescarEstado(); } catch { aviso("No hay conexión con el servidor local. Ejecute python main.py.", "error"); }
  navegar();
})();
