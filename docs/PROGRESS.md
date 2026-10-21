# Progreso

**Checkpoint físico 2026-10-21:** usuario confirma firmware propio, portal Wi-Fi
corregido, hotspot, LED fijo, mDNS, capture y MJPEG; **60 frames 320×240 en 2,232 s,
26,88 FPS recibidos** (no YOLO). Rechazo Origin/CSRF superado. Integración de
software en preparación; pruebas físicas de detección esperan la carcasa.
No cambiar firmware ni calibración. Detalle al final de este registro.

**Resumen 2026-10-10:** primera evaluación de demo3: **6 IN / 4 OUT frente a 6/6**,
error agregado 16,67%. El archivo entrega 848×476 / 29,964 FPS, no 1280×720.
Dos OUT se omiten por cajas ensanchadas después de ByteTrack, rechazo de área y
caducidad del tripwire. Sin cambios de producción, umbrales ni algoritmo.
142 pruebas pertinentes aprobadas. Calibración física y cámara real pendientes.
La regresión completa anterior de auditoría conserva **339 passed in 15.95s**.

## Hito 1 — completado
- Implementados esqueleto, configuración validada, captura de archivo en hilo,
  YOLOv8n/ByteTrack en CPU, filtrado de área y vista anotada local optativa.
- Validación: `.venv/bin/python -m pytest -q`: **18 passed**.
- Ejecutado `.venv/bin/python scripts/run_demo.py --debug --max-frames 80`:
  **80 frames, 33.23 FPS**, YOLOv8n real en CPU y vista OpenCV activada,
  con video sintético sin personas. Esto valida ejecución, no precisión de detección.
- `compileall` y `git diff --check` sin errores.
- Entorno: inicialmente Python 3.14; instalado Python 3.11.15. La descarga
  requirió acceso de red fuera del sandbox. La primera demo dentro del sandbox
  terminó (40 frames, 3.72 FPS), pero macOS avisó de un servicio gráfico no accesible;
  repetida fuera del sandbox sin ese aviso. Caché Ultralytics creada explícitamente.
- Dependencias exactas registradas en `requirements-lock.txt` (macOS ARM64).
- Ningún test falló. Siguiente: hito 2, conteo puro y ocupación.

## Hito 2 — completado
- Implementado tripwire puro con banda, vida mínima, caducidad y retorno del mismo ID.
- Implementada ocupación con calibración/reseteo, límites del semáforo e integración en demo.
- Validación acumulada: `.venv/bin/python -m pytest -q`: **48 passed**.
- Ejecutada demo CPU sobre 40 frames sintéticos; salida numérica con cero entradas,
  salidas y ocupación. Cruces reales del contador verificados con tracks simulados.
- `git diff --check` sin errores. Ningún test falló. Siguiente: fuentes webcam/stream.

## Hito 3 — completado
- Fuentes webcam/HTTP(S)/RTSP seleccionables por YAML, cola reciente para vivo,
  timeouts de stream, errores explícitos y liberación de recursos.
- `.venv/bin/python -m pytest -q`: **61 passed**, incluida lectura HTTP real con
  OpenCV/FFmpeg y servidor 127.0.0.1 (requiere sockets fuera del sandbox).
- Verificados selección YAML, parámetros de webcam/timeouts, reemplazo de frames,
  desconexión, apertura fallida y liberación de capturas. Webcam y RTSP simulados.
- `compileall` y `git diff --check` sin errores. Ningún test falló.
- Siguiente: hito 4, API numérica local y dashboard multivagón.

## Hito 4 — completado (2026-09-30)
- API HTTP local en memoria, esquema numérico validado y publisher integrado en la demo.
- Simulador multivagón y dashboard Streamlit con semáforos, conteos, identificación
  visible de simulación y estado sin señal para datos viejos.
- Corregidas las tres pruebas del dashboard con una ruta absoluta compartida:
  `Path(__file__).resolve().parents[1] / "dashboard" / "app.py"`.
- Suite completa: `.venv/bin/python -m pytest -q` → **68 passed in 1.74s**.
  Ejecutada fuera del sandbox para habilitar los sockets locales de las pruebas.
- Servicios ejecutados después de aprobar la suite:
  - `.venv/bin/python scripts/simulate_telemetry.py`
  - `.venv/bin/python -m streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8501`
- Verificación HTTP: `/health` de la API en el puerto 8765 devolvió **200** con
  `{"ok": 1}`; `/_stcore/health` de Streamlit en 8501 devolvió **200** con `ok`;
  la página `/` devolvió **200**, contenido HTML.
- Dos lecturas de `/telemetry` confirmaron **cuatro vagones**, `simulated=1`,
  timestamps crecientes y entradas cambiantes.
- Dashboard ejecutado mediante AppTest **contra la API real, sin mocks**:
  cero excepciones y errores, etiqueta SIMULACIÓN, tarjetas VAGÓN 01–04 y
  **4 / 4** vagones con señal. Una segunda ejecución actualizó entradas de **650 a 655**.
  La suite también verifica los tres colores, datos caducados y desconexión.
- Límite de esta comprobación: no hubo inspección visual en navegador. La herramienta
  de navegador no estuvo disponible (IAB no disponible; interfaz nativa sin poder
  iniciar y runtime Node ausente al reintentar). Se verificaron HTTP, ejecución de
  Streamlit y actualización de métricas mediante AppTest; no se afirma revisión visual.
- Antecedente resuelto: en el commit WIP `3a0fe43` hubo **65 aprobadas y 3 fallidas**
  porque Streamlit 1.64.0 resolvía la ruta relativa desde `tests/`. Se había detenido
  el trabajo; esta corrección y validación fueron autorizadas al retomarlo.
- Dependencias exactas en `requirements-lock.txt`. No se modificó el producto ni
  se añadieron dependencias para corregir los tests.
- Hito 5 **no iniciado**, por instrucción del usuario. Hito 6 no iniciado.

## Corrección de simulación — completada (2026-09-30)

- Problema: las fórmulas anteriores acumulaban más entradas que salidas para todos
  los vagones, de modo que la ocupación crecía indefinidamente y todos acababan rojos.
- Implementados ciclos acotados en el generador usado por `simulate_telemetry.py`,
  con objetivos y período configurables en `configs/default.yaml`.
- Rangos por defecto con capacidad 100: **10–30, 50–70, 80–100 y 0–110**.
  Entradas/salidas acumulativas, coherentes con el saldo inicial y sin reinicio al
  cambiar de ciclo. Los primeros tres vagones mantienen verde, amarillo y rojo;
  el cuarto cambia entre los tres colores.
- `.venv/bin/python -m pytest -q`: **83 passed in 2.44s**. Regresión de 10.000 pasos
  para capacidades 1, 37, 100 y 317; valida límites, saldo, acumuladores y gradualidad.
  Otras pruebas cubren oscilación, colores, paso 1.000.000.000, cadencia y configuración.
- Reiniciado el simulador local; comprobado por HTTP y con AppTest conectado a la
  API real: cuatro vagones con señal, ocupación acotada, saldo consistente y los tres
  estados presentes en el dashboard, sin errores.
- Sin fallos de pruebas. Hito 5 no iniciado; cambios preexistentes en `AGENTS.md`
  conservados fuera de esta corrección.

## Hito 4.5 — implementación hecha; validación integrada detenida (2026-10-01)

- Commit `91ec1e7`: configuración visual y overlay puro. **94 passed in 2.49s**,
  incluidos colores, toggles, estelas acotadas, copia del frame y stream apagado.
- Commit `e07d2df`: MJPEG local en memoria. **99 passed in 5.06s**. HTTP real,
  cabeceras y JPEG decodificado, apagado, espera sin frames, caducidad, FPS, cierre
  de lectores y prohibición de IO de archivos durante overlay/codificación/HTTP.
- Commit `80b3a39`: dashboard con estado real del video, leyenda local y modo
  `--fake-tracks`. Suite completa: **108 passed in 7.66s**. Tres ciclos producen
  IN=3, OUT=3 y ocupación final=0 en ambas orientaciones/sentidos; alcanza 1 durante
  el ciclo. La CLI fake se prueba sin detector, captura ni escritura de imágenes.
- Ejecución real: `.venv/bin/python scripts/run_demo.py --fake-tracks --config
  .cache/hito45/configs/demo.yaml --max-frames 600`. Configuración temporal de prueba:
  puerto 18765, fake_fps=30, fake_cycle_seconds=1, stream=true y estelas activas.
  Salida exitosa: `{"frames": 600, "fps": 29.93, "entries": 20, "exits": 20,
  "occupancy": 0}`. Es una comprobación funcional, no un benchmark del hito 5.
- **Falló la comprobación integrada posterior** al solicitar `/video/status` en
  127.0.0.1:18765: `URLError: <urlopen error [Errno 61] Connection refused>`.
  La demo finita ya había terminado sus 600 frames y cerrado el servidor. El script
  de comprobación se interrumpió antes de leer dos frames y ejecutar AppTest contra
  ese proceso. No es un fallo de los 108 tests, pero sí de la verificación adicional.
- Según la regla del usuario, se detuvo la validación al primer fallo. No se reinició
  la demo ni se repitió el chequeo; no se completó inspección visual del frame sintético.
- README, DECISIONS y LIMITATIONS actualizados con modo optativo, uso, privacidad
  y alcance pendiente. `visualization.stream` sigue false en `default.yaml`; el
  ejemplo `visual-demo.yaml` requiere selección explícita.
- Al retomar: iniciar un publicador persistente (sin `--max-frames`) o sincronizar
  prueba y proceso con un readiness check; leer MJPEG, verificar AppTest contra la
  API de esa misma demo y revisar un frame sintético solo en memoria. Detener luego
  el proceso de prueba. No afirmar finalización integral hasta cerrar esos pasos.
- Hito 5 no iniciado. Los cambios previos del usuario en `AGENTS.md` quedan intactos.

## Hito 5 — detenido en el paso 0 (2026-10-01)

- Se leyó este documento antes de trabajar. No se repitieron las verificaciones
  anteriores ni se retomó la validación pendiente del hito 4.5.
- Se intentó abrir `data/demo.mov` con `cv2.VideoCapture` desde la raíz del proyecto,
  usando `.venv/bin/python`. Resultado: `capture.isOpened()` devolvió false.
- Mensaje de OpenCV: `Couldn't read video stream from file "data/demo.mov"`.
  La comprobación terminó con código 1 antes de decodificar cualquier frame.
- Comprobación posterior de existencia, sin abrir el contenido: la ruta
  `/Users/andresespinoza/transport-cam-counter/data/demo.mov` **no existe** en este
  workspace (`Path.exists() == False`, `Path.is_file() == False`). No hay evidencia
  de un problema de códec: falta el archivo en la ubicación solicitada.
- FPS, resolución y número de frames: **no disponibles**, porque no se pudo abrir.
  No se copió, modificó, convirtió ni subió ningún video. No se escribieron frames
  ni imágenes a disco.
- Se detuvo el trabajo siguiendo la condición explícita del usuario. No se
  implementaron `--realtime`, `--loop`, evaluación ni benchmark; tampoco se ejecutó
  el barrido ni se modificó la configuración por defecto. No hay resultados nuevos
  de rendimiento o precisión que reportar. La suite no se repitió: solo cambió esta
  documentación después del fallo de la comprobación inicial.
- Para retomar: disponer del video en la ruta indicada o confirmar su ubicación
  local correcta; repetir primero la apertura. Los valores manuales N/M de
  entradas/salidas también quedan pendientes para la evaluación posterior.
- Hito 6 no iniciado. Se preservan los cambios previos del usuario en `AGENTS.md`.

### Reintento del paso 0 — discrepancia de nombre identificada (2026-10-01)

- Se volvió a leer PROGRESS antes de retomar. El usuario confirmó referencia manual:
  **6 entradas y 6 salidas**; esos valores ya no están pendientes.
- La nueva comprobación de `data/demo.mov` falló en `Path.stat()` con
  `FileNotFoundError`, antes de ejecutar `cv2.VideoCapture`. Se detuvo el trabajo
  inmediatamente; no hubo una segunda apertura ni se pasó al benchmark.
- Inspección solo de nombres/metadatos de `data/`: el archivo real presente se
  llama **`data/demo1.mov`**, de **36.190.296 bytes**. También está `data/demo.avi`,
  el video sintético anterior. `data/demo.mov` sigue sin existir en este workspace.
- El fallo anterior no puede marcarse como resuelto todavía: se identificó la
  diferencia `demo1.mov` frente a `demo.mov`, pero no se verificó la apertura del
  archivo encontrado. No se renombró, copió, modificó ni abrió ese video; tampoco
  se guardaron frames o imágenes.
- Para retomar sin cambiar el archivo, usar explícitamente `data/demo1.mov` y
  comprobar primero su apertura. Mantener referencia manual IN=6 / OUT=6.
- Solo se actualiza esta documentación y se conserva la regla de detenerse ante
  fallos. Sin resultados de rendimiento, cambios de código ni inicio del hito 6.

### Paso 0 resuelto — apertura verificada (2026-10-02)

- Por instrucción del usuario se utiliza **`data/demo1.mov`**, sin renombrarlo.
  El fallo de ruta anterior queda **resuelto**: OpenCV/FFmpeg lo abrió y decodificó
  el primer frame en memoria. Referencia manual confirmada: **IN=6, OUT=6**.
- Metadatos: **1080 × 1920**, **59,9724896836 FPS**, **1.308 frames**, **21,81 s**,
  **36.190.296 bytes**. `mtime_ns` inicial: `1790883891314778494`.
- El video sigue siendo solo lectura: sin copia, conversión, subida ni escritura
  de frames/imágenes. No se mostraron imágenes con personas mediante herramientas.
- Revisión del código: todavía faltan realtime/loop, evaluación y benchmark.
  Se continúa desde esas partes, sin repetir la validación del hito 4.5.
- Lectura de hardware: el sandbox restringió `sysctl`; la misma consulta de solo
  lectura se ejecutó con autorización del entorno. Equipo: Mac14,2, Apple M2,
  8 CPU lógicas, 16 GiB, macOS 26.6.2. No fue un fallo de tests ni del video.
- Hito 5 en curso. Hito 6 no iniciado.

### Paso 1 — archivos y evaluación verificados (2026-10-02)

- Implementados `--realtime` y `--loop`, también configurables en YAML. Cada
  vuelta reinicia las identidades y los conteos; no acumula cruces entre vueltas.
- `scripts/evaluate_counts.py` informa conteos por dirección, error absoluto y
  porcentual, incluyendo el caso de referencia cero sin división por cero.
- Suite completa: `.venv/bin/python -m pytest -q -x` → **117 passed in 8.27s**,
  con sockets locales autorizados. Pruebas nuevas de ritmo, bucle y evaluación
  sobre video sintético en memoria. Se eliminó la escritura de AVI temporal de
  las pruebas y se prohíben `imwrite`/`VideoWriter` en toda la suite.
- CLI ejecutada con YOLO/ByteTrack reales sobre el AVI sintético preexistente:
  `evaluate_counts.py --video data/demo.avi --expected-in 0 --expected-out 0`:
  80 frames, IN=0, OUT=0, error 0. Sin creación de imágenes/videos.
- Sin fallos de validación. Siguiente: instrumentación, benchmark y barrido.

### Paso 2 — instrumentación verificada; mediciones en curso (2026-10-02)

- Implementado `benchmark_fps.py`: warmup descartado, tres repeticiones,
  percentiles, barrido de tamaño/stride, captura/inferencia/ByteTrack/conteo/
  overlay+JPEG, comparación sintética y registro de carga de fondo.
- Hilos de torch configurables en YAML/CLI, sin dependencias nuevas. Se mantiene
  la elección automática por defecto. Ningún ajuste de línea, banda o confianza.
- Suite completa: **123 passed in 7.65s**. Incluye warmup, stream en RAM, stride,
  estadísticas, rechazo de realtime y callback de tracking sin duplicación.
- Piloto real ejecutado (300 frames, warmup 30, tres repeticiones por modo):
  320/stride 1, automático = 7 hilos reales; media **69,57 FPS** sin stream,
  **67,32 FPS** con stream. Archivo `docs/benchmarks/benchmark-pilot-auto.json`, solo números.
  Es una muestra inicial, no reemplaza el barrido completo ni evalúa precisión.
- Siguiente: comparar hilos explícitos, barrido completo y evaluación IN=6/OUT=6.

### Paso 3 — barrido completo iniciado (2026-10-02)

- Pilotos de 300 frames, tres repeticiones y ambos modos de stream completados:
  automático (7 hilos), 4 hilos y 1 hilo. Archivos numéricos
  `docs/benchmarks/benchmark-pilot-auto.json`, `docs/benchmarks/benchmark-pilot-4threads.json` y
  `docs/benchmarks/benchmark-pilot-1thread.json`. En real, medias sin/con stream:
  **69,57/67,32**, **71,80/69,42** y **71,32/69,26 FPS**, respectivamente.
- Se eligen 4 hilos explícitos para comparar las 12 combinaciones bajo una misma
  condición; todavía no se cambia la selección automática en default.yaml.
- Suite ampliada: **124 passed in 8.79s**, incluida la CLI de bucle con reinicio
  efectivo de tracker/conteos entre vueltas. Sin fallos de validación.
- En ejecución: `benchmark_fps.py --torch-threads 4 --output
  docs/benchmarks/benchmark-results.json`. Archivo real completo, warmup de 30 inferencias,
  tres repeticiones × 12 combinaciones × dos estados del stream × dos videos.
  La comparación sintética repite el AVI preexistente para igualar 1.308 frames.
  No se ejecutan tests ni otros trabajos de inferencia a la vez que el barrido.

### Detenido tras el barrido — diferencia de frames (2026-10-02)

- `benchmark_fps.py` terminó con código 0: **48 grupos, 144 ejecuciones**, tres
  repeticiones por configuración/modo/fuente, warmup 30, cuatro hilos efectivos.
  Resultados numéricos preservados en `docs/benchmarks/benchmark-results.json`; tablas en
  `docs/BENCHMARK.md`. El origen y la comparación sintética no se modificaron.
- **Falló una comprobación posterior**: `assert all(r['decoded_frames'] == 1308
  for r in runs)` produjo `AssertionError`. El script de comprobación acabó con
  código 1. Ese supuesto de igualdad exacta fue añadido durante esta tarea.
- Diagnóstico solo de los JSON ya generados: OpenCV informa `frames=1308`, pero
  las **72 pasadas reales entregaron 1307**. Las 72 sintéticas se limitaron a
  esos 1307 frames observados. La diferencia es consistente y no prueba por sí
  sola corrupción; falta determinar si es metadato aproximado, fin de lectura
  del backend o pérdida de decodificación. No se volvió a abrir ni convertir el
  video para investigarlo después del fallo.
- Hubo un error de coordinación: en el mismo lote de herramientas se lanzó el
  generador de tablas y la primera evaluación antes de revisar el código de
  salida de esa comprobación. Al advertirlo se detuvo el avance. El evaluador
  CLI terminó, pero su envoltorio falló por la misma exigencia de 1308 frames:
  `RuntimeError: La evaluación no recorrió los 1308 frames del MOV`. No siguió
  con las mejores configuraciones ni generó `docs/evaluations/benchmark-evaluation.json`; no se
  publican conteos de esa evaluación como aceptados.
- El intento de localizar el proceso para interrumpirlo encontró una restricción
  del sandbox en `psutil.process_iter` (`Operation not permitted`). Al consultar
  la sesión, el proceso ya había terminado con código 1 por la comprobación
  anterior; no quedó una evaluación activa ni se reintentó esa operación.
- Las tablas se marcan **provisionales**. Sobre los frames observados, todas las
  combinaciones reales superaron 20 FPS en las tres pasadas; 416/stride 3 no llegó
  a 25 en ninguno de los modos. 320/stride 1: medias **66,72 FPS** sin stream y
  **61,54 FPS** con stream. No se decide una configuración final con la validación
  detenida, ni se cambian imgsz/stride/conf/línea/banda por estos datos.
- Última suite aprobada antes del barrido: **124 passed in 8.79s**. No se repiten
  tests ni mediciones tras este fallo; solo se documenta y conserva el trabajo.
- Privacidad: `data/demo1.mov` conserva **36.190.296 bytes** y `mtime_ns`
  **1790883891314778494**. No se copió, renombró, convirtió ni subió; no se
  escribieron frames o imágenes. Los dos videos siguen ignorados por git.
- Pendiente al retomar: resolver/aceptar explícitamente la discrepancia de un
  frame sin modificar el MOV; aprovechar los 144 resultados sin repetir el barrido
  si siguen siendo válidos; ejecutar evaluación completa de defaults y mejores
  configuraciones contra **IN=6/OUT=6**; cerrar recomendación y documentación;
  crear y verificar `configs/video-demo.yaml` basado en `visual-demo.yaml`, con
  fuente file `data/demo1.mov` y stream activo. Ese YAML **no se creó** por la
  orden de detenerse ante fallos. Hito 5 incompleto; hito 6 no iniciado.

### Reanudación autorizada — tolerancia y demo listas (2026-10-02)

- Se leyó PROGRESS antes de retomar. Por instrucción explícita del usuario, la
  diferencia **1307 − 1308 = −1** queda **resuelta como advertencia aceptada**.
  `validate_frame_count` admite hasta ±2; fuera de ese margen sigue fallando.
  Evalúa pasadas completas, no límites deliberados ni bucles sintéticos.
- Se eliminó la igualdad exacta del envoltorio temporal. Evaluación y benchmark
  usan ahora la política compartida y registran declarado/decodificado/diferencia/
  tolerancia/advertencia. No se modifica el MOV para hacer coincidir sus metadatos.
- Revisados los números existentes: las 72 pasadas reales quedan aceptadas con
  advertencia; las 72 sintéticas habían igualado el total real observado. Registro
  en `docs/evaluations/benchmark-validation.json`, con hash del JSON original sin modificarlo.
  **No se repitió el benchmark ni sus pilotos.**
- Creado `configs/video-demo.yaml`, basado en `visual-demo.yaml`: fuente file
  `data/demo1.mov`, realtime, loop, stream y estelas activos. README contiene los
  dos comandos exactos para publicador y Streamlit con APC_CONFIG.
- Suite completa tras el cambio: **134 passed in 8.73s**, con HTTP local real y
  prohibición global de escritura de imágenes/videos. Incluye ±1/±2, igualdad,
  rechazo de ±3, advertencia propagada y benchmark deliberadamente recortado.
- Primera evaluación completa aceptada con configuración por defecto: **1307
  frames, IN=0, OUT=0** frente a **6/6**; error absoluto **6 por dirección**, **100%**
  por dirección y combinado. La advertencia de un frame no interrumpe la CLI.
  Es un resultado de precisión insuficiente, no una excepción de ejecución.
- Continúa la evaluación de las alternativas seleccionadas del barrido y el
  cierre de BENCHMARK/limitaciones; después se verificará la nueva demo local.
  Hito 6 no iniciado. Cambios previos del usuario en AGENTS.md intactos.

### Hito 5 completado — evaluación y cierre (2026-10-02)

- Commit `f6b0383`: tolerancia versionada, tests, advertencias y configuración
  de video prioritarias. Suite completa **134 passed in 8.73s**; desde esa
  validación solo se añadieron resultados y documentación, no cambios de código.
- Cinco evaluaciones CLI completas terminaron con código 0 y advertencia de −1
  frame. Todas decodificaron 1307; stride 1 analizó 1307, stride 3 analizó 436.
  Resultados y comandos en `docs/evaluations/benchmark-evaluation.json`:

  | imgsz / stride / hilos | IN / OUT | Error absoluto IN / OUT | Error agregado |
  | --- | --- | --- | --- |
  | 320 / 1 / auto (por defecto) | 0 / 0 | 6 / 6 | 100% |
  | 320 / 1 / 4 (mejor FPS procesado sin stream) | 0 / 0 | 6 / 6 | 100% |
  | 352 / 1 / 4 (mejor FPS procesado con stream) | 0 / 1 | 6 / 5 | 91,67% |
  | 320 / 3 / 4 (mejor tasa de origen) | 0 / 0 | 6 / 6 | 100% |
  | 416 / 1 / 4 (mayor resolución con ≥25 FPS) | 0 / 2 | 6 / 4 | 83,33% |

- La falta de precisión queda explícita: el hito completa medición y evaluación,
  no certifica un contador fiable. Se conserva imgsz=320/stride=1; línea, banda,
  dirección, áreas y confianza no se ajustan a un único clip. BENCHMARK propone
  calibrar umbral físico, sentido, banda y detecciones con más escenas anotadas.
- BENCHMARK.md completado con las 144 mediciones existentes, tablas de FPS y
  latencias, evaluación 6/6, hardware/carga, recomendaciones, alcance y CoreML
  no necesario para 20/25 FPS en este equipo. Sin dependencias nuevas, exportación
  ni repetición del barrido. Su JSON original conserva el hash registrado.
- Nueva demo real ejecutada: `run_demo.py --config <config de prueba derivado
  de video-demo.yaml> --max-frames 1400`, realtime y loop activos. Salida:
  **1400 frames, 58,50 FPS globales, IN=0, OUT=0, ocupación=0**. Superó el fin de
  la primera vuelta y terminó correctamente. Es validación funcional, no benchmark.
- Se decodificaron **dos JPEG 1080×1920 en RAM** desde `/video`, con cabeceras
  MJPEG y no-store. Streamlit dio **200** en salud y HTML; AppTest contra esa API
  real mostró video, leyenda local y **1 / 1** vagones con señal, sin excepciones
  ni errores. Sin inspección visual ni envío de imágenes a herramientas externas.
- Los puertos 8765/8501 estaban ocupados: se usó configuración temporal con
  puertos **57444/57445** y rutas absolutas a los mismos video/pesos. Solo se
  copió configuración YAML, nunca el video. Procesos previos intactos; procesos
  de prueba cerrados. Evidencia en `docs/evaluations/video-demo-validation.json`.
- README contiene los dos comandos exactos con `configs/video-demo.yaml` y
  APC_CONFIG; avisa liberar los puertos anteriores. LIMITATIONS refleja el error
  real y las limitaciones de generalización. El MOV conserva tamaño/mtime, sin
  copia, renombrado, conversión, subida ni escritura de frames o imágenes.
- No hubo fallos nuevos de tests ni ejecución. La advertencia MOV queda aceptada.
  El mal conteo es un resultado documentado que requiere una futura tarea de
  calibración. **Hito 6 no iniciado**; cambios previos de AGENTS.md preservados.

## Estado actual — actualizado 2026-10-10

| Hito | Estado | Commit / evidencia |
| --- | --- | --- |
| 1 | Completado | `7dce1fb`, 18 tests + demo CPU con debug |
| 2 | Completado | `130cd6e`, 48 tests + demo CPU con conteos |
| 3 | Completado | `99f4602`, 61 tests + transporte HTTP real |
| 4 | Completado | 83 tests + simulación acotada + API real y AppTest verificados |
| 4.5 | Implementación e integración verificadas | Compuerta/overlay/calibración verificados el 06-10; regresión sintética de auditoría aprobada; precisión pendiente |
| 5 | Mediciones históricas completas | 144 mediciones conservadas; compuerta actual demo2 8/12 frente a 12/13, 20% agregado; precisión insuficiente; próximo video sin medir |
| 6 | Uso/decisiones/límites actualizados | Perfil pendiente y guía de archivo/USB/HTTP/RTSP; cámara física y validación independiente pendientes |

## Calibración y diagnóstico — contador (2026-10-02)

- Inspeccionados AGENTS, configuración, contador, detector, overlay, publisher,
  dashboard, demo y evaluador antes de modificar el comportamiento.
- Reproducido **0 IN / 0 OUT** sobre los **1307 frames** de `demo1.mov` con
  configuración original. Debug textual optativo confirma orientación horizontal
  inadecuada para movimiento lateral y pérdidas de tracks; no hubo rechazos por área.
- El contador usa centroide normalizado, banda inclusiva, lado estable por ID,
  mínimo de observaciones y caducidad; sin cooldown ni reidentificación. Se añade
  diagnóstico acotado por transiciones/30 observaciones, sin recibir imágenes.
- Dirección explícita left/right/up/down, compatible con positive/negative.
  Corregido redondeo en los propios límites .46/.54 y diagnóstico de expiración
  al superar la tolerancia. Ninguno explica por sí solo el 0/0 original.
- Tests de contador/config/debug: **100 passed in 0.14s**. Default de geometría,
  detección y privacidad conservado; únicamente se declara debug.counting=false.
- Siguiente: integrar calibración visual/CLI y registrar evaluación final real.
  Cambios preexistentes del usuario en AGENTS.md permanecen intactos.

## Calibración visual generalizable — implementación (2026-10-03)

- Se leyeron AGENTS.md y el final de este registro antes de actuar. El diagnóstico
  anterior sigue documentado, pero cambios incompletos del árbol habían retirado
  `entry_direction`, `validate_counting`, límites inclusivos y caducidad correcta.
  Se restauró el comportamiento ya versionado en `f41b11f`; left/right/up/down
  y compatibilidad positive/negative vuelven a estar verificados por la suite.
- Se completó el trabajo parcial de calibración: sesión en RAM con revisión,
  API local, aplicación entre frames en la ruta común de `create_source` y guardado
  atómico solo del bloque counting del perfil activo. default.yaml queda protegido
  también mediante API/CLI y alias; no se admite destino alternativo.
- Streamlit: sección Calibración de Conteo en barra lateral, orientación, posición
  y semiancho normalizados 0–1, sentido físico según orientación. Cambios válidos
  previsualizan automáticamente, sin botón Aplicar y sin escribir YAML. Guardar
  calibración persiste explícitamente y su confirmación permanece visible.
- Cambiar geometría reinicia tripwire, ocupación y estelas, conservando captura y
  ByteTrack. Así no se interpretan posiciones previas con una línea nueva. Una
  propuesta fuera de la imagen no modifica la sesión y bloquea el guardado.
- Overlay: línea central sólida identificada, límites discontinuos de banda,
  LÍNEA DE CONTEO con acento dibujado, flechas IN/OUT físicas y marca del centroide.
  Video limitado por altura para mantenerlo revisable junto a controles/semáforo.
- Generalización comprobada con capturas/detector simulados en el pipeline común
  para archivo diferente, USB índice 2, HTTP y RTSP. No hay condición para demo1.mov
  ni dependencia de FileSource en la calibración; cámaras físicas no disponibles.
- Verificación: la primera suite tras restaurar el backend tuvo **9 failed,
  211 passed in 4.21s**, exclusivamente por sockets bloqueados en el sandbox. Se
  resolvió habilitando ejecución de HTTP loopback antes de continuar: **220 passed
  in 9.09s**. Suite de cierre del código: **227 passed in 12.68s**, cero fallos.
  Incluye AppTest, actualización automática, separación de guardado, protección
  default por API, errores, geometría en varias resoluciones y pipeline por fuente.
- Prueba local real con configs/video-demo.yaml y Streamlit en 8765/8501: Chrome
  mostró vista, línea/banda/leyenda y fuente activa. Se movió el deslizador y se
  comprobó revisión solicitada=aplicada=6; el YAML todavía no tenía counting.
  Se pulsó Guardar calibración en la interfaz y se verificó su escritura explícita.
  Los dos procesos de prueba se cerraron correctamente con Ctrl+C.
- Pendiente para el siguiente commit: registrar evaluación real, diagnóstico por
  intervalos, límites de correspondencia con la referencia agregada y documentación.

## Evaluación final real y cierre de documentación (2026-10-03)

- Commits de implementación: `ec3a2e4` (backend, pipeline, guardado y CLI) y
  `2dd7823` (Streamlit automático, overlay y pruebas). README explica barra lateral,
  orientación, línea/banda normalizadas, dirección, guardado explícito y perfil
  futuro configs/live-demo.yaml para webcam/USB o HTTP/RTSP sin modificar código.
- Perfil final **configs/video-demo.yaml**: vertical, posición **0.64**, semiancho
  **0.04**, banda **[0.60,0.68]**, IN **left**, OUT **right**, min_track_frames=3,
  max_missing_frames=2. Solo se guardó counting; detección conserva **320 / stride 1 /
  conf 0.35 / hilos auto**, áreas 0.005–0.85. La geometría se fijó mirando el marco
  antes de evaluar; no se hizo barrido ni ajustes para obtener 6/6.
- Ejecutado con código 0:
  `python scripts/evaluate_counts.py --config configs/video-demo.yaml --expected-in
  6 --expected-out 6 --counting-debug`. **1307 decodificados/procesados**, una sola
  pasada completa, aunque el perfil de reproducción usa loop/realtime. Resultado
  exacto: **IN=1 / OUT=0**, errores absolutos **IN=5 / OUT=6 / total=11**,
  **83.33333333333333% / 100% / 91.66666666666667%**. Ocupación final=1.
  Duración evaluador=**21.488757208921015 s**; no se presenta como benchmark.
- Advertencia conocida y aceptada: declarado=1308, decodificado=1307, diferencia=-1,
  tolerancia=±2. No hubo excepción ni relleno/conversión del MOV.
- Una pasada diagnóstica idéntica confirmó **1/0**, 1307 frames, detecciones de
  persona en **136 frames**, tracks válidos en **123**, **0 rechazos por área**.
  Solo números en RAM/JSON temporal; callback antes de ByteTrack para distinguir
  salida YOLO de tracks. No se cambió modelo, confianza ni parámetros del contador.
- Evento confirmado: ID **4**, frame **345**. Omisiones identificadas con intervalos
  y texto en LIMITATIONS/JSON: IN ID 1, OUT ID 5, OUT IDs 7→8, IN ID 9 y persona
  simultánea sin track, OUT ID 11, OUT ID 13. Dominan caducidades por más de dos
  ausencias, incluso conservando el mismo ID; también vida corta y falta de track
  separado. Visor local original confirma vista cenital, blur, solapamiento y
  movimientos parciales; su contribución causal por frame no se da por demostrada.
- La referencia 6/6 no tiene timestamps. Se localizaron ocho trayectorias completas
  visibles (dos juntas), siete omitidas; las otras dos IN y dos OUT de la referencia
  no se emparejaron inequívocamente. Se conserva la referencia y el error 11; no se
  inventan eventos ni se afirma diagnóstico exhaustivo. Pendiente una anotación
  temporal completa y validación con cámara fija/compañeros para mejorar precisión.
- Suite completa final: **227 passed in 12.68s**, mediante `python -m pytest -q`
  con HTTP loopback habilitado. No hay fallos pendientes. No se han añadido
  dependencias, reidentificación, estabilización ni lógica especial para el MOV.
- Privacidad: original conserva **36.190.296 bytes**, mtime_ns
  **1790883891314778494**, SHA-256
  `cc9da9fbdef81f17a0eca72a6fe5c52e2c3fc3eea575ae7826ac4ea9709dad77`.
  No se guardaron frames, capturas ni videos derivados. **Incidente corregido**:
  abrir file:// en Chrome produjo una descarga no solicitada de demo1 (1).mov en
  Descargas. Se retiró esa copia comprobando su nombre, fecha nueva y hash idéntico,
  conservando el original; después se abrió el original en QuickTime solo lectura
  y se cerró sin guardar. No quedan copias de esa operación ni datos en Git.
- default.yaml conserva exactamente los bytes encontrados al inicio: SHA-256
  `978927e6fa59a1a69b0d48734690f7b8d328e2d94853b940313da76f93a465d4`.
  Su diferencia previa contra HEAD (dos líneas de debug.counting retiradas),
  AGENTS.md y el JSON previo sin seguimiento se preservan fuera de estos commits.
- Evidencia nueva: docs/evaluations/calibration-evaluation.json. Se revisaron git diff y
  diff --check; se versionan únicamente código, tests, YAML propio y documentación.
  La integración y documentación quedan completas; **la precisión y aptitud comercial
  no están validadas**. No se probó físicamente una cámara nueva.

## Nuevo montaje cenital fijo — inicio (2026-10-06)

- Inicio en HEAD `63a5723`; cambios preexistentes de AGENTS.md, default.yaml y
  docs/evaluations/counting-evaluation.json conservados. Suite inicial: 14 fallos por sockets
  bloqueados; resuelto con HTTP loopback habilitado: **227 passed in 12.34s**.
- Nuevo archivo identificado por inventario: `data/demo2.mov`, 81.013.939 bytes,
  HEVC, OpenCV aplica rotación y entrega **1080×1920 / 29.7932035313 FPS**.
  Declara **2053** frames y entrega **2038**. FFprobe independiente confirma
  2038 frames reproducibles y duración editada **67.921667 s**; al ignorar la
  lista de edición obtiene 2053 y 68.908333 s. La diferencia se debe a la edición
  del contenedor, no se rellena ni modifica el archivo. La tolerancia ±2 sigue
  vigente; la evaluación usará una referencia de frames verificada explícita.
- Visor HTTP de revisión exclusivamente loopback, JPEG transitorio en RAM;
  ninguna imagen/video copiado o guardado. Umbral físico en transición de piso
  café a baldosa clara, y≈0.60; línea horizontal, banda [0.56,0.64], IN down.
- Creado perfil independiente configs/door-demo.yaml con detector y contador
  actuales, stride=1. Baseline completo en curso antes de ajustar comportamiento.
- Baseline completado con código actual, sin ajustes: **IN=0 / OUT=0** frente a
  12/13, error absoluto 25 (100% agregado), 2038 frames, 28.7735 s, **70.829 FPS**.
  431 cajas person en 386 frames, 341 observaciones de tracks en 312 frames,
  38 IDs, cero eventos. Ningún ID se observa a ambos lados externos de banda.
  Predominan detecciones ausentes en el umbral; no atribuirlo todo al tracker.
  Datos completos y expiraciones en docs/evaluations/door-demo-baseline.json.
- ByteTrack instalado 8.3.253: high=0.25, low=0.10, new=0.25, buffer=30.
  conf=0.35 impide su segunda asociación de baja confianza. Primer experimento:
  solo conf=0.10; conservar umbrales de asociación/nacimiento y el resto.
- Ensayos secuenciales sin alterar perfil: conf=0.10 → 0/0, 1151 cajas,
  573 observaciones, 70.315 FPS; después solo imgsz=416 → 0/1, 1505 cajas,
  769 observaciones, 49.876 FPS. OUT ID 26/frame 264 contrastado visualmente
  en visor local; ningún ID del baseline cubría ambos lados externos.
- Replay numérico 416 con tolerancias equivalentes a 0.10/0.15/0.20 s
  (2/4/5 ausencias a 29.793 FPS) conserva 0/1: no justifica introducir segundos
  ni prolongar memoria por ahora. Huecos relevantes son mayores (8–20 frames).
- Prueba exploratoria de ROI central en RAM, y=[0.25,0.8125], 1080×1080:
  0/3 con dos ausencias, 40.174 FPS. Rechazada como perfil: cambia/trunca cajas
  y no recupera entradas. Rotación 180 en muestras recupera cajas ausentes,
  por ejemplo frame 1035 y 1990; ensayo controlado de dos orientaciones en curso.
- Extendida evaluación numérica: eventos con frame fuente/procesado, segundos
  aproximados, ID, centroide, edad, lado, huecos, bordes y expiraciones; estadística
  de cajas antes de ByteTrack. --verified-frames conserva declarado original y
  valida ±2 contra referencia independiente; --output no sobrescribe resultados.
- Primer test completo de instrumentación falló en un doble de predictor sin
  results; actualizado el doble al contrato real y verificado: **230 passed
  in 12.94s**. No se cambió contador, anchor, histéresis ni default.yaml.

### Cierre detenido por precisión insuficiente — 2026-10-06

- Ensayo de dos orientaciones 0/180 fusionadas con NMS .5: **1/3**, 29.505 FPS;
  descartado para producto por insuficiencia y coste. Su primer intento temporal
  usó un atributo de predictor inexistente; corregido a results[0].orig_img y
  ejecutado hasta EOF. No queda implementación TTA en src/ ni en el perfil.
- Ensayo de tracking, desde 416/.10 y sin ROI/TTA: solo fuse_score=false → **0/1**,
  mismas 1505 cajas, observaciones **769→932**, IDs **60→44**, 53.564 FPS.
  No demuestra ausencia de switches físicos. Se mantiene asociación/nacimiento
  high/new=.25, low=.10, buffer=30, match=.8; sin ReID ni unión de IDs.
- Replay de esos tracks con 2/3/4/5 ausencias: **0/1, 0/1, 2/1, 4/1**.
  Se elige 5, menor valor ensayado que conserva los cuatro IN contrastados;
  huecos recuperados de 4/5 frames, no trayectorias inferidas sin observación.
  Presupuestos .10/.15/.20 s se tradujeron por FPS a 2/4/5 ausencias, con la
  semántica anterior. Se conserva configuración por frames; no se añadió opción
  de segundos sin ruta temporal común verificada para todas las fuentes.
- Perfil diagnóstico final: YOLOv8n/416/.10/stride1/auto, tracker YAML propio,
  centroide, horizontal y=.60±.04, IN down, mínimo 3 observaciones, ausencias 5.
  Default y video-demo conservan comportamiento anterior. Tracker propio se
  resuelve respecto del YAML y se exige tipo ByteTrack. ROI/TTA descartados.
- Pasada CLI diagnóstica completa: **2038 frames, IN=4/OUT=1**, esperado **12/13**;
  errores absolutos **8/12, total 20, 80% agregado**. **38.8375 s / 52.475 FPS**,
  sin overlay/MJPEG, primera inferencia incluida, carga de pesos fuera del reloj.
  1505 cajas en 1017 frames, 932 observaciones en 807 frames, 44 IDs,
  69 expiraciones, 11 candidatos sin evento con ambos lados observados.
- Se capturan tiempos de contenido de OpenCV en FramePacket, separados del
  timestamp Unix de telemetría. Cero fallbacks de tiempo en esta pasada.
  Eventos: IN ID5 f102/3.400 s; OUT ID11 f264/8.800 s; IN ID12 f402/13.400 s;
  IN ID36 f923/30.768 s; IN ID56 f1454/48.468 s. Consistentes con personas y
  anchors en revisión local. No se certifica correspondencia de todos los 25.
- Tres rechazos por área en diagnóstico final; no se localizaron como causa de
  un cruce. Corregido el campo del baseline a null: no estaba instrumentado allí,
  así que afirmar cero no tenía evidencia. Los conteos iniciales no cambian.
- El visor temporal había cargado el módulo anterior de config y rechazó el
  campo nuevo tracker; reiniciado con código actual. Se sustituyó seek por lectura
  secuencial en revisión para garantizar frame exacto y se comprobó carga de
  imagen antes de contrastar. Un wait del navegador expiró; el estado posterior
  mostró la imagen correcta. No son fallos del pipeline de producción.
- Regresión completa de cierre: **238 passed in 12.33s**, HTTP loopback habilitado.
  Tests nuevos exclusivamente sintéticos: pérdidas hasta 5 y mayores, retorno
  A→banda→A/jitter, desaparición tras cruce, horizontal/vertical, tracker por perfil,
  centroide real, diagnóstico, PTS/fallback y salida JSON sin sobrescritura.
  La suite existente cubre IDs independientes, no duplicación y default protegido.
- **Detención requerida:** no se resolvió correctamente la falta de detección
  alrededor del umbral. El resultado mejora el baseline, pero **no es apto para
  presentar una demo de conteo fiable**. No se continuó con dos repeticiones de
  validación final ni con dashboard del perfil nuevo. No se calcula precision/recall;
  cero FP/duplicados/inversiones conocidos en cinco eventos auditados no es garantía
  global. Pendiente anotar exhaustivamente cruces y revisar encuadre/distancia que
  permita observar cuerpos suficientes; no intentar cerrar 12/13 aumentando memoria.
- Documentación y evidencia numérica en `docs/evaluations/door-demo-baseline.json` y
  `docs/evaluations/door-demo-evaluation.json`.
  Hash/tamaño/mtime idénticos al inicio para demo1/demo2, default, video-demo,
  calibration-evaluation y AGENTS. Sin frames/imágenes persistentes ni videos
  copiados/convertidos/subidos; cambios previos fuera de los commits.

## Reanudación autorizada: compuerta de dos zonas — 2026-10-06

- HEAD inicial c821667, suite inicial **238 passed in 11.95s**. Se conservan los
  cambios previos de AGENTS/default y counting-evaluation fuera de los commits.
- El usuario autoriza ahora 640 px, ROI, TTL de segundos y reasociación geométrica;
  reemplaza para este montaje la decisión anterior de no continuar con esas vías.
  El resultado anterior 4/1 sigue registrado, sin reescribir su evaluación.
- Soporte ROI antes de YOLO, con retorno de cajas/centroide y cálculo de área
  respecto de la imagen completa. Sin dependencias nuevas ni imágenes persistentes.
- Ensayos completos, una variable importante a la vez: 640 sin ROI con tripwire
  **2/6, 30.088 FPS**; después ROI [x=0..1, y=.10..95], **4/8, 28.916 FPS**.
  Ambos 2038 frames, conf=.10 y tracker anterior. El ancho completo conserva
  los bordes laterales; las zonas exteriores futuras quedan dentro del ROI.
- Configuración valida múltiplos de 32 hasta 640 y parámetros geométricos/temporales.
  La ampliación no modifica default ni video-demo. Tests de ROI comprueban
  coordenadas, área, privacidad y buffer por FPS/stride.
- DualZoneCounter intercambiable, TTL por timestamps comunes de fuente, buffer
  de ByteTrack por FPS/stride. Sin ReID ni dependencias; seis puntos por identidad
  lógica y alias recientes, expiración independiente de velocidad de inferencia.
- Compuerta sin stitching **8/11, 27.260 FPS**. Dos pasadas con stitching y dos
  presencias **8/11, 27.179/26.455 FPS**, 1880 cajas, 1265 observaciones, 54 IDs,
  53 identidades lógicas, una unión ID33→37 (gap .20 s, distancia .32024, cos .80261).
  Cambia el IN de f650→640; revisión posterior distingue dos personas, no el mismo
  evento adelantado. No atribuirle mejora agregada ni correspondencia inexistente.
- Diagnóstico de borde ID98: B repetida desde f1908, hueco16 frames antes de
  única A profunda en f1968; dos presencias exteriores impedían confirmar OUT.
  Opción general de presencia profunda (.10) mantiene dos observaciones cerca de
  límites y mínimo tres totales: replay **8/12**, recupera ese OUT contrastado.
  TTL .8/.9/1.0 en tracks idénticos: **8/11, 8/12, 8/12**; .8 pierde OUT84 por hueco
  .833 s, se elige .9. No ampliar radio ni volver a ajustar para cerrar 12/13.
- Revisión local en RAM: zonas representan el umbral físico, centroide real;
  unión 33→37 compatible con misma persona; OUT84/OUT88 son personas distintas,
  OUT98 cruza de baldosa hacia piso café. El visor se reinició tras cambiar config
  (módulo cargado anterior rechazaba el campo nuevo); sin fallo del productor.
  Decodificación secuencial única por revisión evita lecturas concurrentes costosas.
- Revisión f380/410 confirma IN perdido con fragmentos 16→20/21; f635/670
  confirma dos IN y solo uno contado. En el segundo episodio, ByteTrack asigna
  después el antiguo ID33 a la persona distinta (burgundy; anterior gris).
  Se rechaza heredar alias cuando reaparece fuera del radio configurado: f649,
  distancia .378 frente a .35; pasa a identidad independiente. No ampliar radio
  para unir 35→33 ni declarar solucionados switches por conseguir un total.
- Suite tras protección de alias: **277 passed**. Nuevos tests sintéticos cubren
  down/up y vertical, TTL corto/largo, neutral/retorno/jitter, presencia profunda
  y borde, IDs independientes/ambiguos/simultáneos, no duplicación, alias reutilizado
  y memoria acotada. Evaluador consolida IDs físicos en logical_id y relaciona
  eventos/uniones/rechazos/expiraciones con frame, tiempo, anchor y edad.
- Dashboard verificado en navegador con productor YOLO real: API /calibration
  devuelve door-demo/dual_zone/A=.40/B=.65/TTL=.9; MJPEG enabled=ready=1. Franjas
  semitransparentes, neutro, IN↓/OUT↑, cajas/IDs, estelas y centroide visibles.
  Controles editan A/B; tests AppTest verifican aplicar/guardar y rechazar zonas
  inválidas. Default protegido. Smoke de 900 frames: **22.83 FPS**, overlay/JPEG y
  telemetría locales activos, no es pasada completa ni benchmark estadístico.
- Dos pasadas finales aisladas, código/parámetros fijados: **2038 frames cada una,
  8 IN / 12 OUT** frente a **12/13**; errores **4/1**, total **5/25 (20% agregado)**.
  **75.7251 s / 26.9131 FPS**, **77.9113 s / 26.1580 FPS**. Misma secuencia de los
  20 eventos (frame, dirección, ID físico y lógico). Primera inferencia incluida,
  carga de pesos fuera del reloj; sin overlay/JPEG. No benchmark estadístico.
- 1880 cajas/1138 frames, 1265 observaciones/986 frames, 54 IDs físicos y 54
  identidades temporales, 15 rechazos de área, 53 expiraciones (12 en borde de
  imagen), una unión y un rechazo de alias. Cero fallbacks de media_seconds.
  Sin candidatos expirados que alcancen ambos lados; siguen fragmentos incompletos.
- Auditoría parcial adicional f1017/1035/1045/1068: gris sale, burgundy entra.
  Tripwire .9 s en los mismos tracks da 10/14 pero duplica OUT gris, IDs54/52,
  mientras ID54 cambia entre personas. DualZone conserva solo OUT52; IN burgundy
  omitido. Se contrastan **cinco eventos correctos** y **tres IN omitidos** (13 s,
  21 s, 35 s), no todos los 25. No FP/duplicados/inversiones conocidos entre esos
  cinco; precision/recall no calculados. Dos déficits agregados sin etiqueta temporal.
- La pasada con visor simultáneo dio 16.59 FPS y no se usa como rendimiento
  aislado. Archivo, perfiles protegidos, AGENTS y evaluación demo1 conservan hash,
  tamaño y mtime iniciales. Nuevas evaluaciones anteriores tampoco se sobrescriben.
- **Cierre:** arquitectura implementada, tests y dashboard verificados; mejora
  defendible como prototipo, pero **no suficientemente fiable para la demo de
  conteo**. No continuar ajustando totales. Pendiente anotación completa y revisar
  encuadre/distancia con cámara final. Evidencia nueva: `docs/evaluations/door-gate-evaluation.json`.
- Verificación final **277 passed in 12.56s**, `git diff --check` limpio para el
  trabajo nuevo, perfil/JSON/resultados coherentes. Visores y servidores de prueba
  cerrados; sin procesos de inferencia de la tarea dejados activos.

## Auditoría y preparación — etapa 1, 2026-10-10

- Git inicial `457d96d`; diferencias previas en AGENTS.md, default.yaml y
  docs/evaluations/counting-evaluation.json conservadas y excluidas de los commits propios.
- Corregidos reinicio del productor bajo la misma ruta, actualización externa,
  conservación de borradores/conflictos, polling sin POST y reintento explícito.
  Control condicional sesión/revisión en apply/save evita escrituras obsoletas.
- Leyenda usa umbrales numéricos del productor; contrato aditivo/compatibilidad
  documentados en DECISIONS. AppTest cubre reinicio .61→.70, cambios externos,
  conflictos, controles intactos y perfiles con umbrales distintos.
- Primera ejecución: 8 failed / 36 passed (2.32 s): un mock no aceptaba `expected`
  y siete pruebas requerían sockets loopback bloqueados por sandbox. Mock corregido
  y ejecución local autorizada antes de avanzar. Resultado intermedio: 56 passed
  (8.07 s); tras cubrir polling con envío fallido: **57 passed in 8.12s**.
- Comando: `.venv/bin/python -m pytest -q tests/test_dashboard_calibration.py
  tests/test_dashboard.py tests/test_calibration.py tests/test_telemetry.py
  tests/test_simulation.py`. Sin videos privados ni persistencia de imágenes.
- Siguiente: simulación dual_zone y retiro del estado diagnóstico de aliases.

### Etapa 2 — simulación y ciclo de vida diagnóstico, 2026-10-10

- Tracks artificiales dual_zone derivados de A/B, con presencias en extremos y
  edad suficientes; tripwire conservado. Probadas ambas orientaciones/sentidos,
  cuatro geometrías (incluidos .10/.90 y .0001/.9999), mínimos 2/8 y cuatro ciclos.
- CountingDebug libera IDs retirados por stitching, aliases con TTL vencido,
  expiración y reset. Secuencia de eventos idéntica con/sin diagnóstico en dos
  uniones sucesivas. Regresión documenta presencias conservadas durante ausencias.
- Primer resultado: 1 failed / 140 passed (2.80 s). La trayectoria de la segunda
  unión no cumplía movimiento neto compatible en la ventana de seis puntos;
  corregida solo la prueba. Repetición: **141 passed in 2.76s**.
- Comando: `.venv/bin/python -m pytest -q tests/test_dual_zone.py
  tests/test_counting_debug.py tests/test_fake_tracks.py
  tests/test_evaluation_diagnostics.py tests/test_config.py` (sockets locales).
- Siguiente: cola live sin espera por frames y robustez de cierre/control.

### Etapa 3 — backpressure y cierre, 2026-10-10

- Frames live usan inserción no bloqueante y sustitución atómica del antiguo.
  Archivo conserva orden/todos los frames; error y fin no se descartan, incluso
  bajo cola llena. Cierre despierta productores y libera captura.
- Regresión coordinada por eventos: ráfaga de 100 frames antes de consumir entrega
  los dos recientes, consumidor lento de archivo recibe 0..99, errores/fin y
  cierre con cola llena. Una Queue instrumentada prohíbe put bloqueante de frames
  live; no se imponen cotas frágiles de FPS ni latencia.
- `.venv/bin/python -m pytest -q tests/test_source_backpressure.py
  tests/test_live_sources.py tests/test_file_source.py tests/test_file_playback.py`
  → **35 passed in 1.77s**, HTTP loopback sintético autorizado. Sin fallos.
- Siguiente: perfil pendiente, flujo 720p/30 fps sintético, CLI y documentación.

### Etapa 4 — próxima validación y cierre, 2026-10-10

- Perfil independiente configs/next-video.yaml, ruta PENDIENTE, privacidad apagada
  y geometría tripwire default sin validar. No se heredan default.yaml ni la
  calibración/confianza/ROI de videos anteriores. Ninguna ruta privada abierta.
- Flujo sintético 1280×720 y timestamps index/30: ROI no trivial → cajas/centroides
  completos normalizados → contador real en ambos modos → ocupación → overlay.
  Una entrada/una salida, pico 1/saldo final 0; frame original intacto. Detector/
  tracking simulados: no certifica YOLO, cámara ni precisión con personas.
- Evaluador probado con perfil y ruta explícita, sin loop/realtime, referencia
  verified_frames ausente y rechazo de sobrescritura. Benchmark toma source.path
  si falta --video; --real-only permite medir la próxima entrada sin otros videos.
  Pruebas de su CLI simulan medición/metadatos: no se ejecutó benchmark privado.
- Etapa focalizada: `.venv/bin/python -m pytest -q tests/test_next_validation.py
  tests/test_detector.py tests/test_benchmark.py tests/test_evaluation_diagnostics.py
  tests/test_overlay.py tests/test_config.py` → **107 passed in 1.28s**.
- Regresión final: `.venv/bin/python -m pytest -q` con sockets exclusivamente
  locales autorizados → **339 passed in 15.95s**, sin fallos. CLI --help de
  evaluate_counts, benchmark_fps y run_demo ejecutadas con código 0.
- README, DECISIONS, LIMITATIONS y nota BENCHMARK distinguen histórico/compuerta
  actual, observaciones de zona, perfiles independientes, ángulo sin rectificación,
  parámetros solicitados/observados, FPS sin garantía y buffer por actualizaciones.
  Resultados/JSON históricos intactos. Repo sigue público; sin PR, dependencia,
  descarga automática de pesos ni persistencia de imágenes/frames/videos.
- No queda un fallo de software conocido de esta auditoría pendiente. Siguiente:
  grabar nuevo video, recalibrar puerta y etiquetar cruces; evaluar a destinos
  nuevos y luego validar transporte/cámara física. **Precisión no resuelta,
  cámara no comprobada y rendimiento del próximo video no medido.**

## Primera evaluación experimental de demo3 — 2026-10-10

- Leídos AGENTS, README, PROGRESS, DECISIONS, LIMITATIONS y BENCHMARK antes de
  evaluar. HEAD inicial c312bab; cambios preparados en AGENTS.md, default.yaml
  y `docs/evaluations/counting-evaluation.json` conservados. Sin commits, push ni PR.
- Original privado de solo lectura: HEVC, 32.924.215 bytes, 56,268333 s,
  1686 frames declarados, verificados por FFprobe y decodificados por OpenCV.
  Codificado 476×848, matriz de rotación −90°; OpenCV/FFmpeg aplica orientación
  automática (metadato 90°) y entrega 848×476 horizontal a 29,963567 FPS.
  No hay discrepancia de frames ni advertencia de validación. Altura, ángulo,
  dispositivo y resolución de grabación inicial no se certifican por estos datos.
- Baseline: next-video.yaml con --video data/demo3.mov, tripwire, línea
  horizontal y=.50, banda [.46,.54], IN abajo, ROI completo, YOLOv8n CPU,
  320/.35/stride1, hilos auto. Una pasada sin loop/realtime ni imágenes de salida:
  **6/4**, diez eventos, errores absolutos 0/2, suma 2/12 = **16,67%**;
  error OUT 2/6 = 33,33%. Ocupación final incorrecta 2; **17,2886 s / 97,5207 FPS**,
  arranque de inferencia incluido, carga de pesos fuera del reloj. No benchmark.
- Revisión numérica observacional con callbacks, sin cambiar inferencia ni
  tracking: mismos diez eventos por frame/ID/dirección. 912 cajas YOLO en
  856 frames; 865 observaciones válidas en 834 frames; 19 IDs, diez rechazos
  de área, cero fallbacks de timestamp. IDs distintos no equivalen a personas.
- Causa inmediata reproducida: ID16 descartado f835–838 (27,900–28,000 s),
  ID29 f1348–1352 (45,001–45,134 s). YOLO conserva cajas de confianza
  .895–.914 / .884–.900 y áreas .359–.376 / .313–.321. Después de ByteTrack,
  sus áreas son .861–.911 / .855–.939, superan .85 y el adaptador las descarta.
  Ambos IDs siguen asociados; el contador caduca f837/f1350 por más de dos
  ausencias. Reaparecen dentro de banda, sin el lado inferior anterior, y alcanzan
  arriba f846/f1360. No es falta de confianza ni edad insuficiente en esos casos.
- Control causal exclusivamente numérico: mismo contador y configuración,
  reinsertando las diez cajas rastreadas descartadas por área, produce 6/6 y
  conserva los diez eventos anteriores. Añade OUT16 f846/28,266722 s y OUT29
  f1360/45,401044 s. **No es una calibración aplicada ni un resultado operativo**;
  no certifica que sean todos los cruces reales ni ausencia de FP compensatorios.
- No se localizaron visualmente los doce cruces ni el umbral físico. Se abrió
  la vista OpenCV existente solo local, sin capturas; se solicitó la coordenada
  Y de la puerta. Sin esa referencia, demo3.yaml conserva y=.50 y banda=.04,
  explicita IN down y mantiene detector/requisitos del baseline. No hay segunda
  evaluación de una geometría nueva justificada. 897/912 cajas YOLO tocan el
  margen 1% de algún borde; el encuadre no asegura cuerpos completos. El desfase
  de relación de aspecto después de tracking es medido; su causa física exacta
  y la contribución de la inclinación siguen siendo hipótesis por contrastar.
- Benchmark aislado, resolución efectiva original 848×476, CPU/320/stride1,
  siete hilos efectivos, warmup 30 y tres pasadas completas por modo:
  **102,2573 FPS** medios sin overlay (mínimo 101,0768), **102,8231** con
  overlay/JPEG en RAM (mínimo 101,7729). Ventanas de 1656 inferencias, tiempos
  15,899–16,384 / 15,849–16,272 s; suma de las seis ventanas **96,9141 s**.
  JPEG calidad80/límite10, ~9,37 JPEG/s, coste por codificación 1,730 ms medio.
  No mide HTTP/navegador ni latencia extremo a extremo; diferencia pequeña entre
  modos compatible con carga variable. Mac14,2/Apple M2/8 CPU/16 GiB/macOS26.6.2,
  Python3.11.15/OpenCV4.14.0/Ultralytics8.3.253/torch2.14.1. Sin descarga/instalación.
- Comprobado perfil y sentidos con load_config y contador real. Pruebas:
  `.venv/bin/python -m pytest -q tests/test_config.py tests/test_tripwire.py
  tests/test_detector.py tests/test_evaluation_diagnostics.py tests/test_benchmark.py
  tests/test_next_validation.py tests/test_file_source.py tests/test_frame_validation.py`
  → **142 passed in 1.23s**. No cambios de tests ni producción.
- Perfil optativo del dashboard en la carpeta local ignorada: mismo detector/
  geometría, rutas absolutas al original/pesos, loop/realtime y MJPEG locales.
  HTTP real listo, JPEG 848×476 decodificado solo en RAM, AppTest contra el
  productor real sin excepciones ni errores. Advertencias existentes de contexto
  AppTest y valor de widget duplicado; no se corrigen durante este diagnóstico.
  Smoke de 32 frames, no benchmark ni evaluación completa; procesos cerrados.
- Evidencia local ignorada, sin sobrescribir históricos:
  `data/evaluations/demo3-20261010-172037/` contiene preflight, baseline,
  diagnostic-pass, frame-diagnostics, area-audit, diagnosis, benchmark,
  dashboard-check, summary y perfil de vista optativa. Solo JSON/YAML, sin medios.
- Siguiente: confirmar puerta en vista local y anotar los doce cruces con tiempos;
  grabar con más margen de cuerpo antes/después y comprobar resolución del archivo
  entregado. Proponer, sin implementar, una revisión del filtro sobre la caja YOLO
  asociada frente a la estimación de ByteTrack. Validar en clips independientes
  antes de cambiar filtros, memoria o tracker. Cámara real apta para ensayo técnico,
  todavía sin validación de precisión, transporte ni latencia.

## Verificación de nueva calibración demo3 — 2026-10-10

- Nueva instrucción del usuario: contrastar position=.60 antes de implementar
  correcciones. AGENTS y documentación relevante revisados; HEAD c312bab y todos
  los cambios previos conservados. Único parámetro guardado: counting.position
  .50→.60 en configs/demo3.yaml; comentario actualizado. No se toca otro perfil,
  fuente, filtro, umbral, tracker, código de producción ni test. Sin commits/push.
- Productor PID47368 y Streamlit PID47591 usan el YAML auxiliar histórico
  `data/evaluations/demo3-20261010-172037/configs/demo3-dashboard.yaml`.
  Su archivo conserva .50, pero GET /calibration confirma **.6106 en RAM**, revisión
  3 aplicada=3, horizontal/down y banda=.04. No equivale a .60 exacto. La muestra
  6/5 leída de /telemetry es un instante de una vuelta, no un total final. Se
  consultó sin cambiar sesión, controles, YAML auxiliar ni procesos del usuario.
- CLI evaluate_counts con demo3.yaml .60, referencia inmutable 6/6, diagnóstico,
  stride1, sin loop/realtime: **1686/1686 frames, 6 IN / 5 OUT**, once eventos,
  error absoluto 0/1, agregado **8,33%**. Tiempo 23,8777 s, 70,6099 FPS globales.
  El dashboard previo sigue activo: no es un benchmark aislado ni comparativo.
- Pasada de contraste de la misma CLI, inyectando exclusivamente la posición
  exacta leída de RAM (.6106) en la configuración del proceso, sin persistirla:
  **1686 frames, 6/6, doce eventos**, 23,8375 s / 70,7290 FPS. No se seleccionó
  un parámetro por barrido ni se cambió configs/demo3.yaml a ese valor.
- Las dos pasadas coinciden por frame/ID/dirección con replay de tracks históricos
  bajo sus posiciones respectivas. Mismos 912 detecciones, 865 observaciones,
  19 IDs y diez rechazos de área; también iguales rangos de centroide, huecos,
  frames inicial/final y número de observaciones por ID. Los diez pares ID/sentido
  del baseline .50 se conservan en .60 y .6106. IN se confirma algo después y
  OUT antes al desplazar la línea; no aparecen sustituciones por otros IDs.
- ID16: .60 y .6106 cuentan OUT f834/**27,866700 s**, último frame válido antes
  del rechazo f835–838. En .60 y=.548511 < .56; margen 5,469 píxeles y una sola
  observación exterior antes del hueco. Caduca de todos modos f837, con evento
  ya emitido. La calibración evita esta omisión, no arregla la caja/filtro.
- ID29: .60 **todavía omite OUT**. Último punto válido f1347 y=.564967 está dentro
  de [.56,.64], a 2,364 píxeles del límite superior. Rechazo f1348–1352 y caducidad
  f1350 borran el lado de inicio. Con .6106, límite superior .5706, ese mismo punto
  cuenta OUT f1347/**44,967700 s**, 2,681 píxeles fuera de banda y un frame antes
  del rechazo. El 6/6 observado es consistente con el valor activo más preciso.
- Estabilidad numérica: cada recuperación tiene solo una observación exterior
  antes de perderse por área. Sesgo de centroide ±1 píxel en replay conserva los
  totales respectivos; +3 píxeles vuelve a omitir ID29 con .6106, −3 lo recupera
  con .60. Control de sensibilidad de medidas, no nueva evaluación/detección ni
  búsqueda de posición. No se certifica robustez frente a otra grabación.
- Geometría .60: línea y=285,60 píxeles, banda [266,56,304,64] en altura476;
  quedan 171,36 píxeles desde el límite inferior al borde. ROI completo. No hay
  proximidad extrema de la banda al borde; las cajas sí siguen recortadas y
  ensanchadas. Coincidencia con umbral físico pendiente de referencia geométrica.
- No hay timestamps manuales ni auditoría visual completa de los doce cruces.
  El emparejamiento anterior es numérico, no prueba ausencia de FP compensatorios,
  cambios físicos de identidad ni precisión por evento. No implementar corrección
  del filtro por ahora: queda evidencia de fragilidad por contrastar en otros clips.
- Pruebas pertinentes: config, tripwire, evaluation_diagnostics, next_validation
  y calibration. Primer intento: 126 passed/7 failed exclusivamente por sockets
  loopback bloqueados en sandbox. Repetidas con sockets de prueba autorizados:
  **133 passed in 4.80s**, sin cambiar código/tests ni usar imágenes persistentes.
- Evidencia nueva ignorada: `data/evaluations/demo3-position060-20261010-202249/`:
  preflight, config-change, evaluation, evaluation-dashboard-ram y su método,
  stored-tracks-replay, comparison, centroid-sensitivity, validation y summary.
  Históricos y video sin modificar; las imágenes nunca se guardan ni se envían.
- Conclusión: conservar .60 como perfil experimental solicitado, **sin declarar
  resuelto 6/6**. El valor activo .6106 da 6/6 en una pasada, pero el filtro sigue
  descartando y la confirmación de ID29 es estrecha. Siguiente etapa pendiente
  de autorización: anotación temporal y geometría antes de cualquier corrección.
## Organización de resultados JSON — 2026-10-10

- Formalizados con `git mv` los doce movimientos existentes: cuatro mediciones
  en `docs/benchmarks/` y ocho evaluaciones/validaciones en `docs/evaluations/`.
  Actualizados enlaces y comandos Markdown; cambios preexistentes conservados.
- Verificación: doce hashes SHA-256 idénticos, catorce enlaces JSON resueltos y
  ninguna ruta antigua en scripts/configuraciones/tests/código de producción.
  Pruebas de benchmark, diagnóstico de evaluación y próxima validación:
  **18 passed in 1.12s** con datos simulados. `git diff --check` y su variante
  `--cached` sin errores. No se ejecutaron benchmarks ni evaluaciones nuevas.
- Las referencias internas históricas de los JSON se conservan sin cambios.
  Sin modificaciones de algoritmos o parámetros, commits ni push.

## Renombrado del repositorio — 2026-10-16

- `origin` actualizado a `https://github.com/andres-4uni/transitflow-apc.git`
  para fetch y push; acceso a `main` comprobado con `git ls-remote`.
- README actualizado a TransitFlow APC, con enlace y comandos de clonación.
  Conservadas las referencias históricas, el nombre del paquete Python, la
  carpeta local, el código y las configuraciones. Cambios previos preparados
  en AGENTS.md y configs/default.yaml excluidos del commit de esta tarea.
- Primera ejecución: 322 passed / 17 failed por sockets locales bloqueados en
  sandbox. Repetición con acceso a sockets: `.venv/bin/python -m pytest -q`
  → **339 passed in 16.02s**. No se modificaron tests ni dependencias.
- Ejecutados `run_demo.py --help` y `run_demo.py --fake-tracks --max-frames 12`
  con código 0; demo sintética: 12 frames, sin cámara, YOLO ni imágenes guardadas.
  Los 11,91 FPS incluyen el ritmo artificial y no son un benchmark de inferencia.
- GitHub rechazó el push directo a `main` (GH013): la rama está protegida y
  exige pull request. Se publica el cambio en `docs/rename-transitflow-apc`
  para revisión; la integración a `main` queda pendiente del flujo protegido.

## Firmware propio ESP32 — 2026-10-21

- Inspeccionados AGENTS, historial completo de este registro, contexto de hardware,
  fuentes/configuración Python, decisiones y limitaciones antes de editar.
  HEAD inicial a774fa4; main local ya estaba un commit por delante. Preservados
  cambios preparados del usuario en AGENTS/default y documentos locales sin
  seguimiento. No se modifica producción Python, perfiles ni videos privados.
- Referencia oficial Arduino-ESP32 3.3.12 preservada desde archivo instalado con
  SHA-256 verificado contra metadatos del paquete. SSID/password vacíos, manifiesto
  por archivo, licencia y límite explícito: la versión del binario anterior no
  quedó registrada. No se copiaron sketches privados ni se leyó/escribió la placa.
- Firmware independiente con Preferences/WiFi/WebServer del core, AP WPA2 temporal
  APC-Metro-Setup, formulario en 192.168.4.1, escaneo asíncrono/manual y clave AP
  aleatoria local ignorada (no mostrada). Nueva red persiste solo tras IP; NVS
  fallida/candidata inválida conserva anterior. Timeout 25 s, AP 10 min, recuperación
  por BOOT al soltar 3 s / borrado al soltar ≥10 s, limpieza de STA legada incluida.
- Cámara oficial JPEG/PSRAM/OV3660 y panel conservados; ruta :81/stream confirmada
  en fuente, parada segura antes de AP y arranque tras apagar AP/portal. LED21
  LOW no bloqueante, microSD excluida por compartir CS. mDNS/dns-sd con respaldo
  IP serial/DHCP, sin logs SSID/clave. Portal enlazado a interfaz AP, validaciones
  de Host/Origin/token, no-store; sin CORS comodín de video ni cloud/OTA.
- Compilación real CLI 1.5.1/core 3.3.12, XIAO_ESP32S3, PSRAM=opi, FlashSize=8M,
  CDCOnBoot=default, PartitionScheme=default_8MB, DebugLevel=none:
  firmware final **1.086.918 bytes / 3.342.336 (32%)**, globales **72.936 / 327.680
  (22%)**. Referencia oficial sin claves: **997.618 bytes (29%)**, globales
  **68.504 (20%)**. Ambos compilados sin errores; no se subieron al dispositivo.
- Tests nuevos: **12 passed in 2.62s** inicialmente. Política C++17 con warnings
  como errores: timeouts, ida a setup/reconexión, rollover millis, LED, rebote/BOOT,
  validación de credenciales. Controlador C++ real con HAL simulada: AP/video
  excluyentes, Host/Origin/CSRF/interfaz, NUL/clave inválida, persistencia tras IP,
  fallo de escritura, conservación de anterior y borrado. Preparación valida
  hashes y clave privada; secretos no se imprimen ni sustituyen accidentalmente.
- HTTP real solo loopback: formato multipart/boundary/X-Timestamp de Espressif,
  JPEG sintético en RAM, lectura con StreamSource existente; sin imágenes a disco.
  CLI `check_stream.py` usa ese mismo camino para la futura prueba física y
  devuelve solo métricas. Regresión final con sockets locales autorizados:
  `.venv/bin/python -m pytest -q` → **351 passed in 19.66s**, cero fallos.
- Comandos manage --help/ports y check_stream --help ejecutados. Un intento del
  último con Python del sistema falló por falta de PyYAML; corregido al usar
  `.venv/bin/python`, como indica la guía, sin instalar dependencias ni cambios
  de producción. No queda fallo local sin resolver. `ports` no encontró XIAO USB:
  solo puertos Bluetooth/debug; no se intentó upload ni acceso a una IP de cámara.
- `compileall` y comprobaciones de espacios/enlaces/ausencia de clave AP en
  archivos publicables sin errores. Demo Python sintética ejecutada: **12 frames,
  11,92 FPS, IN=0/OUT=0**, sin cámara/YOLO ni grabación; su ritmo es artificial,
  no benchmark. Primer intento bloqueado por sockets del sandbox, repetido con
  loopback autorizado y resuelto sin modificar código ni configuraciones.
- Al preparar el commit, `diff --cached --check` señaló los espacios de contexto
  vacío obligatorios del archivo unified diff. Resuelto con atributo whitespace
  acotado a `patches/*.patch`; no se alteró ni se relajó la revisión del C++.
- Documentación concreta de compilación/USB, casa, iPhone (compatibilidad 2,4 GHz),
  powerbank, red ausente/cambio/reset, descubrimiento e integración por perfil
  ignorado; matriz de aceptación **pendiente de usuario con placa**. BOOT/LED,
  aislamiento por radio, persistencia física/cortes, streaming OV3660, rendimiento
  y conteo no se declaran verificados por tests simulados o compilación.
- `configs/default.yaml` conserva hash inicial
  `978927e6fa59a1a69b0d48734690f7b8d328e2d94853b940313da76f93a465d4`.
  Fuentes, parámetros de conteo, resultados históricos y medios privados intactos.
  Compilados/clave quedan ignorados; no se versionan artefactos que los contengan.
- Commits separados de referencia (`2b03fbc`) y firmware/tests (`706e38c`), más
  guía/resultados. Rama de entrega `feat/esp32-camera-setup`, creada desde el HEAD
  local existente (incluye como antecedente a774fa4 de renombrado). Main requiere
  PR; no se intenta forzar su actualización ni incluir cambios previos preparados.
  Siguiente: subir por USB y ejecutar la matriz física antes de aceptar sustitución.
- Push de los tres commits completado a `origin/feat/esp32-camera-setup`, con
  upstream configurado; main sin modificar. La primera revisión automática lo
  retuvo por destino no verificado. Se comprobó por el conector GitHub que origin
  coincide con el repositorio público de la cuenta autenticada, propietaria y
  administradora; la revisión aceptó el mismo push con esa evidencia, sin cambiar
  de destino ni incluir artefactos privados. No se ha creado ni fusionado PR.

## Rechazo físico de Guardar Wi-Fi — corrección local, pendiente de hardware (2026-10-21)

- Confirmación del usuario: el firmware propio ya está cargado, AP/portal en
  192.168.4.1 funcionan y listan hotspot del iPhone. Guardar devuelve «Solicitud
  inválida; recargar portal»; LED amarillo sigue rápido. Esto confirma descubrimiento
  de la red, no asociación, clave correcta, persistencia ni streaming de la cámara.
- HEAD inicial 1eda48a, misma rama feat/esp32-camera-setup. Leídos AGENTS,
  progreso/contexto previo y código del firmware/tests. Se conservan los cambios
  preparados de AGENTS/default y el contexto de hardware sin seguimiento.
- Inspeccionado core instalado Arduino-ESP32 3.3.12: collectHeaders conserva
  nombres/valores por petición; _parseRequest reconoce Origin y el POST
  application/x-www-form-urlencoded, _parseArguments decodifica los campos y
  String.equalsConstantTime compara el token completo. Sin evidencia de defecto
  en esas funciones. No se modifica el core ni la referencia oficial preservada.
- Causa local reproducida: reply enviaba Referrer-Policy=no-referrer, que en
  navegación POST convierte Origin en null según Fetch. Chrome headless con
  perfil temporal y formulario/cabeceras emitidos por el controlador real devolvió
  Origin null **con token válido**; la regresión de origen esperado falló antes de
  corregir (1 passed/1 failed en 6,86 s). No se capturó el POST real del usuario:
  este mecanismo encaja con su síntoma, sin declararlo confirmado en su placa.
- Cambiado Referrer-Policy a same-origin. Se mantiene rechazo de Origin null y
  ajeno, restricción AP/interfaz/cliente/Host, CSP y comparación constante de CSRF.
  Se recogen Origin y Content-Type, enctype explícito en los dos formularios,
  tipo no admitido rechazado con 415 y campos ausentes separados de clave vacía.
- Diagnósticos estáticos en serial/respuesta para cada rechazo: ap_inactive,
  ap_interface, ap_client, host, origin_null, origin_foreign, post_type,
  csrf_session/missing/length/mismatch, fields_missing, credentials_encoding/
  format, busy y nvs_unavailable. POST aceptado informa categorías origin,
  csrf=ok y form=urlencoded. Nunca imprime token, SSID, claves, cuerpo ni valores
  de cabeceras recibidas. La contraseña AP local se conserva sin mostrarla.
- Doble HAL ajustado a collectHeaders/hasArg y renovación de token entre sesiones.
  Tests del controlador real verifican token válido con origen null/ajeno, tokens
  ausentes/cortos/distintos/caducados con origen válido, tipos de contenido,
  parámetros charset, campos ausentes, Origin ausente y puerto explícito 80,
  además de persistencia/recuperación previas y ausencia de secretos en logs.
- Nuevas pruebas Chrome/loopback: política antigua reproduce null; política actual
  envía origen local. Token de formulario intacto; SSID UTF-8 y signos + & = %
  llegan correctamente codificados. Datos exclusivamente sintéticos, sin perfil
  personal, imágenes ni conexión a la cámara. El POST lo decodifica el servidor
  del Mac; **no sustituye ejecutar el parser WebServer en hardware**.
- Pruebas de firmware: **14 passed in 6.94s**. Tras añadir comprobación exacta del
  token de navegador, regresión final `.venv/bin/python -m pytest -q` con sockets
  loopback/Chrome autorizados: **353 passed in 23.12s**, cero fallos. Dos tests
  Chrome pueden omitirse en equipos sin navegador instalado; aquí sí se ejecutaron.
- Compilación real `python3 firmware/esp32-camera/tools/manage.py build` correcta:
  **1.087.606 bytes (32% de 3.342.336)**, globales **72.936 (22% de 327.680)**.
  XIAO ESP32S3, OPI PSRAM, 8MB, CDC enabled, default_8MB y DebugLevel none
  conservados. Sin dependencias nuevas ni cambios de cámara/stream/contador.
- compileall, diff --check y revisión de artefactos privados realizadas. `ports`
  no detecta XIAO USB (solo Bluetooth/debug). No se intentó upload/monitor ni se
  modificó NVS o la placa. La guía entrega comandos exactos y advierte que
  /dev/cu.usbmodem1101 es el puerto anterior, a sustituir si aparece otro.
- **Siguiente requerido:** usuario carga por USB, abre página nueva del portal y
  repite Guardar. Confirmar post=accepted, intento de red, IP, LED fijo y cierre AP;
  luego panel/MJPEG/persistencia. Si falla, compartir solo código reject=... o
  estados sin secretos. **No se declara resuelto el problema físico.**

## Checkpoint físico confirmado por el usuario — 2026-10-21

- Nueva evidencia comunicada por el usuario, no ejecutada nuevamente por el agente:
  Seeed XIAO ESP32S3 Sense + OV3660, firmware propio instalado, portal
  APC-Metro-Setup funcional tras corregir Origin/CSRF, asociación al hotspot
  del iPhone y LED amarillo fijo. Mac resuelve apc-metro.local; /capture y
  http://apc-metro.local:81/stream funcionales.
- check_stream.py: **60 frames, 320×240, 2,232 segundos, 26,88 FPS recibidos**.
  Usa StreamSource real: recepción/decodificación, no medición de YOLO/ByteTrack,
  conteo, dashboard, latencia ni tasa sostenida. Sin imágenes ni credenciales.
- Este checkpoint supera el rechazo físico de Guardar y los pendientes anteriores
  de mDNS/capture/stream en esa red. No extiende la validación a reinicios/NVS,
  otras redes, BOOT, autonomía, temperatura ni precisión de conteo.
- Releídos AGENTS, contexto, firmware README, README y código de fuente/config/
  detector/demo/dashboard. Estado inicial 56b2f4d; se conservan cambios locales
  preparados de AGENTS/default. El contexto de hardware no estaba versionado;
  se incorpora expresamente al checkpoint solicitado, conservando el historial.
- Antes de implementar: StreamSource ya abre HTTP/MJPEG mediante FFmpeg; no precisa
  adaptador, cambio de transporte ni firmware. Tests existentes de fuentes,
  firmware/check_stream y dashboard con solo loopback: **36 passed in 8.69s**.
  No hubo acceso a la cámara ni nuevos resultados físicos.
- **Restricción:** carcasa en preparación. Registrar checkpoint y preparar software/
  comandos sin requerir detección física ni alterar calibración. Firmware protegido
  contra cambios. Siguiente: perfil ESP32, verificación sintética y métricas separadas.
