"""
generar_datos.py - Genera los datos simulados de la carpeta data/.

Se ejecuta con:  python scripts/generar_datos.py

Usa una semilla fija (2026) para que los archivos sean siempre los mismos y los
resultados del informe se puedan reproducir.
"""

import csv
import json
import os
import random

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(RAIZ, "data")


def escribir(nombre, encabezado, filas):
    with open(os.path.join(DATA, nombre), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(encabezado)
        w.writerows(filas)


# --------------------------------------------------------------------------
# 1) Transacciones (Módulo 2): ruido normal + patrones plantados
# --------------------------------------------------------------------------
def transacciones():
    rnd = random.Random(2026)
    filas = []
    normales = [f"N{i:02d}" for i in range(1, 31)]
    comercios = [f"COM{i}" for i in range(1, 6)]
    # Ruido: transferencias pequeñas, siempre de un índice menor a uno mayor o a
    # un comercio, para que el ruido no forme ciclos por sí solo.
    for _ in range(90):
        i = rnd.randrange(0, len(normales) - 1)
        if rnd.random() < 0.35:
            destino = rnd.choice(comercios)
        else:
            destino = normales[rnd.randrange(i + 1, len(normales))]
        monto = rnd.choice([50, 80, 120, 150, 200, 250, 300, 450, 600, 900, 1200, 1500, 2500])
        dia = rnd.randint(1, 28)
        fila = [normales[i], destino, monto, f"2026-10-{dia:02d}", rnd.choice(["app", "web", "agencia"])]
        if fila not in filas:  # evita duplicados exactos
            filas.append(fila)

    # Patrón 1 (Figura 3): fraccionamiento + ciclo A -> M1,M2,M3 -> C -> A
    filas += [
        ["CTA_A", "M1", 9800, "2026-10-01", "app"],
        ["CTA_A", "M2", 9900, "2026-10-01", "app"],
        ["CTA_A", "M3", 9700, "2026-10-01", "app"],
        ["M1", "CTA_C", 9700, "2026-10-02", "app"],
        ["M2", "CTA_C", 9800, "2026-10-02", "app"],
        ["M3", "CTA_C", 9600, "2026-10-02", "app"],
        ["CTA_C", "CTA_A", 28500, "2026-10-04", "web"],
    ]
    # Patrón 2: abanico de entrada (pitufeo) hacia CTA_P y salida del total a CTA_Q
    pitufos = [("P1", 9500), ("P2", 9600), ("P3", 9700), ("P4", 9800),
               ("P5", 9900), ("P6", 9650), ("P7", 9750), ("P8", 9100)]
    for k, (p, m) in enumerate(pitufos):
        filas.append([p, "CTA_P", m, f"2026-10-{10 + k % 3:02d}", "agencia"])
    filas.append(["CTA_P", "CTA_Q", 9500 + 9600 + 9700 + 9800 + 9900, "2026-10-13", "web"])
    # Patrón 3: abanico de salida desde CTA_F
    for k, m in enumerate([9200, 9400, 9600, 9800, 9300, 9900, 9450]):
        filas.append(["CTA_F", f"F{k + 1}", m, "2026-10-15", "app"])
    # Patrón 4: cadena larga (estratificación) con montos decrecientes día a día
    cadena = ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]
    monto = 50000
    for k in range(len(cadena) - 1):
        filas.append([cadena[k], cadena[k + 1], monto, f"2026-10-{18 + k:02d}", "web"])
        monto -= 500
    # Patrón 5 (trampa temporal): X1->X2 el día 20 y X2->X3 el día 5.
    # Topológicamente hay camino X1->X2->X3, pero en el tiempo es imposible.
    filas += [["X1", "X2", 4000, "2026-10-20", "app"], ["X2", "X3", 3900, "2026-10-05", "app"]]
    # Relación con una cuenta normal para medir proximidad
    filas.append(["N05", "M2", 300, "2026-09-28", "app"])
    filas.sort(key=lambda f: (f[3], f[0], f[1]))
    escribir("transacciones.csv", ["origen", "destino", "monto", "fecha", "canal"], filas)

    nodos = []
    vistos = sorted({f[0] for f in filas} | {f[1] for f in filas})
    for n in vistos:
        nodos.append([n, "comercio" if n.startswith("COM") else "cuenta"])
    escribir("transacciones_nodos.csv", ["id", "tipo"], nodos)


# --------------------------------------------------------------------------
# 2) Enrutamiento (Módulo 3): red de la Guía 10 + extensiones
# --------------------------------------------------------------------------
NODOS_RUTA = [
    # id, tipo, nombre, x, y
    ["A", "billetera", "Yape (A)", 0.0, 1.0],
    ["B", "billetera", "Plin (B)", 1.6, 2.2],
    ["C", "banco", "Cta. BCP (C)", 1.6, 0.0],
    ["D", "compensacion", "Cámara (D)", 3.4, 0.0],
    ["E", "banco", "Cta. BBVA (E)", 4.8, 1.1],
    ["X", "comercio", "Comercio (X)", 6.2, 2.2],
    ["P", "generico", "Pasarela tarjetas (P)", 3.4, 3.2],
    ["ATM", "atm", "Red ATM", 6.2, 0.0],
    ["K", "agencia", "Agencia Cusco (K)", 0.0, -1.3],
    ["L", "agencia", "Agencia Lima (L)", 3.4, -1.6],
]
# origen, destino, C, T, R, I, V, comision_fija, comision_pct, tiempo(min), limite, disponible
ARISTAS_RUTA = [
    ["A", "B", 4, 3, 4, 4, 3, 0.00, 0.5, 2, 500, "si"],
    ["A", "C", 2, 2, 1, 2, 1, 0.00, 0.0, 1, 5000, "si"],
    ["B", "D", 5, 4, 5, 5, 6, 1.50, 0.3, 10, 10000, "si"],
    ["C", "D", 1, 1, 1, 1, 1, 0.50, 0.1, 5, 30000, "si"],
    ["D", "E", 3, 3, 3, 3, 3, 1.00, 0.2, 30, 30000, "si"],
    ["E", "X", 2, 2, 2, 2, 2, 0.00, 1.5, 2, 20000, "si"],
    ["B", "X", 9, 8, 10, 10, 8, 0.00, 3.0, 1, 500, "si"],
    ["C", "E", 8, 7, 8, 8, 7, 7.50, 0.0, 1, 15000, "si"],
    # Extensiones: tarjetas, ATM, interplaza y un canal fuera de servicio
    ["C", "P", 4, 3, 4, 4, 4, 0.00, 2.5, 1, 8000, "si"],
    ["P", "X", 4, 3, 4, 4, 4, 0.00, 1.0, 1, 8000, "si"],
    ["C", "X", 2, 2, 3, 3, 2, 0.00, 0.5, 1, 10000, "no"],
    ["C", "ATM", 1, 1, 2, 1, 2, 0.00, 0.0, 1, 1500, "si"],
    ["E", "ATM", 3, 1, 2, 3, 2, 6.00, 0.0, 1, 1500, "si"],
    ["K", "C", 3, 4, 2, 2, 2, 5.00, 0.0, 60, 50000, "si"],
    ["K", "L", 5, 6, 3, 3, 3, 9.00, 0.1, 240, 50000, "si"],
    ["L", "D", 2, 2, 2, 2, 2, 2.00, 0.0, 10, 50000, "si"],
]
ENCAB_RUTA = ["origen", "destino", "C", "T", "R", "I", "V", "comision_fija", "comision_pct",
              "tiempo", "limite", "disponible", "friccion", "cashback", "cashback_soles"]


def enrutamiento():
    escribir("red_enrutamiento_nodos.csv", ["id", "tipo", "nombre", "x", "y"], NODOS_RUTA)
    escribir("red_enrutamiento_cashback_nodos.csv", ["id", "tipo", "nombre", "x", "y"], NODOS_RUTA)
    filas = [f + ["", "", ""] for f in ARISTAS_RUTA]
    escribir("red_enrutamiento.csv", ENCAB_RUTA, filas)
    # Campaña "CyberDays" (Guía 10, Ejercicio 4): bonos con costo neto negativo
    promo = [
        ["D", "B", "", "", "", "", "", 0.00, 0.0, 5, 100000, "si", 0, 25, 2.0],
        ["E", "C", "", "", "", "", "", 0.00, 0.0, 5, 100000, "si", 0, 1, 0.0],
    ]
    escribir("red_enrutamiento_cashback.csv", ENCAB_RUTA, filas + promo)


# --------------------------------------------------------------------------
# 3) Liquidez (Módulo 4)
# --------------------------------------------------------------------------
def liquidez():
    # Red de la Figura 5 (miles de S/)
    nodos = [
        ["Central", "boveda_central", "Bóveda central", 1000, "", 0.0, 1.0],
        ["Norte", "boveda_regional", "Bóveda reg. Norte", "", "", 2.0, 1.8],
        ["Sur", "boveda_regional", "Bóveda reg. Sur", "", "", 2.0, 0.0],
        ["Urubamba", "agencia", "Ag. Urubamba", "", 300, 4.0, 2.4],
        ["Quillabamba", "agencia", "Ag. Quillabamba", "", 350, 4.0, 1.2],
        ["Sicuani", "agencia", "Ag. Sicuani", "", 600, 4.0, 0.0],
    ]
    escribir("distribucion_liquidez_nodos.csv", ["id", "tipo", "nombre", "oferta", "demanda", "x", "y"], nodos)
    aristas = [
        ["Central", "Norte", 600, 2, 40],
        ["Central", "Sur", 400, 3, 35],
        ["Norte", "Urubamba", 300, 1, 20],
        ["Norte", "Quillabamba", 250, 2, 30],
        ["Sur", "Sicuani", 400, 2, 25],
    ]
    escribir("distribucion_liquidez.csv", ["origen", "destino", "capacidad", "costo", "costo_habilitacion"], aristas)

    # Red ampliada: dos bóvedas centrales y rutas alternativas
    nodos2 = [
        ["Cusco", "boveda_central", "Bóveda Cusco", 900, "", 0.0, 1.6],
        ["Juliaca", "boveda_central", "Bóveda Juliaca", 600, "", 0.6, -1.4],
        ["RNorte", "boveda_regional", "Reg. Norte", "", "", 2.2, 2.6],
        ["RSur", "boveda_regional", "Reg. Sur", "", "", 2.2, 0.9],
        ["Urubamba", "agencia", "Ag. Urubamba", "", 200, 4.4, 3.6],
        ["Quillabamba", "agencia", "Ag. Quillabamba", "", 250, 4.4, 2.5],
        ["Calca", "agencia", "Ag. Calca", "", 150, 4.4, 1.5],
        ["Sicuani", "agencia", "Ag. Sicuani", "", 300, 4.4, 0.5],
        ["Espinar", "agencia", "Ag. Espinar", "", 250, 4.4, -0.5],
        ["PMaldonado", "agencia", "Ag. Pto. Maldonado", "", 200, 4.4, -1.6],
    ]
    escribir("liquidez_red_ampliada_nodos.csv", ["id", "tipo", "nombre", "oferta", "demanda", "x", "y"], nodos2)
    aristas2 = [
        ["Cusco", "RNorte", 450, 2, 40],
        ["RNorte", "Urubamba", 300, 1, 20],
        ["RNorte", "Quillabamba", 250, 3, 45],
        ["RNorte", "Calca", 200, 1, 15],
        ["Cusco", "Calca", 150, 5, 25],
        ["Cusco", "RSur", 350, 2, 35],
        ["RSur", "Sicuani", 300, 2, 30],
        ["RSur", "Espinar", 200, 3, 40],
        ["Juliaca", "RSur", 300, 3, 50],
        ["Juliaca", "Espinar", 150, 4, 45],
        ["Juliaca", "PMaldonado", 150, 6, 70],
        ["Cusco", "PMaldonado", 100, 8, 90],
    ]
    escribir("liquidez_red_ampliada.csv", ["origen", "destino", "capacidad", "costo", "costo_habilitacion"], aristas2)


# --------------------------------------------------------------------------
# 4) Ejemplos de formatos JSON y TXT (Módulo 1)
# --------------------------------------------------------------------------
def ejemplos():
    red = {
        "nombre": "red_atm_cusco",
        "dirigido": False,
        "ponderado": True,
        "nodos": [
            {"id": "AgPlaza", "tipo": "agencia", "nombre": "Agencia Plaza"},
            {"id": "ATM1", "tipo": "atm", "nombre": "ATM San Blas"},
            {"id": "ATM2", "tipo": "atm", "nombre": "ATM Wanchaq"},
            {"id": "ATM3", "tipo": "atm", "nombre": "ATM Aeropuerto"},
            {"id": "Servidor", "tipo": "generico", "nombre": "Servidor central"},
        ],
        "aristas": [
            {"origen": "Servidor", "destino": "AgPlaza", "costo": 4, "tiempo": 20},
            {"origen": "Servidor", "destino": "ATM1", "costo": 6, "tiempo": 35},
            {"origen": "AgPlaza", "destino": "ATM1", "costo": 2, "tiempo": 12},
            {"origen": "AgPlaza", "destino": "ATM2", "costo": 3, "tiempo": 15},
            {"origen": "ATM2", "destino": "ATM3", "costo": 5, "tiempo": 25},
            {"origen": "Servidor", "destino": "ATM3", "costo": 9, "tiempo": 40},
        ],
    }
    with open(os.path.join(DATA, "red_ejemplo.json"), "w", encoding="utf-8") as f:
        json.dump(red, f, ensure_ascii=False, indent=2)
    with open(os.path.join(DATA, "red_ejemplo.txt"), "w", encoding="utf-8") as f:
        f.write("# Ejemplo del enunciado: origen destino comision\n# dirigido: si\n")
        f.write("CuentaA CuentaB 4.50\nCuentaA CuentaC 2.00\nCuentaB CuentaD 5.10\n"
                "CuentaC CuentaD 1.00\nCuentaD CuentaE 3.00\n")


if __name__ == "__main__":
    os.makedirs(DATA, exist_ok=True)
    transacciones()
    enrutamiento()
    liquidez()
    ejemplos()
    print("Datos generados en", DATA)
