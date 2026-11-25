"""
distribucion_liquidez.py - Módulo 4: planificación y optimización de la
distribución de liquidez hacia bóvedas y agencias.

Modelo: RED DE FLUJO dirigida (Guía 11). Nodo = bóveda central, bóveda regional
o agencia. Arista = ruta de traslado con `capacidad` (miles de S/), `costo`
(S/ por mil trasladados) y `costo_habilitacion` (costo fijo de habilitar la ruta).

Como hay varias bóvedas y varias agencias se agregan:
  - SUPERFUENTE  S* -> cada bóveda, capacidad = oferta (efectivo disponible).
  - SUPERSUMIDERO cada agencia -> T*, capacidad = demanda.

Algoritmos:
- Edmonds-Karp (Guía 11)          -> flujo máximo con BFS.                O(V E^2)
- Ford-Fulkerson con DFS (Guía 11) -> para comparar con Edmonds-Karp.
- Corte mínimo (Guía 11)          -> cuellos de botella y validación (flujo = corte).
- Flujo de costo mínimo (Guías 9 y 11) -> caminos aumentantes de menor costo
                                     buscados con Bellman-Ford.          O(F V E)
- Prim y Kruskal (Guía 8)         -> red mínima de rutas a habilitar.     O(E log V)
- Voraz "agencia más cercana primero" (Guía 3) -> línea base para comparar.
"""

import heapq
import math
from collections import deque

from .utils import tabla, fmt_num, titulo

S_ESTRELLA, T_ESTRELLA = "S*", "T*"


# ------------------------------------------------------------ red residual
class RedFlujo:
    """Red residual con lista de aristas: cada arista guarda su arista inversa.
    Admite aristas paralelas y antiparalelas."""

    def __init__(self):
        self.g = {}          # nodo -> [índices de arista]
        self.aristas = []    # [destino, capacidad_residual, costo, origen]
        self.originales = []  # (índice, u, v, capacidad, costo)

    def nodo(self, u):
        self.g.setdefault(u, [])

    def agregar(self, u, v, capacidad, costo=0):
        self.nodo(u)
        self.nodo(v)
        self.g[u].append(len(self.aristas))
        self.aristas.append([v, capacidad, costo, u])
        self.g[v].append(len(self.aristas))
        self.aristas.append([u, 0, -costo, v])        # inversa (índice ^ 1)
        self.originales.append((len(self.aristas) - 2, u, v, capacidad, costo))

    def flujo(self, i):
        """Flujo que pasa por la arista original i = capacidad residual de su inversa."""
        return self.aristas[i ^ 1][1]

    def flujos(self):
        return [(u, v, self.flujo(i), c, w) for i, u, v, c, w in self.originales]


def construir_red(grafo, con_sumidero=True, filtro=None):
    """Construye la red de flujo con S* y T* a partir del grafo del Módulo 1."""
    red = RedFlujo()
    for n, at in grafo.nodos.items():
        red.nodo(n)
        if at.get("oferta", 0) > 0:
            red.agregar(S_ESTRELLA, n, at["oferta"], 0)
        if con_sumidero and at.get("demanda", 0) > 0:
            red.agregar(n, T_ESTRELLA, at["demanda"], 0)
    for u, v, a in grafo.aristas():
        if filtro and not filtro(u, v, a):
            continue
        red.agregar(u, v, a.get("capacidad", 0), a.get("costo", 0))
    red.nodo(S_ESTRELLA)
    red.nodo(T_ESTRELLA)
    return red


# ------------------------------------------------------------ flujo máximo
def _aumentar(red, s, t, buscar):
    total, caminos = 0, []
    while True:
        padre = buscar(red, s, t)
        if padre is None:
            break
        delta, v, ruta = math.inf, t, [t]
        while v != s:
            i = padre[v]
            delta = min(delta, red.aristas[i][1])
            v = red.aristas[i][3]
            ruta.append(v)
        v = t
        while v != s:
            i = padre[v]
            red.aristas[i][1] -= delta
            red.aristas[i ^ 1][1] += delta
            v = red.aristas[i][3]
        total += delta
        caminos.append((ruta[::-1], delta))
    return total, caminos


def _bfs(red, s, t):
    padre = {s: None}
    cola = deque([s])
    while cola:
        u = cola.popleft()
        for i in red.g[u]:
            v, cap = red.aristas[i][0], red.aristas[i][1]
            if cap > 0 and v not in padre:
                padre[v] = i
                if v == t:
                    return padre
                cola.append(v)
    return None


def _dfs(red, s, t):
    padre = {s: None}
    pila = [s]
    while pila:
        u = pila.pop()
        for i in red.g[u]:
            v, cap = red.aristas[i][0], red.aristas[i][1]
            if cap > 0 and v not in padre:
                padre[v] = i
                if v == t:
                    return padre
                pila.append(v)
    return None


def edmonds_karp(red, s=S_ESTRELLA, t=T_ESTRELLA):
    """Ford-Fulkerson eligiendo el camino aumentante con BFS (menos aristas)."""
    return _aumentar(red, s, t, _bfs)


def ford_fulkerson_dfs(red, s=S_ESTRELLA, t=T_ESTRELLA):
    """Ford-Fulkerson básico eligiendo el camino aumentante con DFS."""
    return _aumentar(red, s, t, _dfs)


def corte_minimo(red, s=S_ESTRELLA):
    """Nodos alcanzables desde s en la red residual final (conjunto S) y aristas
    originales que van de S a T. Su capacidad total es igual al flujo máximo."""
    S = {s}
    cola = deque([s])
    while cola:
        u = cola.popleft()
        for i in red.g[u]:
            v, cap = red.aristas[i][0], red.aristas[i][1]
            if cap > 0 and v not in S:
                S.add(v)
                cola.append(v)
    corte = [(u, v, c) for _, u, v, c, _ in red.originales if u in S and v not in S]
    return S, corte


def verificar_flujo(red, s=S_ESTRELLA, t=T_ESTRELLA):
    """Comprueba restricción de capacidad y conservación del flujo."""
    problemas = []
    balance = {n: 0 for n in red.g}
    for u, v, f, c, _ in red.flujos():
        if f < 0 or f > c:
            problemas.append(f"capacidad violada en {u}->{v}: flujo {f} de {c}")
        balance[u] -= f
        balance[v] += f
    for n, b in balance.items():
        if n not in (s, t) and abs(b) > 1e-9:
            problemas.append(f"conservación violada en {n}: entra - sale = {b}")
    return problemas


# ------------------------------------------------------------ costo mínimo
def flujo_costo_minimo(red, s=S_ESTRELLA, t=T_ESTRELLA, objetivo=None):
    """Caminos aumentantes de MENOR COSTO (Bellman-Ford sobre la red residual, que
    tiene costos negativos en las aristas inversas). Envía el flujo máximo (o
    `objetivo`) con el menor costo total. Devuelve (flujo, costo)."""
    flujo = costo_total = 0
    while objetivo is None or flujo < objetivo:
        dist = {n: math.inf for n in red.g}
        padre = {n: None for n in red.g}
        dist[s] = 0
        for _ in range(len(red.g) - 1):
            cambio = False
            for u in red.g:
                if dist[u] == math.inf:
                    continue
                for i in red.g[u]:
                    v, cap, w, _ = red.aristas[i]
                    if cap > 0 and dist[u] + w < dist[v]:
                        dist[v] = dist[u] + w
                        padre[v] = i
                        cambio = True
            if not cambio:
                break
        if dist[t] == math.inf:
            break
        delta, v = math.inf, t
        while v != s:
            i = padre[v]
            delta = min(delta, red.aristas[i][1])
            v = red.aristas[i][3]
        if objetivo is not None:
            delta = min(delta, objetivo - flujo)
        v = t
        while v != s:
            i = padre[v]
            red.aristas[i][1] -= delta
            red.aristas[i ^ 1][1] += delta
            v = red.aristas[i][3]
        flujo += delta
        costo_total += delta * dist[t]
    return flujo, costo_total


def costo_plan(red):
    return sum(f * w for _, _, f, _, w in red.flujos())


# ------------------------------------------------------------ voraz (línea base)
def voraz_mas_cercana(grafo):
    """Línea base voraz: atiende primero a la agencia más barata de alcanzar y le
    envía todo lo que pueda por su ruta más barata, sin corregir decisiones
    anteriores (no usa aristas inversas). Devuelve {agencia: recibido}."""
    red = construir_red(grafo, con_sumidero=False)
    agencias = {n: at["demanda"] for n, at in grafo.nodos.items() if at.get("demanda", 0) > 0}

    def mas_barata(destino):
        dist = {n: math.inf for n in red.g}
        padre = {}
        dist[S_ESTRELLA] = 0
        heap = [(0, S_ESTRELLA)]
        while heap:
            d, u = heapq.heappop(heap)
            if d > dist[u]:
                continue
            for i in red.g[u]:
                if i % 2:  # solo aristas originales (sin inversas): decisión irrevocable
                    continue
                v, cap, w, _ = red.aristas[i]
                if cap > 0 and d + w < dist[v]:
                    dist[v] = d + w
                    padre[v] = i
                    heapq.heappush(heap, (d + w, v))
        return dist, padre

    dist0, _ = mas_barata(None)
    orden = sorted(agencias, key=lambda a: (dist0[a], a))
    recibido = {a: 0 for a in agencias}
    for a in orden:
        while recibido[a] < agencias[a]:
            dist, padre = mas_barata(a)
            if dist[a] == math.inf:
                break
            delta, v = agencias[a] - recibido[a], a
            while v != S_ESTRELLA:
                i = padre[v]
                delta = min(delta, red.aristas[i][1])
                v = red.aristas[i][3]
            v = a
            while v != S_ESTRELLA:
                i = padre[v]
                red.aristas[i][1] -= delta
                red.aristas[i ^ 1][1] += delta
                v = red.aristas[i][3]
            recibido[a] += delta
    return recibido, orden, costo_plan(red)


# ------------------------------------------------------------ Prim / Kruskal
def _no_dirigido(grafo):
    return grafo.a_no_dirigido(peso=lambda a: a.get("costo_habilitacion", a.get("costo", 1)))


def prim(grafo):
    """Árbol (o bosque) de expansión mínima con Prim y heapq. O(E log V)."""
    g = _no_dirigido(grafo)
    visitado, arbol, total = set(), [], 0
    for inicio in g.nodos:
        if inicio in visitado:
            continue
        visitado.add(inicio)
        heap = [(a["peso"], inicio, v) for v, a in g.adj[inicio]]
        heapq.heapify(heap)
        while heap:
            w, u, v = heapq.heappop(heap)
            if v in visitado:
                continue
            visitado.add(v)
            arbol.append((u, v, w))
            total += w
            for x, a in g.adj[v]:
                if x not in visitado:
                    heapq.heappush(heap, (a["peso"], v, x))
    return arbol, total


def kruskal(grafo):
    """Árbol de expansión mínima con Kruskal y conjuntos disjuntos (union-find)."""
    g = _no_dirigido(grafo)
    padre = {n: n for n in g.nodos}
    rango = {n: 0 for n in g.nodos}

    def raiz(x):
        while padre[x] != x:
            padre[x] = padre[padre[x]]  # compresión de caminos
            x = padre[x]
        return x

    arbol, total = [], 0
    for u, v, a in sorted(g.aristas(), key=lambda e: e[2]["peso"]):
        ru, rv = raiz(u), raiz(v)
        if ru == rv:
            continue  # formaría ciclo
        if rango[ru] < rango[rv]:
            ru, rv = rv, ru
        padre[rv] = ru
        if rango[ru] == rango[rv]:
            rango[ru] += 1
        arbol.append((u, v, a["peso"]))
        total += a["peso"]
    return arbol, total


# ------------------------------------------------------------ análisis completo
def distribuir(grafo, algoritmo="edmonds_karp"):
    """Calcula el flujo máximo y arma el resultado completo del Módulo 4."""
    red = construir_red(grafo)
    total, caminos = (edmonds_karp if algoritmo == "edmonds_karp" else ford_fulkerson_dfs)(red)
    S, corte = corte_minimo(red)
    llega = {}
    for u, v, f, c, _ in red.flujos():
        if v == T_ESTRELLA:
            llega[u] = f
    agencias = []
    for n, at in grafo.nodos.items():
        if at.get("demanda", 0) > 0:
            rec = llega.get(n, 0)
            agencias.append({"agencia": n, "demanda": at["demanda"], "recibe": rec, "falta": at["demanda"] - rec})
    deficit = {a["agencia"] for a in agencias if a["falta"] > 0}
    # Cuellos relevantes: aristas saturadas aguas arriba de una agencia con déficit.
    pred = grafo.predecesores()
    cuellos = []
    for ag in sorted(deficit):
        arriba, pila = {ag}, [ag]
        while pila:
            x = pila.pop()
            for u, _ in pred[x]:
                if u not in arriba:
                    arriba.add(u)
                    pila.append(u)
        for u, v, f, c, _ in red.flujos():
            if u in arriba and v in arriba and c > 0 and f >= c and (u, v, ag) not in cuellos:
                cuellos.append((u, v, ag))
    oferta = sum(at.get("oferta", 0) for at in grafo.nodos.values())
    demanda = sum(at.get("demanda", 0) for at in grafo.nodos.values())
    return {
        "red": red, "flujo": total, "caminos": caminos, "S": S, "corte": corte,
        "capacidad_corte": sum(c for _, _, c in corte), "agencias": agencias,
        "cuellos": cuellos, "oferta": oferta, "demanda": demanda,
        "factible": total >= demanda, "costo": costo_plan(red),
        "verificacion": verificar_flujo(red), "algoritmo": algoritmo,
    }


def reporte_distribucion(grafo, res=None):
    res = res or distribuir(grafo)
    txt = titulo(f"Distribución de liquidez - {grafo.nombre} (Edmonds-Karp, miles de S/)")
    txt += (f"\nOferta total: {fmt_num(res['oferta'])}   Demanda total: {fmt_num(res['demanda'])}   "
            f"Flujo máximo: {fmt_num(res['flujo'])}\n")
    txt += ("Plan FACTIBLE: se cubre toda la demanda.\n" if res["factible"]
            else f"Plan NO factible: faltan {fmt_num(res['demanda'] - res['flujo'])}.\n")
    txt += "\nCaminos aumentantes encontrados (BFS):\n"
    txt += "".join(f"  {i}. {' -> '.join(r)}   +{fmt_num(d)}\n" for i, (r, d) in enumerate(res["caminos"], 1))
    txt += "\nCantidades por ruta:\n"
    filas = [[u, v, fmt_num(f), fmt_num(c), f"{100 * f / c:.0f} %" if c else "-", "saturada" if c and f >= c else ""]
             for u, v, f, c, _ in res["red"].flujos() if S_ESTRELLA not in (u, v) and T_ESTRELLA not in (u, v)]
    txt += tabla(["origen", "destino", "flujo", "capacidad", "uso", ""], filas)
    txt += "\n\nAbastecimiento por agencia:\n"
    filas = [[a["agencia"], fmt_num(a["demanda"]), fmt_num(a["recibe"]), fmt_num(a["falta"]),
              "cubierta" if a["falta"] == 0 else "PENDIENTE"] for a in res["agencias"]]
    txt += tabla(["agencia", "demanda", "recibe", "falta", "estado"], filas)
    txt += (f"\n\nCorte mínimo: {' + '.join(f'{u}->{v} ({fmt_num(c)})' for u, v, c in res['corte'])} "
            f"= {fmt_num(res['capacidad_corte'])}")
    txt += (f"\nTeorema flujo máximo = corte mínimo: {fmt_num(res['flujo'])} = {fmt_num(res['capacidad_corte'])} -> "
            f"{'VERIFICADO' if abs(res['flujo'] - res['capacidad_corte']) < 1e-9 else 'NO COINCIDE'}")
    if res["cuellos"]:
        txt += "\n\nCuellos de botella relevantes (tramos saturados que alimentan agencias con déficit):\n"
        txt += "".join(f"  - {u}->{v} (limita a {ag})\n" for u, v, ag in res["cuellos"])
    txt += ("\nVerificación de capacidad y conservación del flujo: "
            + ("OK" if not res["verificacion"] else "; ".join(res["verificacion"])))
    txt += f"\nCosto del plan obtenido (sin optimizar costos): S/ {fmt_num(res['costo'])}"
    return txt


def reporte_costo_minimo(grafo):
    base = distribuir(grafo)
    red = construir_red(grafo)
    flujo, costo = flujo_costo_minimo(red)
    txt = titulo("Plan de traslado de costo mínimo (Bellman-Ford sobre la red residual)")
    txt += f"\nFlujo enviado: {fmt_num(flujo)} (flujo máximo de Edmonds-Karp: {fmt_num(base['flujo'])})"
    txt += f"\nCosto del plan de Edmonds-Karp: S/ {fmt_num(base['costo'])}"
    txt += f"\nCosto del plan de costo mínimo: S/ {fmt_num(costo)}"
    ahorro = base["costo"] - costo
    txt += f"\nAhorro: S/ {fmt_num(ahorro)}" + (f" ({100 * ahorro / base['costo']:.1f} %)" if base["costo"] else "")
    filas = [[u, v, fmt_num(f), fmt_num(c), fmt_num(w)] for u, v, f, c, w in red.flujos()
             if S_ESTRELLA not in (u, v) and T_ESTRELLA not in (u, v) and f > 0]
    txt += "\n\nRutas usadas en el plan de costo mínimo:\n" + tabla(["origen", "destino", "flujo", "capacidad", "costo/u"], filas)
    return txt


def reporte_voraz(grafo):
    base = distribuir(grafo)
    recibido, orden, costo = voraz_mas_cercana(grafo)
    total = sum(recibido.values())
    txt = titulo("Comparación: voraz 'agencia más cercana primero' vs flujo máximo")
    txt += f"\nOrden de atención del voraz: {', '.join(orden)}\n"
    filas = []
    ek = {a["agencia"]: a["recibe"] for a in base["agencias"]}
    dem = {a["agencia"]: a["demanda"] for a in base["agencias"]}
    for a in orden:
        filas.append([a, fmt_num(dem[a]), fmt_num(recibido[a]), fmt_num(ek[a])])
    txt += tabla(["agencia", "demanda", "voraz", "flujo máximo"], filas)
    txt += f"\n\nTotal entregado -> voraz: {fmt_num(total)}   flujo máximo: {fmt_num(base['flujo'])}"
    if total < base["flujo"]:
        txt += (f"\nEl voraz deja de entregar {fmt_num(base['flujo'] - total)}: al no poder corregir decisiones "
                "anteriores (no usa aristas inversas), una agencia atendida primero consume capacidad que otra necesitaba.")
    else:
        txt += "\nEn esta red el voraz alcanza el óptimo, pero no está garantizado en general."
    return txt


def reporte_mst(grafo):
    ap, cp = prim(grafo)
    ak, ck = kruskal(grafo)
    pares = {frozenset((u, v)) for u, v, _ in ak}
    completo = distribuir(grafo)["flujo"]
    red = construir_red(grafo, filtro=lambda u, v, a: frozenset((u, v)) in pares)
    en_arbol, _ = edmonds_karp(red)
    txt = titulo("Red mínima de rutas a habilitar (Prim / Kruskal sobre costo_habilitacion)")
    txt += "\nAristas del árbol (Kruskal):\n" + tabla(["ruta", "", "costo habilitación"],
                                                     [[u, v, fmt_num(w)] for u, v, w in ak])
    txt += f"\n\nCosto total Prim: {fmt_num(cp)}   Kruskal: {fmt_num(ck)}   Coinciden: {'SÍ' if abs(cp - ck) < 1e-9 else 'NO'}"
    txt += f"\n\nFlujo máximo en la red completa: {fmt_num(completo)}"
    txt += f"\nFlujo máximo usando solo las rutas del árbol: {fmt_num(en_arbol)}"
    if en_arbol < completo:
        txt += (f"\nSe pierden {fmt_num(completo - en_arbol)} de capacidad: el árbol deja un solo camino entre cada "
                "par de puntos y no considera capacidades ni la dirección de los traslados.")
    return txt
