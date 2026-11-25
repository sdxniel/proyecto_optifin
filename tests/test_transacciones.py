"""Pruebas del Módulo 2 con la red simulada data/transacciones.csv (patrones plantados)."""
import pytest

from src import analisis_transacciones as at
from src.gestion_red import cargar
from src.utils import ruta_dato


@pytest.fixture(scope="module")
def g():
    red, errores = cargar(ruta_dato("transacciones.csv"), multiarista=True)
    assert errores == []
    return red


def test_bfs_proximidad(g):
    res = at.bfs_proximidad(g, "CTA_A")
    assert res["M1"][0] == 1 and res["N05"][0] == 2
    assert at.camino_bfs(res, "N05") == ["CTA_A", "M2", "N05"]


def test_dfs_temporal_detecta_ciclo(g):
    cadenas = at.rastrear_fondos(g, "CTA_A")
    assert sum(c["ciclo"] for c in cadenas) == 3  # por M1, M2 y M3


def test_dfs_temporal_respeta_fechas(g):
    # X1->X2 (día 20) y X2->X3 (día 5): no se puede encadenar
    assert all(len(c["pasos"]) == 1 for c in at.rastrear_fondos(g, "X1"))


def test_tarjan_igual_kosaraju(g):
    t = sorted(map(tuple, at.tarjan_scc(g)))
    k = sorted(map(tuple, at.kosaraju_scc(g)))
    assert t == k
    assert at.grupos_circulacion(at.tarjan_scc(g)) == [["CTA_A", "CTA_C", "M1", "M2", "M3"]]


def test_capas_topologicas():
    dag = {0: {1, 2}, 1: {3}, 2: {3}, 3: set()}
    assert at.capas_topologicas(dag) == [[0], [1, 2], [3]]


def test_abanicos(g):
    alertas = {(a["tipo"], a["cuenta"]): a for a in at.detectar_abanicos(g)}
    assert len(alertas[("entrada", "CTA_P")]["montos"]) == 8
    assert len(alertas[("salida", "CTA_F")]["montos"]) == 7


def test_suma_subconjuntos():
    assert at.suma_subconjuntos([9500, 9600, 9700, 9800, 9900, 9100], 48500) == [9500, 9600, 9700, 9800, 9900]
    assert at.suma_subconjuntos([3, 5, 7], 4) is None
    assert sum(at.suma_subconjuntos([9700, 9800, 9600], 28500, tolerancia=0.05)) == 29100


def test_reconstruccion_pitufeo(g):
    alerta = next(a for a in at.detectar_abanicos(g) if a["cuenta"] == "CTA_P")
    rec = at.verificar_reconstruccion(g, alerta)
    assert rec["destino"] == "CTA_Q" and rec["suma"] == rec["monto_salida"] == 48500


def test_ranking(g):
    top = [c for c, _ in at.top_k(at.puntajes(g), 6)]
    assert top[0] == "CTA_C" and {"CTA_A", "CTA_P"} <= set(top)
