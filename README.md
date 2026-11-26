# OptiFin – Sistema de Análisis y Optimización de Redes Financieras

Proyecto II – Programación III. Sistema en Python que modela una entidad financiera como un
grafo y resuelve tres escenarios operativos:

1. **Prevención de fraude y lavado de activos** (Módulo 2)
2. **Enrutamiento de operaciones y cálculo de comisiones** (Módulo 3)
3. **Distribución de liquidez hacia bóvedas y agencias** (Módulo 4)

Todos los módulos usan una **representación común** (Módulo 1) y se validan con pruebas y
mediciones (Módulo 5).

---

## 1. Requisitos e instalación

- **Python 3.10 o superior** (probado con Python 3.13).
- Bibliotecas: `matplotlib` (imágenes de la versión de consola) y `pytest` (pruebas). La interfaz
  gráfica y el servidor usan solo la biblioteca estándar y HTML/CSS/JavaScript sin dependencias
  externas. Los algoritmos están implementados desde cero, sin librerías de grafos.

```bash
git clone <URL-del-repositorio>
cd proyecto_optifin
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Ejecución

```bash
python main.py
```

Se levanta un **servidor local** y se abre automáticamente el navegador en
`http://127.0.0.1:8050` con la interfaz gráfica (aplicación web local, una de las opciones que
permite el enunciado). No necesita internet: todo se ejecuta en la computadora. Para cerrar,
presione `Ctrl + C` en la terminal.

Opciones:

```bash
python main.py --terminal          # versión de consola (menús de texto)
python main.py --puerto 8080       # usar otro puerto
python main.py --sin-navegador     # no abrir el navegador automáticamente
```

### Qué ofrece la interfaz

| Sección | Contenido |
| --- | --- |
| **Panel general** | Indicadores de los tres escenarios, redes cargadas, cuentas a revisar, agencias con faltante y arquitectura. |
| **1 · Gestión de la red** | Visor interactivo del grafo (zoom, mover, arrastrar nodos, ver atributos al pasar el mouse, descargar SVG); tablas de nodos y aristas con filtro; agregar, modificar y eliminar nodos y aristas con validación; cargar desde `data/` o subir CSV/TXT/JSON propios; guardar y descargar. |
| **2 · Fraude y lavado** | Proximidad (BFS), rastreo de fondos con orden cronológico (DFS temporal), circulación (Tarjan = Kosaraju + capas topológicas), fraccionamiento (abanicos + suma de subconjuntos) y ranking de cuentas a revisar (heap) con las alertas de ruleteo del Módulo 3. |
| **3 · Rutas y comisiones** | Red de la Guía 10 o la campaña con cashback; origen, destino, criterio (fricción, comisión en S/, tiempo) y monto. Mejor ruta resaltada, todas las alternativas (backtracking), canales excluidos, matriz de todos los pares (Floyd-Warshall vs Johnson) y detección de ruleteo. |
| **4 · Liquidez a bóvedas** | Flujo máximo con Edmonds-Karp, corte mínimo, cuellos de botella, caminos aumentantes, plan de costo mínimo, comparación con el voraz y red mínima (Prim/Kruskal). Permite cambiar oferta y demanda y recalcular. |
| **5 · Evaluación** | Verificaciones cruzadas, gráficos de tiempo vs tamaño, tabla de complejidad y ejecución de las pruebas `pytest` desde la interfaz. |

Cada resultado tiene un botón **Reporte .txt** para descargar el reporte en texto.

### Recorrido sugerido para la demostración

| Paso | Dónde | Qué se ve |
| --- | --- | --- |
| 1 | Panel general | Los tres problemas y sus resultados principales en una pantalla |
| 2 | Fraude → Rastreo de fondos (`CTA_A`) | Las 3 cadenas que vuelven al origen; con `X1`, el DFS **no** encadena fechas imposibles |
| 3 | Fraude → Circulación | Tarjan y Kosaraju coinciden; el grupo CTA_A, CTA_C, M1, M2, M3 en rojo |
| 4 | Fraude → Fraccionamiento | Abanicos de CTA_P y CTA_F; la suma de subconjuntos reconstruye exactamente S/ 48,500 |
| 5 | Rutas → Guía 10 | Mejor ruta A→C→D→E→X = 8 frente a A→B→X = 14; con monto 1,000 se excluyen canales |
| 6 | Rutas → Campaña CyberDays → Detectar ruleteo | Ciclo B→D→B con −20 por vuelta |
| 7 | Fraude → Cuentas a revisar | Ranking con la alerta de ruleteo recibida del Módulo 3 |
| 8 | Liquidez → Figura 5 | Flujo 950 = corte mínimo; faltan 100 en Quillabamba y 200 en Sicuani |
| 9 | Liquidez → Red ampliada | Costo mínimo ahorra S/ 150; el voraz entrega 1,200 de 1,350; el árbol solo 800 |
| 10 | Evaluación | 21/21 verificaciones, gráficos de tiempo y pruebas automáticas en verde |

## 3. Pruebas automatizadas

```bash
python -m pytest -q
```

45 pruebas en `tests/` (un archivo por módulo, más la interfaz). También se ejecutan desde Evaluación → Pruebas automatizadas.

## 4. Estructura

```
proyecto_optifin/
├── main.py                       # inicia la interfaz gráfica (o --terminal)
├── requirements.txt
├── pytest.ini
├── interfaz/                     # interfaz gráfica: index.html, estilos.css, grafo.js, app.js
├── data/                         # datos simulados (CSV, JSON, TXT)
├── src/
│   ├── graph.py                  # estructura común: lista de adyacencia con atributos
│   ├── gestion_red.py            # Módulo 1: carga, validación, guardado, visualización
│   ├── analisis_transacciones.py # Módulo 2: BFS, DFS temporal, Tarjan, Kosaraju, abanicos...
│   ├── enrutamiento_financiero.py# Módulo 3: Dijkstra, Bellman-Ford, Floyd-Warshall, Johnson...
│   ├── distribucion_liquidez.py  # Módulo 4: Edmonds-Karp, corte mínimo, costo mínimo, Prim, Kruskal
│   ├── evaluacion_resultados.py  # Módulo 5: verificaciones, tiempos, memoria, gráficos
│   ├── api.py                    # servicios que usa la interfaz (resultados en JSON)
│   ├── servidor.py               # servidor web local (solo biblioteca estándar)
│   └── utils.py
├── tests/                        # pruebas con pytest
├── scripts/generar_datos.py      # regenera data/ con semilla fija
├── reportes/                     # salidas generadas (no se versionan)
└── docs/                         # informe técnico y diapositivas
```

## 5. Datos simulados (`data/`)

Se regeneran siempre igual con `python scripts/generar_datos.py` (semilla 2026).

| Archivo | Formato | Contenido y finalidad |
| --- | --- | --- |
| `transacciones.csv` + `_nodos.csv` | `origen,destino,monto,fecha,canal` | ~90 transferencias normales (sin ciclos) + patrones plantados: ciclo con fraccionamiento (Figura 3), abanico de entrada CTA_P, abanico de salida CTA_F, cadena larga L1…L7 y la trampa temporal X1/X2/X3. Se sabe de antemano qué debe encontrar el sistema. |
| `red_enrutamiento.csv` + `_nodos.csv` | `origen,destino,C,T,R,I,V,comision_fija,comision_pct,tiempo,limite,disponible` | Red de la Guía 10 (Yape, Plin, BCP, Cámara, BBVA, Comercio) + pasarela de tarjetas, red ATM, agencias interplaza y un canal fuera de servicio. |
| `red_enrutamiento_cashback.csv` | igual + `friccion,cashback,cashback_soles` | Campaña CyberDays (Guía 10, Ej. 4): D→B −25 forma ciclo negativo; E→C −1 no. |
| `distribucion_liquidez.csv` + `_nodos.csv` | aristas `capacidad,costo,costo_habilitacion`; nodos `oferta,demanda` | Red de la Figura 5 (miles de S/): caso con déficit. |
| `liquidez_red_ampliada.csv` + `_nodos.csv` | igual | Dos bóvedas centrales y rutas alternativas: caso factible donde el voraz falla y el árbol de expansión pierde capacidad. |
| `red_ejemplo.json` / `red_ejemplo.txt` | JSON / `origen destino peso` | Ejemplos de los otros formatos de carga. |

**Reglas de los archivos:** los valores numéricos no pueden ser negativos; un bono se registra en
`cashback` (positivo) y el sistema calcula el costo neto. Si existe `<archivo>_nodos.csv`, las
aristas que apunten a nodos inexistentes se rechazan y se reportan.

## 6. Algoritmos por módulo

| Módulo | Algoritmo | Guía | Complejidad |
| --- | --- | --- | --- |
| 2 | BFS (proximidad) | 7 | O(V+E) |
| 2 | DFS con restricción temporal (rastreo) | 7 | O(V+E) por cadena |
| 2 | Tarjan / Kosaraju (circulación) | 7 | O(V+E) |
| 2 | Condensación + orden topológico (capas) | 7 | O(V+E) |
| 2 | Ordenamiento + ventana (abanicos) | 2 | O(E log E) |
| 2 | Suma de subconjuntos (programación dinámica) | 5 | O(n·S) |
| 2 | Heap top-k (ranking) | 2 | O(V log k) |
| 3 | Backtracking con poda (todas las rutas) | 6 | exponencial, acotado |
| 3 | Dijkstra | 9 | O((V+E) log V) |
| 3 | Bellman-Ford (pesos negativos, ruleteo) | 9 | O(V·E) |
| 3 | Floyd-Warshall | 10 | O(V³) |
| 3 | Johnson | 9, 10 | O(V·E + V(V+E) log V) |
| 4 | Edmonds-Karp + corte mínimo | 11 | O(V·E²) |
| 4 | Flujo de costo mínimo (Bellman-Ford en red residual) | 9 + 11 | O(F·V·E) |
| 4 | Prim / Kruskal | 8 | O(E log V) / O(E log E) |

## 7. Reproducir los resultados del informe

```bash
python scripts/generar_datos.py   # mismos datos
python -m pytest -q               # 45 pruebas
python main.py                    # Evaluación → Verificaciones y Desempeño empírico
```

Los tiempos dependen de la computadora, pero la forma de las curvas (por ejemplo, Floyd-Warshall
creciendo como V³ frente a Johnson en redes dispersas) se mantiene.

## 8. Advertencia

Los patrones del Módulo 2 son **indicadores para revisión**. Su detección no prueba por sí sola
fraude ni lavado de activos; la decisión corresponde a auditoría.
