"""Pruebas del Módulo 1: carga, modificación, eliminación, consistencia y visualización."""
import os
import pytest

from src.graph import Grafo, ErrorGrafo
from src import gestion_red as gr
from src.utils import ruta_dato


def red_basica():
    g = Grafo(dirigido=True)
    for n in "ABCD":
        g.agregar_nodo(n, "cuenta")
    g.agregar_arista("A", "B", comision=4.5)
    g.agregar_arista("A", "C", comision=2.0)
    g.agregar_arista("B", "D", comision=5.1)
    return g


def test_crear_y_contar():
    g = red_basica()
    assert g.num_nodos() == 4 and g.num_aristas() == 3


def test_modificar_y_eliminar():
    g = red_basica()
    g.modificar_arista("A", "B", comision=1.0)
    assert g.aristas_entre("A", "B")[0]["comision"] == 1.0
    g.eliminar_nodo("B")
    assert not g.tiene_nodo("B")
    assert all(v != "B" for v, _ in g.adj["A"])  # se eliminan también las conexiones
    g.eliminar_arista("A", "C")
    assert g.num_aristas() == 0


def test_rechaza_nodo_inexistente_y_valores_invalidos():
    g = red_basica()
    with pytest.raises(ErrorGrafo):
        g.agregar_arista("A", "Z", comision=1)
    with pytest.raises(ErrorGrafo):
        g.agregar_arista("A", "D", comision=-3)
    with pytest.raises(ErrorGrafo):
        g.agregar_arista("C", "D", comision="abc")


def test_duplicados():
    g = red_basica()
    with pytest.raises(ErrorGrafo):
        g.agregar_arista("A", "B", comision=9)  # no admite aristas múltiples
    m = Grafo(multiarista=True)
    m.agregar_nodo("A"); m.agregar_nodo("B")
    m.agregar_arista("A", "B", monto=100, fecha="2026-10-01")
    m.agregar_arista("A", "B", monto=100, fecha="2026-10-02")  # otra fecha: válida
    with pytest.raises(ErrorGrafo):
        m.agregar_arista("A", "B", monto=100, fecha="2026-10-01")  # idéntica: duplicado no justificado


def test_no_dirigido_y_matriz():
    g = Grafo(dirigido=False)
    g.agregar_nodo("A"); g.agregar_nodo("B")
    g.agregar_arista("A", "B", peso=3)
    orden, m = g.a_matriz("peso")
    assert m[0][1] == m[1][0] == 3 and g.num_aristas() == 1


def test_carga_formatos():
    for archivo, esperado in [("red_enrutamiento.csv", 16), ("red_ejemplo.json", 6), ("red_ejemplo.txt", 5)]:
        g, errores = gr.cargar(ruta_dato(archivo))
        assert errores == [] and g.num_aristas() == esperado


def test_carga_reporta_registros_invalidos(tmp_path):
    nodos = tmp_path / "r_nodos.csv"
    nodos.write_text("id,tipo\nA,cuenta\nB,cuenta\n", encoding="utf-8")
    aristas = tmp_path / "r.csv"
    aristas.write_text("origen,destino,monto\nA,B,10\nA,Z,5\nB,A,-4\n", encoding="utf-8")
    g, errores = gr.cargar(str(aristas))
    assert g.num_aristas() == 1 and len(errores) == 2


def test_validar_bucle_negativo():
    g = Grafo()
    g.agregar_nodo("A")
    g.adj["A"].append(("A", {"friccion": 0, "cashback": 5}))
    assert any("ciclo negativo" in o for o in g.validar())


def test_visualizar(tmp_path):
    g, _ = gr.cargar(ruta_dato("distribucion_liquidez.csv"))
    ruta = gr.visualizar(g, archivo=str(tmp_path / "red.png"), etiqueta="capacidad")
    assert os.path.getsize(ruta) > 0
