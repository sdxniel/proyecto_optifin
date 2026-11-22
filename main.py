"""
OptiFin - Sistema de Análisis y Optimización de Redes Financieras
Programación III - Proyecto II

Ejecutar con:
    python main.py              -> interfaz gráfica (aplicación web local en el navegador)
    python main.py --terminal   -> versión de consola
    python main.py --puerto 8080 --sin-navegador
"""

import os
import subprocess
import sys

from src.graph import ErrorGrafo
from src import gestion_red as gr
from src import analisis_transacciones as at
from src import enrutamiento_financiero as ef
from src import distribucion_liquidez as dl
from src import evaluacion_resultados as ev
from src.utils import (pedir, pedir_nodo, pedir_atributos, guardar_reporte, ruta_dato, titulo,
                       CARPETA_DATOS, RAIZ, fmt_num)

REDES_POR_DEFECTO = {
    "transacciones": ("transacciones.csv", {"multiarista": True, "tipo_por_defecto": "cuenta"}),
    "enrutamiento": ("red_enrutamiento.csv", {}),
    "liquidez": ("distribucion_liquidez.csv", {}),
}


class App:
    def __init__(self):
        self.redes = {}
        self.alertas_ruleteo = []
        for clave, (archivo, op) in REDES_POR_DEFECTO.items():
            g, errores = gr.cargar(ruta_dato(archivo), **op)
            self.redes[clave] = g
            if errores:
                print(f"Avisos al cargar {archivo}: {len(errores)}")
        self.redes["activa"] = self.redes["enrutamiento"]

    # ------------------------------------------------------------- utilidades
    @staticmethod
    def mostrar(texto, nombre_reporte):
        print(texto)
        if pedir("\n¿Guardar este reporte en reportes/? (s/n)", "n", opciones=["s", "n"]) == "s":
            print("Guardado en:", guardar_reporte(nombre_reporte, texto))

    @staticmethod
    def imagen(ruta):
        print(f"Imagen guardada en: {ruta}")
        if pedir("¿Abrir la imagen? (s/n)", "n", opciones=["s", "n"]) == "s":
            gr.abrir_archivo(ruta)

    @staticmethod
    def elegir_archivo():
        archivos = sorted(f for f in os.listdir(CARPETA_DATOS)
                          if f.endswith((".csv", ".json", ".txt")) and not f.endswith("_nodos.csv"))
        for i, f in enumerate(archivos, 1):
            print(f"  {i}. {f}")
        r = pedir("Número de archivo o ruta completa", "1")
        if r.isdigit() and 1 <= int(r) <= len(archivos):
            return os.path.join(CARPETA_DATOS, archivos[int(r) - 1])
        return r

    def cargar_red(self):
        ruta = self.elegir_archivo()
        if not os.path.exists(ruta):
            print("El archivo no existe.")
            return None
        op = {}
        if ruta.endswith(".csv"):
            op["dirigido"] = pedir("¿Red dirigida? (s/n)", "s", opciones=["s", "n"]) == "s"
            op["multiarista"] = pedir("¿Permitir varias aristas entre el mismo par (transferencias)? (s/n)",
                                      "s" if "transac" in ruta else "n", opciones=["s", "n"]) == "s"
        try:
            g, errores = gr.cargar(ruta, **op)
        except ErrorGrafo as e:
            print("Error:", e)
            return None
        print(f"Cargada: {g}")
        if errores:
            print(f"Se rechazaron {len(errores)} registros inválidos:")
            for e in errores[:15]:
                print("  -", e)
        return g

    # ------------------------------------------------------------- menú 1
    def menu_gestion(self):
        while True:
            g = self.redes["activa"]
            print(titulo(f"MÓDULO 1 - Gestión de la red  [activa: {g.nombre}]"))
            print("1. Cargar red desde archivo (CSV, TXT o JSON)\n2. Ver resumen\n3. Listar nodos\n"
                  "4. Listar aristas\n5. Agregar nodo\n6. Modificar nodo\n7. Eliminar nodo\n"
                  "8. Agregar arista\n9. Modificar arista\n10. Eliminar arista\n11. Validar consistencia\n"
                  "12. Visualizar red\n13. Guardar red (JSON o CSV)\n14. Usar la red activa en otro módulo\n"
                  "15. Cambiar red activa\n0. Volver")
            op = pedir("Opción", "0")
            try:
                if op == "1":
                    nueva = self.cargar_red()
                    if nueva:
                        self.redes["activa"] = nueva
                elif op == "2":
                    print(gr.texto_resumen(g))
                elif op == "3":
                    print(gr.texto_nodos(g))
                elif op == "4":
                    print(gr.texto_aristas(g))
                elif op == "5":
                    nid = pedir("Id del nodo")
                    tipo = pedir("Tipo (cuenta, agencia, boveda_central, boveda_regional, atm, banco, billetera...)", "cuenta")
                    g.agregar_nodo(nid, tipo, **pedir_atributos("Atributos opcionales (ej. oferta=500)"))
                    print("Nodo agregado.")
                elif op == "6":
                    nid = pedir_nodo(g, "Nodo")
                    g.modificar_nodo(nid, **pedir_atributos())
                    print("Nodo modificado:", g.nodos[nid])
                elif op == "7":
                    g.eliminar_nodo(pedir_nodo(g, "Nodo a eliminar"))
                    print("Nodo y sus conexiones eliminados.")
                elif op == "8":
                    u, v = pedir_nodo(g, "Origen"), pedir_nodo(g, "Destino")
                    g.agregar_arista(u, v, **pedir_atributos("Atributos (ej. comision=2.5,tiempo=10)"))
                    print("Arista agregada.")
                elif op == "9":
                    u, v = pedir_nodo(g, "Origen"), pedir_nodo(g, "Destino")
                    idx = pedir("Índice (si hay varias aristas entre ellos)", 0, int)
                    g.modificar_arista(u, v, idx, **pedir_atributos())
                    print("Arista modificada.")
                elif op == "10":
                    u, v = pedir_nodo(g, "Origen"), pedir_nodo(g, "Destino")
                    g.eliminar_arista(u, v, pedir("Índice", 0, int))
                    print("Arista eliminada.")
                elif op == "11":
                    obs = g.validar()
                    print("Red consistente: sin observaciones." if not obs else "\n".join(obs))
                elif op == "12":
                    etiqueta = pedir("Atributo a mostrar en las aristas (vacío = ninguno)", "-")
                    self.imagen(gr.visualizar(g, etiqueta=None if etiqueta == "-" else etiqueta))
                elif op == "13":
                    nombre = pedir("Nombre del archivo (en data/, .json o .csv)", f"{g.nombre}_editada.json")
                    ruta = os.path.join(CARPETA_DATOS, nombre)
                    print("Guardado:", gr.guardar_json(g, ruta) if nombre.endswith(".json") else gr.guardar_csv(g, ruta))
                elif op == "14":
                    destino = pedir("Usar en el módulo (transacciones / enrutamiento / liquidez)",
                                    opciones=["transacciones", "enrutamiento", "liquidez"])
                    self.redes[destino] = g
                    print(f"La red '{g.nombre}' ahora la usa el módulo de {destino}.")
                elif op == "15":
                    clave = pedir("Red (transacciones / enrutamiento / liquidez)",
                                  opciones=["transacciones", "enrutamiento", "liquidez"])
                    self.redes["activa"] = self.redes[clave]
                elif op == "0":
                    return
            except ErrorGrafo as e:
                print("Error de validación:", e)

    # ------------------------------------------------------------- menú 2
    def menu_transacciones(self):
        while True:
            g = self.redes["transacciones"]
            print(titulo(f"MÓDULO 2 - Análisis de transacciones  [red: {g.nombre}, "
                         f"{g.num_nodos()} cuentas, {g.num_aristas()} transferencias]"))
            print("1. Proximidad entre cuentas (BFS)\n2. Rastrear fondos (DFS temporal)\n"
                  "3. Grupos con circulación de fondos (Tarjan/Kosaraju) y capas\n"
                  "4. Operaciones fragmentadas (abanicos + suma de subconjuntos)\n"
                  "5. Cuentas a revisar primero (puntaje, heap)\n6. Visualizar alrededor de una cuenta\n"
                  "7. Cargar otra red de transacciones\n0. Volver")
            op = pedir("Opción", "0")
            if op == "1":
                c = pedir_nodo(g, "Cuenta", "CTA_A")
                self.mostrar(at.reporte_proximidad(g, c, pedir("Máximo de saltos", 3, int)), "proximidad")
            elif op == "2":
                c = pedir_nodo(g, "Cuenta de origen", "CTA_A")
                v = pedir("Ventana máxima entre transferencias (días)", 7, int)
                self.mostrar(at.reporte_rastreo(g, c, v), "rastreo")
            elif op == "3":
                c = pedir("Cuenta para ver capas (vacío = ninguna)", "-")
                self.mostrar(at.reporte_circulacion(g, c if g.tiene_nodo(c) else None), "circulacion")
            elif op == "4":
                umbral = pedir("Umbral de reporte (S/)", at.UMBRAL_REPORTE, float)
                ventana = pedir("Ventana (días)", 3, int)
                self.mostrar(at.reporte_fraccionamiento(g, umbral, ventana), "fraccionamiento")
            elif op == "5":
                k = pedir("¿Cuántas cuentas mostrar?", 10, int)
                m = pedir("Cuentas ya marcadas, separadas por coma (vacío = ninguna)", "-")
                marcadas = [] if m == "-" else [x.strip() for x in m.split(",")]
                self.mostrar(at.reporte_revision(g, k, marcadas, self.alertas_ruleteo), "cuentas_a_revisar")
            elif op == "6":
                c = pedir_nodo(g, "Cuenta", "CTA_A")
                radio = pedir("Radio (saltos)", 2, int)
                cerca = at.bfs_proximidad(g, c, radio)
                niveles = self._niveles_dirigidos(g, c, radio, set(cerca))
                grupos = at.grupos_circulacion(at.tarjan_scc(g), g)
                en_ciclo = {n for gr_ in grupos for n in gr_}
                rojas = {(u, v) for u in cerca for v, _ in g.adj[u] if v in cerca and u in en_ciclo and v in en_ciclo}
                self.imagen(gr.visualizar(g, nodos=list(cerca), titulo=f"Relaciones de {c} (rojo = circulación)",
                                          posiciones=gr.posiciones_por_niveles(niveles),
                                          resaltar_aristas=rojas, resaltar_nodos={c},
                                          etiqueta=lambda u, v, a: f"{fmt_num(a.get('monto'))}\n{a.get('fecha', '')[5:]}",
                                          archivo=os.path.join(RAIZ, "reportes", f"transacciones_{c}.png")))
            elif op == "7":
                nueva = self.cargar_red()
                if nueva:
                    self.redes["transacciones"] = nueva
            elif op == "0":
                return

    @staticmethod
    def _niveles_dirigidos(g, c, radio, permitidos):
        """Columna de cada cuenta para el dibujo: a la derecha las que reciben dinero
        de c (BFS por aristas salientes), a la izquierda las que le envían."""
        from collections import deque
        niveles = {c: 0}
        for signo, vec in ((1, {u: [v for v, _ in g.adj[u]] for u in g.adj}),
                           (-1, {u: [v for v, _ in lst] for u, lst in g.predecesores().items()})):
            cola, vistos = deque([(c, 0)]), {c}
            while cola:
                u, d = cola.popleft()
                if d >= radio:
                    continue
                for v in vec[u]:
                    if v in permitidos and v not in vistos:
                        vistos.add(v)
                        niveles.setdefault(v, signo * (d + 1))
                        cola.append((v, d + 1))
        pendientes = set(permitidos) - set(niveles)
        while pendientes:  # el resto se ubica junto a la cuenta con la que se relaciona
            avance = False
            for n in sorted(pendientes):
                for v, _ in g.adj[n]:
                    if v in niveles:
                        niveles[n] = niveles[v] - 1
                        break
                else:
                    for u, _ in g.predecesores()[n]:
                        if u in niveles:
                            niveles[n] = niveles[u] + 1
                            break
                if n in niveles:
                    pendientes.discard(n)
                    avance = True
            if not avance:
                for n in pendientes:
                    niveles[n] = radio + 1
                break
        return niveles

    # ------------------------------------------------------------- menú 3
    def menu_enrutamiento(self):
        while True:
            g = self.redes["enrutamiento"]
            print(titulo(f"MÓDULO 3 - Rutas y comisiones  [red: {g.nombre}]"))
            print("1. Analizar ruta entre dos entidades\n2. Costos entre todos los pares (Floyd-Warshall vs Johnson)\n"
                  "3. Detectar ciclos negativos (ruleteo)\n4. Cambiar red (normal / con cashback / otra)\n"
                  "5. Visualizar la mejor ruta\n0. Volver")
            op = pedir("Opción", "0")
            if op in ("1", "2", "3", "5"):
                crit = pedir("Criterio (friccion / comision / tiempo)", "friccion",
                             opciones=["friccion", "comision", "tiempo"])
                monto = pedir("Monto de la operación (S/)", 100, float)
            if op == "1":
                o, d = pedir_nodo(g, "Origen", "A"), pedir_nodo(g, "Destino", "X")
                res = ef.analizar_ruta(g, o, d, crit, monto)
                self._registrar_alertas(res["alertas"])
                self.mostrar(ef.reporte_ruta(res), "ruta")
            elif op == "2":
                self.mostrar(ef.reporte_todos_los_pares(g, crit, monto), "todos_los_pares")
            elif op == "3":
                txt, alertas = ef.reporte_ciclos(g, crit, monto)
                self._registrar_alertas(alertas)
                self.mostrar(txt, "ciclos_negativos")
            elif op == "4":
                print("1. red_enrutamiento.csv (Guía 10)\n2. red_enrutamiento_cashback.csv (campaña CyberDays)\n3. Otro archivo")
                r = pedir("Opción", "1", opciones=["1", "2", "3"])
                if r == "3":
                    nueva = self.cargar_red()
                else:
                    nueva, _ = gr.cargar(ruta_dato("red_enrutamiento.csv" if r == "1" else "red_enrutamiento_cashback.csv"))
                if nueva:
                    self.redes["enrutamiento"] = nueva
                    print("Red cargada:", nueva)
            elif op == "5":
                o, d = pedir_nodo(g, "Origen", "A"), pedir_nodo(g, "Destino", "X")
                res = ef.analizar_ruta(g, o, d, crit, monto)
                if not res["mejor"]:
                    print("No hay ruta.")
                    continue
                ruta = res["mejor"][1]
                pares = set(zip(ruta, ruta[1:]))
                colores = {(u, v): "#C0392B" for u, v, _ in res["excluidas"]}
                colores.update({p: "#2E8B57" for p in pares})
                self.imagen(gr.visualizar(
                    g, titulo=f"Mejor ruta {o} -> {d} (verde) - costo {fmt_num(res['mejor'][0])}; rojo = excluida",
                    colores_aristas=colores, resaltar_nodos={o, d},
                    etiqueta=lambda u, v, a: fmt_num(ef.costo_arista(a, crit, monto)),
                    archivo=os.path.join(RAIZ, "reportes", f"ruta_{o}_{d}.png")))
            elif op == "0":
                return

    def _registrar_alertas(self, alertas):
        for a in alertas:
            if a not in self.alertas_ruleteo:
                self.alertas_ruleteo.append(a)

    # ------------------------------------------------------------- menú 4
    def menu_liquidez(self):
        while True:
            g = self.redes["liquidez"]
            print(titulo(f"MÓDULO 4 - Distribución de liquidez  [red: {g.nombre}]"))
            print("1. Calcular distribución (Edmonds-Karp + corte mínimo)\n2. Plan de costo mínimo\n"
                  "3. Comparar con el voraz 'agencia más cercana primero'\n"
                  "4. Red mínima de rutas (Prim/Kruskal) y su efecto en el flujo\n5. Visualizar resultado\n"
                  "6. Cambiar red (Figura 5 / red ampliada / otra)\n7. Modificar oferta o demanda de un nodo\n0. Volver")
            op = pedir("Opción", "0")
            if op == "1":
                self.mostrar(dl.reporte_distribucion(g), "distribucion")
            elif op == "2":
                self.mostrar(dl.reporte_costo_minimo(g), "costo_minimo")
            elif op == "3":
                self.mostrar(dl.reporte_voraz(g), "voraz_vs_flujo")
            elif op == "4":
                self.mostrar(dl.reporte_mst(g), "arbol_expansion")
            elif op == "5":
                res = dl.distribuir(g)
                flujo = {(u, v): (f, c) for u, v, f, c, _ in res["red"].flujos()}
                corte = {(u, v) for u, v, _ in res["corte"]}
                colores = {}
                for (u, v), (f, c) in flujo.items():
                    if (u, v) in corte:
                        colores[(u, v)] = "#C0392B"
                    elif c and f >= c:
                        colores[(u, v)] = "#E08E1B"
                    elif f > 0:
                        colores[(u, v)] = "#2E8B57"
                self.imagen(gr.visualizar(
                    g, titulo=f"Flujo máximo {fmt_num(res['flujo'])} de {fmt_num(res['demanda'])} "
                              "(rojo = corte mínimo, naranja = saturada, verde = con flujo)",
                    colores_aristas=colores,
                    etiqueta=lambda u, v, a: f"{fmt_num(flujo[(u, v)][0])} de {fmt_num(a.get('capacidad'))}",
                    archivo=os.path.join(RAIZ, "reportes", f"liquidez_{g.nombre}.png")))
            elif op == "6":
                print("1. distribucion_liquidez.csv (Figura 5)\n2. liquidez_red_ampliada.csv\n3. Otro archivo")
                r = pedir("Opción", "1", opciones=["1", "2", "3"])
                nueva = self.cargar_red() if r == "3" else gr.cargar(
                    ruta_dato("distribucion_liquidez.csv" if r == "1" else "liquidez_red_ampliada.csv"))[0]
                if nueva:
                    self.redes["liquidez"] = nueva
                    print("Red cargada:", nueva)
            elif op == "7":
                n = pedir_nodo(g, "Nodo")
                campo = pedir("Campo (oferta / demanda)", "demanda", opciones=["oferta", "demanda"])
                try:
                    g.modificar_nodo(n, **{campo: pedir("Nuevo valor (miles de S/)", 0, float)})
                    print("Actualizado:", g.nodos[n])
                except ErrorGrafo as e:
                    print("Error:", e)
            elif op == "0":
                return

    # ------------------------------------------------------------- menú 5
    def menu_evaluacion(self):
        while True:
            print(titulo("MÓDULO 5 - Evaluación, comparación y validación"))
            print("1. Verificaciones cruzadas (resultados que deben coincidir)\n"
                  "2. Medir tiempos y memoria (redes aleatorias) + gráfico\n"
                  "3. Tabla de complejidad teórica\n4. Ejecutar pruebas automatizadas (pytest)\n0. Volver")
            op = pedir("Opción", "0")
            if op == "1":
                self.mostrar(ev.reporte_verificaciones(), "verificaciones")
            elif op == "2":
                dens = pedir("Densidad (dispersa / densa)", "dispersa", opciones=["dispersa", "densa"])
                t = pedir("Tamaños V separados por coma (Floyd-Warshall es O(V³): >300 tarda)", "10,50,100,200")
                tamanos = [int(x) for x in t.split(",") if x.strip().isdigit()]
                res = ev.benchmark(tamanos, dens, progreso=lambda n: print(f"  midiendo V = {n} ..."))
                self.mostrar(ev.reporte_benchmark(res, dens), f"benchmark_{dens}")
                self.imagen(ev.graficar(res, dens))
            elif op == "3":
                self.mostrar(ev.reporte_complejidad(), "complejidad")
            elif op == "4":
                subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=RAIZ)
            elif op == "0":
                return

    # ------------------------------------------------------------- principal
    def ejecutar(self):
        print(titulo("OptiFin - Sistema de Análisis y Optimización de Redes Financieras"))
        print("Redes cargadas por defecto:")
        for k in ("transacciones", "enrutamiento", "liquidez"):
            print(f"  - {k}: {self.redes[k]}")
        while True:
            print(titulo("MENÚ PRINCIPAL"))
            print("1. Gestionar red financiera\n2. Analizar transacciones sospechosas\n3. Rutas y comisiones\n"
                  "4. Distribución de liquidez\n5. Evaluación y pruebas\n0. Salir")
            op = pedir("Opción", "0")
            acciones = {"1": self.menu_gestion, "2": self.menu_transacciones, "3": self.menu_enrutamiento,
                        "4": self.menu_liquidez, "5": self.menu_evaluacion}
            if op == "0":
                print("Hasta luego.")
                return
            if op in acciones:
                acciones[op]()


def principal():
    import argparse
    parser = argparse.ArgumentParser(description="OptiFin - Análisis y optimización de redes financieras")
    parser.add_argument("--terminal", action="store_true", help="usar la versión de consola")
    parser.add_argument("--puerto", type=int, default=None, help="puerto del servidor local (por defecto 8050)")
    parser.add_argument("--sin-navegador", action="store_true", help="no abrir el navegador automáticamente")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")  # evita errores con ∞ o → en consolas antiguas
    if args.terminal:
        try:
            App().ejecutar()
        except (KeyboardInterrupt, EOFError):
            print("\nSesión terminada.")
    else:
        from src.servidor import iniciar
        iniciar(args.puerto, abrir_navegador=not args.sin_navegador)


if __name__ == "__main__":
    principal()
