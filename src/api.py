"""
api.py - Capa de servicios entre la interfaz gráfica y los algoritmos.

Cada método de `Sesion` recibe parámetros simples y devuelve un diccionario
serializable a JSON con:
  - los datos estructurados del resultado (para tarjetas, tablas y gráficos),
  - el grafo a dibujar con lo que hay que resaltar,
  - el texto del reporte (para descargarlo).
La interfaz no ejecuta algoritmos: solo muestra lo que devuelve esta capa.
"""

import math
import os
import random
import subprocess
import sys
import tempfile
import time
from collections import deque

from .graph import ErrorGrafo
from . import gestion_red as gr
from . import analisis_transacciones as at
from . import enrutamiento_financiero as ef
from . import distribucion_liquidez as dl
from . import evaluacion_resultados as ev
from .utils import ruta_dato, CARPETA_DATOS, RAIZ, convertir_valor

REDES_INICIALES = {
    "transacciones": ("transacciones.csv", {"multiarista": True, "tipo_por_defecto": "cuenta"}),
    "enrutamiento": ("red_enrutamiento.csv", {}),
    "cashback": ("red_enrutamiento_cashback.csv", {}),
    "liquidez": ("distribucion_liquidez.csv", {}),
    "liquidez_ampliada": ("liquidez_red_ampliada.csv", {}),
}
NOMBRES_REDES = {
    "transacciones": "Transacciones entre cuentas",
    "enrutamiento": "Red de pagos (Guía 10)",
    "cashback": "Red de pagos con cashback (CyberDays)",
    "liquidez": "Bóvedas y agencias (Figura 5)",
    "liquidez_ampliada": "Bóvedas y agencias (red ampliada)",
    "personal": "Red cargada por el usuario",
}


class ErrorApi(Exception):
    pass


def limpiar(obj):
    """Convierte infinitos y tuplas para que el resultado sea JSON válido."""
    if isinstance(obj, float):
        if math.isinf(obj) or math.isnan(obj):
            return None
        return round(obj, 6)
    if isinstance(obj, dict):
        return {str(k): limpiar(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [limpiar(v) for v in obj]
    return obj


# ---------------------------------------------------------------- layouts
def _componentes(grafo, nodos):
    conjunto = set(nodos)
    vec = {n: set() for n in nodos}
    for u in nodos:
        for v, _ in grafo.adj[u]:
            if v in conjunto and v != u:
                vec[u].add(v)
                vec[v].add(u)
    vistos, comps = set(), []
    for n in nodos:
        if n in vistos:
            continue
        comp, cola = [], deque([n])
        vistos.add(n)
        while cola:
            x = cola.popleft()
            comp.append(x)
            for y in sorted(vec[x]):
                if y not in vistos:
                    vistos.add(y)
                    cola.append(y)
        comps.append(comp)
    return comps, vec


def _fuerzas(nodos, vec, iteraciones, semilla):
    """Fruchterman-Reingold sobre una componente conexa. Devuelve posiciones con
    distancia típica 1 entre vecinos."""
    n = len(nodos)
    if n == 1:
        return {nodos[0]: (0.0, 0.0)}
    rnd = random.Random(semilla)
    r0 = math.sqrt(n)
    pos = {v: [r0 * math.cos(2 * math.pi * i / n) + rnd.uniform(-.2, .2), r0 * math.sin(2 * math.pi * i / n) + rnd.uniform(-.2, .2)]
           for i, v in enumerate(nodos)}
    k = 1.0
    temp = r0
    pares = {tuple(sorted((u, v))) for u in nodos for v in vec[u]}
    for _ in range(iteraciones):
        disp = {v: [0.0, 0.0] for v in nodos}
        for i in range(n):
            a = nodos[i]
            for j in range(i + 1, n):
                b = nodos[j]
                dx, dy = pos[a][0] - pos[b][0], pos[a][1] - pos[b][1]
                d2 = dx * dx + dy * dy or 1e-6
                f = k * k / d2
                disp[a][0] += dx * f
                disp[a][1] += dy * f
                disp[b][0] -= dx * f
                disp[b][1] -= dy * f
        for a, b in pares:
            dx, dy = pos[a][0] - pos[b][0], pos[a][1] - pos[b][1]
            d = math.hypot(dx, dy) or 1e-6
            f = d / k
            disp[a][0] -= dx * f
            disp[a][1] -= dy * f
            disp[b][0] += dx * f
            disp[b][1] += dy * f
        for v in nodos:
            d = math.hypot(*disp[v]) or 1e-6
            paso = min(d, temp)
            pos[v][0] += disp[v][0] / d * paso
            pos[v][1] += disp[v][1] / d * paso
        temp = max(temp * 0.985, 0.01)
    for _ in range(60):  # separa nodos que quedaron demasiado cerca
        movio = False
        for i in range(n):
            a = nodos[i]
            for j in range(i + 1, n):
                b = nodos[j]
                dx, dy = pos[b][0] - pos[a][0], pos[b][1] - pos[a][1]
                d = math.hypot(dx, dy)
                if d < 1.15:
                    if d < 1e-6:
                        dx, dy, d = 1.0, 0.0, 1.0
                    m = (1.15 - d) / 2
                    pos[a][0] -= dx / d * m; pos[a][1] -= dy / d * m
                    pos[b][0] += dx / d * m; pos[b][1] += dy / d * m
                    movio = True
        if not movio:
            break
    return {v: (p[0], p[1]) for v, p in pos.items()}


def layout_fuerzas(grafo, nodos=None, iteraciones=300, semilla=7):
    """Disposición para redes sin coordenadas: fuerzas (Fruchterman-Reingold) dentro
    de cada componente conexa y luego las componentes se acomodan en filas, de
    la más grande a la más pequeña, para que no se superpongan."""
    nodos = list(nodos or grafo.nodos)
    if not nodos:
        return {}
    comps, vec = _componentes(grafo, nodos)
    comps.sort(key=lambda c: (-len(c), c[0]))
    bloques = []
    for i, c in enumerate(comps):
        p = _fuerzas(c, vec, iteraciones if len(c) > 2 else 1, semilla + i)
        xs, ys = [q[0] for q in p.values()], [q[1] for q in p.values()]
        bloques.append((p, min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)))
    ancho_fila = max(max(b[3] for b in bloques), math.sqrt(sum((b[3] + 1.6) * (b[4] + 1.6) for b in bloques) * 2.4))
    pos, x, y, alto_fila = {}, 0.0, 0.0, 0.0
    for p, mx, my, w, h in bloques:
        if x > 0 and x + w > ancho_fila:
            x, y, alto_fila = 0.0, y + alto_fila + 1.6, 0.0
        for v, (px, py) in p.items():
            pos[v] = (x + px - mx, -(y + py - my))
        x += w + 1.6
        alto_fila = max(alto_fila, h)
    return pos


def niveles_dirigidos(grafo, centro, radio, permitidos):
    """Columna de cada nodo: a la derecha quienes reciben dinero del centro, a la
    izquierda quienes le envían."""
    niveles = {centro: 0}
    pred = grafo.predecesores()
    for signo, vec in ((1, {u: [v for v, _ in grafo.adj[u]] for u in grafo.adj}),
                       (-1, {u: [v for v, _ in lst] for u, lst in pred.items()})):
        cola, vistos = deque([(centro, 0)]), {centro}
        while cola:
            u, d = cola.popleft()
            if d >= radio:
                continue
            for v in vec[u]:
                if v in permitidos and v not in vistos:
                    vistos.add(v)
                    niveles.setdefault(v, signo * (d + 1))
                    cola.append((v, d + 1))
    pendientes = set(permitidos) - set(niveles)
    for _ in range(len(pendientes) + 1):
        if not pendientes:
            break
        for nd in sorted(pendientes):
            vecino = next((v for v, _ in grafo.adj[nd] if v in niveles), None)
            if vecino is not None:
                niveles[nd] = niveles[vecino] - 1
            else:
                origen = next((u for u, _ in pred[nd] if u in niveles), None)
                if origen is not None:
                    niveles[nd] = niveles[origen] + 1
        pendientes -= set(niveles)
    for nd in pendientes:
        niveles[nd] = radio + 1
    return gr.posiciones_por_niveles(niveles)


def posiciones(grafo, nodos=None):
    """Usa las coordenadas x, y de los nodos si existen. Los nodos agregados sin
    coordenadas se ubican junto a sus vecinos; si la mayoría no tiene, se usa la
    disposición por fuerzas."""
    nodos = list(nodos or grafo.nodos)
    con = [v for v in nodos if "x" in grafo.nodos[v] and "y" in grafo.nodos[v]]
    if not con or len(con) < len(nodos) / 2:
        return layout_fuerzas(grafo, nodos)
    pos = {v: (grafo.nodos[v]["x"], grafo.nodos[v]["y"]) for v in con}
    xs, ys = [p[0] for p in pos.values()], [p[1] for p in pos.values()]
    paso = max(max(xs) - min(xs), max(ys) - min(ys), 1) / 8
    pred = grafo.predecesores()
    for i, v in enumerate(n for n in nodos if n not in pos):
        vecinos = [w for w, _ in grafo.adj[v] if w in pos] + [u for u, _ in pred[v] if u in pos]
        if vecinos:
            cx = sum(pos[w][0] for w in vecinos) / len(vecinos)
            cy = sum(pos[w][1] for w in vecinos) / len(vecinos)
            pos[v] = (cx + paso * 0.9, cy - paso * 0.9)
        else:
            pos[v] = (max(xs) + paso * (1 + i % 3), min(ys) - paso * (i // 3))
    return pos


def grafo_json(grafo, nodos=None, pos=None, etiqueta=None, clases_aristas=None, clases_nodos=None,
               insignias=None, titulo=None, leyenda=None):
    """Serializa un grafo para el visor SVG de la interfaz.

    clases_aristas: {(u, v): clase}  (ruta, excluida, ciclo, corte, saturada, flujo, arbol, abanico, ...)
    clases_nodos:   {nodo: clase}    (origen, destino, alerta, marcado, ...)
    insignias:      {nodo: texto}    (texto pequeño sobre el nodo)
    """
    nodos = list(nodos or grafo.nodos)
    conjunto = set(nodos)
    pos = pos or posiciones(grafo, nodos)
    clases_aristas = clases_aristas or {}
    clases_nodos = clases_nodos or {}
    insignias = insignias or {}
    lista_n = []
    for v in nodos:
        at_ = grafo.nodos[v]
        x, y = pos.get(v, (0, 0))
        lista_n.append({
            "id": v, "tipo": at_.get("tipo", "generico"), "nombre": at_.get("nombre", v),
            "x": x, "y": -y,  # en SVG el eje y crece hacia abajo
            "atributos": {k: val for k, val in at_.items() if k not in ("x", "y")},
            "clase": clases_nodos.get(v, ""), "insignia": insignias.get(v, ""),
        })
    lista_a = []
    for i, (u, v, a) in enumerate(grafo.aristas()):
        if u not in conjunto or v not in conjunto:
            continue
        txt = etiqueta(u, v, a) if callable(etiqueta) else (a.get(etiqueta, "") if etiqueta else "")
        lista_a.append({"id": i, "origen": u, "destino": v, "atributos": a,
                        "etiqueta": "" if txt is None else str(txt),
                        "clase": clases_aristas.get((u, v), "")})
    return limpiar({"dirigido": grafo.dirigido, "nodos": lista_n, "aristas": lista_a,
                    "titulo": titulo or grafo.nombre, "leyenda": leyenda or []})


def _fmt(x):
    if x is None:
        return "-"
    if isinstance(x, float):
        if math.isinf(x):
            return "∞"
        if not x.is_integer():
            return f"{x:,.2f}"
    return f"{int(x):,}"


def _dia(f):
    """'2026-10-04' -> '04/10'."""
    f = str(f or "")
    return f"{f[8:10]}/{f[5:7]}" if len(f) >= 10 else f


def _medir(func, *args):
    t0 = time.perf_counter()
    r = func(*args)
    return r, (time.perf_counter() - t0) * 1000


# ================================================================ sesión
class Sesion:
    def __init__(self):
        self.redes = {}
        self.archivos = {}
        self.alertas_ruleteo = []
        for clave, (archivo, op) in REDES_INICIALES.items():
            g, _ = gr.cargar(ruta_dato(archivo), **op)
            self.redes[clave] = g
            self.archivos[clave] = archivo
        self._pos_cache = {}

    def red(self, clave):
        if clave not in self.redes:
            raise ErrorApi(f"No hay una red cargada con la clave '{clave}'.")
        return self.redes[clave]

    def _pos(self, clave):
        g = self.red(clave)
        firma = (clave, g.num_nodos(), g.num_aristas(), tuple(sorted(g.nodos)))
        if firma not in self._pos_cache:
            self._pos_cache[firma] = posiciones(g)
        return dict(self._pos_cache[firma])

    # ------------------------------------------------------------ general
    def estado(self):
        archivos = sorted(f for f in os.listdir(CARPETA_DATOS)
                          if f.endswith((".csv", ".json", ".txt")) and not f.endswith("_nodos.csv"))
        return {
            "redes": [{**g.resumen(), "clave": k, "nombre": NOMBRES_REDES.get(k, k),
                       "archivo": self.archivos.get(k, "")} for k, g in self.redes.items()],
            "archivos": archivos,
            "alertas_ruleteo": self.alertas_ruleteo,
        }

    def inicio(self):
        """Indicadores del tablero de inicio."""
        gt = self.redes["transacciones"]
        grupos = at.grupos_circulacion(at.tarjan_scc(gt), gt)
        abanicos = at.detectar_abanicos(gt)
        top = at.top_k(at.puntajes(gt), 5)
        ruta = ef.analizar_ruta(self.redes["enrutamiento"], "A", "X", "friccion", 100)
        adj_c, _ = ef.red_ponderada(self.redes["cashback"], "friccion", 100)
        ciclos, _ = ef.ciclos_negativos(adj_c)
        liq = dl.distribuir(self.redes["liquidez"])
        return limpiar({
            "redes": self.estado()["redes"],
            "fraude": {"grupos": len(grupos), "cuentas_en_ciclo": sum(len(g) for g in grupos),
                       "abanicos": len(abanicos),
                       "top": [{"cuenta": c, "puntaje": p, "motivos": m} for c, (p, m) in top]},
            "rutas": {"mejor": ruta["mejor"][0], "ruta": ruta["mejor"][1],
                      "menos_saltos": ruta["menos_saltos"][0], "ruta_saltos": ruta["menos_saltos"][1],
                      "ciclos_cashback": [" → ".join(c["ciclo"]) for c in ciclos],
                      "costo_ciclo": ciclos[0]["costo"] if ciclos else None},
            "liquidez": {"flujo": liq["flujo"], "demanda": liq["demanda"], "oferta": liq["oferta"],
                         "corte": liq["capacidad_corte"],
                         "pendientes": [a for a in liq["agencias"] if a["falta"] > 0]},
        })

    # ======================================================== MÓDULO 1
    def red_completa(self, clave):
        g = self.red(clave)
        etiqueta = {"transacciones": "monto", "liquidez": "capacidad", "liquidez_ampliada": "capacidad"}.get(clave)
        if clave in ("enrutamiento", "cashback"):
            etiqueta = lambda u, v, a: _fmt(ef.friccion(a))  # noqa: E731
        nodos = [{"id": n, "tipo": a.get("tipo", ""), "atributos": {k: v for k, v in a.items() if k not in ("tipo",)},
                  "grado_salida": g.grado_salida(n)} for n, a in g.nodos.items()]
        aristas = []
        cont = {}
        for u, v, a in g.aristas():
            idx = cont.get((u, v), 0)
            cont[(u, v)] = idx + 1
            aristas.append({"origen": u, "destino": v, "indice": idx, "atributos": a})
        return limpiar({
            "clave": clave, "nombre": NOMBRES_REDES.get(clave, clave), "resumen": g.resumen(),
            "validacion": g.validar(), "nodos": nodos, "aristas": aristas,
            "grafo": grafo_json(g, pos=self._pos(clave), etiqueta=etiqueta),
            "reporte": gr.texto_resumen(g) + "\n\n" + gr.texto_nodos(g, 10 ** 6) + "\n\n" + gr.texto_aristas(g, 10 ** 6),
        })

    def cargar_archivo(self, clave, archivo, dirigido=True, multiarista=False):
        ruta = os.path.join(CARPETA_DATOS, os.path.basename(archivo))
        if not os.path.exists(ruta):
            raise ErrorApi(f"No existe el archivo {archivo}.")
        g, errores = gr.cargar(ruta, dirigido=dirigido, multiarista=multiarista)
        self.redes[clave] = g
        self.archivos[clave] = os.path.basename(archivo)
        return {"errores": errores, "red": self.red_completa(clave)}

    def subir_archivo(self, clave, nombre, contenido, contenido_nodos=None, dirigido=True, multiarista=False):
        carpeta = tempfile.mkdtemp(prefix="optifin_")
        nombre = os.path.basename(nombre) or "red.csv"
        ruta = os.path.join(carpeta, nombre)
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(contenido)
        ruta_nodos = None
        if contenido_nodos:
            ruta_nodos = ruta[:-4] + "_nodos.csv"
            with open(ruta_nodos, "w", encoding="utf-8") as f:
                f.write(contenido_nodos)
        try:
            g, errores = gr.cargar(ruta, dirigido=dirigido, multiarista=multiarista, ruta_nodos=ruta_nodos)
        except ErrorGrafo as e:
            raise ErrorApi(str(e))
        self.redes[clave] = g
        self.archivos[clave] = nombre
        return {"errores": errores, "red": self.red_completa(clave)}

    def editar_nodo(self, clave, accion, nodo, tipo="generico", atributos=""):
        g = self.red(clave)
        at_ = self._atributos(atributos)
        if accion == "agregar":
            g.agregar_nodo(nodo, tipo or "generico", **at_)
        elif accion == "modificar":
            if tipo:
                at_["tipo"] = tipo
            g._existe(nodo)
            tipo_n = at_.pop("tipo", None)
            g.modificar_nodo(nodo, **at_)
            if tipo_n:
                g.nodos[nodo]["tipo"] = tipo_n
        elif accion == "eliminar":
            g.eliminar_nodo(nodo)
        return self.red_completa(clave)

    def editar_arista(self, clave, accion, origen, destino, indice=0, atributos=""):
        g = self.red(clave)
        at_ = self._atributos(atributos)
        if accion == "agregar":
            g.agregar_arista(origen, destino, **at_)
        elif accion == "modificar":
            g.modificar_arista(origen, destino, int(indice or 0), **at_)
        elif accion == "eliminar":
            g.eliminar_arista(origen, destino, int(indice or 0))
        return self.red_completa(clave)

    @staticmethod
    def _atributos(texto):
        if isinstance(texto, dict):
            return {k: convertir_valor(v, k) for k, v in texto.items() if str(v).strip() != ""}
        res = {}
        for par in str(texto or "").split(","):
            if "=" in par:
                k, v = par.split("=", 1)
                val = convertir_valor(v, k.strip())
                if val is not None:
                    res[k.strip()] = val
        return res

    def guardar(self, clave, nombre):
        g = self.red(clave)
        nombre = os.path.basename(nombre or f"{g.nombre}_editada.json")
        ruta = os.path.join(CARPETA_DATOS, nombre)
        if nombre.endswith(".csv"):
            gr.guardar_csv(g, ruta)
        else:
            if not nombre.endswith(".json"):
                nombre += ".json"
                ruta += ".json"
            gr.guardar_json(g, ruta)
        with open(ruta, encoding="utf-8") as f:
            contenido = f.read()
        return {"archivo": nombre, "contenido": contenido}

    # ======================================================== MÓDULO 2
    def _subgrafo_transacciones(self, nodos, centro=None, radio=2, clases_a=None, clases_n=None, insignias=None,
                                leyenda=None, titulo=None):
        g = self.red("transacciones")
        nodos = [n for n in g.nodos if n in set(nodos)]
        pos = niveles_dirigidos(g, centro, radio, set(nodos)) if centro else layout_fuerzas(g, nodos)
        return grafo_json(g, nodos=nodos, pos=pos, clases_aristas=clases_a, clases_nodos=clases_n,
                          insignias=insignias, leyenda=leyenda, titulo=titulo,
                          etiqueta=lambda u, v, a: f"{_fmt(a.get('monto'))} ({_dia(a.get('fecha'))})")

    def _aristas_ciclo(self, g):
        grupos = at.grupos_circulacion(at.tarjan_scc(g), g)
        miembro = {n: i for i, gr_ in enumerate(grupos) for n in gr_}
        return {(u, v) for u in g.adj for v, _ in g.adj[u] if u in miembro and miembro.get(v) == miembro[u]}, grupos

    def proximidad(self, cuenta, saltos=2):
        g = self.red("transacciones")
        g._existe(cuenta)
        res, ms = _medir(at.bfs_proximidad, g, cuenta, int(saltos))
        filas = sorted(({"cuenta": n, "saltos": lv, "camino": at.camino_bfs(res, n)}
                        for n, (lv, _) in res.items() if n != cuenta), key=lambda f: (f["saltos"], f["cuenta"]))
        ciclo, _ = self._aristas_ciclo(g)
        clases = {e: "ciclo" for e in ciclo}
        por_nivel = {}
        for f in filas:
            por_nivel[f["saltos"]] = por_nivel.get(f["saltos"], 0) + 1
        return limpiar({
            "filas": filas, "por_nivel": por_nivel, "tiempo_ms": ms,
            "grafo": self._subgrafo_transacciones(list(res), cuenta, int(saltos), clases, {cuenta: "origen"},
                                                  {n: f"{lv}" for n, (lv, _) in res.items() if n != cuenta},
                                                  [["ciclo", "Transferencia dentro de un ciclo"], ["origen", "Cuenta analizada"]],
                                                  f"Cuentas relacionadas con {cuenta} (BFS, hasta {saltos} saltos)"),
            "reporte": at.reporte_proximidad(g, cuenta, int(saltos)),
        })

    def rastreo(self, cuenta, ventana=7, profundidad=8):
        g = self.red("transacciones")
        g._existe(cuenta)
        cadenas, ms = _medir(at.rastrear_fondos, g, cuenta, int(ventana), int(profundidad))
        cadenas.sort(key=lambda c: (-c["ciclo"], -len(c["pasos"])))
        nodos = {cuenta}
        clases = {}
        for c in cadenas:
            for u, v, _, _ in c["pasos"]:
                nodos |= {u, v}
                if clases.get((u, v)) != "ciclo":
                    clases[(u, v)] = "ciclo" if c["ciclo"] else "ruta"
        return limpiar({
            "cadenas": [{"ciclo": c["ciclo"], "pasos": [{"origen": u, "destino": v, "monto": m, "fecha": f}
                                                         for u, v, m, f in c["pasos"]]} for c in cadenas[:40]],
            "total": len(cadenas), "con_ciclo": sum(c["ciclo"] for c in cadenas), "tiempo_ms": ms,
            "grafo": self._subgrafo_transacciones(nodos, cuenta, int(profundidad), clases, {cuenta: "origen"}, None,
                                                  [["ruta", "Cadena de fondos"], ["ciclo", "Cadena que vuelve al origen"]],
                                                  f"Rastreo de fondos desde {cuenta} (DFS temporal, ventana {ventana} días)"),
            "reporte": at.reporte_rastreo(g, cuenta, int(ventana), int(profundidad)),
        })

    def circulacion(self, cuenta=""):
        g = self.red("transacciones")
        t, ms_t = _medir(at.tarjan_scc, g)
        k, ms_k = _medir(at.kosaraju_scc, g)
        aristas, grupos = self._aristas_ciclo(g)
        capas = []
        if cuenta and g.tiene_nodo(cuenta):
            capas = at.capas_desde(g, cuenta)
        clases_n = {n: "alerta" for gr_ in grupos for n in gr_}
        if cuenta in g.nodos:
            clases_n[cuenta] = "origen"
        return limpiar({
            "grupos": grupos, "componentes": len(t), "coinciden": sorted(map(tuple, t)) == sorted(map(tuple, k)),
            "tiempo_tarjan_ms": ms_t, "tiempo_kosaraju_ms": ms_k, "capas": capas,
            "grafo": grafo_json(g, pos=self._pos("transacciones"), clases_aristas={e: "ciclo" for e in aristas},
                                clases_nodos=clases_n,
                                leyenda=[["ciclo", "Dinero que circula (componente fuertemente conexa)"]],
                                titulo="Red completa de transacciones: grupos con circulación"),
            "reporte": at.reporte_circulacion(g, cuenta if g.tiene_nodo(cuenta or "") else None),
        })

    def fraccionamiento(self, umbral=10000, ventana=3, minimo=3):
        g = self.red("transacciones")
        alertas, ms = _medir(at.detectar_abanicos, g, float(umbral), 0.8, int(ventana), int(minimo))
        nodos, clases, clases_n, recs = set(), {}, {}, []
        for a in alertas:
            nodos.add(a["cuenta"])
            nodos |= set(a["contrapartes"])
            clases_n[a["cuenta"]] = "alerta"
            for c in a["contrapartes"]:
                clases[(c, a["cuenta"]) if a["tipo"] == "entrada" else (a["cuenta"], c)] = "abanico"
            rec = at.verificar_reconstruccion(g, a, float(umbral))
            a["reconstruccion"] = rec
            if rec:
                recs.append(rec)
                nodos.add(rec["destino"])
                clases[(rec["cuenta"], rec["destino"])] = "ciclo"
        return limpiar({
            "alertas": alertas, "reconstrucciones": recs, "tiempo_ms": ms,
            "grafo": self._subgrafo_transacciones(nodos, None, 2, clases, clases_n, None,
                                                  [["abanico", "Transferencia bajo el umbral"],
                                                   ["ciclo", "Monto grande reconstruido (suma de subconjuntos)"]],
                                                  "Operaciones fragmentadas (abanicos)"),
            "reporte": at.reporte_fraccionamiento(g, float(umbral), int(ventana), int(minimo)),
        })

    def ranking(self, k=10, marcadas=""):
        g = self.red("transacciones")
        marc = [m.strip() for m in str(marcadas or "").split(",") if m.strip()]
        pts, ms = _medir(at.puntajes, g, marc)
        top = at.top_k(pts, int(k))
        maximo = top[0][1][0] if top else 1
        clases_n = {c: "alerta" for c, _ in top}
        for m in marc:
            if m in g.nodos:
                clases_n[m] = "origen"
        aristas, _ = self._aristas_ciclo(g)
        return limpiar({
            "filas": [{"cuenta": c, "puntaje": p, "motivos": m, "relativo": p / maximo} for c, (p, m) in top],
            "alertas_ruleteo": self.alertas_ruleteo, "tiempo_ms": ms,
            "grafo": grafo_json(g, pos=self._pos("transacciones"), clases_nodos=clases_n,
                                clases_aristas={e: "ciclo" for e in aristas},
                                insignias={c: str(p) for c, (p, _) in top},
                                leyenda=[["alerta", "Cuenta del ranking (número = puntaje)"]],
                                titulo=f"Top {k} cuentas a revisar"),
            "reporte": at.reporte_revision(g, int(k), marc, self.alertas_ruleteo),
        })

    # ======================================================== MÓDULO 3
    def ruta(self, red, origen, destino, criterio="friccion", monto=100):
        g = self.red(red)
        g._existe(origen)
        g._existe(destino)
        monto = float(monto)
        res, ms = _medir(ef.analizar_ruta, g, origen, destino, criterio, monto)
        for a in res["alertas"]:
            if a not in self.alertas_ruleteo:
                self.alertas_ruleteo.append(a)
        clases = {(u, v): "excluida" for u, v, _ in res["excluidas"]}
        for c in res["ciclos"]:
            for u, v in zip(c["ciclo"], c["ciclo"][1:]):
                clases[(u, v)] = "ciclo"
        if res["mejor"]:
            r = res["mejor"][1]
            for u, v in zip(r, r[1:]):
                clases[(u, v)] = "ruta"
        ref = res["mejor"][0] if res["mejor"] else None
        alternativas = [{"costo": c, "ruta": r, "tramos": len(r) - 1,
                         "sobrecosto": (c - ref) if ref is not None else None} for c, r in res["alternativas"][:20]]
        return limpiar({
            "mejor": {"costo": res["mejor"][0], "ruta": res["mejor"][1]} if res["mejor"] else None,
            "menos_saltos": {"costo": res["menos_saltos"][0], "ruta": res["menos_saltos"][1]} if res["menos_saltos"] else None,
            "algoritmo": res["algoritmo"], "excluidas": [{"origen": u, "destino": v, "motivo": m} for u, v, m in res["excluidas"]],
            "ciclos": [{"ciclo": c["ciclo"], "costo": c["costo"], "retiradas": [f"{u}→{v}" for u, v, _ in c["retiradas"]]}
                       for c in res["ciclos"]],
            "alternativas": alternativas, "total_alternativas": len(res["alternativas"]), "tiempo_ms": ms,
            "unidad": ef.CRITERIOS[criterio],
            "grafo": grafo_json(g, pos=self._pos(red), clases_aristas=clases,
                                clases_nodos={origen: "origen", destino: "destino"},
                                etiqueta=lambda u, v, a: _fmt(ef.costo_arista(a, criterio, monto)),
                                leyenda=[["ruta", "Mejor ruta"], ["excluida", "Canal excluido (restricción)"],
                                         ["ciclo", "Ciclo negativo (ruleteo)"]],
                                titulo=f"Ruta {origen} → {destino} · {ef.CRITERIOS[criterio]}"),
            "reporte": ef.reporte_ruta(res),
        })

    def todos_los_pares(self, red, criterio="friccion", monto=100):
        g = self.red(red)
        adj, _ = ef.red_ponderada(g, criterio, float(monto))
        (orden, dist, _), ms_fw = _medir(ef.floyd_warshall, adj)
        neg = ef.nodos_en_ciclo_negativo_fw(orden, dist)
        johnson, ms_j, iguales = None, None, None
        if not neg:
            johnson, ms_j = _medir(ef.johnson, adj)
            iguales = all(dist[i][j] == johnson[orden[i]][orden[j]] for i in range(len(orden)) for j in range(len(orden)))
        return limpiar({
            "orden": orden, "nombres": {n: g.nodos[n].get("nombre", n) for n in orden},
            "matriz": dist, "ciclo_negativo": neg, "tiempo_fw_ms": ms_fw, "tiempo_johnson_ms": ms_j,
            "iguales": iguales, "unidad": ef.CRITERIOS[criterio],
            "reporte": ef.reporte_todos_los_pares(g, criterio, float(monto)),
        })

    def ciclos(self, red, criterio="friccion", monto=100):
        g = self.red(red)
        adj, _ = ef.red_ponderada(g, criterio, float(monto))
        negativas = [{"origen": u, "destino": v, "costo": w} for u in adj for v, w in adj[u] if w < 0]
        hallados, _ = ef.ciclos_negativos(adj)
        orden, dist, _ = ef.floyd_warshall(adj)
        en_fw = ef.nodos_en_ciclo_negativo_fw(orden, dist)
        texto, alertas = ef.reporte_ciclos(g, criterio, float(monto))
        for a in alertas:
            if a not in self.alertas_ruleteo:
                self.alertas_ruleteo.append(a)
        clases = {(n["origen"], n["destino"]): "abanico" for n in negativas}
        for c in hallados:
            for u, v in zip(c["ciclo"], c["ciclo"][1:]):
                clases[(u, v)] = "ciclo"
        return limpiar({
            "negativas": negativas, "en_floyd_warshall": en_fw,
            "ciclos": [{"ciclo": c["ciclo"], "costo": c["costo"], "retiradas": [f"{u}→{v}" for u, v, _ in c["retiradas"]]}
                       for c in hallados],
            "unidad": ef.CRITERIOS[criterio],
            "grafo": grafo_json(g, pos=self._pos(red), clases_aristas=clases,
                                clases_nodos={n: "alerta" for c in hallados for n in c["ciclo"]},
                                etiqueta=lambda u, v, a: _fmt(ef.costo_arista(a, criterio, float(monto))),
                                leyenda=[["ciclo", "Ciclo negativo"], ["abanico", "Arista con costo negativo"]],
                                titulo="Detección de ciclos negativos"),
            "reporte": texto,
        })

    # ======================================================== MÓDULO 4
    def _liq_nodos(self, g):
        return [{"id": n, "nombre": a.get("nombre", n), "tipo": a.get("tipo", ""),
                 "oferta": a.get("oferta", 0), "demanda": a.get("demanda", 0)} for n, a in g.nodos.items()]

    def _grafo_flujo(self, red, flujos, corte=(), titulo="", extra_clases=None):
        g = self.red(red)
        corte = {(u, v) for u, v, *_ in corte}
        clases = {}
        for (u, v), (f, c) in flujos.items():
            if (u, v) in corte:
                clases[(u, v)] = "corte"
            elif c and f >= c:
                clases[(u, v)] = "saturada"
            elif f > 0:
                clases[(u, v)] = "flujo"
        clases.update(extra_clases or {})
        recibe = {}
        for (u, v), (f, _) in flujos.items():
            recibe[v] = recibe.get(v, 0) + f
        insignias, clases_n = {}, {}
        for n, a in g.nodos.items():
            if a.get("demanda", 0) > 0:
                insignias[n] = f"{_fmt(recibe.get(n, 0))}/{_fmt(a['demanda'])}"
                clases_n[n] = "alerta" if recibe.get(n, 0) < a["demanda"] else "ok"
            elif a.get("oferta", 0) > 0:
                insignias[n] = f"oferta {_fmt(a['oferta'])}"
        return grafo_json(g, pos=self._pos(red), clases_aristas=clases, clases_nodos=clases_n, insignias=insignias,
                          etiqueta=lambda u, v, a: f"{_fmt(flujos.get((u, v), (0, 0))[0])} de {_fmt(a.get('capacidad'))}",
                          leyenda=[["corte", "Arista del corte mínimo"], ["saturada", "Saturada fuera del corte"],
                                   ["flujo", "Con flujo"]], titulo=titulo)

    def distribucion(self, red):
        g = self.red(red)
        res, ms = _medir(dl.distribuir, g)
        flujos = {(u, v): (f, c) for u, v, f, c, _ in res["red"].flujos()}
        rutas = [{"origen": u, "destino": v, "flujo": f, "capacidad": c, "costo": w, "uso": (f / c if c else 0)}
                 for u, v, f, c, w in res["red"].flujos() if dl.S_ESTRELLA not in (u, v) and dl.T_ESTRELLA not in (u, v)]
        return limpiar({
            "flujo": res["flujo"], "oferta": res["oferta"], "demanda": res["demanda"], "factible": res["factible"],
            "costo": res["costo"], "capacidad_corte": res["capacidad_corte"], "tiempo_ms": ms,
            "corte": [{"origen": u, "destino": v, "capacidad": c} for u, v, c in res["corte"]],
            "cuellos": [{"origen": u, "destino": v, "agencia": a} for u, v, a in res["cuellos"]],
            "caminos": [{"ruta": r, "delta": d} for r, d in res["caminos"]],
            "agencias": res["agencias"], "rutas": rutas, "verificacion": res["verificacion"],
            "nodos": self._liq_nodos(g),
            "grafo": self._grafo_flujo(red, flujos, res["corte"],
                                       f"Flujo máximo {_fmt(res['flujo'])} de {_fmt(res['demanda'])} (miles de S/)"),
            "reporte": dl.reporte_distribucion(g, res),
        })

    def costo_minimo(self, red):
        g = self.red(red)
        base = dl.distribuir(g)
        r = dl.construir_red(g)
        (flujo, costo), ms = _medir(dl.flujo_costo_minimo, r)
        flujos = {(u, v): (f, c) for u, v, f, c, _ in r.flujos()}
        rutas = [{"origen": u, "destino": v, "flujo": f, "capacidad": c, "costo": w, "flujo_ek": next(
            (x for a, b, x, _, _ in base["red"].flujos() if a == u and b == v), 0)}
            for u, v, f, c, w in r.flujos() if dl.S_ESTRELLA not in (u, v) and dl.T_ESTRELLA not in (u, v)]
        return limpiar({
            "flujo": flujo, "costo": costo, "costo_ek": base["costo"], "ahorro": base["costo"] - costo,
            "tiempo_ms": ms, "rutas": rutas,
            "grafo": self._grafo_flujo(red, flujos, (), f"Plan de costo mínimo: S/ {_fmt(costo)}"),
            "reporte": dl.reporte_costo_minimo(g),
        })

    def voraz(self, red):
        g = self.red(red)
        base = dl.distribuir(g)
        recibido, orden, costo = dl.voraz_mas_cercana(g)
        ek = {a["agencia"]: a for a in base["agencias"]}
        return limpiar({
            "orden": orden, "total_voraz": sum(recibido.values()), "total_flujo": base["flujo"],
            "filas": [{"agencia": a, "demanda": ek[a]["demanda"], "voraz": recibido[a], "flujo": ek[a]["recibe"]} for a in orden],
            "reporte": dl.reporte_voraz(g),
        })

    def arbol(self, red):
        g = self.red(red)
        (ap, cp), ms_p = _medir(dl.prim, g)
        (ak, ck), ms_k = _medir(dl.kruskal, g)
        pares = {frozenset((u, v)) for u, v, _ in ak}
        completo = dl.distribuir(g)["flujo"]
        r = dl.construir_red(g, filtro=lambda u, v, a: frozenset((u, v)) in pares)
        en_arbol, _ = dl.edmonds_karp(r)
        clases = {(u, v): "arbol" for u, v, _ in g.aristas() if frozenset((u, v)) in pares}
        return limpiar({
            "aristas": [{"a": u, "b": v, "costo": w} for u, v, w in ak], "costo_prim": cp, "costo_kruskal": ck,
            "tiempo_prim_ms": ms_p, "tiempo_kruskal_ms": ms_k, "flujo_completo": completo, "flujo_arbol": en_arbol,
            "grafo": grafo_json(g, pos=self._pos(red), clases_aristas=clases,
                                etiqueta=lambda u, v, a: _fmt(a.get("costo_habilitacion", a.get("costo"))),
                                leyenda=[["arbol", "Ruta del árbol de expansión mínima"]],
                                titulo=f"Red mínima de rutas: costo de habilitación {_fmt(ck)}"),
            "reporte": dl.reporte_mst(g),
        })

    def editar_liquidez(self, red, nodo, oferta=None, demanda=None):
        g = self.red(red)
        cambios = {}
        if oferta not in (None, ""):
            cambios["oferta"] = float(oferta)
        if demanda not in (None, ""):
            cambios["demanda"] = float(demanda)
        g.modificar_nodo(nodo, **cambios)
        return self.distribucion(red)

    # ======================================================== MÓDULO 5
    def verificaciones(self):
        filas, ms = _medir(ev.verificaciones_cruzadas)
        return {"filas": [{"escenario": a, "comparacion": b, "ok": c == "OK", "detalle": d} for a, b, c, d in filas],
                "tiempo_ms": ms, "reporte": ev.reporte_verificaciones()}

    def benchmark(self, tamanos="10,50,100,200", densidad="dispersa"):
        lista = [int(x) for x in str(tamanos).split(",") if x.strip().isdigit()]
        if not lista:
            raise ErrorApi("Indique al menos un tamaño.")
        if max(lista) > 400:
            raise ErrorApi("Use tamaños de hasta 400 nodos (Floyd-Warshall es O(V³)).")
        res = ev.benchmark(lista, densidad, repeticiones=2)
        return limpiar({"series": {alg: [{"n": n, "e": e, "ms": ms, "kb": kb} for n, e, ms, kb in d]
                                   for alg, d in res.items()},
                        "densidad": densidad, "reporte": ev.reporte_benchmark(res, densidad)})

    def complejidad(self):
        return {"filas": [dict(zip(["modulo", "algoritmo", "guia", "paradigma", "tiempo", "espacio"], f))
                          for f in ev.COMPLEJIDADES], "reporte": ev.reporte_complejidad()}

    def pruebas(self):
        t0 = time.perf_counter()
        p = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=RAIZ,
                           capture_output=True, text=True, timeout=300)
        salida = (p.stdout + p.stderr).strip()
        return {"ok": p.returncode == 0, "salida": salida, "tiempo_s": time.perf_counter() - t0,
                "resumen": salida.splitlines()[-1] if salida else ""}
