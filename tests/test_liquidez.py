"""Pruebas del Módulo 4: red de la Figura 5 y red ampliada."""
import pytest

from src import distribucion_liquidez as dl
from src.gestion_red import cargar
from src.utils import ruta_dato


@pytest.fixture(scope="module")
def fig5():
    return cargar(ruta_dato("distribucion_liquidez.csv"))[0]


@pytest.fixture(scope="module")
def ampliada():
    return cargar(ruta_dato("liquidez_red_ampliada.csv"))[0]


def test_flujo_maximo_figura5(fig5):
    r = dl.distribuir(fig5)
    assert r["flujo"] == 950 and not r["factible"]
    faltan = {a["agencia"]: a["falta"] for a in r["agencias"]}
    assert faltan == {"Urubamba": 0, "Quillabamba": 100, "Sicuani": 200}


def test_corte_minimo_igual_flujo(fig5):
    r = dl.distribuir(fig5)
    assert r["capacidad_corte"] == r["flujo"]
    assert {(u, v) for u, v, _ in r["corte"]} == {("Central", "Sur"), ("Norte", "Urubamba"), ("Norte", "Quillabamba")}


def test_cuellos_relevantes(fig5):
    cuellos = {(u, v) for u, v, _ in dl.distribuir(fig5)["cuellos"]}
    assert cuellos == {("Central", "Sur"), ("Sur", "Sicuani"), ("Norte", "Quillabamba")}


def test_restricciones_del_flujo(fig5, ampliada):
    assert dl.distribuir(fig5)["verificacion"] == []
    assert dl.distribuir(ampliada)["verificacion"] == []


def test_edmonds_karp_igual_ford_fulkerson(ampliada):
    ek, _ = dl.edmonds_karp(dl.construir_red(ampliada))
    ff, _ = dl.ford_fulkerson_dfs(dl.construir_red(ampliada))
    assert ek == ff == 1350


def test_costo_minimo(ampliada):
    base = dl.distribuir(ampliada)
    flujo, costo = dl.flujo_costo_minimo(dl.construir_red(ampliada))
    assert flujo == base["flujo"] and costo <= base["costo"] and costo == 6350


def test_voraz_no_es_optimo(ampliada):
    recibido, _, _ = dl.voraz_mas_cercana(ampliada)
    assert sum(recibido.values()) == 1200 < dl.distribuir(ampliada)["flujo"]


def test_prim_igual_kruskal(ampliada):
    ap, cp = dl.prim(ampliada)
    ak, ck = dl.kruskal(ampliada)
    assert cp == ck == 325 and len(ap) == len(ak) == 9
