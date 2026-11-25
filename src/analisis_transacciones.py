"""
analisis_transacciones.py - Módulo 2: análisis de transacciones y detección de
operaciones sospechosas (prevención de fraude y lavado de activos).

Modelo: grafo DIRIGIDO con aristas MÚLTIPLES. Nodo = cuenta o cliente; arista =
una transferencia con atributos `monto`, `fecha` y `canal`.

Algoritmos:
- BFS (Guía 7)                          -> proximidad entre cuentas.          O(V + E)
- DFS con restricción temporal (Guía 7) -> rastreo de fondos en orden.        O(V + E) por cadena;
                                           la enumeración se acota por profundidad.
- Tarjan y Kosaraju (Guía 7)            -> grupos donde el dinero circula.    O(V + E)
- Condensación + orden topológico       -> capas origen -> intermediarios.    O(V + E)
- Ordenamiento + ventana (Guía 2)       -> fraccionamiento (abanicos).        O(E log E)
- Suma de subconjuntos (Guía 5, PD)     -> montos que reconstruyen uno mayor. O(n * S)
- Heap / heapq (Guía 2)                 -> cuentas a revisar primero.         O(V log k)

IMPORTANTE: los patrones son indicadores para revisión; no prueban fraude.
"""

import heapq
import sys
from collections import deque

from .utils import fecha, dias_entre, tabla, fmt_num, titulo

sys.setrecursionlimit(max(10000, sys.getrecursionlimit()))

UMBRAL_REPORTE = 10000  # S/. Parámetro configurable (ver normativa de la UIF-Perú)


# --------------------------------------------------------------------- BFS
def bfs_proximidad(grafo, origen, max_nivel=None, ambos_sentidos=True):
    """BFS desde `origen`. Devuelve {nodo: (nivel, padre)}.

    El nivel es el número de saltos (intermediarios + 1). Con ambos_sentidos=True
    se considera relacionada una cuenta que envía o que recibe dinero.
    """
    vecinos = _vecinos_relacion(grafo, ambos_sentidos)
    visitado = {origen: (0, None)}
    cola = deque([origen])
    while cola:
        u = cola.popleft()
        nivel = visitado[u][0]
        if max_nivel is not None and nivel >= max_nivel:
            continue
        for v in vecinos[u]:
            if v not in visitado:
                visitado[v] = (nivel + 1, u)
                cola.append(v)
    return visitado


def camino_bfs(resultado, destino):
    if destino not in resultado:
        return None
    camino = []
    while destino is not None:
        camino.append(destino)
        destino = resultado[destino][1]
    return camino[::-1]


def _vecinos_relacion(grafo, ambos_sentidos):
    vec = {n: [] for n in grafo.nodos}
    for u in grafo.adj:
        for v, _ in grafo.adj[u]:
            if v not in vec[u]:
                vec[u].append(v)
            if ambos_sentidos and u not in vec[v]:
                vec[v].append(u)
    return vec


# --------------------------------------------------------- DFS temporal
def rastrear_fondos(grafo, origen, ventana_dias=7, max_profundidad=8, max_cadenas=300):
    """DFS que sigue el dinero respetando el orden de las fechas.

    Desde una transferencia de fecha f solo se continúa por transferencias con
    fecha en [f, f + ventana_dias]. Así se evitan cadenas imposibles (usar dinero
    antes de recibirlo). Devuelve las cadenas maximales como listas de
    (origen, destino, monto, fecha). Si una cadena vuelve a `origen` se marca
    como ciclo.
    """
    cadenas = []

    def dfs(u, fecha_actual, camino, en_camino):
        if len(cadenas) >= max_cadenas:
            return
        extendida = False
        if len(camino) < max_profundidad:
            salidas = sorted(grafo.adj[u], key=lambda x: str(x[1].get("fecha", "")))
            for v, a in salidas:
                f = a.get("fecha")
                if f is None:
                    continue
                if fecha_actual is not None:
                    d = dias_entre(fecha_actual, f)
                    if d < 0 or d > ventana_dias:
                        continue
                paso = (u, v, a.get("monto", 0), str(f))
                if v == origen and camino:
                    cadenas.append({"pasos": camino + [paso], "ciclo": True})
                    extendida = True
                    continue
                if v in en_camino:
                    continue
                extendida = True
                en_camino.add(v)
                dfs(v, f, camino + [paso], en_camino)
                en_camino.discard(v)
        if not extendida and camino:
            cadenas.append({"pasos": camino, "ciclo": False})

    dfs(origen, None, [], {origen})
    return cadenas


# ------------------------------------------------------------ Tarjan / Kosaraju
def tarjan_scc(grafo):
    """Componentes fuertemente conexas (Tarjan). Una sola pasada DFS. O(V + E)."""
    indice, bajo, en_pila = {}, {}, set()
    pila, comps = [], []
    contador = [0]

    def visitar(u):
        indice[u] = bajo[u] = contador[0]
        contador[0] += 1
        pila.append(u)
        en_pila.add(u)
        for v, _ in grafo.adj[u]:
            if v not in indice:
                visitar(v)
                bajo[u] = min(bajo[u], bajo[v])
            elif v in en_pila:
                bajo[u] = min(bajo[u], indice[v])
        if bajo[u] == indice[u]:
            comp = []
            while True:
                w = pila.pop()
                en_pila.discard(w)
                comp.append(w)
                if w == u:
                    break
            comps.append(sorted(comp))

    for n in grafo.nodos:
        if n not in indice:
            visitar(n)
    return comps


def kosaraju_scc(grafo):
    """Componentes fuertemente conexas (Kosaraju). Dos pasadas DFS. O(V + E)."""
    visto, orden = set(), []

    def dfs1(u):
        visto.add(u)
        for v, _ in grafo.adj[u]:
            if v not in visto:
                dfs1(v)
        orden.append(u)

    for n in grafo.nodos:
        if n not in visto:
            dfs1(n)
    inv = {n: [] for n in grafo.nodos}
    for u in grafo.adj:
        for v, _ in grafo.adj[u]:
            inv[v].append(u)
    asignado, comps = set(), []

    def dfs2(u, comp):
        asignado.add(u)
        comp.append(u)
        for v in inv[u]:
            if v not in asignado:
                dfs2(v, comp)

    for u in reversed(orden):
        if u not in asignado:
            comp = []
            dfs2(u, comp)
            comps.append(sorted(comp))
    return comps


def grupos_circulacion(comps, grafo=None):
    """Componentes de más de una cuenta (o con bucle): el dinero puede volver."""
    res = [c for c in comps if len(c) > 1]
    if grafo is not None:
        res += [[u] for u in grafo.adj for v, _ in grafo.adj[u] if v == u and [u] not in res]
    return res


# ------------------------------------------------ condensación + topológico
def condensacion(grafo, comps):
    """Comprime cada componente en un nodo. El resultado es un DAG."""
    comp_de = {n: i for i, c in enumerate(comps) for n in c}
    dag = {i: set() for i in range(len(comps))}
    for u in grafo.adj:
        for v, _ in grafo.adj[u]:
            if comp_de[u] != comp_de[v]:
                dag[comp_de[u]].add(comp_de[v])
    return comp_de, dag


def capas_topologicas(dag):
    """Orden topológico por capas (algoritmo de Kahn). Capa 0 = orígenes."""
    grado = {i: 0 for i in dag}
    for u in dag:
        for v in dag[u]:
            grado[v] += 1
    capa = [i for i in dag if grado[i] == 0]
    capas = []
    while capa:
        capas.append(sorted(capa))
        siguiente = []
        for u in capa:
            for v in dag[u]:
                grado[v] -= 1
                if grado[v] == 0:
                    siguiente.append(v)
        capa = siguiente
    return capas


def capas_desde(grafo, origen):
    """Capas del recorrido del dinero que sale de `origen` (sobre la condensación)."""
    comps = tarjan_scc(grafo)
    comp_de, dag = condensacion(grafo, comps)
    alcanzables = set()
    pila = [comp_de[origen]]
    while pila:
        c = pila.pop()
        if c in alcanzables:
            continue
        alcanzables.add(c)
        pila.extend(dag[c])
    sub = {c: {d for d in dag[c] if d in alcanzables} for c in alcanzables}
    return [[comps[c] for c in capa] for capa in capas_topologicas(sub)]


# --------------------------------------------------------- fraccionamiento
def transferencias(grafo):
    """Lista de transferencias (origen, destino, monto, fecha) ordenada por fecha."""
    lista = [(u, v, a.get("monto", 0), fecha(a["fecha"])) for u, v, a in grafo.aristas() if "fecha" in a]
    lista.sort(key=lambda t: t[3])  # Guía 2: ordenamiento O(E log E)
    return lista


def detectar_abanicos(grafo, umbral=UMBRAL_REPORTE, pct_min=0.8, ventana_dias=3, min_contrapartes=3):
    """Detecta abanicos de ENTRADA (muchas cuentas envían a una) y de SALIDA (una
    envía a muchas) con montos justo por debajo del umbral, dentro de una ventana
    de días. Usa transferencias ordenadas por fecha y dos punteros.
    """
    trs = [t for t in transferencias(grafo) if umbral * pct_min <= t[2] < umbral]
    por_cuenta = {"entrada": {}, "salida": {}}
    for u, v, m, f in trs:
        por_cuenta["salida"].setdefault(u, []).append((v, m, f))
        por_cuenta["entrada"].setdefault(v, []).append((u, m, f))
    alertas = []
    for tipo, mapa in por_cuenta.items():
        for cuenta, movs in mapa.items():
            mejor = None
            i = 0
            for j in range(len(movs)):  # ventana deslizante
                while (movs[j][2] - movs[i][2]).days > ventana_dias:
                    i += 1
                ventana = movs[i:j + 1]
                contrapartes = {c for c, _, _ in ventana}
                if len(contrapartes) >= min_contrapartes and (mejor is None or len(ventana) > len(mejor)):
                    mejor = ventana
            if mejor:
                alertas.append({
                    "tipo": tipo, "cuenta": cuenta,
                    "contrapartes": sorted({c for c, _, _ in mejor}),
                    "montos": [m for _, m, _ in mejor],
                    "total": sum(m for _, m, _ in mejor),
                    "desde": str(mejor[0][2]), "hasta": str(mejor[-1][2]),
                })
    alertas.sort(key=lambda a: (-len(a["montos"]), a["cuenta"]))
    return alertas


def suma_subconjuntos(montos, objetivo, tolerancia=0.0):
    """Programación dinámica (Guía 5): ¿existe un subconjunto de `montos` cuya
    suma esté en [objetivo, objetivo * (1 + tolerancia)]?

    Estado: alcanzable[s] = índice del último monto usado para llegar a la suma s.
    Complejidad O(n * S) en tiempo y O(S) en memoria, con S = objetivo máximo.
    Devuelve la lista de montos elegidos o None.
    """
    montos = [int(round(m)) for m in montos]
    maximo = int(objetivo * (1 + tolerancia))
    padre = [None] * (maximo + 1)  # padre[s] = (suma_anterior, índice)
    alcanzable = [False] * (maximo + 1)
    alcanzable[0] = True
    for i, m in enumerate(montos):
        for s in range(maximo, m - 1, -1):  # de mayor a menor: cada monto se usa una vez
            if not alcanzable[s] and alcanzable[s - m]:
                alcanzable[s] = True
                padre[s] = (s - m, i)
    for s in range(int(objetivo), maximo + 1):
        if alcanzable[s] and s > 0:
            elegidos = []
            while s > 0:
                anterior, i = padre[s]
                elegidos.append(montos[i])
                s = anterior
            return sorted(elegidos)
    return None


def verificar_reconstruccion(grafo, alerta, umbral=UMBRAL_REPORTE, tolerancia=0.05, dias_despues=5):
    """Para un abanico de ENTRADA: ¿la cuenta envía luego un monto grande que se
    reconstruye con las transferencias pequeñas recibidas?"""
    if alerta["tipo"] != "entrada":
        return None
    cuenta = alerta["cuenta"]
    desde = fecha(alerta["desde"])
    for v, a in grafo.adj[cuenta]:
        m = a.get("monto", 0)
        if m >= umbral and "fecha" in a and 0 <= (fecha(a["fecha"]) - desde).days <= dias_despues + 3:
            sub = suma_subconjuntos(alerta["montos"], m, tolerancia)
            if sub:
                return {"cuenta": cuenta, "destino": v, "monto_salida": m, "fecha": a["fecha"],
                        "montos_usados": sub, "suma": sum(sub)}
    return None


# -------------------------------------------------------------- puntaje
def puntajes(grafo, marcadas=(), umbral=UMBRAL_REPORTE, ventana_dias=3, cadena_min=4):
    """Combina los indicadores en un puntaje por cuenta y devuelve
    {cuenta: (puntaje, [motivos])}."""
    pts = {}

    def sumar(c, p, motivo):
        actual = pts.setdefault(c, [0, []])
        if motivo not in actual[1]:  # cada motivo suma una sola vez
            actual[0] += p
            actual[1].append(motivo)

    for comp in grupos_circulacion(tarjan_scc(grafo), grafo):
        for c in comp:
            sumar(c, 3, f"ciclo de {len(comp)} cuentas")
    for al in detectar_abanicos(grafo, umbral, ventana_dias=ventana_dias):
        sumar(al["cuenta"], 2, f"abanico de {al['tipo']} ({len(al['montos'])} transf.)")
        for c in al["contrapartes"]:
            sumar(c, 1, f"participa en abanico de {al['cuenta']}")
        rec = verificar_reconstruccion(grafo, al, umbral)
        if rec:
            sumar(al["cuenta"], 2, f"reenvía {fmt_num(rec['monto_salida'])} armado con montos pequeños")
    entradas = {n: 0 for n in grafo.nodos}
    for u in grafo.adj:
        for v, _ in grafo.adj[u]:
            entradas[v] += 1
    for n in grafo.nodos:
        if entradas[n] == 0 and grafo.adj[n]:
            for cad in rastrear_fondos(grafo, n, ventana_dias=7, max_profundidad=cadena_min + 4, max_cadenas=50):
                if len(cad["pasos"]) >= cadena_min and es_estratificacion(cad["pasos"]):
                    motivo = f"cadena de {len(cad['pasos'])} transferencias sucesivas (reenvía >= 90 %)"
                    for u, v, _, _ in cad["pasos"]:
                        sumar(u, 2, motivo)
                    sumar(cad["pasos"][-1][1], 2, motivo)
    for m in marcadas:
        if m in grafo.nodos:
            for n, (nivel, _) in bfs_proximidad(grafo, m, max_nivel=2).items():
                if n != m:
                    sumar(n, 1, f"a {nivel} salto(s) de la cuenta marcada {m}")
    return {c: (p, mot) for c, (p, mot) in pts.items()}


def es_estratificacion(pasos, retencion_min=0.9):
    """Cadena de transferencias sucesivas donde cada cuenta reenvía casi todo lo
    recibido (entre 90 % y 100 %): patrón típico de estratificación (layering)."""
    for (_, _, m1, _), (_, _, m2, _) in zip(pasos, pasos[1:]):
        if not (m1 > 0 and retencion_min <= m2 / m1 <= 1.0):
            return False
    return True


def top_k(puntos, k=10):
    """Las k cuentas con mayor puntaje usando un heap (heapq.nlargest). O(V log k)."""
    return heapq.nlargest(k, puntos.items(), key=lambda it: (it[1][0], it[0]))


# ---------------------------------------------------------------- reportes
def reporte_proximidad(grafo, origen, max_nivel=3):
    res = bfs_proximidad(grafo, origen, max_nivel)
    filas = sorted(((n, nivel, " -> ".join(camino_bfs(res, n))) for n, (nivel, _) in res.items() if n != origen),
                   key=lambda f: (f[1], f[0]))
    txt = titulo(f"Proximidad desde {origen} (BFS, hasta {max_nivel} saltos)")
    txt += f"\nCuentas relacionadas: {len(filas)}\n\n"
    txt += tabla(["cuenta", "saltos", "camino"], filas) if filas else "Sin relaciones."
    return txt


def reporte_rastreo(grafo, origen, ventana_dias=7, max_profundidad=8):
    cadenas = rastrear_fondos(grafo, origen, ventana_dias, max_profundidad)
    txt = titulo(f"Rastreo de fondos desde {origen} (DFS temporal, ventana {ventana_dias} días)")
    if not cadenas:
        return txt + "\nNo hay transferencias salientes con fecha."
    cadenas.sort(key=lambda c: (-c["ciclo"], -len(c["pasos"])))
    for i, c in enumerate(cadenas[:25], 1):
        marca = "  [CICLO: el dinero vuelve al origen]" if c["ciclo"] else ""
        txt += f"\nCadena {i} ({len(c['pasos'])} transferencias){marca}\n"
        for u, v, m, f in c["pasos"]:
            txt += f"   {f}  {u:>8} -> {v:<8} S/ {fmt_num(m)}\n"
    if len(cadenas) > 25:
        txt += f"\n... y {len(cadenas) - 25} cadenas más."
    return txt


def reporte_circulacion(grafo, origen=None):
    t = tarjan_scc(grafo)
    k = kosaraju_scc(grafo)
    grupos = grupos_circulacion(t, grafo)
    iguales = sorted(map(tuple, t)) == sorted(map(tuple, k))
    txt = titulo("Grupos de cuentas con circulación de fondos (Tarjan / Kosaraju)")
    txt += f"\nComponentes fuertemente conexas: {len(t)}   Tarjan y Kosaraju coinciden: {'SÍ' if iguales else 'NO'}\n"
    if not grupos:
        txt += "\nNo se encontraron grupos donde el dinero circule."
    for i, g in enumerate(grupos, 1):
        txt += f"\nGrupo {i} ({len(g)} cuentas): {', '.join(g)}"
    if origen:
        txt += f"\n\nCapas del recorrido desde {origen} (condensación + orden topológico):\n"
        for i, capa in enumerate(capas_desde(grafo, origen)):
            txt += f"  Capa {i}: " + " | ".join("{" + ", ".join(c) + "}" if len(c) > 1 else c[0] for c in capa) + "\n"
    return txt


def reporte_fraccionamiento(grafo, umbral=UMBRAL_REPORTE, ventana_dias=3, min_contrapartes=3):
    alertas = detectar_abanicos(grafo, umbral, ventana_dias=ventana_dias, min_contrapartes=min_contrapartes)
    txt = titulo(f"Operaciones fragmentadas (montos entre {fmt_num(umbral * 0.8)} y {fmt_num(umbral)}, "
                 f"ventana {ventana_dias} días)")
    if not alertas:
        return txt + "\nNo se detectaron abanicos."
    filas = [[a["tipo"], a["cuenta"], len(a["montos"]), fmt_num(a["total"]), f"{a['desde']} a {a['hasta']}",
              ", ".join(a["contrapartes"])] for a in alertas]
    txt += "\n" + tabla(["abanico", "cuenta", "transf.", "total S/", "periodo", "contrapartes"], filas)
    for a in alertas:
        rec = verificar_reconstruccion(grafo, a, umbral)
        if rec:
            dif = rec["suma"] - rec["monto_salida"]
            txt += (f"\n\nSuma de subconjuntos: {rec['cuenta']} envía S/ {fmt_num(rec['monto_salida'])} a "
                    f"{rec['destino']} el {rec['fecha']}, monto que se arma con "
                    f"{len(rec['montos_usados'])} transferencias recibidas: "
                    f"{' + '.join(fmt_num(m) for m in rec['montos_usados'])} = {fmt_num(rec['suma'])}"
                    + (" (coincidencia exacta)" if dif == 0 else f" (retiene S/ {fmt_num(dif)}, posible comisión)"))
    return txt


def reporte_revision(grafo, k=10, marcadas=(), alertas_ruleteo=()):
    pts = puntajes(grafo, marcadas)
    mejores = top_k(pts, k)
    txt = titulo(f"Cuentas a revisar primero (top {k} por puntaje, heap)")
    filas = [[i, c, p, "; ".join(m)] for i, (c, (p, m)) in enumerate(mejores, 1)]
    txt += "\n" + (tabla(["#", "cuenta", "puntaje", "motivos"], filas) if filas else "Sin indicadores.")
    if alertas_ruleteo:
        txt += "\n\nAlertas de ruleteo recibidas del Módulo 3:\n"
        for al in alertas_ruleteo:
            txt += f"  - {al}\n"
    txt += ("\n\nNota: los patrones son INDICADORES PARA REVISIÓN. Su detección no prueba por sí sola "
            "fraude ni lavado de activos; la decisión corresponde a auditoría.")
    return txt
