"""
gestion_red.py - Módulo 1: gestión y modelamiento de redes financieras.

Crea, carga (CSV, TXT, JSON), modifica, valida, guarda y visualiza la red común
que usan los demás módulos.
"""

import csv
import json
import math
import os

from .graph import Grafo, ErrorGrafo
from .utils import convertir_valor, tabla, CARPETA_REPORTES

COLORES_TIPO = {
    "cuenta": "#DCE8F5", "cliente": "#ECEEF1", "billetera": "#E8DFF5", "banco": "#DCE8F5",
    "compensacion": "#FCEBD2", "comercio": "#DDF0E3", "boveda_central": "#F8DDDA",
    "boveda_regional": "#FCEBD2", "agencia": "#DDF0E3", "atm": "#F8DDDA",
    "superfuente": "#ECEEF1", "supersumidero": "#ECEEF1", "generico": "#ECEEF1",
}
BORDES_TIPO = {
    "cuenta": "#2F5D8C", "cliente": "#6B7280", "billetera": "#7E57C2", "banco": "#2F5D8C",
    "compensacion": "#E08E1B", "comercio": "#2E8B57", "boveda_central": "#C0392B",
    "boveda_regional": "#E08E1B", "agencia": "#2E8B57", "atm": "#C0392B", "generico": "#6B7280",
}


# ------------------------------------------------------------------- carga
def cargar_csv(ruta_aristas, ruta_nodos=None, dirigido=True, multiarista=False,
               tipo_por_defecto="generico", nombre=None):
    """Carga una red desde CSV.

    Archivo de aristas: columnas obligatorias `origen,destino`; el resto son
    atributos (comision, tiempo, capacidad, monto, fecha...).
    Archivo de nodos (opcional): columnas `id,tipo,...`. Si se entrega, las
    aristas que apunten a nodos inexistentes se rechazan y se reportan.

    Devuelve (grafo, errores) donde errores es una lista de textos.
    """
    g = Grafo(dirigido=dirigido, ponderado=True, multiarista=multiarista,
              nombre=nombre or os.path.splitext(os.path.basename(ruta_aristas))[0])
    errores = []
    if ruta_nodos:
        with open(ruta_nodos, newline="", encoding="utf-8") as f:
            for i, fila in enumerate(csv.DictReader(f), start=2):
                try:
                    nid = fila.pop("id").strip()
                    tipo = (fila.pop("tipo", "") or tipo_por_defecto).strip()
                    at = {k: convertir_valor(v, k) for k, v in fila.items() if k}
                    g.agregar_nodo(nid, tipo, **{k: v for k, v in at.items() if v is not None})
                except (ErrorGrafo, KeyError, AttributeError) as e:
                    errores.append(f"{os.path.basename(ruta_nodos)} línea {i}: {e}")
    with open(ruta_aristas, newline="", encoding="utf-8") as f:
        lector = csv.DictReader(f)
        if not lector.fieldnames or "origen" not in lector.fieldnames or "destino" not in lector.fieldnames:
            raise ErrorGrafo("El CSV de aristas debe tener las columnas 'origen' y 'destino'.")
        for i, fila in enumerate(lector, start=2):
            u, v = (fila.pop("origen") or "").strip(), (fila.pop("destino") or "").strip()
            at = {k: convertir_valor(val, k) for k, val in fila.items() if k}
            at = {k: val for k, val in at.items() if val is not None}
            try:
                if not ruta_nodos:
                    g.asegurar_nodo(u, tipo_por_defecto)
                    g.asegurar_nodo(v, tipo_por_defecto)
                g.agregar_arista(u, v, **at)
            except ErrorGrafo as e:
                errores.append(f"{os.path.basename(ruta_aristas)} línea {i}: {e}")
    return g, errores


def cargar_json(ruta):
    """Formato: {"dirigido": true, "multiarista": false, "nodos": [{"id":..., "tipo":...}],
    "aristas": [{"origen":..., "destino":..., ...}]}"""
    with open(ruta, encoding="utf-8") as f:
        d = json.load(f)
    g = Grafo(dirigido=d.get("dirigido", True), ponderado=d.get("ponderado", True),
              multiarista=d.get("multiarista", False),
              nombre=d.get("nombre", os.path.splitext(os.path.basename(ruta))[0]))
    errores = []
    for n in d.get("nodos", []):
        n = dict(n)
        try:
            g.agregar_nodo(n.pop("id"), n.pop("tipo", "generico"), **n)
        except (ErrorGrafo, KeyError) as e:
            errores.append(f"nodo {n}: {e}")
    for a in d.get("aristas", []):
        a = dict(a)
        try:
            g.agregar_arista(a.pop("origen"), a.pop("destino"), **a)
        except (ErrorGrafo, KeyError) as e:
            errores.append(f"arista {a}: {e}")
    return g, errores


def cargar_txt(ruta, atributo="peso", dirigido=True):
    """Formato: una arista por línea `origen destino [peso]`. Líneas con # son comentarios.
    Una línea `# dirigido: no` convierte la red en no dirigida."""
    aristas, errores = [], []
    ponderado = False
    with open(ruta, encoding="utf-8") as f:
        for i, linea in enumerate(f, start=1):
            linea = linea.strip()
            if linea.lower().startswith("# dirigido:"):
                dirigido = linea.split(":", 1)[1].strip().lower() in ("si", "sí", "true", "1")
                continue
            if not linea or linea.startswith("#"):
                continue
            partes = linea.split()
            if len(partes) not in (2, 3):
                errores.append(f"línea {i}: se esperaban 2 o 3 columnas")
                continue
            peso = convertir_valor(partes[2]) if len(partes) == 3 else None
            if peso is not None:
                ponderado = True
            aristas.append((i, partes[0], partes[1], peso))
    g = Grafo(dirigido=dirigido, ponderado=ponderado, nombre=os.path.splitext(os.path.basename(ruta))[0])
    for i, u, v, p in aristas:
        try:
            g.asegurar_nodo(u)
            g.asegurar_nodo(v)
            g.agregar_arista(u, v, **({atributo: p} if p is not None else {}))
        except ErrorGrafo as e:
            errores.append(f"línea {i}: {e}")
    return g, errores


def cargar(ruta, **opciones):
    """Elige el cargador según la extensión del archivo."""
    ext = os.path.splitext(ruta)[1].lower()
    if ext == ".json":
        return cargar_json(ruta)
    if ext == ".txt":
        return cargar_txt(ruta, dirigido=opciones.get("dirigido", True))
    if ext == ".csv":
        nodos = opciones.get("ruta_nodos")
        if nodos is None:
            candidato = ruta[:-4] + "_nodos.csv"
            nodos = candidato if os.path.exists(candidato) else None
        return cargar_csv(ruta, nodos, dirigido=opciones.get("dirigido", True),
                          multiarista=opciones.get("multiarista", False),
                          tipo_por_defecto=opciones.get("tipo_por_defecto", "generico"))
    raise ErrorGrafo(f"Formato no soportado: {ext}. Use CSV, TXT o JSON.")


def guardar_json(grafo, ruta):
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(grafo.a_dict(), f, ensure_ascii=False, indent=2)
    return ruta


def guardar_csv(grafo, ruta_aristas):
    claves = sorted({k for _, _, a in grafo.aristas() for k in a})
    with open(ruta_aristas, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["origen", "destino"] + claves)
        for u, v, a in grafo.aristas():
            w.writerow([u, v] + [a.get(k, "") for k in claves])
    ruta_nodos = ruta_aristas[:-4] + "_nodos.csv"
    claves_n = sorted({k for at in grafo.nodos.values() for k in at if k != "tipo"})
    with open(ruta_nodos, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "tipo"] + claves_n)
        for n, at in grafo.nodos.items():
            w.writerow([n, at.get("tipo", "")] + [at.get(k, "") for k in claves_n])
    return ruta_aristas, ruta_nodos


# ----------------------------------------------------------------- reportes
def texto_resumen(grafo):
    r = grafo.resumen()
    lineas = [f"Red: {r['nombre']}",
              f"Tipo: {'dirigida' if r['dirigido'] else 'no dirigida'}, "
              f"{'ponderada' if r['ponderado'] else 'no ponderada'}"
              f"{', con aristas múltiples' if r['multiarista'] else ''}",
              f"Nodos: {r['nodos']}   Aristas: {r['aristas']}",
              "Nodos por tipo: " + ", ".join(f"{t}={c}" for t, c in sorted(r["tipos"].items()))]
    return "\n".join(lineas)


def texto_aristas(grafo, limite=60):
    claves = []
    for _, _, a in grafo.aristas():
        for k in a:
            if k not in claves:
                claves.append(k)
    filas = []
    for i, (u, v, a) in enumerate(grafo.aristas()):
        if i >= limite:
            filas.append(["..."] * (2 + len(claves)))
            break
        filas.append([u, "->" if grafo.dirigido else "--", v] + [a.get(k, "") for k in claves])
    return tabla(["origen", "", "destino"] + claves, filas)


def texto_nodos(grafo, limite=80):
    claves = sorted({k for at in grafo.nodos.values() for k in at if k not in ("tipo", "x", "y")})
    filas = []
    for i, (n, at) in enumerate(grafo.nodos.items()):
        if i >= limite:
            filas.append(["..."] * (3 + len(claves)))
            break
        filas.append([n, at.get("tipo", ""), grafo.grado_salida(n)] + [at.get(k, "") for k in claves])
    return tabla(["id", "tipo", "grado salida"] + claves, filas)


# ------------------------------------------------------------ visualización
def _posiciones(grafo, nodos):
    if all("x" in grafo.nodos[n] and "y" in grafo.nodos[n] for n in nodos):
        return {n: (grafo.nodos[n]["x"], grafo.nodos[n]["y"]) for n in nodos}
    # Disposición circular agrupando por tipo.
    orden = sorted(nodos, key=lambda n: (grafo.nodos[n].get("tipo", ""), n))
    k = len(orden)
    return {n: (math.cos(2 * math.pi * i / k), math.sin(2 * math.pi * i / k)) for i, n in enumerate(orden)}


def _dist_segmento(c, p, q):
    """Distancia del punto c al segmento pq."""
    px, py = q[0] - p[0], q[1] - p[1]
    largo = px * px + py * py or 1e-12
    t = max(0.0, min(1.0, ((c[0] - p[0]) * px + (c[1] - p[1]) * py) / largo))
    return math.hypot(p[0] + t * px - c[0], p[1] + t * py - c[1])


def posiciones_por_niveles(niveles):
    """Disposición por capas: x = nivel (saltos desde el origen), y repartida."""
    por_nivel = {}
    for n, nivel in sorted(niveles.items(), key=lambda it: (it[1], it[0])):
        por_nivel.setdefault(nivel, []).append(n)
    pos = {}
    for nivel, ns in por_nivel.items():
        for i, n in enumerate(ns):
            pos[n] = (nivel * 2.0, (len(ns) - 1) / 2 - i)
    return pos


def visualizar(grafo, archivo=None, titulo=None, resaltar_aristas=None, resaltar_nodos=None,
               etiqueta=None, nodos=None, mostrar=False, colores_aristas=None, posiciones=None):
    """Dibuja la red con matplotlib y la guarda como PNG.

    resaltar_aristas: conjunto de pares (u, v) que se pintan en rojo.
    colores_aristas: dict (u, v) -> color (tiene prioridad).
    etiqueta: nombre del atributo o función f(u, v, atributos) -> texto.
    """
    import matplotlib
    matplotlib.use("Agg")  # se guarda como PNG; no requiere ventana gráfica
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch

    nodos = list(nodos or grafo.nodos)
    pos = posiciones or _posiciones(grafo, nodos)
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    span = max(max(xs) - min(xs), max(ys) - min(ys), 1e-9)
    radio = 0.045 * span if len(nodos) < 25 else 0.025 * span
    fig_w = 11 if len(nodos) < 25 else 13
    fig, ax = plt.subplots(figsize=(fig_w, fig_w * 0.7))
    resaltar_aristas = set(resaltar_aristas or [])
    resaltar_nodos = set(resaltar_nodos or [])
    colores_aristas = colores_aristas or {}
    conjunto = set(nodos)
    dibujadas = set()
    for u, v, a in grafo.aristas():
        if u not in conjunto or v not in conjunto or u == v:
            continue
        clave = (u, v)
        p, q = pos[u], pos[v]
        dx, dy = q[0] - p[0], q[1] - p[1]
        d = math.hypot(dx, dy) or 1
        ux, uy = dx / d, dy / d
        a1 = (p[0] + ux * radio, p[1] + uy * radio)
        b1 = (q[0] - ux * radio * 1.1, q[1] - uy * radio * 1.1)
        col = colores_aristas.get(clave, "#C0392B" if clave in resaltar_aristas else "#9AA3AF")
        lw = 2.6 if clave in resaltar_aristas or clave in colores_aristas else 1.2
        bidireccional = (v, u) in dibujadas or (grafo.dirigido and any(w == u for w, _ in grafo.adj[v]))
        tapa_nodo = any(_dist_segmento(pos[n], p, q) < radio * 1.3 for n in nodos if n not in (u, v))
        curva = "arc3,rad=0.35" if tapa_nodo else ("arc3,rad=0.15" if bidireccional else "arc3")
        ax.add_patch(FancyArrowPatch(a1, b1, arrowstyle="-|>" if grafo.dirigido else "-",
                                     mutation_scale=12, color=col, lw=lw, connectionstyle=curva, zorder=4))
        dibujadas.add(clave)
        if etiqueta and len(nodos) < 30:
            txt = etiqueta(u, v, a) if callable(etiqueta) else a.get(etiqueta, "")
            if txt not in ("", None):
                mx, my = (a1[0] + b1[0]) / 2, (a1[1] + b1[1]) / 2
                rad = 0.35 if tapa_nodo else (0.15 if bidireccional else 0)
                mx, my = mx + rad * (b1[1] - a1[1]) / 2, my - rad * (b1[0] - a1[0]) / 2
                ax.text(mx, my, str(txt), fontsize=7.5,
                        ha="center", va="center", color=col if col != "#9AA3AF" else "#4B5563",
                        bbox=dict(fc="white", ec="none", pad=0.4), zorder=6)
    for n in nodos:
        tipo = grafo.nodos[n].get("tipo", "generico")
        fc = COLORES_TIPO.get(tipo, "#ECEEF1")
        ec = "#C0392B" if n in resaltar_nodos else BORDES_TIPO.get(tipo, "#6B7280")
        ax.add_patch(plt.Circle(pos[n], radio, fc=fc, ec=ec, lw=2.6 if n in resaltar_nodos else 1.6, zorder=2))
        ax.text(pos[n][0], pos[n][1] - radio * 1.25, grafo.nodos[n].get("nombre", n), ha="center", va="top",
                fontsize=7.5 if len(nodos) < 25 else 5.5, weight="bold", zorder=3,
                bbox=dict(fc="white", ec="none", pad=0.2, alpha=0.8))
    ax.set_aspect("equal")
    ax.set_xlim(min(xs) - 2 * radio, max(xs) + 2 * radio)
    ax.set_ylim(min(ys) - 3 * radio, max(ys) + 2 * radio)
    ax.axis("off")
    ax.set_title(titulo or grafo.nombre, loc="left", color="#2F5D8C", weight="bold")
    os.makedirs(CARPETA_REPORTES, exist_ok=True)
    archivo = archivo or os.path.join(CARPETA_REPORTES, f"red_{grafo.nombre}.png")
    fig.savefig(archivo, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    if mostrar:
        abrir_archivo(archivo)
    return archivo


def abrir_archivo(ruta):
    """Abre un archivo con el visor del sistema operativo (si es posible)."""
    import subprocess
    import sys
    try:
        if sys.platform.startswith("win"):
            os.startfile(ruta)  # noqa
        elif sys.platform == "darwin":
            subprocess.Popen(["open", ruta])
        else:
            subprocess.Popen(["xdg-open", ruta], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
