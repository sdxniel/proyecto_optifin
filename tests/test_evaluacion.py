"""Pruebas del Módulo 5: verificaciones cruzadas y medición."""
from src import evaluacion_resultados as ev


def test_verificaciones_cruzadas_todas_ok():
    filas = ev.verificaciones_cruzadas(tamanos=(10, 25))
    fallas = [f for f in filas if f[2] != "OK"]
    assert not fallas, fallas


def test_red_aleatoria_reproducible():
    a = ev.red_aleatoria(30, "dispersa", 7)
    b = ev.red_aleatoria(30, "dispersa", 7)
    assert list(a.aristas()) == list(b.aristas()) and a.num_aristas() == 90


def test_benchmark_y_grafico(tmp_path):
    res = ev.benchmark((10, 20), "dispersa", repeticiones=1)
    assert all(len(v) == 2 for v in res.values())
    assert ev.graficar(res, "dispersa", str(tmp_path / "b.png")).endswith("b.png")
