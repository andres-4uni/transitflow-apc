# TransitFlow APC

Repositorio: [andres-4uni/transitflow-apc](https://github.com/andres-4uni/transitflow-apc).

Prototipo universitario de conteo de pasajeros. Procesamiento local en notebook
sin GPU; no almacena frames, rostros ni videos de salida. El modo normal publica
solo telemetría numérica; el video local anotado es una opción de demostración.

Firmware independiente para **XIAO ESP32S3 Sense + OV3660**, con configuración
Wi-Fi por AP protegido, NVS y LED: [guía de cámara](firmware/esp32-camera/README.md).
Compilado y probado con hardware simulado; la carga y aceptación física del nuevo
firmware siguen pendientes. No modifica los defaults ni el pipeline de conteo.

## Instalación (Python 3.11)

```sh
git clone https://github.com/andres-4uni/transitflow-apc.git
cd transitflow-apc
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
mkdir -p models
curl -L --fail https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt -o models/yolov8n.pt
```

`requirements-lock.txt` registra las versiones verificadas en macOS ARM64;
para reproducirlas: `python -m pip install -r requirements-lock.txt`.

Ponga un video autorizado en `data/demo.avi` o seleccione un perfil propio con
`--config`, cambiando allí `source.path`. Las rutas se resuelven desde el padre de `configs/`.

```sh
python scripts/run_demo.py                         # Sin mostrar video
python scripts/run_demo.py --debug                # Vista local; Q termina
python scripts/run_demo.py --max-frames 100
python -m pytest -q
```

Configure `imgsz` (múltiplos de 32 entre 320 y 640), `conf`, `vid_stride`, áreas y
geometría en YAML. Los defaults siguen usando 320; 640 aumenta el coste CPU.
`detection.torch_threads` permite limitar hilos CPU; `0` conserva la selección
automática de Ultralytics. Los hilos usados se registran en el benchmark.
Se informa FPS incluyendo arranque de inferencia; no es un benchmark estable.
Los pesos se descargan una vez, antes de la demo.

La línea horizontal cuenta entrada hacia abajo por defecto (`positive`).
Use `up/down` para horizontal y `left/right` para vertical; `positive/negative`
se conservan por compatibilidad. En **tripwire**, ajuste `position` y
`band_half_width` en coordenadas 0–1. El resumen incluye entradas, salidas y ocupación.
`occupancy.initial` calibra la ocupación al iniciar; la API Python ofrece
`OccupancyCounter.calibrate(n)`, `reset()` y `TripwireCounter.reset()`.
`counting.mode: dual_zone` selecciona la compuerta A/neutro/B mediante el mismo
pipeline: **dual_zone usa `zone_a_max`/`zone_b_min`, no position/band_half_width**.
`min_zone_frames` cuenta observaciones en la zona candidata y conserva presencias
durante una ausencia tolerada; no garantiza frames consecutivos del video.
`max_missing_seconds > 0` usa tiempo de la fuente; `0` conserva el
presupuesto histórico por frames del tripwire. Ambos contadores ofrecen `reset()`.

## Fuentes

Cambie únicamente `source` en un perfil propio, por ejemplo `configs/live-demo.yaml`:

```yaml
# Webcam del notebook; puede requerir permiso del sistema operativo.
source:
  type: webcam
  index: 0
  width: 640
  height: 480
```

```yaml
# URL del flujo de video, no la página de administración de la cámara.
source:
  type: stream
  url: "http://192.168.1.20:8080/video"  # También rtsp://...
  open_timeout_ms: 5000
  read_timeout_ms: 2000
```

Conserve las otras secciones del YAML. Webcam y stream priorizan frames recientes;
archivo conserva todos. Ante desconexión, el programa termina con error y libera
la fuente. Reinicie después de recuperar la conexión.

Para archivos, `--realtime` limita la entrega al FPS original informado por
OpenCV y `--loop` repite el mismo archivo sin copiarlo. Cada vuelta reinicia
ByteTrack, tripwire, ocupación al valor inicial y estelas; los totales corresponden
a esa vuelta. También se configuran con `source.realtime` y `source.loop`.
Si el procesamiento es lento, la reproducción tarda más; no se descartan frames
para recuperar retraso. Ambos flags requieren una fuente `file`.

## Nuevo montaje fijo: perfil de diagnóstico

`configs/door-demo.yaml` usa **data/demo2.mov**: 1080×1920, 29,793 FPS,
2038 frames reproducibles y 67,922 s de contenido editado. La lista de edición
MOV explica los 2053 frames declarados; FFprobe confirmó 2038, y 2053 al ignorarla.
No se modifica el video ni se amplía la tolerancia ±2. `--verified-frames 2038`
expresa esa referencia independiente para este archivo; no reutilizarla en otros.

**Mejora clara, aún insuficiente para certificar una demo de conteo fiable:**
**8 IN / 12 OUT frente a 12/13**, error agregado 5/25 = **20%**, antes 4/1 (80%).
La auditoría temporal es parcial: tres IN omitidos están contrastados, además de
cinco eventos correctos y cambios de ID entre personas. No se calcula
precision/recall ni se certifica ausencia global de FP/duplicados/inversiones.
Historial intacto: [evaluación tripwire](docs/evaluations/door-demo-evaluation.json).
Resultado nuevo y ablaciones: [evaluación de compuerta](docs/evaluations/door-gate-evaluation.json).

Perfil actual: `mode: dual_zone`, horizontal, A y<.40 / B y>.65; neutro [.40,.65]
contiene el umbral físico y≈.60. IN↓ A→B / OUT↑ B→A, anchor centroide, mínimo
3 observaciones totales. Dos presencias por zona; una profunda A<.30/B>.75 puede
confirmar antes de desaparecer por el borde. TTL .9 s por tiempo del contenido;
no depende del FPS de procesamiento. Sin eventos por A→neutro→A ni por seguir en B.

YOLOv8n CPU, **640**, conf=.10, stride=1, hilos auto, ROI x=0..1/y=.10..95.
El ancho completo conserva bordes laterales; cajas, áreas y anchors vuelven a
coordenadas completas. ByteTrack: high/new=.25, low=.10, match=.8, fuse_score=false,
buffer=1 s derivado de FPS/stride (30 actualizaciones aquí). La unión conservadora
requiere TTL, movimiento compatible de dos fragmentos, radio normalizado ≤.35,
coseno ≥.80 y candidato único; registra logical_id además del ID físico.
Un alias antiguo que reaparece fuera del radio inicia otra identidad. No hay
ReID neuronal ni dependencias nuevas. `position/band_half_width` solo afectan
tripwire; el dashboard de compuerta calibra A/B y muestra ambas franjas.

Webcam/HTTP/RTSP se eligen cambiando `source` sin tocar código. En vivo, el contador
usa timestamps de captura; el buffer nominal de ByteTrack puede diferir del tiempo
real si se descartan frames. Recalibre ROI, zonas y radio para otra cámara.

Para abrir el perfil, use dos terminales desde la raíz. Dashboard y productor
verificados con el video real; stream local, estelas y controles A/B operativos:

```sh
.venv/bin/python scripts/run_demo.py --config configs/door-demo.yaml
APC_CONFIG=configs/door-demo.yaml .venv/bin/python -m streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8501
```

Abra http://127.0.0.1:8501, con los puertos 8765/8501 libres. Video/estelas solo
locales y en RAM; el archivo se repite y reinicia conteos por vuelta.
Para otra evaluación numérica completa (destino nuevo; no sobrescribe):

```sh
.venv/bin/python scripts/evaluate_counts.py --config configs/door-demo.yaml --expected-in 12 --expected-out 13 --verified-frames 2038 --diagnostics --output docs/evaluations/nueva-door-gate-evaluation.json
```

El JSON relaciona eventos, lados, edad, centroide, pérdidas, bordes, expiraciones,
uniones de IDs y reapariciones rechazadas. Fragmentos sin evento son candidatos
numéricos para revisar, no omisiones automáticamente certificadas.
Usa tiempo del contenido de OpenCV; si falta, declara fallback frame/FPS.
La evaluación no publica video ni telemetría y desactiva loop/realtime del perfil.
Dos pasadas finales aisladas: **8/12 en ambas**, mismos 20 eventos por frame/ID/
dirección, **26,91 y 26,16 FPS**, incluyendo la primera inferencia,
sin overlay/JPEG y con carga de pesos fuera del reloj; no es benchmark estadístico.
Smoke de dashboard, 900 frames con overlay/JPEG/telemetría: **22,83 FPS**.

## Video real anotado en el dashboard

Desde la raíz del proyecto, cierre el simulador/publicador y el Streamlit anterior
si ocupan los puertos 8765/8501. Ejecute estos dos comandos en terminales separadas:

```sh
.venv/bin/python scripts/run_demo.py --config configs/video-demo.yaml
```

```sh
APC_CONFIG=configs/video-demo.yaml .venv/bin/python -m streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8501
```

Abra **http://127.0.0.1:8501** en este equipo. `video-demo.yaml` usa
`data/demo1.mov`, activa el stream con estelas y establece `source.realtime: true`
y `source.loop: true` (equivalentes a `--realtime --loop`). El archivo no se copia
ni se modifica. Cada vuelta reinicia tracker, contadores y estelas; los conteos
corresponden a esa pasada. La referencia manual es IN=6/OUT=6, no un valor forzado
en el contador. `Ctrl+C` termina cada proceso.

Resultado final con calibración visual: **IN=1/OUT=0 frente a 6/6**. Errores
absolutos IN=5, OUT=6, total=11 (**91,67%**). La línea vertical está en x=0.64,
banda ±0.04 e IN hacia la izquierda. Se conservaron imgsz=320, conf=0.35,
stride=1 y tolerancia de dos frames perdidos; no se ajustaron al objetivo 6/6.
El conteo aún no es fiable. Diagnóstico por intervalo y resultados reproducibles
en [calibration-evaluation.json](docs/evaluations/calibration-evaluation.json) y
[LIMITATIONS](docs/LIMITATIONS.md#evaluación-real-con-calibración-visual--2026-10-03).

**VIDEO LOCAL: no se guarda ni se transmite fuera de este equipo**.
El YAML normal conserva `visualization.stream: false`.

## Calibración de Conteo en Streamlit

Con los dos procesos anteriores abiertos, entre a http://127.0.0.1:8501 y abra
la barra lateral con la flecha de la esquina superior izquierda si está cerrada.
La sección **Calibración de Conteo** muestra la fuente y el perfil que usa el
contador conectado; funciona con archivo, webcam/cámara USB, HTTP y RTSP.

1. Elija **Vertical** para movimiento izquierda/derecha u **Horizontal** para
   arriba/abajo.
2. Mueva **Posición de la línea** hasta el umbral físico del paso. Los valores
   0–1 representan x/anchura o y/altura, independientemente de la resolución.
   Puede usar las flechas del teclado sobre el deslizador para ajustes finos.
3. Ajuste **Semiancho de banda** en 0–1: los límites son posición ± semiancho.
   La histéresis requiere semiancho positivo y ambos límites dentro de la imagen.
   Una propuesta inválida muestra un error y conserva la última calibración válida.
4. Elija el **Sentido de ENTRADA**: izquierda/derecha para vertical, arriba/abajo
   para horizontal. OUT es el movimiento opuesto.
5. Cada cambio válido actualiza automáticamente el video en el siguiente frame,
   sujeto al límite de FPS del MJPEG. La línea central sólida y su leyenda
   **LÍNEA DE CONTEO**, la banda discontinua y las flechas IN/OUT permiten verificarlo.
   Mover controles **reinicia los conteos y la ocupación de la sesión** al valor
   inicial, conservando captura y ByteTrack; termine de calibrar antes de contar.
6. Pulse **Guardar calibración** cuando esté conforme. Solo entonces se escribe
   `counting` en el **YAML activo del contador**, conservando fuente, comentarios y
   demás secciones. No hay selector de otro destino. Con `default.yaml` activo,
   puede previsualizar pero el guardado está bloqueado con un mensaje claro.

Los cambios de vista previa viven en RAM: se pierden al reiniciar el contador si
no los guarda. Mantenga `visualization.stream`, `show_line` y `show_band` activos
para revisar la geometría. El simulador numérico no ofrece calibración de cámara.

Para el pitch con una futura cámara, copie **solo el YAML** de ejemplo y edite su
bloque `source`; no necesita modificar Python:

```sh
cp configs/visual-demo.yaml configs/live-demo.yaml
```

```yaml
source:
  type: webcam
  index: 1  # Ajustar al índice real de la cámara USB o webcam.
  width: 640
  height: 480
```

Para HTTP/RTSP, reemplace ese bloque por `type: stream` y `url` como en la sección
Fuentes. Después ejecute en dos terminales:

```sh
python scripts/run_demo.py --config configs/live-demo.yaml
APC_CONFIG=configs/live-demo.yaml streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8501
```

Calibre observando ese montaje y guarde en `live-demo.yaml`. La calibración del
MOV no se reutiliza automáticamente en la cámara. Flujo compartido:
fuente → YOLO/ByteTrack → zona normalizada → IN/OUT → ocupación → dashboard.

También existe una CLI sin cámara ni imágenes: muestra la propuesta y solo la
persiste con `--save`, siempre en el perfil activo y con la misma protección:

```sh
python scripts/calibrate_counting.py --config configs/live-demo.yaml --orientation vertical --enter-direction left --position 0.5 --band-half-width 0.04
```

## Dashboard y demo sin cámara

**Hito 4 completado:** suite de 83 pruebas aprobada, simulador y servidor Streamlit
verificados por HTTP, y dashboard ejecutado con AppTest contra la API real de cuatro
vagones. Consulte [la evidencia y el alcance de la verificación](docs/PROGRESS.md).

Abra dos terminales desde la raíz, con `.venv` activado:

```sh
# Terminal 1: cuatro vagones simulados; Ctrl+C termina.
python scripts/simulate_telemetry.py
```

```sh
# Terminal 2: dashboard local.
streamlit run dashboard/app.py --server.address 127.0.0.1
```

Abra http://127.0.0.1:8501. El panel indica **SIMULACIÓN**, muestra los tres colores
y se actualiza solo. El gris significa dato de más de `stale_after_seconds` segundos.
La ocupación simulada oscila en ciclos de dos minutos, sin crecimiento ilimitado:

| Vagón | Perfil | Ocupación con capacidad 100 |
| --- | --- | --- |
| 1 | Bajo | 10–30 personas (verde) |
| 2 | Medio | 50–70 personas (amarillo) |
| 3 | Alto | 80–100 personas (rojo) |
| 4 | Variable | 0–110 personas (cambia de color) |

Los perfiles se repiten si configura más vagones. La sección `simulation` del
YAML permite ajustar período, objetivos, variación, máximo y ocupación inicial
del vagón variable. Los cambios son de personas enteras y las entradas/salidas
son acumulativas: `occupancy = initial_occupancy + entries - exits` incluso al
comenzar otro ciclo. El máximo se redondea hacia abajo para no superar el 110%.

Para usar cámara/video, cierre el simulador y ejecute `python scripts/run_demo.py`
en la primera terminal. Un archivo termina al llegar al final; en ese momento
también se cierra la API y el panel indica desconexión.

La API sirve `GET http://127.0.0.1:8765/telemetry` y `/health`, solo en este equipo.
`telemetry.port`, `wagon_id`, `interval_seconds` y `simulated_wagons` se configuran
en YAML. Para un YAML alternativo use `--config ruta/configs/default.yaml` en los
scripts y `APC_CONFIG=ruta/configs/default.yaml streamlit run dashboard/app.py`.

Campos por vagón: `wagon_id`, `entries`, `exits`, `initial_occupancy`, `occupancy`,
`capacity`, `level` (0 verde, 1 amarillo, 2 rojo), `timestamp` (Unix), `fps` y
`simulated` (0/1), `green_below` y `red_above` (razones 0–1 del productor).
La leyenda utiliza esos umbrales, incluso con un YAML distinto en el dashboard.
El cliente admite muestras anteriores sin umbrales y muestra “no informados”.
Consumidores antiguos que rechazan campos adicionales deben actualizar su esquema;
los campos existentes conservan nombre y significado. `/telemetry` no transmite imágenes, coordenadas ni IDs de personas.
No ejecute dos publicadores en el mismo puerto. `Ctrl+C` libera servidor y fuente.

## Vista en vivo anotada — hito 4.5

**Implementada y verificada con el perfil door-demo actual.** El hito 4.5 registró
108 tests y una CLI sintética correcta; una comprobación HTTP posterior a esa demo
finita recibió conexión rechazada y provocó la detención histórica. Se conserva
esa evidencia en [PROGRESS](docs/PROGRESS.md). La comprobación actual del productor
común, MJPEG y navegador se describe en la sección de demo2.

Para la demo visual sin cámara, pesos YOLO ni archivos de video, cierre cualquier
simulador/publicador anterior y use estas dos terminales desde la raíz:

```sh
# Terminal 1: mantener activo mientras se usa el dashboard.
python scripts/run_demo.py --fake-tracks --config configs/visual-demo.yaml
```

```sh
# Terminal 2: abrir http://127.0.0.1:8501 en este mismo equipo.
APC_CONFIG=configs/visual-demo.yaml streamlit run dashboard/app.py --server.address 127.0.0.1
```

`configs/visual-demo.yaml` activa explícitamente el video y las estelas; sus campos
omitidos usan los valores de las dataclasses, no heredan cambios de `default.yaml`.
En `configs/default.yaml`, **`visualization.stream: false` sigue siendo el valor
normal**. Para usar cámara o archivo, configure su fuente y quite `--fake-tracks`.

La sección `visualization` controla línea/banda, cajas, IDs, estelas, contadores,
colores `#RRGGBB`, `trail_length`, `jpeg_quality` (1–100) y `max_fps` (por defecto 10).
La línea sólida azul se identifica como LÍNEA DE CONTEO; la banda es discontinua,
IN es verde y OUT rojo, con flechas físicas según la orientación. El panel incluye ocupación y la leyenda:
**VIDEO LOCAL: no se guarda ni se transmite fuera de este equipo**.

El servidor existente ofrece `/video` como MJPEG exclusivamente en 127.0.0.1.
Solo conserva el último JPEG en RAM y reemplaza el anterior, sin historial ni
grabación. `/video/status` indica si está habilitado y tiene un frame reciente.
Video desactivado devuelve HTTP 404; habilitado sin frames recientes, HTTP 503.
El dashboard muestra un aviso en ambos casos. El JPEG caduca con
`telemetry.stale_after_seconds`; las conexiones terminan al cerrar el publicador.

`--fake-tracks` genera dos cajas con IDs nuevos por ciclo: una entra y otra sale,
alimentando el contador seleccionado y overlay reales. Por defecto, cada ciclo de 8 s
produce IN +1 y OUT +1, con ocupación intermedia 1 y final 0 si se inicia vacío.
`simulation.fake_fps`, `fake_cycle_seconds` y `source.width/height` controlan la
escena artificial. `--max-frames 120` finaliza un ciclo y **cierra también la API**;
omita ese límite para revisar el panel sin que termine antes de abrirlo.

El simulador multivagón `simulate_telemetry.py` sigue publicando solo números.
La demo de tracks usa un único vagón para mantener iguales los conteos visibles
en el video y en la telemetría; no mezcla esos cruces con ocupaciones de prueba ajenas.

## Validación

```sh
python -m pytest -q
```

La suite usa tracks, video sintético, HTTP local real y Streamlit AppTest. No abre
la cámara física ni descarga pesos. La prueba HTTP requiere permitir sockets locales.
La regresión de simulación recorre 10.000 pasos por capacidad y comprueba límites,
saldo, acumuladores no decrecientes y cambios graduales. También verifica que los
perfiles oscilen y que los tres colores sigan presentes durante varios ciclos.
Las pruebas del hito 4.5 incluyen overlay sin mutación del frame, MJPEG por HTTP
local, límites de FPS, apagado por defecto, cierre, prohibición de IO de imágenes
y conteos de tracks artificiales. La suite prohíbe escribir imágenes o videos:
las capturas sintéticas de tests están en RAM, y el transporte HTTP decodifica
MJPEG real generado en memoria. Las nuevas pruebas verifican ritmo del archivo,
reinicio de conteos al repetir, evaluación, warmup y medición de etapas.

## Benchmark y evaluación — hito 5

**Hito 5 completado:** 134 tests aprobados, demo comprobada por HTTP/AppTest y
cinco evaluaciones de conteo documentadas. Se usaron las 144 mediciones existentes,
sin repetir el barrido. OpenCV
declara 1.308 frames del MOV y entrega 1.307: diferencias de hasta **±2 frames**
se registran como advertencia, por instrucción del usuario; no bloquean la
evaluación. Una diferencia mayor sigue produciendo error.

Se mantienen **imgsz=320 / vid_stride=1**. A cuatro hilos, el benchmark en este
equipo dio medias de **66,72 FPS sin stream / 61,54 con stream**. La evaluación
por defecto dio **0/0 frente a 6/6 (100% de error agregado)**; la mejor alternativa
evaluada, 416/1, dio **0/2 (83,33%)**. Se requiere calibrar y validar el conteo;
esas mediciones preceden a la calibración visual actual descrita arriba.
La documentación de uso y limitaciones está actualizada; la precisión sigue pendiente.

El video local autorizado es **`data/demo1.mov`**; no se renombra ni se incluye
en git. Referencia manual: **6 entradas y 6 salidas**. Es solo lectura y no se
generan imágenes ni videos de salida. El benchmark corre **en este equipo**;
un solo video no valida precisión general. Metodología, tablas, recomendaciones y límites
en [BENCHMARK](docs/BENCHMARK.md); estado de ejecución en [PROGRESS](docs/PROGRESS.md).

```sh
# Evaluación final del perfil calibrado: una pasada, sin realtime ni loop.
python scripts/evaluate_counts.py --config configs/video-demo.yaml --expected-in 6 --expected-out 6

# Alternativa puntual, sin modificar la calibración del YAML.
python scripts/evaluate_counts.py --video data/demo1.mov --expected-in 6 --expected-out 6 --imgsz 416 --vid-stride 1 --torch-threads 4

# Máxima velocidad: sin realtime, 12 combinaciones, stream apagado/encendido,
# video real y AVI sintético preexistente, warmup 30, tres repeticiones.
python scripts/benchmark_fps.py --video data/demo1.mov --torch-threads 4 --output docs/benchmarks/nueva-medicion.json
```

El benchmark conserva solo estadísticas JSON y rechaza sobrescribir resultados.
`--imgsz 320 352`, `--vid-stride 1 2`, `--warmup`, `--repeats` y `--max-frames`
permiten acotar otra medición. Usa por defecto `data/demo.avi` como comparación
sintética preexistente; `--synthetic-video` permite indicar otra entrada autorizada.
Mide FPS procesados y de origen por separado; stride no debe inflar la cifra de
imágenes analizadas. El modo stream mide overlay/JPEG en RAM, sin navegador ni
transporte HTTP. No se deben ejecutar otras inferencias o tests en paralelo al medir.

El evaluador informa IN/OUT, error absoluto y porcentaje por dirección, y suma
errores absolutos sin cancelarlos entre direcciones. Si la referencia es cero y
hay detecciones, su porcentaje es `null` (indefinido). Los conteos y umbrales
requieren calibración y validación independiente; no se ajustan línea, banda ni
confianza automáticamente a este video.

Estado: [PROGRESS](docs/PROGRESS.md). Supuestos: [DECISIONS](docs/DECISIONS.md).
Alcance: [LIMITATIONS](docs/LIMITATIONS.md).

## Próximo video y futura cámara — preparación 2026-10-10

`configs/next-video.yaml` es un perfil **independiente**, con ruta local
`data/PENDIENTE-proximo-video.mp4`. El archivo todavía no existe y no se abrió
para esta corrección. Campos omitidos usan defaults de dataclasses; ningún perfil
hereda `default.yaml`. Tripwire, ROI completo y confianza siguen sus defaults:
la geometría del ejemplo **no está validada** sobre la puerta nueva.

El montaje previsto es aproximadamente 1280×720 / 30 fps e inclinación de 30°.
El código no rectifica perspectiva ni admite líneas/franjas oblicuas: solo ejes
horizontal/vertical. Recalibre observando la puerta, defina sentido y mida cruces
individuales con referencia temporal antes de evaluar precisión.

Cuando exista el archivo, use su ruta explícita y conteos manuales reales:

```sh
# Defina VIDEO, IN_MANUAL y OUT_MANUAL con la ruta y referencias del nuevo video.
.venv/bin/python scripts/evaluate_counts.py --config configs/next-video.yaml --video "$VIDEO" --expected-in "$IN_MANUAL" --expected-out "$OUT_MANUAL" --diagnostics --output docs/evaluations/next-video-evaluation-01.json

# Tres repeticiones, solo esa entrada; mide overlay/JPEG apagado y encendido en RAM.
.venv/bin/python scripts/benchmark_fps.py --config configs/next-video.yaml --video "$VIDEO" --real-only --imgsz 320 --vid-stride 1 --warmup 30 --repeats 3 --output docs/benchmarks/next-video-benchmark-01.json
```

Ambas herramientas rechazan destinos existentes; cambie el sufijo para otra
pasada. Evaluación desactiva loop/realtime incluso si están activos en el perfil;
benchmark real usa una pasada sin realtime. No use `--verified-frames 2038`:
ese número corresponde exclusivamente a demo2; omita el flag hasta contar con
una referencia independiente del archivo nuevo. No hay resultados de rendimiento
ni precisión del video pendiente. El benchmark toma `source.path` si se omite
`--video`; `--real-only` evita depender del AVI histórico. Sin ese flag conserva
la comparación sintética preexistente; imgsz/stride siguen siendo un barrido si
no se especifican explícitamente como arriba.

Para seleccionar fuente de demo, copie **solo el perfil YAML** a
`configs/live-demo.yaml` y edite su bloque `source` (no cambie Python):

| Fuente | Bloque source | Datos reales / solicitudes |
| --- | --- | --- |
| Archivo | `type: file`, `path: /ruta/local/nuevo.mp4`, `loop: false`, `realtime: false` | Resolución/FPS/frames se leen del archivo; width/height YAML no lo redimensionan. |
| Webcam/USB | `type: webcam`, `index: 0`, `width: 1280`, `height: 720` | Índice selecciona dispositivo; width/height son solicitudes que puede rechazar. |
| HTTP/RTSP | `type: stream`, `url: http://IP/video` o `rtsp://IP/flujo` | FFmpeg lee el flujo ofrecido; width/height YAML no negocian resolución. Timeouts de apertura/lectura son solicitudes al backend. |

No se configura un FPS objetivo para la cámara. CAP_PROP_FPS informa una tasa
nominal del backend (puede faltar); los píxeles decodificados determinan resolución
real, y timestamps de captura/contenido rigen el contador. Solicitar 1280×720 no
promete 30 fps efectivos. **OV3660 identifica un sensor, no el transporte**:
confirme si el equipo completo ofrece USB, HTTP o RTSP antes de elegir fuente.

```sh
.venv/bin/python scripts/run_demo.py --config configs/live-demo.yaml
APC_CONFIG=configs/live-demo.yaml .venv/bin/python -m streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8501
```

Para usar el archivo en la demo, cambie la ruta pendiente en next-video.yaml y
seleccione ese perfil con `--config`. Stream y debug permanecen apagados por
defecto; una revisión visual exige activar explícitamente stream en el perfil
local o usar `--debug`. API/MJPEG continúan exclusivamente en 127.0.0.1.
Mover un control válido actualiza la vista y reinicia conteos; consultar no.
Un reinicio del productor adopta su geometría si no hay borrador pendiente.
Ante cambio externo/reinicio con edición pendiente, el panel conserva el borrador
y exige elegir “Usar configuración del productor” o “Aplicar edición local”.
Guardar sigue siendo un botón explícito; revisión pendiente espera el próximo
frame y un envío fallido no se reintenta automáticamente.

Los FPS mostrados por demo/dashboard son promedios de ejecución, no certifican
capacidad sostenida ni latencia. La cola live acotada reemplaza frames sin esperar,
pero dispositivo/driver/FFmpeg pueden conservar buffers anteriores. ByteTrack
vence por **actualizaciones de inferencia**: su buffer nominal no equivale
exactamente a segundos cuando se descartan frames o cambia la cadencia.
Las pruebas sintéticas 720p/30 fps verifican el flujo de coordenadas y eventos;
no comprueban detección YOLO sobre personas, montaje físico ni precisión APC.
