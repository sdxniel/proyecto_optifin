"""
evaluacion_resultados.py - Módulo 5: evaluación, comparación y validación.

1. Verificaciones cruzadas: algoritmos distintos que deben dar el mismo resultado.
2. Comparación de desempeño: tiempo (time.perf_counter) y memoria (tracemalloc)
   en redes aleatorias con semilla fija, de distintos tamaños y densidades.
3. Gráfico de tiempo medido contra tamaño (metodología de la Guía 1).
"""

import math
import os
import random
import time
import tracemalloc

from .graph import Grafo
from . import analisis_transacciones as at
from . import enrutamiento_financiero as ef
from . import distribucion_liquidez as dl
from .gestion_red import cargar
from .utils import tabla, titulo, ruta_dato, CARPETA_REPORTES

COMPLEJIDADES = [
    # módulo, algoritmo, guía, paradigma, tiempo, espacio
    ("2", "BFS", "7", "Recorrido por niveles", "O(V + E)", "O(V)"),
    ("2", "DFS con restricción temporal", "7", "Recorrido en profundidad", "O(V + E) por cadena", "O(V)"),
    ("2", "Tarjan / Kosaraju", "7", "Recorrido en profundidad", "O(V + E)", "O(V)"),
    ("2", "Condensación + orden topológico", "7", "Kahn", "O(V + E)", "O(V)"),
    ("2", "Ordenamiento + ventana", "2", "Ordenamiento", "O(E log E)", "O(E)"),
    ("2", "Suma de subconjuntos", "5", "Programación dinámica", "O(n · S)", "O(S)"),
    ("2", "Heap top-k", "2", "Cola de prioridad", "O(V log k)", "O(k)"),
    ("3", "Backtracking con poda", "6", "Retroceso", "O(V!) peor caso", "O(V)"),
    ("3", "Dijkstra", "9", "Voraz", "O((V + E) log V)", "O(V)"),
    ("3", "Bellman-Ford", "9", "Programación dinámica", "O(V · E)", "O(V)"),
    ("3", "Floyd-Warshall", "10", "Programación dinámica", "O(V³)", "O(V²)"),
    ("3", "Johnson", "9, 10", "Reponderación + voraz", "O(V·E + V(V+E) log V)", "O(V²)"),
    ("4", "Edmonds-Karp", "11", "Caminos aumentantes (BFS)", "O(V · E²)", "O(V + E)"),
    ("4", "Corte mínimo", "11", "BFS en red residual", "O(V + E)", "O(V)"),
    ("4", "Flujo de costo mínimo", "9 + 11", "Caminos aumentantes de menor costo", "O(F · V · E)", "O(V + E)"),
    ("4", "Prim", "8", "Voraz", "O(E log V)", "O(V + E)"),
    ("4", "Kruskal", "8", "Voraz + union-find", "O(E log E)", "O(V)"),
]


# ------------------------------------------------------------ generadores
def red_aleatoria(n, densidad="dispersa", semilla=2026, peso_min=1, peso_max=20, capacidades=False):
    """Grafo dirigido aleatorio reproducible. Dispersa: E ≈ 3V. Densa: E ≈ V²/4."""
    rnd = random.Random(semilla + n)
    m = 3 * n if densidad == "dispersa" else max(1, n * n // 4)
    m = min(m, n * (n - 1))
    g = Grafo(dirigido=True, nombre=f"aleatoria_{densidad}_{n}")
    for i in range(n):
        g.agregar_nodo(str(i))
    # un camino base asegura que todos los nodos sean alcanzables desde 0
    pares = {(str(i), str(i + 1)) for i in range(n - 1)}
    while len(pares) < m:
        u, v = rnd.randrange(n), rnd.randrange(n)
        if u != v:
            pares.add((str(u), str(v)))
    for u, v in sorted(pares):
        if capacidades:
            g.agregar_arista(u, v, capacidad=rnd.randint(5, 100), costo=rnd.randint(1, 9),
                             costo_habilitacion=rnd.randint(1, 50))
        else:
            g.agregar_arista(u, v, peso=rnd.randint(peso_min, peso_max))
    if capacidades:
        g.modificar_nodo("0", oferta=10 ** 6)
        g.modificar_nodo(str(n - 1), demanda=10 ** 6)
    return g


def _adj_peso(g):
    return {u: [(v, a["peso"]) for v, a in g.adj[u]] for u in g.adj}


# ------------------------------------------------------------ medición
def medir(funcion, *args, repeticiones=3):
    """Tiempo promedio (ms) con perf_counter y pico de memoria (KB) con tracemalloc."""
    tiempos = []
    resultado = None
    for _ in range(repeticiones):
        t0 = time.perf_counter()
        resultado = funcion(*args)
        tiempos.append((time.perf_counter() - t0) * 1000)
    tracemalloc.start()
    funcion(*args)
    _, pico = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return sum(tiempos) / len(tiempos), pico / 1024, resultado


# ------------------------------------------------------------ verificaciones
def verificaciones_cruzadas(tamanos=(10, 30, 60), semilla=2026):
    """Devuelve filas [escenario, comparación, resultado, detalle]."""
    filas = []

    def agregar(esc, comp, ok, det=""):
        filas.append([esc, comp, "OK" if ok else "FALLA", det])

    # --- Rutas: Dijkstra, Bellman-Ford, Floyd-Warshall y Johnson coinciden
    for n in tamanos:
        adj = _adj_peso(red_aleatoria(n, "dispersa", semilla))
        orden, fw, _ = ef.floyd_warshall(adj)
        jo = ef.johnson(adj)
        ok = True
        for i, s in enumerate(orden):
            d, _ = ef.dijkstra(adj, s)
            b, _, _ = ef.bellman_ford(adj, s)
            for j, t in enumerate(orden):
                if not (d[t] == b[t] == fw[i][j] == jo[s][t]):
                    ok = False
        agregar("Rutas", f"Dijkstra = Bellman-Ford = Floyd-Warshall = Johnson (n={n})", ok)
    g, _ = cargar(ruta_dato("red_enrutamiento.csv"))
    res = ef.analizar_ruta(g, "A", "X", "friccion", 100)
    agregar("Rutas", "Mejor ruta del backtracking = Dijkstra (red Guía 10)",
            res["alternativas"][0][0] == res["mejor"][0], f"costo {res['mejor'][0]}")
    agregar("Rutas", "Costo A -> X con fricción = 8 (valor de la Guía 10)", res["mejor"][0] == 8,
            " -> ".join(res["mejor"][1]))
    # --- Ruleteo: Bellman-Ford y Floyd-Warshall detectan el ciclo
    gc, _ = cargar(ruta_dato("red_enrutamiento_cashback.csv"))
    adj, _ = ef.red_ponderada(gc, "friccion", 100)
    _, _, ciclo = ef.bellman_ford(adj)
    orden, dist, _ = ef.floyd_warshall(adj)
    neg = ef.nodos_en_ciclo_negativo_fw(orden, dist)
    agregar("Ruleteo", "Bellman-Ford y Floyd-Warshall detectan el ciclo negativo",
            bool(ciclo) and set(ciclo) <= set(neg), f"ciclo {' -> '.join(ciclo or [])}")
    # --- Circulación: Tarjan = Kosaraju
    gt, _ = cargar(ruta_dato("transacciones.csv"), multiarista=True)
    for nombre, gr in [("transacciones.csv", gt)] + [(f"aleatoria n={n}", red_aleatoria(n, "dispersa", semilla)) for n in tamanos]:
        t = sorted(map(tuple, at.tarjan_scc(gr)))
        k = sorted(map(tuple, at.kosaraju_scc(gr)))
        agregar("Circulación", f"Tarjan = Kosaraju ({nombre})", t == k, f"{len(t)} componentes")
    # --- Liquidez: flujo = corte, restricciones, EK = FF-DFS = costo mínimo
    for archivo in ("distribucion_liquidez.csv", "liquidez_red_ampliada.csv"):
        gl, _ = cargar(ruta_dato(archivo))
        r = dl.distribuir(gl)
        agregar("Liquidez", f"Flujo máximo = corte mínimo ({archivo})", r["flujo"] == r["capacidad_corte"],
                f"{r['flujo']} = {r['capacidad_corte']}")
        agregar("Liquidez", f"Capacidad y conservación del flujo ({archivo})", not r["verificacion"])
        ff, _ = dl.ford_fulkerson_dfs(dl.construir_red(gl))
        mc, _ = dl.flujo_costo_minimo(dl.construir_red(gl))
        agregar("Liquidez", f"Edmonds-Karp = Ford-Fulkerson DFS = costo mínimo ({archivo})",
                r["flujo"] == ff == mc, f"{r['flujo']}")
        _, cp = dl.prim(gl)
        _, ck = dl.kruskal(gl)
        agregar("Diseño de red", f"Prim = Kruskal ({archivo})", cp == ck, f"costo {cp}")
    gl, _ = cargar(ruta_dato("distribucion_liquidez.csv"))
    agregar("Liquidez", "Figura 5: flujo máximo = 950", dl.distribuir(gl)["flujo"] == 950)
    # --- Fraude: patrones plantados detectados
    alertas = {a["cuenta"] for a in at.detectar_abanicos(gt)}
    agregar("Fraude", "Abanicos plantados (CTA_P entrada, CTA_F salida) detectados",
            {"CTA_P", "CTA_F"} <= alertas)
    cad = at.rastrear_fondos(gt, "X1")
    agregar("Fraude", "DFS temporal no encadena X1->X2->X3 (fechas imposibles)",
            all(len(c["pasos"]) == 1 for c in cad))
    return filas


def reporte_verificaciones():
    filas = verificaciones_cruzadas()
    ok = sum(1 for f in filas if f[2] == "OK")
    return titulo("Verificaciones cruzadas (resultados que deben coincidir)") + \
        f"\n{ok} de {len(filas)} verificaciones correctas\n\n" + tabla(["escenario", "comparación", "resultado", "detalle"], filas)


# ------------------------------------------------------------ desempeño
def benchmark(tamanos=(10, 50, 100, 200), densidad="dispersa", repeticiones=3, semilla=2026, progreso=None):
    """Mide tiempo y memoria de cada algoritmo en redes aleatorias.
    Devuelve {algoritmo: [(n, E, ms, KB), ...]}."""
    res = {}

    def reg(nombre, n, e, func, *args):
        ms, kb, _ = medir(func, *args, repeticiones=repeticiones)
        res.setdefault(nombre, []).append((n, e, ms, kb))

    for n in tamanos:
        if progreso:
            progreso(n)
        g = red_aleatoria(n, densidad, semilla)
        e = g.num_aristas()
        adj = _adj_peso(g)
        reg("Dijkstra (1 origen)", n, e, ef.dijkstra, adj, "0")
        reg("Bellman-Ford (1 origen)", n, e, ef.bellman_ford, adj, "0")
        reg("Floyd-Warshall (todos los pares)", n, e, ef.floyd_warshall, adj)
        reg("Johnson (todos los pares)", n, e, ef.johnson, adj)
        reg("Tarjan", n, e, at.tarjan_scc, g)
        reg("Kosaraju", n, e, at.kosaraju_scc, g)
        reg("BFS", n, e, at.bfs_proximidad, g, "0")
        gf = red_aleatoria(n, densidad, semilla, capacidades=True)
        reg("Edmonds-Karp", n, e, lambda: dl.edmonds_karp(dl.construir_red(gf)))
        reg("Ford-Fulkerson DFS", n, e, lambda: dl.ford_fulkerson_dfs(dl.construir_red(gf)))
        reg("Prim", n, e, dl.prim, gf)
        reg("Kruskal", n, e, dl.kruskal, gf)
    return res


def reporte_benchmark(res, densidad):
    txt = titulo(f"Desempeño empírico - redes {densidad}s (promedio de repeticiones)")
    filas = []
    for alg, datos in res.items():
        for n, e, ms, kb in datos:
            filas.append([alg, n, e, f"{ms:.3f}", f"{kb:.1f}"])
    txt += "\n" + tabla(["algoritmo", "V", "E", "tiempo (ms)", "memoria pico (KB)"], filas,
                        ["<", ">", ">", ">", ">"])
    return txt


def graficar(res, densidad, archivo=None):
    """Gráfico de tiempo contra V (escala logarítmica), por grupos de algoritmos."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    grupos = [
        ("Rutas: todos los pares", ["Floyd-Warshall (todos los pares)", "Johnson (todos los pares)"]),
        ("Rutas: un origen", ["Dijkstra (1 origen)", "Bellman-Ford (1 origen)"]),
        ("Recorridos y componentes", ["BFS", "Tarjan", "Kosaraju"]),
        ("Flujo y árbol de expansión", ["Edmonds-Karp", "Ford-Fulkerson DFS", "Prim", "Kruskal"]),
    ]
    fig, ejes = plt.subplots(2, 2, figsize=(11, 8))
    for ax, (tit, algs) in zip(ejes.flat, grupos):
        for alg in algs:
            if alg in res:
                ns = [d[0] for d in res[alg]]
                ms = [max(d[2], 1e-4) for d in res[alg]]
                ax.plot(ns, ms, marker="o", label=alg)
        ax.set_yscale("log")
        ax.set_title(tit, loc="left", fontsize=11, color="#2F5D8C", weight="bold")
        ax.set_xlabel("número de nodos V")
        ax.set_ylabel("tiempo (ms, escala log)")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
    fig.suptitle(f"Tiempo de ejecución contra tamaño de la red ({densidad})", weight="bold")
    fig.tight_layout()
    os.makedirs(CARPETA_REPORTES, exist_ok=True)
    archivo = archivo or os.path.join(CARPETA_REPORTES, f"benchmark_{densidad}.png")
    fig.savefig(archivo, dpi=140)
    plt.close(fig)
    return archivo


def reporte_complejidad():
    return titulo("Complejidad teórica de los algoritmos seleccionados") + "\n" + tabla(
        ["módulo", "algoritmo", "guía", "paradigma", "tiempo", "espacio"], COMPLEJIDADES)
