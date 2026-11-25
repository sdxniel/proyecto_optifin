"""Pruebas del Módulo 3 con la red de la Guía 10."""
import math
import pytest

from src import enrutamiento_financiero as ef
from src.gestion_red import cargar
from src.utils import ruta_dato


@pytest.fixture(scope="module")
def g():
    return cargar(ruta_dato("red_enrutamiento.csv"))[0]


@pytest.fixture(scope="module")
def gc():
    return cargar(ruta_dato("red_enrutamiento_cashback.csv"))[0]


def test_formula_friccion():
    # pesos de la tabla de la Guía 10
    assert ef.friccion(dict(C=4, T=3, R=4, I=4, V=3)) == 4
    assert ef.friccion(dict(C=5, T=4, R=5, I=5, V=6)) == 5  # exactamente 5.0: no debe subir a 6
    assert ef.friccion(dict(C=9, T=8, R=10, I=10, V=8)) == 10


def test_mejor_ruta_guia10(g):
    res = ef.analizar_ruta(g, "A", "X", "friccion", 100)
    assert res["mejor"] == (8, ["A", "C", "D", "E", "X"])
    assert res["menos_saltos"] == (14, ["A", "B", "X"])
    assert res["alternativas"][0][0] == 8


def test_restricciones_de_servicio(g):
    res = ef.analizar_ruta(g, "A", "X", "comision", 1000)
    excluidas = {(u, v) for u, v, _ in res["excluidas"]}
    assert ("A", "B") in excluidas and ("C", "X") in excluidas
    assert all("B" not in r for _, r in res["alternativas"])


def test_dijkstra_rechaza_negativos():
    with pytest.raises(ValueError):
        ef.dijkstra({"A": [("B", -1)], "B": []}, "A")


def test_ciclo_negativo_guia10(gc):
    adj, _ = ef.red_ponderada(gc, "friccion", 100)
    _, _, ciclo = ef.bellman_ford(adj)
    assert set(ciclo) == {"B", "D"}
    assert ef.costo_ruta(adj, ["B", "D", "B"]) == -20


def test_peso_negativo_sin_ciclo(g):
    # solo E->C (-1): hay peso negativo pero no ciclo negativo
    adj, _ = ef.red_ponderada(g, "friccion", 100)
    adj["E"].append(("C", -1))
    _, _, ciclo = ef.bellman_ford(adj)
    assert ciclo is None


def test_analizar_con_cashback_recalcula(gc):
    res = ef.analizar_ruta(gc, "A", "X", "friccion", 100)
    assert len(res["ciclos"]) == 1 and res["mejor"][0] == 8 and res["alertas"]


def test_floyd_warshall_igual_johnson(g):
    adj, _ = ef.red_ponderada(g, "friccion", 100)
    orden, dist, sig = ef.floyd_warshall(adj)
    jo = ef.johnson(adj)
    for i, s in enumerate(orden):
        for j, t in enumerate(orden):
            assert dist[i][j] == jo[s][t]
    assert ef.ruta_fw(orden, sig, "A", "X") == ["A", "C", "D", "E", "X"]


def test_johnson_detecta_ciclo(gc):
    adj, _ = ef.red_ponderada(gc, "friccion", 100)
    with pytest.raises(ef.CicloNegativo):
        ef.johnson(adj)


def test_backtracking_poda():
    adj = {"A": [("B", 1), ("C", 5)], "B": [("D", 1)], "C": [("D", 1)], "D": []}
    assert [r for _, r in ef.enumerar_rutas(adj, "A", "D")] == [["A", "B", "D"], ["A", "C", "D"]]
    assert len(ef.enumerar_rutas(adj, "A", "D", costo_max=3)) == 1
