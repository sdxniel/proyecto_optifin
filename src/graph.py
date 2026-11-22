"""
graph.py - Estructura de datos común para representar las redes financieras.

Representación elegida: LISTA DE ADYACENCIA con atributos por arista.

    adj = {
        "A": [("B", {"monto": 9800, "fecha": "2026-10-01"}), ...],
        "B": [...],
    }

Justificación:
- Las redes financieras son dispersas (una cuenta no está conectada con todas las
  demás), así que la lista de adyacencia usa memoria O(V + E) frente a O(V^2) de
  una matriz.
- Recorrer los vecinos de un nodo cuesta O(grado), que es lo que necesitan BFS,
  DFS, Dijkstra, Bellman-Ford y Edmonds-Karp.
- Cada arista guarda un DICCIONARIO de atributos (comisión, tiempo, riesgo,
  capacidad, monto, fecha...). Cada módulo elige qué atributo usa como peso, de
  modo que los tres escenarios comparten la misma estructura.
- Cuando un algoritmo necesita otra representación (matriz para Floyd-Warshall,
  grafo no dirigido para Prim/Kruskal) se obtiene con un método de conversión.
"""

import copy
import math

# Atributos que deben ser numéricos y no negativos.
ATRIBUTOS_NUMERICOS = {
    "monto", "comision", "comision_fija", "comision_pct", "tiempo", "riesgo",
    "capacidad", "costo", "costo_habilitacion", "limite", "friccion",
    "C", "T", "R", "I", "V", "cashback", "cashback_soles", "peso",
    "oferta", "demanda", "x", "y",
}
# Atributos que pueden ser negativos (coordenadas de dibujo).
ATRIBUTOS_CON_SIGNO = {"x", "y"}


class ErrorGrafo(ValueError):
    """Error de validación al construir o modificar un grafo."""


class Grafo:
    """Grafo dirigido o no dirigido, ponderado o no, con atributos por arista."""

    def __init__(self, dirigido=True, ponderado=True, multiarista=False, nombre="red"):
        self.dirigido = dirigido
        self.ponderado = ponderado
        # multiarista=True permite varias aristas entre el mismo par de nodos
        # (por ejemplo, dos transferencias A->B en fechas distintas).
        self.multiarista = multiarista
        self.nombre = nombre
        self.nodos = {}  # id -> {"tipo": ..., otros atributos}
        self.adj = {}    # id -> [(destino, atributos), ...]

    # ------------------------------------------------------------------ nodos
    def agregar_nodo(self, nodo, tipo="generico", **atributos):
        nodo = str(nodo).strip()
        if not nodo:
            raise ErrorGrafo("El identificador del nodo no puede estar vacío.")
        if nodo in self.nodos:
            raise ErrorGrafo(f"El nodo '{nodo}' ya existe.")
        _validar_valores(atributos, f"nodo {nodo}")
        self.nodos[nodo] = {"tipo": tipo, **atributos}
        self.adj[nodo] = []
        return nodo

    def asegurar_nodo(self, nodo, tipo="generico"):
        """Crea el nodo solo si no existe."""
        if nodo not in self.nodos:
            self.agregar_nodo(nodo, tipo)

    def modificar_nodo(self, nodo, **atributos):
        self._existe(nodo)
        _validar_valores(atributos, f"nodo {nodo}")
        self.nodos[nodo].update(atributos)

    def eliminar_nodo(self, nodo):
        """Elimina el nodo y todas las aristas que entran o salen de él. O(V + E)."""
        self._existe(nodo)
        del self.nodos[nodo]
        del self.adj[nodo]
        for u in self.adj:
            self.adj[u] = [(v, a) for v, a in self.adj[u] if v != nodo]

    def tiene_nodo(self, nodo):
        return nodo in self.nodos

    # ---------------------------------------------------------------- aristas
    def agregar_arista(self, u, v, **atributos):
        """Agrega la arista u -> v (y v -> u si el grafo es no dirigido).

        Valida que ambos nodos existan, que los valores numéricos sean válidos y
        que no se cree una arista duplicada sin justificación.
        """
        self._existe(u)
        self._existe(v)
        _validar_valores(atributos, f"arista {u}->{v}")
        if self.ponderado and not atributos:
            raise ErrorGrafo(f"La arista {u}->{v} no tiene peso y el grafo es ponderado.")
        existentes = [a for w, a in self.adj[u] if w == v]
        if existentes:
            if not self.multiarista:
                raise ErrorGrafo(f"Arista duplicada {u}->{v}: el grafo no admite aristas múltiples.")
            if any(a == atributos for a in existentes):
                raise ErrorGrafo(
                    f"Arista duplicada no justificada {u}->{v}: ya existe otra con los mismos atributos.")
        self.adj[u].append((v, dict(atributos)))
        if not self.dirigido and u != v:
            self.adj[v].append((u, dict(atributos)))

    def eliminar_arista(self, u, v, indice=0):
        """Elimina la arista u -> v número `indice` (si hay varias)."""
        posiciones = [i for i, (w, _) in enumerate(self.adj.get(u, [])) if w == v]
        if not posiciones or indice >= len(posiciones):
            raise ErrorGrafo(f"No existe la arista {u}->{v} (índice {indice}).")
        _, atributos = self.adj[u].pop(posiciones[indice])
        if not self.dirigido and u != v:
            for i, (w, a) in enumerate(self.adj[v]):
                if w == u and a == atributos:
                    self.adj[v].pop(i)
                    break

    def modificar_arista(self, u, v, indice=0, **atributos):
        _validar_valores(atributos, f"arista {u}->{v}")
        posiciones = [i for i, (w, _) in enumerate(self.adj.get(u, [])) if w == v]
        if not posiciones or indice >= len(posiciones):
            raise ErrorGrafo(f"No existe la arista {u}->{v} (índice {indice}).")
        anterior = dict(self.adj[u][posiciones[indice]][1])
        self.adj[u][posiciones[indice]][1].update(atributos)
        if not self.dirigido and u != v:
            for w, a in self.adj[v]:
                if w == u and a == anterior:
                    a.update(atributos)
                    break

    def aristas_entre(self, u, v):
        return [a for w, a in self.adj.get(u, []) if w == v]

    def vecinos(self, u):
        self._existe(u)
        return self.adj[u]

    def aristas(self):
        """Itera (u, v, atributos). En grafos no dirigidos cada arista sale una vez."""
        vistos = set()
        for u in self.adj:
            for v, a in self.adj[u]:
                if not self.dirigido:
                    par = (min(u, v), max(u, v), tuple(sorted(a.items(), key=str)))
                    if par in vistos:
                        continue
                    vistos.add(par)
                yield u, v, a

    def predecesores(self):
        """Devuelve {nodo: [(origen, atributos), ...]} (lista de adyacencia inversa)."""
        inv = {n: [] for n in self.nodos}
        for u in self.adj:
            for v, a in self.adj[u]:
                inv[v].append((u, a))
        return inv

    # ---------------------------------------------------------------- medidas
    def num_nodos(self):
        return len(self.nodos)

    def num_aristas(self):
        return sum(1 for _ in self.aristas())

    def grado_salida(self, u):
        return len(self.adj[u])

    # ------------------------------------------------------------ conversiones
    def a_matriz(self, peso="peso", orden=None):
        """Matriz de adyacencia n x n (inf si no hay arista, 0 en la diagonal).

        `peso` es el nombre de un atributo o una función f(atributos) -> número.
        Si hay aristas múltiples se toma la de menor peso.
        """
        orden = list(orden or self.nodos)
        idx = {n: i for i, n in enumerate(orden)}
        n = len(orden)
        m = [[math.inf] * n for _ in range(n)]
        for i in range(n):
            m[i][i] = 0
        f = _funcion_peso(peso)
        for u, v, a in self.aristas():
            if u not in idx or v not in idx:
                continue
            w = f(a)
            i, j = idx[u], idx[v]
            if i == j:
                m[i][i] = min(m[i][i], w)
            elif w < m[i][j]:
                m[i][j] = w
            if not self.dirigido and w < m[j][i]:
                m[j][i] = w
        return orden, m

    def a_no_dirigido(self, peso="peso"):
        """Versión no dirigida (para Prim/Kruskal). Conserva el menor peso de cada par."""
        g = Grafo(dirigido=False, ponderado=True, nombre=self.nombre + " (no dirigido)")
        for n, at in self.nodos.items():
            g.agregar_nodo(n, **at)
        f = _funcion_peso(peso)
        mejor = {}
        for u, v, a in self.aristas():
            if u == v:
                continue
            par = tuple(sorted((u, v)))
            w = f(a)
            if par not in mejor or w < mejor[par]:
                mejor[par] = w
        for (u, v), w in mejor.items():
            g.agregar_arista(u, v, peso=w)
        return g

    def subgrafo(self, filtro_arista=None, nodos=None):
        """Copia con solo las aristas que cumplen filtro_arista(u, v, atributos)."""
        g = Grafo(self.dirigido, self.ponderado, self.multiarista, self.nombre)
        conservar = set(nodos) if nodos is not None else set(self.nodos)
        for n, at in self.nodos.items():
            if n in conservar:
                g.nodos[n] = dict(at)
                g.adj[n] = []
        for u in self.adj:
            if u not in conservar:
                continue
            for v, a in self.adj[u]:
                if v in conservar and (filtro_arista is None or filtro_arista(u, v, a)):
                    g.adj[u].append((v, dict(a)))
        return g

    def copia(self):
        return copy.deepcopy(self)

    # -------------------------------------------------------------- validación
    def validar(self):
        """Revisa la consistencia de la red. Devuelve una lista de observaciones."""
        obs = []
        for u in self.adj:
            if u not in self.nodos:
                obs.append(f"ERROR: lista de adyacencia de un nodo inexistente '{u}'.")
            vistos = []
            for v, a in self.adj[u]:
                if v not in self.nodos:
                    obs.append(f"ERROR: la arista {u}->{v} apunta a un nodo inexistente.")
                if u == v:
                    neg = _peso_neto_negativo(a)
                    obs.append(f"AVISO: bucle {u}->{u}" +
                               (" con costo negativo: es por sí solo un ciclo negativo." if neg else "."))
                try:
                    _validar_valores(a, f"arista {u}->{v}")
                except ErrorGrafo as e:
                    obs.append(f"ERROR: {e}")
                if (v, a) in vistos and self.dirigido:
                    obs.append(f"ERROR: arista duplicada no justificada {u}->{v}.")
                vistos.append((v, a))
        aislados = [n for n in self.nodos if not self.adj[n]
                    and not any(v == n for u in self.adj for v, _ in self.adj[u])]
        for n in aislados:
            obs.append(f"AVISO: el nodo '{n}' está aislado (sin conexiones).")
        return obs

    # ------------------------------------------------------------- utilidades
    def _existe(self, nodo):
        if nodo not in self.nodos:
            raise ErrorGrafo(f"El nodo '{nodo}' no existe.")

    def resumen(self):
        tipos = {}
        for at in self.nodos.values():
            tipos[at.get("tipo", "generico")] = tipos.get(at.get("tipo", "generico"), 0) + 1
        return {
            "nombre": self.nombre,
            "dirigido": self.dirigido,
            "ponderado": self.ponderado,
            "multiarista": self.multiarista,
            "nodos": self.num_nodos(),
            "aristas": self.num_aristas(),
            "tipos": tipos,
        }

    def a_dict(self):
        return {
            "nombre": self.nombre,
            "dirigido": self.dirigido,
            "ponderado": self.ponderado,
            "multiarista": self.multiarista,
            "nodos": [{"id": n, **at} for n, at in self.nodos.items()],
            "aristas": [{"origen": u, "destino": v, **a} for u, v, a in self.aristas()],
        }

    def __repr__(self):
        r = self.resumen()
        return (f"Grafo('{r['nombre']}', {'dirigido' if r['dirigido'] else 'no dirigido'}, "
                f"{r['nodos']} nodos, {r['aristas']} aristas)")


# ---------------------------------------------------------------------- apoyo
def _validar_valores(atributos, contexto):
    for k, val in atributos.items():
        if k in ATRIBUTOS_NUMERICOS:
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                raise ErrorGrafo(f"Valor inválido en {contexto}: '{k}' debe ser numérico (recibido {val!r}).")
            if math.isnan(val):
                raise ErrorGrafo(f"Valor inválido en {contexto}: '{k}' es NaN.")
            if val < 0 and k not in ATRIBUTOS_CON_SIGNO:
                raise ErrorGrafo(
                    f"Valor inválido en {contexto}: '{k}' = {val} es negativo. "
                    "Los bonos se registran en el atributo 'cashback' (positivo).")


def _peso_neto_negativo(a):
    base = a.get("friccion", a.get("costo", a.get("peso", 0))) or 0
    return base - a.get("cashback", 0) < 0


def _funcion_peso(peso):
    if callable(peso):
        return peso
    return lambda a: a.get(peso, 1)
