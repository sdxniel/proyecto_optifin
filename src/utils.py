"""
utils.py - Funciones auxiliares: lectura de valores, fechas, tablas de texto,
entrada por teclado y guardado de reportes.
"""

import datetime as _dt
import math
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETA_DATOS = os.path.join(RAIZ, "data")
CARPETA_REPORTES = os.path.join(RAIZ, "reportes")

VERDADERO = {"si", "sí", "true", "1", "yes", "s", "verdadero"}
FALSO = {"no", "false", "0", "n", "falso"}


def convertir_valor(texto, clave=""):
    """Convierte el texto de una celda en int, float, bool o str."""
    t = str(texto).strip()
    if t == "":
        return None
    if clave in ("disponible", "promocion") or t.lower() in ("true", "false"):
        if t.lower() in VERDADERO:
            return True
        if t.lower() in FALSO:
            return False
    try:
        if t.lstrip("-").isdigit():
            return int(t)
        return float(t.replace(",", "")) if _parece_numero(t) else t
    except ValueError:
        return t


def _parece_numero(t):
    try:
        float(t.replace(",", ""))
        return True
    except ValueError:
        return False


def fecha(texto):
    """'2026-10-01' -> date. Acepta date ya convertida."""
    if isinstance(texto, _dt.date):
        return texto
    return _dt.date.fromisoformat(str(texto).strip())


def dias_entre(f1, f2):
    return (fecha(f2) - fecha(f1)).days


def fmt_num(x, dec=2):
    if x is None:
        return "-"
    if isinstance(x, float) and math.isinf(x):
        return "∞" if x > 0 else "-∞"
    if isinstance(x, float) and not x.is_integer():
        return f"{x:,.{dec}f}"
    return f"{int(x):,}"


def tabla(encabezados, filas, alinear=None):
    """Devuelve una tabla de texto con columnas alineadas."""
    filas = [[str(c) for c in f] for f in filas]
    anchos = [len(str(h)) for h in encabezados]
    for f in filas:
        for i, c in enumerate(f):
            anchos[i] = max(anchos[i], len(c))
    alinear = alinear or ["<"] * len(encabezados)

    def linea(cols):
        return "  ".join(f"{c:{alinear[i]}{anchos[i]}}" for i, c in enumerate(cols))

    sep = "  ".join("-" * a for a in anchos)
    return "\n".join([linea([str(h) for h in encabezados]), sep] + [linea(f) for f in filas])


def titulo(texto):
    return f"\n{'=' * len(texto)}\n{texto}\n{'=' * len(texto)}"


def guardar_reporte(nombre, contenido):
    """Guarda un reporte de texto en reportes/ y devuelve la ruta."""
    os.makedirs(CARPETA_REPORTES, exist_ok=True)
    marca = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta = os.path.join(CARPETA_REPORTES, f"{nombre}_{marca}.txt")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(contenido)
    return ruta


def ruta_dato(nombre):
    return os.path.join(CARPETA_DATOS, nombre)


# ------------------------------------------------------------ entrada teclado
def pedir(texto, defecto=None, tipo=str, opciones=None):
    """Pide un valor por teclado con valor por defecto y validación."""
    sufijo = f" [{defecto}]" if defecto is not None else ""
    while True:
        r = input(f"{texto}{sufijo}: ").strip()
        if r == "" and defecto is not None:
            r = str(defecto)
        if r == "":
            print("  Debe ingresar un valor.")
            continue
        if opciones and r not in opciones:
            print(f"  Opción inválida. Opciones: {', '.join(opciones)}")
            continue
        try:
            if tipo is bool:
                return r.lower() in VERDADERO
            return tipo(r)
        except ValueError:
            print("  Valor inválido, intente de nuevo.")


def pedir_nodo(grafo, texto, defecto=None):
    while True:
        n = pedir(texto, defecto)
        if grafo.tiene_nodo(n):
            return n
        sugeridos = [x for x in grafo.nodos if n.lower() in x.lower()][:8]
        print(f"  El nodo '{n}' no existe." + (f" ¿Quiso decir: {', '.join(sugeridos)}?" if sugeridos else ""))


def pedir_atributos(texto="Atributos (clave=valor separados por coma)"):
    r = input(f"{texto}: ").strip()
    at = {}
    if not r:
        return at
    for par in r.split(","):
        if "=" not in par:
            continue
        k, v = par.split("=", 1)
        val = convertir_valor(v, k.strip())
        if val is not None:
            at[k.strip()] = val
    return at


def pausa():
    input("\nPresione Enter para continuar...")
