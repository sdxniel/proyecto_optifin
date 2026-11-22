"""
servidor.py - Servidor web local de la interfaz gráfica (solo biblioteca estándar).

GET  /              -> interfaz (carpeta interfaz/)
GET  /api/<acción>  -> consultas
POST /api/<acción>  -> acciones con parámetros JSON
"""

import json
import mimetypes
import os
import socket
import threading
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from .api import Sesion, ErrorApi
from .graph import ErrorGrafo
from .utils import RAIZ

CARPETA_INTERFAZ = os.path.join(RAIZ, "interfaz")
_bloqueo = threading.Lock()


def crear_manejador(sesion):
    rutas = {
        "estado": sesion.estado, "inicio": sesion.inicio,
        "red": sesion.red_completa, "cargar": sesion.cargar_archivo, "subir": sesion.subir_archivo,
        "nodo": sesion.editar_nodo, "arista": sesion.editar_arista, "guardar": sesion.guardar,
        "proximidad": sesion.proximidad, "rastreo": sesion.rastreo, "circulacion": sesion.circulacion,
        "fraccionamiento": sesion.fraccionamiento, "ranking": sesion.ranking,
        "ruta": sesion.ruta, "todos_los_pares": sesion.todos_los_pares, "ciclos": sesion.ciclos,
        "distribucion": sesion.distribucion, "costo_minimo": sesion.costo_minimo, "voraz": sesion.voraz,
        "arbol": sesion.arbol, "editar_liquidez": sesion.editar_liquidez,
        "verificaciones": sesion.verificaciones, "benchmark": sesion.benchmark,
        "complejidad": sesion.complejidad, "pruebas": sesion.pruebas,
    }

    class Manejador(BaseHTTPRequestHandler):
        def log_message(self, *args):  # silencia el registro por petición
            pass

        def _responder(self, codigo, cuerpo, tipo="application/json; charset=utf-8"):
            datos = cuerpo if isinstance(cuerpo, bytes) else json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(datos)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(datos)

        def _api(self, accion, params):
            if accion not in rutas:
                return self._responder(404, {"error": f"Acción desconocida: {accion}"})
            try:
                with _bloqueo:  # una operación a la vez sobre la sesión
                    resultado = rutas[accion](**params)
                self._responder(200, resultado)
            except (ErrorApi, ErrorGrafo, ValueError, KeyError, TypeError) as e:
                self._responder(400, {"error": str(e)})
            except Exception as e:  # error inesperado: se informa sin cerrar el servidor
                traceback.print_exc()
                self._responder(500, {"error": f"Error interno: {e}"})

        def do_GET(self):
            url = urlparse(self.path)
            if url.path.startswith("/api/"):
                params = {k: v[0] for k, v in parse_qs(url.query).items()}
                return self._api(url.path[5:], params)
            ruta = url.path.lstrip("/") or "index.html"
            archivo = os.path.normpath(os.path.join(CARPETA_INTERFAZ, ruta))
            if not archivo.startswith(CARPETA_INTERFAZ) or not os.path.isfile(archivo):
                return self._responder(404, b"No encontrado", "text/plain")
            tipo = mimetypes.guess_type(archivo)[0] or "application/octet-stream"
            if tipo.startswith("text/") or tipo.endswith("javascript"):
                tipo += "; charset=utf-8"
            with open(archivo, "rb") as f:
                self._responder(200, f.read(), tipo)

        def do_POST(self):
            url = urlparse(self.path)
            if not url.path.startswith("/api/"):
                return self._responder(404, {"error": "Ruta no válida"})
            largo = int(self.headers.get("Content-Length") or 0)
            try:
                params = json.loads(self.rfile.read(largo) or b"{}")
            except json.JSONDecodeError:
                return self._responder(400, {"error": "JSON inválido"})
            self._api(url.path[5:], params)

    return Manejador


def puerto_libre(inicial=8050):
    for p in range(inicial, inicial + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    raise OSError("No hay puertos libres entre 8050 y 8100.")


def iniciar(puerto=None, abrir_navegador=True):
    print("Cargando redes y preparando la interfaz...")
    sesion = Sesion()
    puerto = puerto or puerto_libre()
    servidor = ThreadingHTTPServer(("127.0.0.1", puerto), crear_manejador(sesion))
    url = f"http://127.0.0.1:{puerto}"
    print(f"\n  OptiFin está listo en  {url}\n  (Ctrl + C para cerrar)\n")
    if abrir_navegador:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
    finally:
        servidor.server_close()
