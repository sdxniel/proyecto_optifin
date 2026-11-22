"""Pruebas de la capa de servicios (src/api.py) y del servidor web de la interfaz."""
import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from src.api import Sesion, ErrorApi
from src.servidor import crear_manejador


@pytest.fixture(scope="module")
def sesion():
    return Sesion()


def test_inicio_resume_los_tres_escenarios(sesion):
    d = sesion.inicio()
    assert d["rutas"]["mejor"] == 8 and d["liquidez"]["flujo"] == 950 and d["fraude"]["grupos"] == 1


def test_resultados_serializables(sesion):
    for r in (sesion.red_completa("transacciones"), sesion.proximidad("CTA_A", 2), sesion.rastreo("CTA_A"),
              sesion.circulacion("N05"), sesion.fraccionamiento(), sesion.ranking(5),
              sesion.ruta("cashback", "A", "X"), sesion.todos_los_pares("enrutamiento"), sesion.ciclos("cashback"),
              sesion.distribucion("liquidez"), sesion.costo_minimo("liquidez_ampliada"), sesion.voraz("liquidez_ampliada"),
              sesion.arbol("liquidez_ampliada"), sesion.complejidad()):
        json.dumps(r)  # no debe fallar (sin infinitos ni tuplas)


def test_ruleteo_llega_al_modulo_2(sesion):
    sesion.ruta("cashback", "A", "X")
    assert any("B -> D -> B" in a for a in sesion.ranking(5)["alertas_ruleteo"])


def test_edicion_y_validacion(sesion):
    sesion.editar_nodo("liquidez_ampliada", "agregar", "ATM9", "atm", "nombre=ATM 9")
    with pytest.raises(Exception):
        sesion.editar_arista("liquidez_ampliada", "agregar", "Cusco", "ATM9", 0, "capacidad=-5")
    d = sesion.editar_arista("liquidez_ampliada", "agregar", "Cusco", "ATM9", 0, "capacidad=50,costo=1")
    assert d["resumen"]["aristas"] == 13
    sesion.editar_nodo("liquidez_ampliada", "eliminar", "ATM9")


def test_subir_archivo(sesion):
    r = sesion.subir_archivo("personal", "mi_red.csv", "origen,destino,peso\nA,B,1\nB,C,-2\n")
    assert r["red"]["resumen"]["aristas"] == 1 and len(r["errores"]) == 1


def test_servidor_responde(sesion):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), crear_manejador(sesion))
    hilo = threading.Thread(target=srv.serve_forever, daemon=True)
    hilo.start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        html = urllib.request.urlopen(base + "/").read().decode("utf-8")
        assert "OptiFin" in html
        req = urllib.request.Request(base + "/api/distribucion", data=json.dumps({"red": "liquidez"}).encode(),
                                     headers={"Content-Type": "application/json"})
        assert json.loads(urllib.request.urlopen(req).read())["flujo"] == 950
        malo = urllib.request.Request(base + "/api/ruta", data=json.dumps({"red": "enrutamiento", "origen": "ZZ", "destino": "X"}).encode())
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(malo)
        assert e.value.code == 400
    finally:
        srv.shutdown()
