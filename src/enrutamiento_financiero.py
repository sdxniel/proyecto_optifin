"""
enrutamiento_financiero.py - Módulo 3: optimización del enrutamiento de
operaciones financieras y cálculo de comisiones.

Modelo: grafo DIRIGIDO y PONDERADO. Nodo = billetera, banco, cámara de
compensación, comercio, pasarela de tarjetas, red ATM o agencia. El peso de cada
arista depende del criterio elegido:

  - "friccion":  ceil(0.20C + 0.15T + 0.25R + 0.25I + 0.15V) - cashback   (Guía 10)
  - "comision":  comision_fija + comision_pct/100 * monto - cashback_soles (S/)
  - "tiempo":    tiempo de procesamiento (minutos)

Restricciones de servicio: se excluyen los canales con disponible = no y los
que tienen un límite transaccional menor que el monto de la operación.

Algoritmos:
- Backtracking con poda (Guía 6)  -> todas las rutas alternativas.
- Dijkstra (Guía 9, voraz)        -> menor costo con pesos >= 0.     O((V+E) log V)
- Bellman-Ford (Guía 9, PD)       -> pesos negativos y ciclos negativos (ruleteo). O(V E)
- Floyd-Warshall (Guía 10, PD)    -> todos los pares.                 O(V^3)
- Johnson (Guías 9 y 10)          -> todos los pares en redes dispersas. O(VE + V(V+E) log V)
- BFS (Guía 7)                    -> línea base: ruta con menos saltos.
"""

import heapq
import math
import time
from collections import deque

from .utils import tabla, fmt_num, titulo

CRITERIOS = {"friccion": "fricción (puntos)", "comision": "comisión (S/)", "tiempo": "tiempo (min)"}
INF = math.inf


class CicloNegativo(Exception):
    def __init__(self, ciclo):
        super().__init__(f"Ciclo negativo: {' -> '.join(ciclo)}")
        self.ciclo = ciclo


# ------------------------------------------------------------ pesos
def friccion(a):
    """Costo de fricción transaccional de la Guía 10 (menos el cashback, si hay)."""
    if "friccion" in a:
        base = a["friccion"]
    else:
        x = 0.20 * a.get("C", 0) + 0.15 * a.get("T", 0) + 0.25 * a.get("R", 0) \
            + 0.25 * a.get("I", 0) + 0.15 * a.get("V", 0)
        base = math.ceil(round(x, 9))  # round evita que 5.000000001 suba a 6
    return base - a.get("cashback", 0)


def costo_arista(a, criterio="friccion", monto=0):
    if criterio == "friccion":
        return friccion(a)
    if criterio == "comision":
        return round(a.get("comision_fija", 0) + a.get("comision_pct", 0) / 100 * monto
                     - a.get("cashback_soles", 0), 4)
    if criterio == "tiempo":
        return a.get("tiempo", 0)
    if criterio in a:
        return a[criterio]
    raise ValueError(f"Criterio desconocido: {criterio}")


def red_ponderada(grafo, criterio="friccion", monto=0):
    """Aplica las restricciones de servicio y calcula el peso de cada arista.

    Devuelve (adj, excluidas) con adj = {u: [(v, peso), ...]}.
    """
    adj = {n: [] for n in grafo.nodos}
    excluidas = []
    for u, v, a in grafo.aristas():
        if a.get("disponible", True) is False:
            excluidas.append((u, v, "canal no disponible"))
            continue
        if "limite" in a and monto > a["limite"]:
            excluidas.append((u, v, f"límite S/ {fmt_num(a['limite'])} menor que el monto"))
            continue
        adj[u].append((v, costo_arista(a, criterio, monto)))
    return adj, excluidas


def tiene_negativos(adj):
    return any(w < 0 for u in adj for _, w in adj[u])


def costo_ruta(adj, ruta):
    total = 0
    for u, v in zip(ruta, ruta[1:]):
        total += min(w for x, w in adj[u] if x == v)
    return total


# ------------------------------------------------------------ Dijkstra
def dijkstra(adj, origen):
    """Rutas de menor costo desde `origen` (pesos >= 0). Cola de prioridad heapq."""
    if tiene_negativos(adj):
        raise ValueError("Dijkstra no admite pesos negativos: use Bellman-Ford.")
    dist = {n: INF for n in adj}
    pred = {n: None for n in adj}
    dist[origen] = 0
    heap = [(0, origen)]
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]:
            continue
        for v, w in adj[u]:
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                pred[v] = u
                heapq.heappush(heap, (nd, v))
    return dist, pred


def camino(pred, destino):
    if destino not in pred:
        return None
    ruta, n, pasos = [], destino, 0
    while n is not None:
        ruta.append(n)
        n = pred[n]
        pasos += 1
        if pasos > len(pred) + 1:
            return None
    return ruta[::-1]


# ------------------------------------------------------------ Bellman-Ford
def bellman_ford(adj, origen=None):
    """Bellman-Ford. Si `origen` es None usa un origen virtual conectado a todos los
    nodos con costo 0, lo que permite detectar ciclos negativos en toda la red.

    Devuelve (dist, pred, ciclo). `ciclo` es None o la lista de nodos del ciclo
    negativo encontrado (reconstruido con los predecesores).
    """
    nodos = list(adj)
    dist = {n: (0 if origen is None else INF) for n in nodos}
    pred = {n: None for n in nodos}
    if origen is not None:
        dist[origen] = 0
    aristas = [(u, v, w) for u in adj for v, w in adj[u]]
    x = None
    for _ in range(len(nodos)):  # V iteraciones: la última solo detecta ciclos
        x = None
        for u, v, w in aristas:
            if dist[u] != INF and dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
                pred[v] = u
                x = v
        if x is None:
            break
    if x is None:
        return dist, pred, None
    for _ in range(len(nodos)):  # retroceder V veces para caer dentro del ciclo
        x = pred[x]
    ciclo, v = [x], pred[x]
    while v != x:
        ciclo.append(v)
        v = pred[v]
    ciclo.reverse()
    return dist, pred, ciclo


# ------------------------------------------------------------ Floyd-Warshall
def floyd_warshall(adj):
    """Todos los pares por programación dinámica. Devuelve (orden, dist, sig).

    dist[i][j] = costo mínimo; sig[i][j] = siguiente nodo en la ruta.
    Si dist[i][i] < 0, el nodo i está en un ciclo negativo.
    """
    orden = list(adj)
    idx = {n: i for i, n in enumerate(orden)}
    n = len(orden)
    dist = [[INF] * n for _ in range(n)]
    sig = [[None] * n for _ in range(n)]
    for i in range(n):
        dist[i][i] = 0
        sig[i][i] = i
    for u in adj:
        for v, w in adj[u]:
            i, j = idx[u], idx[v]
            if w < dist[i][j]:
                dist[i][j] = w
                sig[i][j] = j
    for k in range(n):
        dk = dist[k]
        for i in range(n):
            dik = dist[i][k]
            if dik == INF:
                continue
            di = dist[i]
            for j in range(n):
                nd = dik + dk[j]
                if nd < di[j]:
                    di[j] = nd
                    sig[i][j] = sig[i][k]
    return orden, dist, sig


def ruta_fw(orden, sig, origen, destino):
    idx = {n: i for i, n in enumerate(orden)}
    i, j = idx[origen], idx[destino]
    if sig[i][j] is None:
        return None
    ruta = [origen]
    while i != j:
        i = sig[i][j]
        ruta.append(orden[i])
        if len(ruta) > len(orden) + 1:
            return None
    return ruta


def nodos_en_ciclo_negativo_fw(orden, dist):
    return [orden[i] for i in range(len(orden)) if dist[i][i] < 0]


# ------------------------------------------------------------ Johnson
def johnson(adj):
    """Todos los pares: Bellman-Ford para obtener potenciales h, reponderación
    w'(u,v) = w + h(u) - h(v) >= 0 y Dijkstra desde cada nodo.
    Lanza CicloNegativo si existe uno."""
    h, _, ciclo = bellman_ford(adj, None)
    if ciclo:
        raise CicloNegativo(ciclo)
    adj2 = {u: [(v, w + h[u] - h[v]) for v, w in adj[u]] for u in adj}
    res = {}
    for s in adj:
        d, _ = dijkstra(adj2, s)
        res[s] = {t: (d[t] - h[s] + h[t]) if d[t] != INF else INF for t in adj}
    return res


# ------------------------------------------------------------ Backtracking
def enumerar_rutas(adj, origen, destino, max_tramos=8, costo_max=None, limite=500):
    """Backtracking (Guía 6): enumera los caminos simples de origen a destino.

    Poda: (1) no pasar dos veces por el mismo nodo, (2) no superar `max_tramos`,
    (3) si todos los pesos son >= 0, cortar la rama cuando el costo parcial ya
    supera `costo_max`. Devuelve [(costo, ruta)] ordenado por costo.
    """
    podar_costo = costo_max is not None and not tiene_negativos(adj)
    rutas = []
    camino_actual = [origen]
    visitado = {origen}

    def bt(u, costo):
        if len(rutas) >= limite:
            return
        if u == destino:
            rutas.append((costo, list(camino_actual)))
            return
        if len(camino_actual) > max_tramos:
            return
        for v, w in adj[u]:
            if v in visitado:
                continue
            if podar_costo and costo + w > costo_max:
                continue
            visitado.add(v)
            camino_actual.append(v)
            bt(v, costo + w)
            camino_actual.pop()          # retroceder
            visitado.discard(v)

    bt(origen, 0)
    rutas.sort(key=lambda r: (r[0], len(r[1])))
    return rutas


def bfs_menos_saltos(adj, origen, destino):
    """Línea base: la ruta con menos tramos, sin mirar el costo."""
    pred = {origen: None}
    cola = deque([origen])
    while cola:
        u = cola.popleft()
        if u == destino:
            break
        for v, _ in adj[u]:
            if v not in pred:
                pred[v] = u
                cola.append(v)
    return camino(pred, destino) if destino in pred else None


# ------------------------------------------------------------ procedimiento
def ciclos_negativos(adj):
    """Encuentra ciclos negativos uno por uno. Tras hallar uno, retira sus aristas
    de peso negativo (las promociones) y vuelve a buscar.
    Devuelve (lista_de_ciclos, adj_sin_ciclos)."""
    adj = {u: list(vs) for u, vs in adj.items()}
    hallados = []
    while True:
        _, _, ciclo = bellman_ford(adj, None)
        if not ciclo:
            return hallados, adj
        cerrado = ciclo + [ciclo[0]]
        costo = costo_ruta(adj, cerrado)
        retiradas = []
        for u, v in zip(cerrado, cerrado[1:]):
            w = min(x for y, x in adj[u] if y == v)
            if w < 0:
                adj[u] = [(y, x) for y, x in adj[u] if not (y == v and x == w)]
                retiradas.append((u, v, w))
        if not retiradas:  # ciclo negativo sin promociones (no debería ocurrir)
            u, v = cerrado[0], cerrado[1]
            adj[u] = [(y, x) for y, x in adj[u] if y != v]
            retiradas.append((u, v, None))
        hallados.append({"ciclo": cerrado, "costo": costo, "retiradas": retiradas})


def analizar_ruta(grafo, origen, destino, criterio="friccion", monto=100.0, max_tramos=8):
    """Procedimiento completo del Módulo 3.

    1. Aplica restricciones de servicio y calcula pesos.
    2. Si no hay pesos negativos usa Dijkstra; si hay, Bellman-Ford.
    3. Si hay ciclo negativo: lo reporta (ruleteo), retira esas promociones y recalcula.
    4. Enumera todas las alternativas (backtracking) y la ruta de menos saltos (BFS).
    """
    adj, excluidas = red_ponderada(grafo, criterio, monto)
    res = {"origen": origen, "destino": destino, "criterio": criterio, "monto": monto,
           "excluidas": excluidas, "ciclos": [], "alertas": []}
    negativos = tiene_negativos(adj)
    if negativos:
        ciclos, adj_ok = ciclos_negativos(adj)
        res["ciclos"] = ciclos
        for c in ciclos:
            res["alertas"].append(
                f"Ruleteo: ciclo {' -> '.join(c['ciclo'])} con costo {fmt_num(c['costo'])} por vuelta "
                f"({CRITERIOS.get(criterio, criterio)}); promociones retiradas: "
                + ", ".join(f"{u}->{v}" for u, v, _ in c["retiradas"]))
        adj = adj_ok
        dist, pred, _ = bellman_ford(adj, origen)
        res["algoritmo"] = "Bellman-Ford (hay pesos negativos)"
    else:
        dist, pred = dijkstra(adj, origen)
        res["algoritmo"] = "Dijkstra (todos los pesos >= 0)"
    if dist.get(destino, INF) == INF:
        res["mejor"] = None
    else:
        res["mejor"] = (dist[destino], camino(pred, destino))
    res["alternativas"] = enumerar_rutas(adj, origen, destino, max_tramos=max_tramos)
    saltos = bfs_menos_saltos(adj, origen, destino)
    res["menos_saltos"] = (costo_ruta(adj, saltos), saltos) if saltos else None
    res["adj"] = adj
    return res


def reporte_ruta(res):
    unidad = CRITERIOS.get(res["criterio"], res["criterio"])
    txt = titulo(f"Ruta de {res['origen']} a {res['destino']} - criterio: {unidad}, monto S/ {fmt_num(res['monto'])}")
    if res["excluidas"]:
        txt += "\nCanales excluidos por restricciones de servicio:\n"
        txt += "".join(f"  - {u}->{v}: {motivo}\n" for u, v, motivo in res["excluidas"])
    if res["ciclos"]:
        txt += "\n¡ALERTA! Se detectaron ciclos negativos (posible ruleteo):\n"
        for c in res["ciclos"]:
            txt += (f"  - Ciclo {' -> '.join(c['ciclo'])}: costo {fmt_num(c['costo'])} por vuelta. "
                    f"Se retiran las promociones {', '.join(f'{u}->{v} ({fmt_num(w)})' for u, v, w in c['retiradas'])} "
                    "y se recalcula.\n")
        txt += "  El ciclo se envía al reporte de auditoría (Módulo 2).\n"
    txt += f"\nAlgoritmo usado: {res['algoritmo']}\n"
    if not res["mejor"]:
        return txt + "\nNo existe una ruta que cumpla las restricciones para ese monto."
    costo, ruta = res["mejor"]
    txt += f"\nMEJOR RUTA: {' -> '.join(ruta)}   costo total = {fmt_num(costo)}\n"
    if res["menos_saltos"]:
        c2, r2 = res["menos_saltos"]
        extra = c2 - costo
        txt += (f"Ruta con menos saltos (BFS): {' -> '.join(r2)}   costo = {fmt_num(c2)}"
                + (f"   (sobrecosto {fmt_num(extra)})" if extra > 0 else "   (coincide en costo)") + "\n")
    alts = res["alternativas"]
    txt += f"\nAlternativas encontradas por backtracking: {len(alts)}\n"
    filas = [[i, " -> ".join(r), len(r) - 1, fmt_num(c), "mejor" if i == 1 else ""] for i, (c, r) in enumerate(alts[:15], 1)]
    txt += tabla(["#", "ruta", "tramos", "costo", ""], filas)
    return txt


def reporte_todos_los_pares(grafo, criterio="friccion", monto=100.0):
    adj, _ = red_ponderada(grafo, criterio, monto)
    txt = titulo(f"Costos mínimos entre todos los pares - {CRITERIOS.get(criterio, criterio)}")
    t0 = time.perf_counter()
    orden, dist, _ = floyd_warshall(adj)
    t_fw = time.perf_counter() - t0
    neg = nodos_en_ciclo_negativo_fw(orden, dist)
    if neg:
        txt += (f"\nFloyd-Warshall: dist[i][i] < 0 para {', '.join(neg)} -> hay ciclo negativo; "
                "los costos no están definidos. Use la opción de detección de ciclos.\n")
        return txt
    t0 = time.perf_counter()
    try:
        dj = johnson(adj)
        t_j = time.perf_counter() - t0
        iguales = all(abs(dj[orden[i]][orden[j]] - dist[i][j]) < 1e-9 or (dj[orden[i]][orden[j]] == dist[i][j])
                      for i in range(len(orden)) for j in range(len(orden)))
    except CicloNegativo:
        t_j, iguales = None, False
    filas = [[orden[i]] + [fmt_num(dist[i][j]) for j in range(len(orden))] for i in range(len(orden))]
    txt += "\n" + tabla(["desde \\ hacia"] + orden, filas)
    txt += f"\n\nTiempo Floyd-Warshall: {t_fw * 1000:.3f} ms"
    if t_j is not None:
        txt += f"   Tiempo Johnson: {t_j * 1000:.3f} ms"
    txt += f"\nAmbos algoritmos dan la misma matriz: {'SÍ' if iguales else 'NO'}"
    return txt


def reporte_ciclos(grafo, criterio="friccion", monto=100.0):
    adj, _ = red_ponderada(grafo, criterio, monto)
    txt = titulo(f"Detección de ciclos negativos (ruleteo) - {CRITERIOS.get(criterio, criterio)}")
    neg = [(u, v, w) for u in adj for v, w in adj[u] if w < 0]
    if not neg:
        return txt + "\nNo hay aristas con costo negativo: no puede haber ciclos negativos.", []
    txt += "\nAristas con costo neto negativo (promociones/cashback):\n"
    txt += "".join(f"  - {u}->{v}: {fmt_num(w)}\n" for u, v, w in neg)
    ciclos, _ = ciclos_negativos(adj)
    orden, dist, _ = floyd_warshall(adj)
    en_fw = nodos_en_ciclo_negativo_fw(orden, dist)
    if not ciclos:
        txt += "\nBellman-Ford: hay pesos negativos pero NINGÚN ciclo negativo. Las rutas siguen definidas."
    for c in ciclos:
        txt += (f"\nBellman-Ford: ciclo {' -> '.join(c['ciclo'])} con costo {fmt_num(c['costo'])} por vuelta"
                f" -> cada vuelta deja {fmt_num(-c['costo'])} a favor del usuario.")
    txt += (f"\nFloyd-Warshall: nodos con dist[i][i] < 0: {', '.join(en_fw) if en_fw else 'ninguno'}"
            " (incluye los nodos que pueden salir y volver pasando por el ciclo)")
    txt += ("\n\nLectura financiera: un cashback real tiene tope por usuario; el ciclo infinito revela un defecto "
            "en el diseño de la promoción. Se reporta como alerta y no se recomienda como ruta.")
    return txt, [f"Ciclo {' -> '.join(c['ciclo'])} (costo {fmt_num(c['costo'])} por vuelta)" for c in ciclos]
