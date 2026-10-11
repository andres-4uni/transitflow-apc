# Hito 5 — benchmark local

Medición de este equipo, no una certificación de precisión APC ni de rendimiento
en cualquier notebook. Referencia manual del único video real: **IN=6, OUT=6**.
**Hito 5 completado como medición y evaluación, no como validación de precisión.**
Se conservan las 144 ejecuciones originales, sin repetir el barrido. Por instrucción
del usuario se admite la diferencia normal del MOV: **1.308 declarados / 1.307
decodificados**, dentro de **±2 frames**, con advertencia. La revisión de las 72
pasadas reales está en [benchmark-validation.json](evaluations/benchmark-validation.json),
con hash del archivo original; los tiempos y resultados no se modificaron.

Todas las combinaciones reales superaron 20 FPS en las tres repeticiones y ambos
modos; todas salvo **416/stride 3** llegaron a 25. El conteo por defecto fue
**IN=0/OUT=0 frente a 6/6: 100% de error agregado**. La mejor alternativa de las
evaluadas, 416/stride 1, dio **0/2: 83,33% de error agregado**. Hace falta calibrar
y validar el conteo; la velocidad suficiente no demuestra precisión.

## Equipo y entradas

- Mac14,2, Apple M2, 8 CPU lógicas, 16 GiB; macOS 26.6.2 (25G83), ARM64.
- Python 3.11.15, torch 2.14.1, OpenCV 4.14.0, Ultralytics 8.3.253; CPU obligatoria,
  YOLOv8n local, ByteTrack integrado, clase `person`, sin nuevas dependencias.
- MOV real: `data/demo1.mov`, 1080×1920, 59,9724896836 FPS, 1.308 frames,
  21,81 s, 36.190.296 bytes. Solo lectura; no renombrado, copiado ni convertido.
- Comparación: `data/demo.avi`, sintético preexistente sin personas, **640×480,
  20 FPS declarados, 80 frames**. No se creó
  otro archivo de video. Sus dimensiones y códec distintos limitan la comparación.
- No se guardan frames, imágenes, rostros, boxes ni IDs en los resultados. Solo
  estadísticas numéricas y metadatos técnicos; el JPEG optativo vive en RAM.

## Método reproducible

```sh
.venv/bin/python scripts/benchmark_fps.py --torch-threads 4 --output docs/benchmarks/nueva-medicion.json
```

El resultado no puede sobreescribir un archivo existente. Por defecto mide las
12 combinaciones de `imgsz` 320/352/384/416 y `vid_stride` 1/2/3; tres repeticiones
por video y estado del stream: **144 ejecuciones**. Orden de combinaciones mezclado
con semilla 17, fuentes/modos en secuencia; no se ejecutan benchmarks en paralelo.
En cada ejecución se descartan las primeras 30 inferencias (no 30 frames de origen).
La captura usa un hilo separado y una cola acotada de dos frames.

El MOV se lee hasta que OpenCV devuelve fin de lectura, sin `--realtime`. El AVI
sintético se repite hasta igualar los **1.307 frames efectivamente decodificados**
del MOV; cada vuelta reinicia ByteTrack y
conteos. No se descartan frames durante captura; stride omite inferencias. El
calentamiento consume más frames de origen con stride mayor, por lo que los
intervalos medidos no son idénticos. Apertura, carga de pesos y cierre quedan
fuera de los FPS medidos. El evaluador usa otra pasada hasta fin de lectura y
**no descarta calentamiento**. Cada una de las cinco evaluaciones recorrió 1.307
frames. La tolerancia se aplica al total decodificado de una pasada completa,
no al número de inferencias tras stride ni a un benchmark recortado/en bucle.

Se separan:

- **FPS procesados**: inferencias medidas / segundos de pared. La media, p50 y
  p95 principales se calculan sobre las tres repeticiones. “>20” y “≥25” exigen
  que las tres superen el umbral correspondiente, usando el mínimo sin redondear.
- **FPS de origen**: frames decodificados / segundos de pared; sube con stride,
  pero no equivale al número de imágenes analizadas. Los JSON incluyen también
  media/p50/p95 de FPS instantáneos entre inferencias.
- **Captura**: tiempo de `VideoCapture.read()` en el hilo, por frame decodificado.
  La espera del consumidor en cola se reporta aparte. Captura e inferencia se
  solapan: no sumar sus latencias para deducir FPS.
- **Inferencia**: ejecución de la red según el temporizador de Ultralytics.
  Preproceso, postproceso y resto de adaptación Python se registran por separado.
- **Tracking**: callback real de ByteTrack, incluida conversión de sus resultados.
- **Conteo**: tripwire, ocupación y actualización de estelas si están habilitadas.
- **Overlay+JPEG**: mismo overlay y `LatestFrame` que la demo, calidad 80,
  máximo 10 FPS. La media por inferencia incluye ceros cuando se limita el stream;
  `encoded_only` informa el coste de los frames efectivamente codificados.
  Apagado cuesta cero porque se omiten overlay y JPEG. No mide transferencia
  HTTP, consumo de Streamlit ni renderizado del navegador.

Los percentiles de latencia agrupan todas las muestras medidas de las tres
repeticiones. p95 de FPS representa el extremo rápido; p95 de latencia representa
el extremo lento. Se conserva el detalle por repetición en el JSON.

La carga de fondo se estima con tiempos CPU de sistema menos los del proceso de
benchmark, divididos por tiempo de pared × ocho CPU. Se registra también load
average. Es una estimación: incluye procesos ajenos, núcleo y actividad del IDE;
no se cerraron aplicaciones del usuario ni se controló temperatura/energía.

## Piloto de hilos

300 frames por pasada, warmup 30, 320/stride 1, tres repeticiones. Cada celda es
media de FPS procesados. Estos pilotos breves orientan la elección de hilos;
no sustituyen el barrido completo.

| Hilos solicitados / efectivos | Real apagado | Real encendido | Sintético apagado | Sintético encendido |
| --- | ---: | ---: | ---: | ---: |
| Auto / 7 | 69,57 | 67,32 | 85,72 | 84,82 |
| 4 / 4 | 71,80 | 69,42 | 99,75 | 98,23 |
| 1 / 1 | 71,32 | 69,26 | 72,01 | 70,15 |

Se usan cuatro hilos explícitos en el barrido. La diferencia real entre uno y
cuatro es pequeña; el sintético favorece cuatro. No se afirma una ventaja
universal ni se modifica el modo automático por estos pilotos.

Datos: [auto](benchmarks/benchmark-pilot-auto.json), [cuatro hilos](benchmarks/benchmark-pilot-4threads.json),
[un hilo](benchmarks/benchmark-pilot-1thread.json).

## Resultados del barrido completo

Datos numéricos de las 144 ejecuciones: [benchmark-results.json](benchmarks/benchmark-results.json).
La discrepancia 1.307/1.308 quedó aceptada con advertencia. Cada celda
de FPS muestra **media / p50 / p95** de tres pasadas; los mínimos se muestran
separadamente. Se usan cuatro hilos de torch en todas ellas.


### FPS — MOV real

| imgsz / stride | Stream apagado | Mínimo | Stream encendido | Mínimo | FPS origen medios apagado / encendido | >20 / ≥25 en ambos modos |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 320 / 1 | 66.72 / 66.46 / 70.80 | 62.42 | 61.54 / 61.68 / 61.83 | 61.11 | 66.72 / 61.54 | Sí / Sí |
| 320 / 2 | 38.25 / 37.95 / 39.39 | 37.25 | 36.49 / 36.10 / 37.27 | 35.96 | 76.50 / 72.97 | Sí / Sí |
| 320 / 3 | 34.19 / 34.17 / 34.47 | 33.88 | 32.86 / 33.16 / 33.18 | 32.25 | 102.64 / 98.66 | Sí / Sí |
| 352 / 1 | 60.69 / 60.37 / 61.63 | 59.92 | 64.31 / 64.74 / 64.87 | 63.31 | 60.69 / 64.31 | Sí / Sí |
| 352 / 2 | 40.51 / 40.73 / 40.79 | 40.01 | 38.26 / 38.12 / 38.52 | 38.09 | 81.02 / 76.51 | Sí / Sí |
| 352 / 3 | 31.96 / 32.07 / 32.65 | 31.09 | 29.75 / 29.65 / 29.94 | 29.63 | 95.95 / 89.33 | Sí / Sí |
| 384 / 1 | 52.19 / 52.14 / 52.60 | 51.79 | 49.64 / 49.70 / 49.87 | 49.34 | 52.19 / 49.64 | Sí / Sí |
| 384 / 2 | 37.73 / 37.32 / 38.78 | 36.91 | 31.73 / 31.13 / 33.52 | 30.28 | 75.45 / 63.46 | Sí / Sí |
| 384 / 3 | 31.20 / 30.85 / 32.18 | 30.42 | 28.42 / 28.53 / 28.92 | 27.76 | 93.67 / 85.33 | Sí / Sí |
| 416 / 1 | 43.77 / 44.31 / 44.98 | 41.95 | 44.46 / 44.11 / 46.95 | 42.00 | 43.77 / 44.46 | Sí / Sí |
| 416 / 2 | 43.45 / 43.34 / 43.67 | 43.31 | 42.44 / 42.34 / 42.68 | 42.27 | 86.90 / 84.88 | Sí / Sí |
| 416 / 3 | 24.15 / 24.07 / 24.72 | 23.60 | 21.88 / 21.85 / 21.96 | 21.82 | 72.52 / 65.70 | Sí / No |

### Latencia por etapa — MOV real, stream apagado

Milisegundos **media / p50 / p95**, agrupando las muestras de las tres pasadas. Captura usa muestras por frame de origen; las otras etapas, por inferencia.

| imgsz / stride | Captura | Inferencia | Tracking | Conteo | Overlay+JPEG |
| --- | ---: | ---: | ---: | ---: | ---: |
| 320 / 1 | 5.565 / 5.503 / 6.648 | 12.162 / 12.231 / 13.837 | 0.124 / 0.084 / 0.356 | 0.005 / 0.004 / 0.008 | 0.000 / 0.000 / 0.000 |
| 320 / 2 | 8.427 / 8.314 / 11.421 | 22.394 / 22.323 / 25.599 | 0.201 / 0.131 / 0.540 | 0.007 / 0.006 / 0.012 | 0.000 / 0.000 / 0.000 |
| 320 / 3 | 7.575 / 7.398 / 10.389 | 25.700 / 25.513 / 29.036 | 0.199 / 0.192 / 0.464 | 0.006 / 0.005 / 0.010 | 0.000 / 0.000 / 0.000 |
| 352 / 1 | 5.396 / 5.220 / 6.536 | 13.750 / 13.311 / 16.249 | 0.139 / 0.096 / 0.361 | 0.005 / 0.005 / 0.008 | 0.000 / 0.000 / 0.000 |
| 352 / 2 | 6.637 / 6.455 / 8.334 | 21.290 / 21.278 / 23.137 | 0.169 / 0.107 / 0.453 | 0.006 / 0.005 / 0.010 | 0.000 / 0.000 / 0.000 |
| 352 / 3 | 7.591 / 7.465 / 10.400 | 27.730 / 27.626 / 30.732 | 0.186 / 0.120 / 0.488 | 0.006 / 0.005 / 0.011 | 0.000 / 0.000 / 0.000 |
| 384 / 1 | 5.565 / 5.489 / 6.393 | 16.267 / 16.204 / 17.712 | 0.154 / 0.097 / 0.409 | 0.005 / 0.005 / 0.009 | 0.000 / 0.000 / 0.000 |
| 384 / 2 | 6.929 / 6.782 / 8.696 | 23.055 / 22.983 / 25.948 | 0.182 / 0.113 / 0.485 | 0.006 / 0.006 / 0.011 | 0.000 / 0.000 / 0.000 |
| 384 / 3 | 7.485 / 7.345 / 10.377 | 28.463 / 28.306 / 31.803 | 0.192 / 0.121 / 0.502 | 0.006 / 0.005 / 0.011 | 0.000 / 0.000 / 0.000 |
| 416 / 1 | 5.891 / 5.685 / 6.994 | 19.868 / 19.832 / 21.778 | 0.181 / 0.108 / 0.474 | 0.006 / 0.005 / 0.010 | 0.000 / 0.000 / 0.000 |
| 416 / 2 | 5.258 / 5.075 / 6.570 | 20.415 / 19.819 / 24.662 | 0.165 / 0.106 / 0.383 | 0.005 / 0.005 / 0.009 | 0.000 / 0.000 / 0.000 |
| 416 / 3 | 8.850 / 8.784 / 11.221 | 37.274 / 37.248 / 41.742 | 0.261 / 0.238 / 0.620 | 0.008 / 0.007 / 0.013 | 0.000 / 0.000 / 0.000 |

### Latencia por etapa — MOV real, stream encendido

Milisegundos **media / p50 / p95**, agrupando las muestras de las tres pasadas. Captura usa muestras por frame de origen; las otras etapas, por inferencia.

| imgsz / stride | Captura | Inferencia | Tracking | Conteo | Overlay+JPEG |
| --- | ---: | ---: | ---: | ---: | ---: |
| 320 / 1 | 5.599 / 5.488 / 6.525 | 12.476 / 12.440 / 13.393 | 0.127 / 0.086 / 0.368 | 0.005 / 0.004 / 0.009 | 0.793 / 0.000 / 5.672 |
| 320 / 2 | 8.299 / 8.194 / 11.233 | 21.796 / 21.746 / 24.840 | 0.202 / 0.133 / 0.546 | 0.007 / 0.006 / 0.012 | 1.929 / 0.000 / 8.810 |
| 320 / 3 | 7.547 / 7.359 / 10.470 | 25.119 / 25.058 / 29.150 | 0.199 / 0.195 / 0.467 | 0.006 / 0.005 / 0.010 | 1.726 / 0.000 / 7.404 |
| 352 / 1 | 4.885 / 4.763 / 5.542 | 12.685 / 12.545 / 14.189 | 0.122 / 0.083 / 0.330 | 0.005 / 0.004 / 0.008 | 0.595 / 0.000 / 4.318 |
| 352 / 2 | 6.595 / 6.296 / 8.234 | 21.367 / 21.280 / 23.325 | 0.171 / 0.109 / 0.457 | 0.006 / 0.005 / 0.010 | 1.403 / 0.000 / 6.589 |
| 352 / 3 | 7.684 / 7.563 / 10.610 | 28.034 / 27.925 / 30.978 | 0.191 / 0.122 / 0.507 | 0.006 / 0.006 / 0.011 | 1.886 / 0.000 / 7.536 |
| 384 / 1 | 5.499 / 5.510 / 6.098 | 16.231 / 16.204 / 17.121 | 0.156 / 0.097 / 0.413 | 0.005 / 0.005 / 0.009 | 0.978 / 0.000 / 5.841 |
| 384 / 2 | 8.041 / 7.910 / 10.479 | 25.846 / 25.658 / 30.077 | 0.212 / 0.130 / 0.583 | 0.007 / 0.006 / 0.013 | 2.080 / 0.000 / 8.890 |
| 384 / 3 | 7.817 / 7.634 / 10.481 | 29.387 / 29.180 / 32.924 | 0.202 / 0.127 / 0.521 | 0.006 / 0.006 / 0.011 | 2.077 / 0.000 / 7.620 |
| 416 / 1 | 5.458 / 5.326 / 6.334 | 18.637 / 18.532 / 20.433 | 0.171 / 0.103 / 0.442 | 0.005 / 0.005 / 0.009 | 1.145 / 0.000 / 6.129 |
| 416 / 2 | 5.174 / 5.059 / 6.245 | 20.212 / 19.811 / 23.888 | 0.163 / 0.104 / 0.381 | 0.005 / 0.005 / 0.009 | 0.850 / 0.000 / 4.304 |
| 416 / 3 | 9.129 / 9.167 / 11.470 | 38.118 / 38.133 / 42.938 | 0.284 / 0.248 / 0.688 | 0.008 / 0.007 / 0.015 | 3.295 / 0.000 / 10.763 |

### FPS — AVI sintético preexistente

| imgsz / stride | Stream apagado | Mínimo | Stream encendido | Mínimo | FPS origen medios apagado / encendido | >20 / ≥25 en ambos modos |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 320 / 1 | 102.06 / 101.35 / 103.30 | 101.31 | 102.54 / 102.73 / 102.76 | 102.13 | 102.06 / 102.54 | Sí / Sí |
| 320 / 2 | 92.01 / 92.41 / 92.95 | 90.61 | 92.96 / 93.22 / 93.55 | 92.07 | 184.02 / 185.92 | Sí / Sí |
| 320 / 3 | 95.78 / 95.80 / 97.54 | 93.81 | 94.66 / 95.18 / 95.87 | 92.86 | 284.32 / 280.99 | Sí / Sí |
| 352 / 1 | 89.53 / 89.85 / 91.46 | 87.12 | 85.48 / 88.59 / 91.17 | 76.39 | 89.53 / 85.48 | Sí / Sí |
| 352 / 2 | 81.94 / 81.67 / 82.40 | 81.67 | 84.07 / 84.02 / 84.86 | 83.25 | 163.88 / 168.15 | Sí / Sí |
| 352 / 3 | 80.86 / 80.92 / 81.59 | 80.00 | 81.66 / 81.69 / 82.46 | 80.75 | 240.03 / 242.41 | Sí / Sí |
| 384 / 1 | 81.11 / 81.30 / 82.27 | 79.66 | 83.36 / 83.57 / 83.68 | 82.82 | 81.11 / 83.36 | Sí / Sí |
| 384 / 2 | 68.22 / 68.77 / 69.94 | 65.83 | 71.74 / 72.35 / 72.85 | 69.96 | 136.45 / 143.48 | Sí / Sí |
| 384 / 3 | 74.54 / 73.79 / 76.70 | 72.79 | 77.50 / 77.41 / 77.78 | 77.25 | 221.25 / 230.04 | Sí / Sí |
| 416 / 1 | 70.09 / 70.18 / 70.30 | 69.78 | 69.12 / 69.13 / 70.19 | 67.93 | 70.09 / 69.12 | Sí / Sí |
| 416 / 2 | 64.72 / 64.88 / 64.91 | 64.36 | 64.22 / 64.23 / 64.90 | 63.46 | 129.43 / 128.44 | Sí / Sí |
| 416 / 3 | 58.28 / 57.78 / 59.71 | 57.14 | 61.79 / 62.19 / 62.71 | 60.42 | 173.00 / 183.42 | Sí / Sí |

### Latencia por etapa — AVI sintético preexistente, stream apagado

Milisegundos **media / p50 / p95**, agrupando las muestras de las tres pasadas. Captura usa muestras por frame de origen; las otras etapas, por inferencia.

| imgsz / stride | Captura | Inferencia | Tracking | Conteo | Overlay+JPEG |
| --- | ---: | ---: | ---: | ---: | ---: |
| 320 / 1 | 0.407 / 0.402 / 0.480 | 9.215 / 9.193 / 9.705 | 0.063 / 0.061 / 0.085 | 0.003 / 0.003 / 0.004 | 0.000 / 0.000 / 0.000 |
| 320 / 2 | 0.436 / 0.425 / 0.513 | 10.240 / 10.244 / 10.518 | 0.060 / 0.059 / 0.071 | 0.003 / 0.003 / 0.004 | 0.000 / 0.000 / 0.000 |
| 320 / 3 | 0.394 / 0.386 / 0.469 | 9.855 / 9.852 / 10.248 | 0.058 / 0.056 / 0.071 | 0.003 / 0.003 / 0.004 | 0.000 / 0.000 / 0.000 |
| 352 / 1 | 0.397 / 0.392 / 0.476 | 10.497 / 10.323 / 11.148 | 0.065 / 0.064 / 0.078 | 0.004 / 0.003 / 0.004 | 0.000 / 0.000 / 0.000 |
| 352 / 2 | 0.423 / 0.418 / 0.513 | 11.458 / 11.356 / 12.048 | 0.073 / 0.072 / 0.085 | 0.004 / 0.003 / 0.004 | 0.000 / 0.000 / 0.000 |
| 352 / 3 | 0.413 / 0.412 / 0.472 | 11.665 / 11.550 / 12.189 | 0.073 / 0.072 / 0.085 | 0.004 / 0.004 / 0.004 | 0.000 / 0.000 / 0.000 |
| 384 / 1 | 0.441 / 0.435 / 0.503 | 11.582 / 11.627 / 12.029 | 0.073 / 0.073 / 0.082 | 0.004 / 0.004 / 0.004 | 0.000 / 0.000 / 0.000 |
| 384 / 2 | 0.481 / 0.467 / 0.584 | 13.848 / 13.642 / 14.977 | 0.078 / 0.076 / 0.092 | 0.004 / 0.004 / 0.005 | 0.000 / 0.000 / 0.000 |
| 384 / 3 | 0.435 / 0.431 / 0.504 | 12.671 / 12.638 / 13.700 | 0.076 / 0.074 / 0.092 | 0.004 / 0.004 / 0.005 | 0.000 / 0.000 / 0.000 |
| 416 / 1 | 0.447 / 0.443 / 0.488 | 13.478 / 13.375 / 13.891 | 0.077 / 0.076 / 0.086 | 0.004 / 0.004 / 0.004 | 0.000 / 0.000 / 0.000 |
| 416 / 2 | 0.386 / 0.373 / 0.479 | 14.651 / 14.146 / 17.594 | 0.085 / 0.083 / 0.105 | 0.004 / 0.004 / 0.005 | 0.000 / 0.000 / 0.000 |
| 416 / 3 | 0.484 / 0.478 / 0.565 | 16.280 / 16.206 / 17.473 | 0.083 / 0.082 / 0.096 | 0.004 / 0.004 / 0.005 | 0.000 / 0.000 / 0.000 |

### Latencia por etapa — AVI sintético preexistente, stream encendido

Milisegundos **media / p50 / p95**, agrupando las muestras de las tres pasadas. Captura usa muestras por frame de origen; las otras etapas, por inferencia.

| imgsz / stride | Captura | Inferencia | Tracking | Conteo | Overlay+JPEG |
| --- | ---: | ---: | ---: | ---: | ---: |
| 320 / 1 | 0.403 / 0.398 / 0.476 | 9.121 / 9.153 / 9.440 | 0.060 / 0.059 / 0.071 | 0.003 / 0.003 / 0.004 | 0.062 / 0.000 / 0.677 |
| 320 / 2 | 0.428 / 0.419 / 0.501 | 10.064 / 10.069 / 10.564 | 0.059 / 0.058 / 0.072 | 0.003 / 0.003 / 0.004 | 0.075 / 0.000 / 0.753 |
| 320 / 3 | 0.401 / 0.388 / 0.481 | 9.901 / 9.877 / 10.506 | 0.057 / 0.056 / 0.070 | 0.003 / 0.003 / 0.004 | 0.073 / 0.000 / 0.718 |
| 352 / 1 | 0.390 / 0.380 / 0.488 | 11.016 / 10.281 / 13.618 | 0.071 / 0.066 / 0.096 | 0.004 / 0.004 / 0.005 | 0.064 / 0.000 / 0.575 |
| 352 / 2 | 0.411 / 0.405 / 0.495 | 11.090 / 11.063 / 11.448 | 0.071 / 0.070 / 0.081 | 0.003 / 0.003 / 0.004 | 0.078 / 0.000 / 0.715 |
| 352 / 3 | 0.406 / 0.405 / 0.463 | 11.467 / 11.471 / 11.699 | 0.073 / 0.071 / 0.085 | 0.004 / 0.004 / 0.004 | 0.081 / 0.000 / 0.730 |
| 384 / 1 | 0.429 / 0.422 / 0.498 | 11.187 / 11.148 / 11.596 | 0.072 / 0.071 / 0.080 | 0.004 / 0.004 / 0.004 | 0.077 / 0.000 / 0.690 |
| 384 / 2 | 0.451 / 0.440 / 0.553 | 13.050 / 12.769 / 14.949 | 0.076 / 0.075 / 0.088 | 0.004 / 0.004 / 0.005 | 0.103 / 0.000 / 0.800 |
| 384 / 3 | 0.412 / 0.408 / 0.476 | 12.078 / 11.994 / 12.588 | 0.074 / 0.073 / 0.082 | 0.004 / 0.004 / 0.004 | 0.093 / 0.000 / 0.730 |
| 416 / 1 | 0.448 / 0.442 / 0.497 | 13.585 / 13.453 / 14.128 | 0.077 / 0.076 / 0.089 | 0.004 / 0.004 / 0.004 | 0.096 / 0.000 / 0.712 |
| 416 / 2 | 0.391 / 0.377 / 0.481 | 14.680 / 14.093 / 17.878 | 0.085 / 0.083 / 0.104 | 0.004 / 0.004 / 0.005 | 0.086 / 0.000 / 0.585 |
| 416 / 3 | 0.457 / 0.457 / 0.523 | 15.236 / 15.005 / 15.965 | 0.080 / 0.078 / 0.091 | 0.004 / 0.004 / 0.005 | 0.113 / 0.000 / 0.777 |

### Codificación efectiva y carga observada

Coste de un JPEG **cuando sí se codifica**, separado del promedio por inferencia que incluye frames omitidos por el límite de 10 JPEG/s:

| Fuente / configuración | Overlay+JPEG activo, ms media / p50 / p95 | JPEG/s medios |
| --- | ---: | ---: |
| real / 320 / 1 | 5.554 / 5.499 / 5.898 | 8.79 |
| synthetic / 320 / 1 | 0.679 / 0.679 / 0.717 | 9.34 |
| real / 416 / 1 | 5.855 / 5.817 / 6.511 | 8.68 |
| synthetic / 416 / 1 | 0.705 / 0.696 / 0.738 | 9.39 |

Carga ajena estimada (media de las 144 ejecuciones): **11.1%** del total de ocho CPU; rango **1.3–38.4%**. CPU total ocupada media: **54.7%**. Load average de un minuto al iniciar cada ejecución: **3.58–10.98**. Son observaciones de la sesión, no un entorno aislado.

Los modos se ejecutaron secuencialmente. Diferencias de FPS donde stream encendido parece más rápido no prueban que el overlay acelere inferencia: hay variación de carga y condiciones térmicas no controladas. El coste directo de overlay/JPEG está medido en las tablas por etapa.

## Evaluación contra IN=6 / OUT=6

Datos completos, comandos y advertencias: [benchmark-evaluation.json](evaluations/benchmark-evaluation.json).
Una pasada por configuración, con tracker y contadores inicialmente vacíos, sin
loop, sin descartar calentamiento y sin modificar `conf=0.35`, áreas ni conteo.
La configuración por defecto usa hilos automáticos (7 en este entorno); el
barrido y sus alternativas usan cuatro. El evaluador ignora realtime/loop del
YAML para terminar una sola pasada, incluso si se le proporciona video-demo.yaml.

```sh
.venv/bin/python scripts/evaluate_counts.py --video data/demo1.mov --expected-in 6 --expected-out 6
```

| Configuración y selección | Frames analizados | IN | OUT | Error absoluto IN / OUT | Error % IN / OUT | Error agregado % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 320 / stride 1 / auto — valores por defecto | 1307 | 0 | 0 | 6 / 6 | 100 / 100 | 100 |
| 320 / stride 1 / 4 hilos — mayor media de FPS procesados sin stream | 1307 | 0 | 0 | 6 / 6 | 100 / 100 | 100 |
| 352 / stride 1 / 4 hilos — mayor media de FPS procesados con stream | 1307 | 0 | 1 | 6 / 5 | 100 / 83,33 | 91,67 |
| 320 / stride 3 / 4 hilos — mayor media de FPS de origen | 436 | 0 | 0 | 6 / 6 | 100 / 100 | 100 |
| 416 / stride 1 / 4 hilos — mayor resolución sin saltos que supera 25 FPS | 1307 | 0 | 2 | 6 / 4 | 100 / 66,67 | 83,33 |

Todos decodificaron 1.307 frames; stride 3 analizó 436 de ellos. Error por dirección
= `abs(obtenido - esperado) / esperado × 100`; error agregado =
`(abs(IN - 6) + abs(OUT - 6)) / 12 × 100`. No es una medida de precisión/recall por
evento: faltan etiquetas temporales para emparejar cruces y detectar compensaciones.
Los cinco comandos terminaron correctamente, con la advertencia de −1 frame.
Los errores de conteo son resultados de la evaluación, no excepciones de ejecución.

## Recomendación y optimización

- **Conservar imgsz=320 y vid_stride=1** como base de rendimiento. A cuatro hilos,
  dieron 66,72 FPS medios sin stream y 61,54 con stream, mínimos 62,42 y 61,11,
  respectivamente. Se analizan todos los frames y hay margen sobre 20/25 FPS.
  Ya son los valores de `configs/default.yaml`: no es necesario cambiarlos.
- Para reproducir la medición, usar **torch_threads=4**; el YAML normal mantiene
  `0` (auto) y la demo de video conserva ese valor. Los pilotos favorecieron
  cuatro frente a auto en media, con poca diferencia entre uno/cuatro sobre el
  MOV. No se concluye que cuatro sea óptimo bajo toda carga o en otro equipo.
- 352/stride 1 tuvo mayor media con stream (64,31), pero su ventaja no aparece
  en ambos modos y la carga varió. Recuperó solo una salida. No justifica cambiar
  el valor global por esta única escena. 416/stride 1 recuperó dos salidas, ninguna
  entrada, y promedió 44,46 FPS con stream: cumple 25, pero no los casi 60 FPS
  originales si se pretende analizar todos sus frames a ritmo real.
- **No aumentar stride para esta demo**. La tasa de origen puede subir (hasta
  102,64 FPS medios en 320/3 sin stream), pero la tasa de imágenes analizadas cae
  y no mejoró el conteo. Decodificación e inferencia compiten por CPU; el barrido
  no aísla todos los efectos de carga/temperatura. 416/3 sostuvo solo 21,88 FPS
  medios con stream y es la única combinación real que no alcanzó 25.
- El stream se limita a **10 JPEG/s, calidad 80**. En 320/1 real, codificar un
  frame anotado costó 5,554 ms de media (p95 5,898); se codificaron 8,79 JPEG/s.
  El coste amortizado fue 0,793 ms por inferencia. Conservar el límite evita
  intentar codificar a la tasa completa del detector. Estelas y navegador pueden
  añadir trabajo; el barrido usa estelas apagadas.
- **No hace falta exportar a CoreML para cumplir 20/25 FPS en este equipo** con
  320/1. No se implementó exportación ni se añadieron dependencias. Considerarla
  solo ante un cuello de botella de inferencia medido en otra configuración;
  acelerar el modelo no corrige la geometría o la lógica de un cruce perdido.

## Ajustes de conteo propuestos, sin aplicarlos

Se conservan en los YAML y dataclasses la línea horizontal en `position=0.5`,
`band_half_width=0.04`, dirección positiva, vida mínima 3, tolerancia de pérdida 2
y confianza 0.35. El experimento muestra conteos insuficientes; no permite atribuir
con certeza las pérdidas a una sola causa sin revisar eventos anotados.

1. **Calibrar línea y sentido sobre el umbral físico de la puerta**, en un YAML
   específico. El centro geométrico de la imagen no necesariamente coincide con
   el lugar donde se contaron manualmente las entradas/salidas. Elegir orientación
   según la trayectoria y comprobar `enter_direction` con cruces individuales.
2. **Revisar la banda con las estelas locales.** El semiancho actual 0,04 implica
   una franja total de aproximadamente 154 píxeles en la imagen de 1920 píxeles
   de alto. Si una persona cruza la puerta sin alcanzar ambos lados de esa franja,
   ensayar un semiancho menor (por ejemplo 0,02, unos 77 píxeles totales), y volver
   a probar detenciones/ida y vuelta para detectar dobles conteos por oscilación.
3. **Revisar detecciones e identidades antes de bajar confianza.** Si el overlay
   muestra desapariciones antes del cruce, comparar 0,35 con 0,25 en el YAML de
   experimento y medir también falsos positivos. Si las cajas existen pero cambia
   el ID, revisar continuidad de ByteTrack y pérdidas; cambiar solo `conf` no
   demuestra que se haya corregido ese caso. Verificar también el filtro de área.
4. Repetir esa calibración con varios clips autorizados y referencia temporal de
   cada evento, reservando escenas independientes para validación. No elegir
   valores globales buscando únicamente obtener 6/6 en este video.

## Demo visual y límites de la verificación

`configs/video-demo.yaml` habilita archivo, realtime, loop, MJPEG y estelas. Se
ejecutó la CLI con ese contenido durante **1.400 frames, 58,50 FPS globales**,
superando el fin de la primera pasada; finalizó IN=0/OUT=0. Esa tasa incluye
arranque y la reproducción limitada: es una comprobación funcional, no otro
benchmark ni una repetición de las mediciones anteriores.

Se decodificaron dos JPEG **solo en RAM** (1080×1920), se verificaron HTTP 200 en
salud/HTML de Streamlit y AppTest contra la API real sin excepciones ni errores,
con panel de video y un vagón con señal. Como 8765/8501 estaban ocupados, se usó
una copia de configuración de prueba con rutas absolutas y puertos libres
57444/57445; el MOV no se copió y los procesos previos no se alteraron. Los
procesos de prueba se cerraron. Evidencia: [video-demo-validation.json](evaluations/video-demo-validation.json).

No hubo inspección visual en navegador ni imágenes de personas enviadas a
herramientas externas. Reiniciar los contadores por vuelta evita acumular las
pasadas; no obliga al detector a dar 6/6. Los tests sintéticos sí verifican el
reinicio efectivo de tracker y contadores con cruces conocidos.

Un clip de 21,81 s y tres repeticiones de rendimiento no certifican precisión
general, estabilidad térmica durante horas, ni rendimiento con otra CPU/cámara.
El fondo de carga no estuvo aislado. No se validaron aglomeraciones, oclusiones,
contraluz ni la cámara definitiva. El error observado exige calibración y más
datos antes de presentar este prototipo como contador fiable.

## Nota del nuevo montaje — etapa tripwire histórica, 2026-10-06

La evaluación de `data/demo2.mov` está separada en [door-demo-baseline.json](evaluations/door-demo-baseline.json) y
[door-demo-evaluation.json](evaluations/door-demo-evaluation.json): 2038 frames reproducibles,
1080×1920, 29.793 FPS declarados; lista de edición verificada con FFprobe.
Baseline 320/.35: **70.829 FPS, 0/0**. Perfil diagnóstico 416/.10, ByteTrack sin
fuse_score y cinco ausencias: **52.475 FPS, 4/1** frente a 12/13.
Son tasas de una pasada completa, primera inferencia incluida, sin overlay/JPEG;
carga del modelo fuera del reloj y carga externa sin controlar. **No se repite ni
se sustituye el benchmark histórico** y no se certifica FPS con dashboard nuevo.
La precisión seguía insuficiente y en esa etapa se detuvo la validación final
repetida/demo integrada. La reanudación con compuerta se describe a continuación.


## Compuerta actual y siguiente entrada — actualizado 2026-10-10

El perfil door-demo actual usa dual_zone A=.40/B=.65, TTL .9 s, observaciones de
zona y unión conservadora de fragmentos. Resultado histórico posterior al
tripwire: **8/12 frente a 12/13 (20% agregado)**; dos pasadas de 2038 frames con
misma secuencia, **26.913/26.158 FPS** sin overlay/JPEG. Smoke de dashboard:
**22.83 FPS**. Evidencia separada: [door-gate-evaluation.json](evaluations/door-gate-evaluation.json).
No se sobrescriben ni repiten los pilotos/barridos/JSON anteriores. Esa mejora
no certifica precisión y los promedios de demo no prueban capacidad sostenida
ni latencia. min_zone_frames mide observaciones conservables durante ausencia
admitida, no necesariamente frames consecutivos del archivo.

En esta auditoría solo hubo pruebas sintéticas. El próximo video no existe;
720p/30 fps/30° son previsiones de montaje, no metadatos medidos. El perfil
configs/next-video.yaml conserva defaults como propuesta sin validar; el código
no rectifica perspectiva ni admite franjas oblicuas. Hay que recalibrar.

Benchmark acepta --config y --video; si se omite --video ahora usa source.path
(en comandos históricos el default era data/demo1.mov). Para reproducir esa
entrada histórica especifique --video data/demo1.mov. --real-only permite medir
únicamente la próxima entrada, sin la comparación AVI. La evaluación desactiva
loop/realtime y no reutiliza verified-frames=2038. Destinos JSON deben ser nuevos.
Comandos de próxima validación en README; **no hay una medición nueva del video
pendiente ni de una cámara física**. Descartes live y buffers del dispositivo/
FFmpeg afectan latencia; el buffer de ByteTrack cuenta actualizaciones y no es
un TTL exacto en segundos bajo descartes/cadencia irregular.
