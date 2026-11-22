/* grafo.js - Visor interactivo de grafos en SVG y gráficos de líneas.
   Sin bibliotecas externas: funciona sin internet. */

const SVGNS = "http://www.w3.org/2000/svg";

const COLOR_TIPO = {
  cuenta: ["#E8F0F9", "#2F5D8C"], cliente: ["#EEF1F5", "#6B7688"], billetera: ["#EFEAFA", "#7651C2"],
  banco: ["#E8F0F9", "#2F5D8C"], compensacion: ["#FDF1E3", "#D9822B"], comercio: ["#E3F4EC", "#1F8A5B"],
  boveda_central: ["#FBEAE8", "#C0392B"], boveda_regional: ["#FDF1E3", "#D9822B"], agencia: ["#E3F4EC", "#1F8A5B"],
  atm: ["#FBEAE8", "#C0392B"], generico: ["#EEF1F5", "#6B7688"],
};
const NOMBRE_TIPO = {
  cuenta: "Cuenta", cliente: "Cliente", billetera: "Billetera digital", banco: "Banco / cuenta bancaria",
  compensacion: "Cámara de compensación", comercio: "Comercio", boveda_central: "Bóveda central",
  boveda_regional: "Bóveda regional", agencia: "Agencia", atm: "Cajero / red ATM", generico: "Otro",
};
const ESTILO_ARISTA = {
  "": { c: "#A9B4C4", w: 1.6 },
  ruta: { c: "#1F8A5B", w: 4.2 }, flujo: { c: "#1F8A5B", w: 3.2 }, excluida: { c: "#C0392B", w: 2, dash: "7 5" },
  ciclo: { c: "#C0392B", w: 3.8 }, corte: { c: "#C0392B", w: 4.4 }, saturada: { c: "#D9822B", w: 3.6 },
  arbol: { c: "#2F5D8C", w: 4.2 }, abanico: { c: "#D9822B", w: 2.6 },
};
const ANILLO_NODO = { origen: "#2F5D8C", destino: "#1F8A5B", alerta: "#C0392B", ok: "#1F8A5B" };

function el(tag, atributos = {}, padre = null) {
  const e = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(atributos)) if (v !== undefined && v !== null) e.setAttribute(k, v);
  if (padre) padre.appendChild(e);
  return e;
}

function fmtNum(x, dec = 2) {
  if (x === null || x === undefined || x === "") return "–";
  if (typeof x !== "number") return String(x);
  if (!isFinite(x)) return "∞";
  return Number.isInteger(x) ? x.toLocaleString("es-PE") : x.toLocaleString("es-PE", { maximumFractionDigits: dec });
}

class VisorGrafo {
  constructor(contenedor) {
    this.cont = contenedor;
    this.cont.innerHTML = "";
    this.cont.classList.add("visor");
    this.mostrarEtiquetas = true;
    this.t = { x: 0, y: 0, k: 1 };
    this.svg = el("svg", {}, this.cont);
    const defs = el("defs", {}, this.svg);
    for (const [clase, est] of Object.entries(ESTILO_ARISTA)) {
      const m = el("marker", { id: `fl-${clase || "base"}-${VisorGrafo.cuenta}`, viewBox: "0 0 10 10", refX: 9, refY: 5,
        markerWidth: 10, markerHeight: 10, markerUnits: "userSpaceOnUse", orient: "auto-start-reverse" }, defs);
      el("path", { d: "M0,0 L10,5 L0,10 z", fill: est.c }, m);
    }
    const sombra = el("filter", { id: `brillo-${VisorGrafo.cuenta}`, x: "-50%", y: "-50%", width: "200%", height: "200%" }, defs);
    el("feGaussianBlur", { stdDeviation: 4 }, sombra);
    this.id = VisorGrafo.cuenta++;
    this.g = el("g", {}, this.svg);
    this.capaAristas = el("g", {}, this.g);
    this.capaNodos = el("g", {}, this.g);
    this.leyenda = document.createElement("div");
    this.leyenda.className = "leyenda";
    this.cont.appendChild(this.leyenda);
    this._eventos();
  }

  /* ---------------------------------------------------------- datos */
  dibujar(datos) {
    this.datos = datos;
    this.pos = {};
    this._leyenda();
    const arriba = (this.leyenda.offsetHeight || 0) + 26;
    const ancho = this.cont.clientWidth || 900, alto = this.cont.clientHeight || 560;
    this.svg.setAttribute("viewBox", `0 0 ${ancho} ${alto}`);
    const n = datos.nodos.length;
    const xs = datos.nodos.map(d => d.x), ys = datos.nodos.map(d => d.y);
    const minx = Math.min(...xs), maxx = Math.max(...xs), miny = Math.min(...ys), maxy = Math.max(...ys);
    const pad = 60, abajo = 48, sx = maxx - minx || 1, sy = maxy - miny || 1;
    const k = Math.min((ancho - 2 * pad) / sx, (alto - arriba - abajo - 20) / sy);
    const ox = (ancho - sx * k) / 2, oy = arriba + 20 + ((alto - arriba - abajo - 20) - sy * k) / 2;
    for (const d of datos.nodos) {
      this.pos[d.id] = {
        x: maxx === minx ? ancho / 2 : ox + (d.x - minx) * k,
        y: maxy === miny ? alto / 2 : oy + (d.y - miny) * k,
      };
    }
    this.nodoPorId = Object.fromEntries(datos.nodos.map(d => [d.id, d]));
    // radio de los nodos según la distancia típica al vecino más cercano
    const ps = Object.values(this.pos), cercanos = [];
    for (const a of ps) {
      let m = Infinity;
      for (const b of ps) if (a !== b) m = Math.min(m, Math.hypot(a.x - b.x, a.y - b.y));
      if (isFinite(m)) cercanos.push(m);
    }
    cercanos.sort((a, b) => a - b);
    const mediana = cercanos.length ? cercanos[Math.floor(cercanos.length / 2)] : 80;
    this.R = Math.max(9, Math.min(20, mediana * 0.3));
    this.ajustar();
    this._render();
  }

  /* ---------------------------------------------------------- geometría */
  _desplazamientos() {
    const grupos = {};
    for (const a of this.datos.aristas) {
      const [p, q] = a.origen < a.destino ? [a.origen, a.destino] : [a.destino, a.origen];
      (grupos[p + "\u0000" + q] = grupos[p + "\u0000" + q] || []).push(a);
    }
    const desp = {};
    for (const lista of Object.values(grupos)) {
      lista.sort((a, b) => (a.origen < b.origen ? -1 : 1) || a.id - b.id);
      const m = lista.length;
      lista.forEach((a, i) => { desp[a.id] = m > 1 ? (i - (m - 1) / 2) * 34 : 0; });
    }
    return desp;
  }

  _geometria(a, desp) {
    const R = this.R, P = this.pos[a.origen], Q = this.pos[a.destino];
    const [ca, cb] = a.origen < a.destino ? [P, Q] : [Q, P];   // marco canónico para curvas paralelas
    let dx = cb.x - ca.x, dy = cb.y - ca.y, L = Math.hypot(dx, dy) || 1;
    const nx = -dy / L, ny = dx / L;
    let off = desp;
    if (!off) {
      // si la recta pasa sobre otro nodo, se curva hacia el lado libre
      for (const [id, c] of Object.entries(this.pos)) {
        if (id === a.origen || id === a.destino) continue;
        const t = Math.max(0, Math.min(1, ((c.x - P.x) * (Q.x - P.x) + (c.y - P.y) * (Q.y - P.y)) / (L * L)));
        const px = P.x + t * (Q.x - P.x), py = P.y + t * (Q.y - P.y);
        if (Math.hypot(px - c.x, py - c.y) < R * 1.7) {
          const lado = ((c.x - ca.x) * nx + (c.y - ca.y) * ny) > 0 ? -1 : 1;
          off = lado * Math.max(46, R * 3);
          break;
        }
      }
    }
    const mx = (P.x + Q.x) / 2, my = (P.y + Q.y) / 2;
    if (!off) {
      const ux = (Q.x - P.x) / L, uy = (Q.y - P.y) / L;
      const s = { x: P.x + ux * R, y: P.y + uy * R }, e = { x: Q.x - ux * (R + 1), y: Q.y - uy * (R + 1) };
      return { d: `M${s.x},${s.y} L${e.x},${e.y}`, lx: (s.x + e.x) / 2, ly: (s.y + e.y) / 2 };
    }
    const C = { x: mx + nx * off * 2, y: my + ny * off * 2 };
    const u1 = Math.hypot(C.x - P.x, C.y - P.y) || 1, u2 = Math.hypot(C.x - Q.x, C.y - Q.y) || 1;
    const s = { x: P.x + (C.x - P.x) / u1 * R, y: P.y + (C.y - P.y) / u1 * R };
    const e = { x: Q.x + (C.x - Q.x) / u2 * (R + 1), y: Q.y + (C.y - Q.y) / u2 * (R + 1) };
    return { d: `M${s.x},${s.y} Q${C.x},${C.y} ${e.x},${e.y}`, lx: .25 * s.x + .5 * C.x + .25 * e.x, ly: .25 * s.y + .5 * C.y + .25 * e.y };
  }

  /* ---------------------------------------------------------- render */
  _render() {
    const d = this.datos;
    this.capaAristas.innerHTML = "";
    this.capaNodos.innerHTML = "";
    const desp = this._desplazamientos();
    const orden = [...d.aristas].sort((a, b) => (a.clase ? 1 : 0) - (b.clase ? 1 : 0));
    const etiquetas = [];
    for (const a of orden) {
      const est = ESTILO_ARISTA[a.clase] || ESTILO_ARISTA[""];
      const geo = this._geometria(a, desp[a.id]);
      const g = el("g", { class: "arista" }, this.capaAristas);
      el("path", { d: geo.d, class: "golpe" }, g);
      el("path", { d: geo.d, class: "trazo", stroke: est.c, "stroke-width": est.w, "stroke-dasharray": est.dash,
        "marker-end": d.dirigido ? `url(#fl-${a.clase || "base"}-${this.id})` : null,
        opacity: a.clase || !this._hayResaltado() ? 1 : .55 }, g);
      g.addEventListener("mousemove", ev => this._tooltipArista(ev, a));
      g.addEventListener("mouseleave", () => ocultarTooltip());
      if (this.mostrarEtiquetas && a.etiqueta && d.nodos.length <= 70) etiquetas.push([geo, a, est]);
    }
    for (const [geo, a, est] of etiquetas) {
      const fondo = el("rect", { fill: "#fff", opacity: .92, rx: 4 }, this.capaAristas);
      const t = el("text", { x: geo.lx, y: geo.ly + 4, "text-anchor": "middle", "font-size": a.clase ? 12 : 11,
        "font-weight": a.clase ? 700 : 500, fill: a.clase ? est.c : "#5A6578" }, this.capaAristas);
      t.textContent = a.etiqueta;
      try {
        const b = t.getBBox();
        fondo.setAttribute("x", b.x - 3); fondo.setAttribute("y", b.y - 1);
        fondo.setAttribute("width", b.width + 6); fondo.setAttribute("height", b.height + 2);
      } catch { fondo.remove(); }
    }
    const R = this.R;
    for (const n of d.nodos) {
      const p = this.pos[n.id];
      const [relleno, borde] = COLOR_TIPO[n.tipo] || COLOR_TIPO.generico;
      const g = el("g", { class: "nodo", transform: `translate(${p.x},${p.y})`, "data-id": n.id }, this.capaNodos);
      if (n.clase && ANILLO_NODO[n.clase]) {
        if (n.clase === "alerta") el("circle", { r: R + 6, fill: "#C0392B", opacity: .18, filter: `url(#brillo-${this.id})` }, g);
        el("circle", { r: R + 5, fill: "none", stroke: ANILLO_NODO[n.clase], "stroke-width": 2.5,
          "stroke-dasharray": n.clase === "destino" ? "4 3" : null }, g);
      }
      el("circle", { r: R, class: "cuerpo", fill: relleno, stroke: borde, "stroke-width": 2.2,
        style: "cursor: move" }, g);
      if (R >= 14) {
        const t = el("text", { "text-anchor": "middle", y: 4, "font-size": R >= 20 ? 11 : 9.5, "font-weight": 700, fill: borde }, g);
        t.textContent = abreviar(n);
      }
      {
        const t = el("text", { "text-anchor": "middle", y: R + (R >= 14 ? 15 : 12), "font-size": R >= 20 ? 12 : R >= 14 ? 10.5 : 9, "font-weight": 600,
          fill: "#1B2433", "paint-order": "stroke", stroke: "#fff", "stroke-width": 4, "stroke-linejoin": "round" }, g);
        t.textContent = n.nombre;
      }
      if (n.insignia) {
        const txt = String(n.insignia), w = Math.max(20, txt.length * 6.6 + 10);
        const col = n.clase === "alerta" ? "#C0392B" : n.clase === "ok" ? "#1F8A5B" : "#2F5D8C";
        el("rect", { x: R * .5, y: -R - 12, width: w, height: 18, rx: 9, fill: col }, g);
        const t = el("text", { x: R * .5 + w / 2, y: -R + 1, "text-anchor": "middle", "font-size": 10.5, "font-weight": 700, fill: "#fff" }, g);
        t.textContent = txt;
      }
      g.addEventListener("mousedown", ev => { ev.stopPropagation(); this.arrastre = { id: n.id }; ocultarTooltip(); });
      g.addEventListener("mousemove", ev => { if (!this.arrastre) this._tooltipNodo(ev, n); });
      g.addEventListener("mouseleave", () => ocultarTooltip());
    }
    this.g.setAttribute("transform", `translate(${this.t.x},${this.t.y}) scale(${this.t.k})`);
  }

  _hayResaltado() { return this.datos.aristas.some(a => a.clase); }

  _leyenda() {
    const tipos = [...new Set(this.datos.nodos.map(n => n.tipo))];
    const items = [];
    for (const [clase, texto] of this.datos.leyenda || []) {
      const est = ESTILO_ARISTA[clase];
      if (est) items.push(`<span class="item"><span class="linea ${est.dash ? "discontinua" : ""}" style="border-color:${est.c}"></span>${texto}</span>`);
      else if (ANILLO_NODO[clase]) items.push(`<span class="item"><svg width="16" height="16"><circle cx="8" cy="8" r="6" fill="none" stroke="${ANILLO_NODO[clase]}" stroke-width="2.5"/></svg>${texto}</span>`);
    }
    const nodos = tipos.map(t => {
      const [f, b] = COLOR_TIPO[t] || COLOR_TIPO.generico;
      return `<span class="item"><svg width="14" height="14"><circle cx="7" cy="7" r="6" fill="${f}" stroke="${b}" stroke-width="2"/></svg>${NOMBRE_TIPO[t] || t}</span>`;
    });
    this.leyenda.innerHTML = (items.length ? `<div class="tipos">${items.join("")}</div>` : "") + `<div class="tipos">${nodos.join("")}</div>`;
  }

  /* ---------------------------------------------------------- interacción */
  _punto(ev) {
    const r = this.svg.getBoundingClientRect();
    const vb = this.svg.viewBox.baseVal;
    const escala = Math.min(r.width / vb.width, r.height / vb.height);
    const offx = (r.width - vb.width * escala) / 2, offy = (r.height - vb.height * escala) / 2;
    return { x: (ev.clientX - r.left - offx) / escala, y: (ev.clientY - r.top - offy) / escala };
  }

  _eventos() {
    this.svg.addEventListener("wheel", ev => {
      ev.preventDefault();
      const p = this._punto(ev), f = Math.exp(-ev.deltaY * 0.0015);
      const k = Math.min(6, Math.max(.25, this.t.k * f));
      this.t.x = p.x - (p.x - this.t.x) * (k / this.t.k);
      this.t.y = p.y - (p.y - this.t.y) * (k / this.t.k);
      this.t.k = k;
      this.g.setAttribute("transform", `translate(${this.t.x},${this.t.y}) scale(${this.t.k})`);
    }, { passive: false });
    this.svg.addEventListener("mousedown", ev => {
      this.paneo = { x: ev.clientX, y: ev.clientY, tx: this.t.x, ty: this.t.y };
      this.svg.classList.add("arrastrando");
    });
    window.addEventListener("mousemove", ev => {
      if (this.arrastre) {
        const p = this._punto(ev);
        this.pos[this.arrastre.id] = { x: (p.x - this.t.x) / this.t.k, y: (p.y - this.t.y) / this.t.k };
        this._render();
      } else if (this.paneo) {
        const r = this.svg.getBoundingClientRect(), vb = this.svg.viewBox.baseVal;
        const escala = Math.min(r.width / vb.width, r.height / vb.height);
        this.t.x = this.paneo.tx + (ev.clientX - this.paneo.x) / escala;
        this.t.y = this.paneo.ty + (ev.clientY - this.paneo.y) / escala;
        this.g.setAttribute("transform", `translate(${this.t.x},${this.t.y}) scale(${this.t.k})`);
      }
    });
    window.addEventListener("mouseup", () => {
      this.arrastre = null; this.paneo = null; this.svg.classList.remove("arrastrando");
    });
  }

  zoom(f) {
    const vb = this.svg.viewBox.baseVal, c = { x: vb.width / 2, y: vb.height / 2 };
    const k = Math.min(6, Math.max(.25, this.t.k * f));
    this.t.x = c.x - (c.x - this.t.x) * (k / this.t.k);
    this.t.y = c.y - (c.y - this.t.y) * (k / this.t.k);
    this.t.k = k;
    this.g.setAttribute("transform", `translate(${this.t.x},${this.t.y}) scale(${this.t.k})`);
  }
  ajustar() { this.t = { x: 0, y: 0, k: 1 }; this.g.setAttribute("transform", ""); }
  alternarEtiquetas() { this.mostrarEtiquetas = !this.mostrarEtiquetas; this._render(); }

  descargarSVG(nombre = "red.svg") {
    const copia = this.svg.cloneNode(true);
    copia.setAttribute("xmlns", SVGNS);
    copia.insertBefore(el("rect", { width: "100%", height: "100%", fill: "#ffffff" }), copia.firstChild.nextSibling);
    copia.setAttribute("style", "font-family: Segoe UI, Arial, sans-serif");
    descargar(nombre, new XMLSerializer().serializeToString(copia), "image/svg+xml");
  }

  /* ---------------------------------------------------------- tooltips */
  _tooltipNodo(ev, n) {
    const filas = Object.entries(n.atributos || {}).filter(([k]) => !["nombre"].includes(k))
      .map(([k, v]) => `<div class="fila-t"><span>${k}</span><span>${typeof v === "number" ? fmtNum(v) : v}</span></div>`).join("");
    mostrarTooltip(ev, `<b>${n.nombre}</b><div style="color:#93A4BC;margin-bottom:4px">${NOMBRE_TIPO[n.tipo] || n.tipo} · id ${n.id}</div>${filas}`);
  }
  _tooltipArista(ev, a) {
    const nom = id => (this.nodoPorId[id] || {}).nombre || id;
    const filas = Object.entries(a.atributos || {})
      .map(([k, v]) => `<div class="fila-t"><span>${k}</span><span>${typeof v === "number" ? fmtNum(v) : v}</span></div>`).join("");
    mostrarTooltip(ev, `<b>${nom(a.origen)} → ${nom(a.destino)}</b>${a.etiqueta ? `<div style="color:#93A4BC;margin:2px 0 4px">${a.etiqueta}</div>` : ""}${filas}`);
  }
}
VisorGrafo.cuenta = 0;

function abreviar(n) {
  const m = /\(([^)]+)\)\s*$/.exec(n.nombre || "");
  if (m && m[1].length <= 4) return m[1];
  if (n.id.length <= 5) return n.id;
  return n.id.slice(0, 3);
}

function mostrarTooltip(ev, html) {
  const t = document.getElementById("tooltip");
  t.innerHTML = html;
  t.style.display = "block";
  const w = t.offsetWidth, h = t.offsetHeight;
  let x = ev.clientX + 16, y = ev.clientY + 16;
  if (x + w > window.innerWidth - 10) x = ev.clientX - w - 16;
  if (y + h > window.innerHeight - 10) y = ev.clientY - h - 16;
  t.style.left = x + "px";
  t.style.top = y + "px";
}
function ocultarTooltip() { document.getElementById("tooltip").style.display = "none"; }

function descargar(nombre, contenido, tipo = "text/plain;charset=utf-8") {
  const blob = new Blob([contenido], { type: tipo });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = nombre;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
}

/* ============================================================ gráfico de líneas */
const PALETA = ["#2F5D8C", "#D9822B", "#1F8A5B", "#C0392B", "#7651C2", "#0E8FA3"];

function graficoLineas(contenedor, series, op = {}) {
  const W = 560, H = 300, m = { l: 62, r: 16, t: 34, b: 44 };
  const pts = series.flatMap(s => s.puntos);
  if (!pts.length) { contenedor.innerHTML = `<div class="vacio">Sin datos</div>`; return; }
  const xs = [...new Set(pts.map(p => p.x))].sort((a, b) => a - b);
  const ys = pts.map(p => Math.max(p.y, 1e-4));
  const log = op.logY !== false;
  let y0 = Math.min(...ys), y1 = Math.max(...ys);
  if (log) { y0 = Math.pow(10, Math.floor(Math.log10(y0))); y1 = Math.pow(10, Math.ceil(Math.log10(y1))); if (y0 === y1) y1 *= 10; }
  else { y0 = 0; y1 = y1 * 1.1 || 1; }
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  const fx = x => m.l + (x1 === x0 ? .5 : (x - x0) / (x1 - x0)) * (W - m.l - m.r);
  const fy = y => log ? H - m.b - (Math.log10(Math.max(y, 1e-4)) - Math.log10(y0)) / (Math.log10(y1) - Math.log10(y0)) * (H - m.t - m.b)
                      : H - m.b - (y - y0) / (y1 - y0) * (H - m.t - m.b);
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}` });
  const ticks = [];
  if (log) for (let v = y0; v <= y1 * 1.0001; v *= 10) ticks.push(v);
  else for (let i = 0; i <= 4; i++) ticks.push(y0 + (y1 - y0) * i / 4);
  for (const v of ticks) {
    el("line", { x1: m.l, x2: W - m.r, y1: fy(v), y2: fy(v), stroke: "#E6EAF0" }, svg);
    const t = el("text", { x: m.l - 8, y: fy(v) + 4, "text-anchor": "end", "font-size": 11, fill: "#6B7688" }, svg);
    t.textContent = v >= 1000 ? `${v / 1000}k` : v < 0.01 ? v.toExponential(0) : fmtNum(v, 3);
  }
  for (const x of xs) {
    const t = el("text", { x: fx(x), y: H - m.b + 18, "text-anchor": "middle", "font-size": 11, fill: "#6B7688" }, svg);
    t.textContent = x;
  }
  el("line", { x1: m.l, x2: W - m.r, y1: H - m.b, y2: H - m.b, stroke: "#A9B4C4" }, svg);
  const tx = el("text", { x: (m.l + W - m.r) / 2, y: H - 6, "text-anchor": "middle", "font-size": 11.5, fill: "#4A5568" }, svg);
  tx.textContent = op.xEtiqueta || "";
  const ty = el("text", { x: 14, y: (m.t + H - m.b) / 2, "text-anchor": "middle", "font-size": 11.5, fill: "#4A5568",
    transform: `rotate(-90 14 ${(m.t + H - m.b) / 2})` }, svg);
  ty.textContent = op.yEtiqueta || "";
  let lx = m.l + 4;
  series.forEach((s, i) => {
    const c = s.color || PALETA[i % PALETA.length];
    const d = s.puntos.map((p, j) => `${j ? "L" : "M"}${fx(p.x)},${fy(p.y)}`).join(" ");
    el("path", { d, fill: "none", stroke: c, "stroke-width": 2.4 }, svg);
    for (const p of s.puntos) {
      const cc = el("circle", { cx: fx(p.x), cy: fy(p.y), r: 3.8, fill: "#fff", stroke: c, "stroke-width": 2 }, svg);
      cc.addEventListener("mousemove", ev => mostrarTooltip(ev, `<b>${s.nombre}</b><div class="fila-t"><span>V</span><span>${p.x}</span></div><div class="fila-t"><span>tiempo</span><span>${fmtNum(p.y, 3)} ms</span></div>`));
      cc.addEventListener("mouseleave", ocultarTooltip);
    }
    el("rect", { x: lx, y: 10, width: 12, height: 4, rx: 2, fill: c }, svg);
    const t = el("text", { x: lx + 17, y: 16, "font-size": 11.5, fill: "#1B2433", "font-weight": 600 }, svg);
    t.textContent = s.nombre;
    lx += 26 + s.nombre.length * 6.6;
  });
  contenedor.innerHTML = "";
  contenedor.appendChild(svg);
}
