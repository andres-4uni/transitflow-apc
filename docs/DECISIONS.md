# Decisiones

## Hito 1 — 2026-09-30
- Usar la raíz existente como `apc-metro/`, sin duplicar carpetas.
- Configuración con dataclasses y YAML seguro; rutas relativas al padre de la
  carpeta del YAML. Se rechazan opciones desconocidas y valores inválidos.
- Tracks y línea normalizados: cambiar resolución no cambia la calibración.
- Captura en hilo con cola acotada; los archivos conservan todos sus frames.
  `vid_stride` selecciona los frames antes de inferencia.
- CPU obligatoria; YOLOv8n y ByteTrack, clase person. `lap` es requerido por ByteTrack.
- Pesos locales explícitos: no descargar modelos durante una demo.
- Debug local optativo, sin grabación. Pruebas con video sintético.
- API verificada en [documentación oficial](https://docs.ultralytics.com/modes/track/).

## Hito 2
- La banda se expresa como semiancho normalizado. Solo pasar de un lado externo
  al otro confirma el cruce; permanecer dentro no genera eventos. Volver a cruzar
  permite otro evento con el mismo ID.
- Vida mínima = observaciones efectivas; tolerancia de pérdidas = llamadas al
  contador sin ese ID. Los frames omitidos por `vid_stride` no son observaciones.
- Si el ID cambia, no se intenta reconocer a la persona. Mantener el mismo ID
  permite tolerar hasta dos pérdidas; una ausencia mayor caduca su historial.
- Calibrar ocupación establece un saldo inicial y reinicia entradas/salidas.
  `reset()` fija cero; al reiniciar toda una sesión también se resetea el tripwire.
- Ocupación = max(0, saldo inicial + entradas − salidas), sin limitar a capacidad;
  40% y 75% son amarillos. Salidas sin entradas pueden exigir recalibración.

## Hito 3
- `create_source` selecciona archivo, webcam o stream sin cambiar la inferencia.
- En vivo se descarta el frame más antiguo cuando se llena la cola. En archivo
  se conserva el orden completo. Los errores y el final no se descartan.
- Stream usa FFmpeg y timeouts de apertura/lectura, según
  [OpenCV](https://docs.opencv.org/4.x/d4/d15/group__videoio__flags__base.html).
- Una desconexión termina con error explícito. No reconectar automáticamente:
  hacerlo sin reiniciar el tracker podría unir IDs entre sesiones distintas.
- Webcam validada con backend simulado; HTTP con servidor real local de video sintético.

## Hito 4
- API HTTP de solo lectura con la biblioteca estándar; Streamlit consulta
  `/telemetry` a intervalos configurables. Evita incorporar FastAPI/WebSocket
  cuando la demo requiere únicamente unos pocos números cada medio segundo.
- Servidor ligado exclusivamente a 127.0.0.1, sin registro ni persistencia.
  Esquema validado de valores numéricos: incluye ID de vagón, nunca ID de persona.
- `level`: 0 verde, 1 amarillo, 2 rojo; `simulated`: 0 real, 1 prueba;
  timestamp Unix de captura. Muestras antiguas no reemplazan las más nuevas.
- Simulador separado para varios vagones. No mezclar datos de prueba con la cámara
  dentro de una misma demo. El programa de cámara publica un vagón configurado.
- Dashboard con refresco automático mediante
  [st.fragment](https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment).
  Datos caducados se muestran grises y se excluyen del total con señal.
- API y dashboard se cierran por separado; cuando acaba el archivo, termina su API.
  No se muestran datos viejos como si continuara la captura.

## Corrección del simulador — 2026-09-30
- Reemplazar el crecimiento lineal de entradas/salidas por ondas triangulares
  deterministas: movimientos graduales alrededor de objetivos bajo, medio y alto,
  y un cuarto vagón que recorre todo el rango de 0 a 110%.
- Período y perfiles configurables en `simulation`; los pasos se convierten a
  segundos usando `telemetry.interval_seconds`. Por defecto el ciclo dura 120 s,
  con rangos 10–30%, 50–70%, 80–100% y 0–110% para capacidad 100.
- Calcular entradas y salidas acumuladas a partir de los tramos recorridos y ciclos
  completos, sin reiniciar conteos ni recortar el saldo después de contarlos.
  La identidad `initial_occupancy + entries - exits = occupancy` se conserva.
- Cálculo directo de cualquier paso, sin reproducir ni guardar la historia. No se
  añaden dependencias ni aleatoriedad; pruebas reproducibles incluso para pasos grandes.
- Personas enteras: el límite global se redondea hacia abajo; si un perfil queda
  sin amplitud por una capacidad muy pequeña, permanece constante.
- Son patrones de demostración para visualizar estados y transiciones, no un modelo
  de demanda de pasajeros validado en trenes. El hito 5 no se inicia.

## Hito 4.5 — vista local anotada (2026-10-01)

- El usuario autoriza explícitamente video como **modo demo opcional y local**.
  `visualization.stream` permanece apagado por defecto; la telemetría numérica
  sigue siendo lo único publicado en modo normal. `/telemetry` conserva su esquema.
- Overlay puro en `visualization/overlay.py`: copia del frame, sin IO ni estado
  global. La estela es un estado separado y acotado de coordenadas, no de imágenes.
  Los colores YAML son RGB y se convierten a BGR al dibujar con OpenCV.
- JPEG mediante `cv2.imencode`, exclusivamente en memoria. Un único JPEG vigente
  compartido, sin cola de video ni historial; cada cliente puede tener un buffer
  transitorio de envío. El cierre elimina la referencia al JPEG.
- MJPEG en `/video` del HTTP existente, siempre en 127.0.0.1. Se limita tanto la
  codificación como el envío a `visualization.max_fps`; lectores lentos reciben
  el frame más reciente y tienen timeout de escritura. No se introduce otro servidor.
- `/video/status` separa habilitado y listo; stream apagado responde 404 y sin
  frame reciente responde 503. La caducidad usa el umbral de telemetría existente.
- Streamlit consulta el estado real del backend y muestra un `<img>` a la URL
  loopback junto a los semáforos, con la leyenda de video local. El navegador
  recibe MJPEG directamente; Streamlit no guarda ni reenvía imágenes.
  Se usa [HTML en Streamlit](https://docs.streamlit.io/develop/api-reference/text/st.markdown)
  para el consumidor MJPEG, manteniendo el frontend existente.
- `run_demo.py --fake-tracks` genera frames artificiales en RAM y entrega tracks
  al mismo contador y overlay del modo cámara. No instancia detector ni captura.
  Dos IDs nuevos por ciclo permiten comprobar exactamente una entrada y una salida.
- El simulador multivagón anterior continúa siendo numérico: no se vinculan sus
  ocupaciones inventadas con conteos de otra escena. La demo visual usa un vagón.
- Las pruebas integradas y su estado pendiente se registran en PROGRESS. No se
  inicia el benchmark ni la optimización del hito 5.

## Hito 5 — archivos y evaluación (2026-10-02)

- El usuario autoriza retomar el hito 5 con `data/demo1.mov`, referencia IN=6 y
  OUT=6. Se conserva el archivo local sin copiarlo, modificarlo ni subirlo.
- `source.realtime` / `--realtime` limita la entrega al FPS informado por OpenCV;
  si el cómputo es más lento, no descarta frames para ponerse al día. `--loop`
  rebobina el mismo archivo y reinicia ByteTrack, tripwire, ocupación y estelas
  por vuelta: el salto final→inicio no representa un cruce real.
- La evaluación siempre recorre una sola pasada completa, sin descartar
  calentamiento; informa cada dirección y la suma de errores absolutos, para
  evitar que una entrada extra oculte una salida perdida. Con referencia cero,
  el porcentaje es 0 si no hay error y `null` si no se puede definir.
- Los tests de archivo usan frames sintéticos en RAM y un backend de captura
  simulado. El test HTTP sigue usando OpenCV/FFmpeg real, con MJPEG generado en
  RAM. Se prohíben `imwrite` y `VideoWriter` durante toda la suite. La apertura
  real de MOV y el AVI sintético preexistente se verifican fuera de esos mocks.
- `detection.torch_threads=0` conserva la selección automática; un entero positivo
  se aplica después de la inicialización CPU de Ultralytics. Se mide el callback
  integrado de ByteTrack sin cambiar el tracker. Inferencia/pre/postproceso usan
  sus temporizadores internos; la primera llamada sin callback instrumentado se
  descarta dentro del calentamiento.
- Benchmark sin realtime y sin servidor HTTP: el modo stream utiliza el mismo
  overlay y `LatestFrame` (calidad 80, máximo 10 JPEG/s) en RAM; mide codificación,
  no transporte ni renderizado en navegador. Captura y espera en cola se reportan
  por separado: la captura se solapa con inferencia, sus latencias no son sumables.
- FPS procesados = inferencias medidas / tiempo de pared; FPS de origen = frames
  decodificados / tiempo de pared. Los umbrales 20/25 se aplican al mínimo de las
  tres repeticiones de FPS procesados. Se reportan también FPS instantáneos.
- La comparación sintética lee `data/demo.avi`, creado en hitos anteriores;
  lo repite en memoria hasta igualar los frames decodificados del MOV, reiniciando
  tracks por vuelta. No se crea un video nuevo ni se usa el MOV como material
  sintético. Las diferentes resoluciones/contenidos limitan la comparación.
- Al retomar, el usuario acepta explícitamente la diferencia normal de metadatos
  del MOV: **±2 frames** en una pasada completa generan advertencia, no fallo;
  fuera de esa tolerancia sigue habiendo error. La política vive en
  `sources/validation.py` y queda registrada en el JSON de evaluación/benchmark.
  Las mediciones recortadas o en bucle no comparan su total con el de una pasada.
  Se revisan los resultados existentes sin repetir las 144 ejecuciones.
- `video-demo.yaml` deriva del ejemplo visual: archivo `data/demo1.mov`, stream
  con estelas, realtime y loop activos en YAML. Conserva detección y conteo por
  defecto. Cada vuelta reinicia tracker, tripwire, ocupación y estelas como ya
  implementa la CLI; la referencia 6/6 no se inyecta en los contadores.

## Calibración visual por sesión — 2026-10-03

- Reutilizar HTTP loopback y el consumidor MJPEG existente. CalibrationSession
  comparte solo geometría normalizada, revisión y perfil activo, con RLock; no
  expone URL/credenciales de stream ni conserva imágenes. No se añadió dependencia.
- Streamlit consulta el perfil real del backend. Mover controles envía geometría
  válida a RAM automáticamente; el productor la consume entre frames en el bucle
  común de create_source. FileSource solo aparece en el evaluador de archivos,
  nunca en la calibración. La vista se actualiza incluso antes de guardar.
- Al cambiar geometría, reiniciar tripwire, ocupación al valor inicial y estelas,
  manteniendo fuente y ByteTrack. Evitar cruces ficticios por aplicar la nueva
  línea a estados antiguos. No rearmar ni reiniciar por consultas sin cambios.
- Guardar solo por botón explícito o --save en CLI, exclusivamente en el YAML
  activo del productor. No ofrecer destinos hermanos ni creación automática
  desde default: si default está activo, bloquear escritura y explicar cómo
  arrancar con otro perfil. Protección también en backend contra alias.
- Persistencia atómica mediante archivo temporal YAML junto al destino y replace;
  editar solo counting en formato de bloque, preservar comentarios y validar que
  las demás secciones mantienen exactamente sus valores. Rechazar mapas inline
  o alias no conservables, sin escribir. El temporal se limpia incluso tras error.
- Controles 0–1 independientes de resolución. Conservar validación física existente:
  semiancho positivo y banda interior a la imagen. Propuestas inválidas conservan
  la última geometría y muestran error. IN físico depende del eje; OUT es opuesto.
- Línea central sólida y banda discontinua con muestras en leyenda; flechas reales
  de OpenCV para evitar caracteres Unicode ausentes en Hershey. El acento de
  LÍNEA DE CONTEO se dibuja. Marcar el centroide usado por el contador, sin cambiar
  la lógica a pies/cabezas durante una tarea de interfaz.
- Para este montaje, fijar x=0.64/±0.04, vertical e IN izquierda mirando el marco
  antes de evaluar. No alterar conf, resolución, tolerancia o tracker para cerrar
  6/6. La insuficiencia 1/0 y la correspondencia temporal incompleta con la referencia
  se documentan. Otros montajes se calibran en su propio perfil, sin código especial.

## Montaje cenital fijo — 2026-10-06

- Perfil nuevo `door-demo.yaml`; preservar demo1, video-demo y su evaluación.
  Geometría elegida mirando la transición física de pisos del marco: horizontal
  y=0.60, banda ±0.04 inicial, IN abajo / OUT arriba. No elegir posición por totales.
- La lista de edición del nuevo MOV reproduce 2038 de sus 2053 muestras. FFprobe
  con y sin `-ignore_editlist 1` verifica esa diferencia. Comparar una evaluación
  con frames reproducibles verificados explícitamente, registrando también el
  declarado original; no ampliar ±2 ni silenciar discrepancias desconocidas.
- Primer ensayo de detección: conf=0.10 para permitir la segunda asociación de
  ByteTrack (low=0.10, high/new=0.25, buffer=30 en versión instalada 8.3.253).
  Una caja débil por sí sola no inicia un ID. No cambiar tracker ni hacer ReID.
  Fuente oficial: https://docs.ultralytics.com/modes/track/ ; la implementación
  instalada se inspeccionó porque la documentación web corresponde a otra versión.
- Mantener centroide tras replay de bottom-center sobre tracks idénticos: cambia
  a cuatro eventos distintos, confirma en otros momentos y mezcla cabeza/pies
  según sentido. Una mejora agregada no justifica ese anchor para vista cenital.
- Descartar ROI y TTA 0/180: 0/3 y 1/3 siguen insuficientes. No versionar código
  exploratorio ni imponer coste/recortes sin evidencia de solución defendible.
- Adoptar asociación geométrica ByteTrack sin fuse_score, conservando umbrales
  de nacimiento y asociación. Misma salida YOLO: menos fragmentación (60→44 IDs)
  y más observaciones (769→932); no equivale a ReID ni certifica ausencia de switches.
- Separar memoria del contador (5 ausencias, menor valor ensayado que recupera
  los cuatro IN concretos) de buffer de ByteTrack (30). Conservar ventana corta
  en vez de unir pérdidas de 7–19 frames sin pruebas de falsos cruces. La opción
  por frames sigue compatible; FPS/stride requieren recalibración en otra fuente.
- Añadir media_seconds optativo a FramePacket para evaluación; timestamp Unix
  de telemetría no cambia. Usar OpenCV POS_MSEC, declarar fallback frame/FPS si
  no existe. No confundir duración editada del MOV con frames/FPS promedio.
- Detener antes de fases finales: 4/1 frente a 12/13 no resuelve el objetivo de
  demo fiable. No afirmar ≥95%, precision/recall ni validación integrada. Se guarda
  perfil para diagnóstico y evidencia, no como montaje aprobado para la demo.

## Compuerta A/neutro/B y reasociación geométrica — 2026-10-06

- Nueva instrucción del usuario autoriza expresamente 640, ROI, memoria temporal
  de .8–1 s y stitching. Sustituye para este montaje las restricciones anteriores
  sobre esas alternativas; se conserva su evidencia histórica. El documento
  anterior no contenía una compuerta implementada: esta sección registra su diseño.
- `counting.mode`: tripwire por defecto, dual_zone optativo mediante factory común
  a demo/evaluador/benchmark. Mismo contrato Track→CrossingEvent→ocupación;
  el contador puro no importa OpenCV/YOLO ni recibe frames. Los perfiles existentes
  conservan caducidad por frames cuando max_missing_seconds=0.
- Eje configurable, anchor centroide restituido a imagen completa. A y<.40,
  B y>.65, límites inclusivos neutros. El umbral físico y≈.60 queda entre ambos:
  A es piso café del pasillo; B, baldosa después de la puerta. Son franjas de
  presencia, no un nuevo umbral elegido para conseguir totales. IN A→B (abajo).
- Se arma un lado observado; neutral conserva historia y no emite eventos. Solo
  el lado opuesto confirmado rearma. A→neutral→A y observaciones repetidas no
  cuentan. Dos observaciones de zona (pueden conservarse durante una ausencia tolerada),
  mínimo tres observaciones totales.
  En el perfil, un punto profundo (margen .10: A<.30/B>.75) confirma por sí solo
  si se cumple la edad; recupera salida ID98 f1968, única presencia final en A
  tras una trayectoria larga en B. No relajar a una presencia junto al límite:
  el test de jitter aislado sigue rechazándola. Opción desactivada por defecto.
- TTL del contador por tiempo de contenido en archivos (POS_MSEC; fallback
  índice/FPS), captura Unix en webcam/HTTP/RTSP. No usar tiempo de procesamiento
  del notebook. ByteTrack recibe ceil(buffer_seconds×FPS/stride) actualizaciones;
  perfil 1 s = 30 en esta fuente, contador .9 s. FPS inválido en fuente viva:
  ByteTrack conserva estimación nominal 30; el contador sigue usando captura.
  En colas vivas con descartes el buffer nominal no equivale a un TTL exacto,
  aunque el contador sí caduca con tiempo transcurrido.
- Unión de fragmentos: antiguo no visible, nuevo sin eventos y con al menos
  dos puntos para medir dirección; dentro del TTL y corredor de límites ±.10.
  Distancia euclidiana normalizada ≤.35, movimiento por eje ≥.015, coseno ≥.80
  entre vectores y respecto del desplazamiento hacia la zona opuesta. Son unidades
  de imagen, no metros; recalibrar para otro encuadre. Emparejamiento mutuo único
  con margen .05 frente al segundo candidato; rechazar IDs simultáneos/ambigüedad.
  No predicción de personas sin detección, clasificación por aspecto ni ReID.
- Identidad lógica guarda seis puntos numéricos y alias recientes limitados por
  TTL. La unión reproduce el breve fragmento nuevo todavía sin eventos, conservando
  el lado anterior. ID físico actual y logical_id se exponen en eventos/diagnóstico.
  Si reaparecen alias simultáneamente se omite el antiguo para no actualizar dos
  veces al pasajero; se registra ambigüedad para auditoría, no se garantiza ReID.
- ROI conservador x=0..1, y=.10..95 antes de YOLO, sin recortar los bordes laterales.
  Cajas/centroide y filtro de área se calculan en coordenadas completas, igual que
  overlay y zonas. No hay excepciones por nombre de video. Resolución 640 autorizada
  expresamente frente al límite histórico 416; defaults y pesos siguen intactos.
- Evaluación por ablaciones: 640→2/6; ROI→4/8; compuerta .9 s→8/11; stitching
  conserva 8/11: ID33→37 confirma una persona en f640. La revisión f635–670
  muestra que el 33 posterior pertenece a la otra persona: igualdad agregada no
  demuestra correspondencia temporal. Proteger reaparición de alias con el mismo
  radio (.378 > .35 en f649), registrar rechazo e iniciar fragmento independiente.
  Presencia profunda→8/12 en replay. TTL .8 pierde OUT84 (hueco .833 s); .9 y 1.0
  conservan los mismos eventos: elegir .9, no ampliar radios por buscar 12/13.
  Las cifras agregadas no son precision/recall. La auditoría temporal es parcial.
- Control de memoria aislado en los mismos tracks: tripwire con .9 s da 10/14,
  pero duplica la salida gris con IDs54/52 alrededor de 35 s. La compuerta
  conserva una salida y pierde la entrada burgundy simultánea. No usar el menor
  error agregado como criterio de selección; anotar cruces antes de comparar
  precision/recall. Mantener el paradigma pedido y documentar el intercambio.

## Correcciones de auditoría — dashboard, 2026-10-10

- Cada CalibrationSession crea un `session_id` nuevo, independiente de ruta,
  fuente y modo. El dashboard compara sesión/revisión/configuración con su último
  estado aceptado. Las consultas adoptan cambios externos sin POST ni reinicio.
  Un borrador pendiente se conserva y exige elegir productor o edición local.
  Un fallo de envío no provoca reintentos por polling; se reintenta explícitamente.
- Apply/save admiten `expected: {session_id, revision}` opcional: se comprueba bajo
  el mismo lock para rechazar una escritura si el productor cambió entre GET y
  POST. Solicitudes anteriores sin `expected` siguen aceptadas. Guardar continúa
  siendo exclusivamente explícito. Un productor antiguo sin session_id permite
  detectar cambios de valores/revisión, pero no todo reinicio idéntico.
- `/telemetry` añade por vagón `green_below` y `red_above`, razones numéricas 0–1
  del productor. Make_sample y simulación las publican; cliente valida rango y
  coherencia con level. Dashboard muestra leyenda por grupo de umbrales cuando
  difieren por vagón. Nunca usa el YAML local para inferirlos.
- Compatibilidad: no se retiran ni renombran campos. El cliente nuevo lee muestras
  anteriores con ambos umbrales ausentes (-1/-1 interno = desconocidos) y muestra
  un aviso sin inventar leyenda. Consumidores que ignoran campos extra siguen
  compatibles; consumidores antiguos con esquema estricto deben actualizarse
  para aceptar estos dos campos adicionales. Telemetría solo numérica, sin IDs
  de personas; session_id pertenece exclusivamente al endpoint de calibración.

## Correcciones de auditoría — simulación y debug, 2026-10-10

- FakeTracksSource tripwire conserva sus trayectorias anteriores. En dual_zone
  los extremos se derivan de A/2 y (1+B)/2; hay esperas medidas en observaciones
  para armar ambos lados y cumplir edad/presencias. Cada ciclo usa dos IDs nuevos,
  pasa por el contador real y produce IN antes de OUT. Si el ciclo solicitado es
  demasiado corto, el simulador lo extiende a `4*max(min_zone_frames,
  min_track_frames)+2` frames; no modifica defaults ni fuerza eventos.
- El contador emite `retired_track_ids` en diagnóstico al unir, caducar aliases,
  expirar pasajeros o resetear. CountingDebug retira esas claves; el contador
  sigue sin conocer el debug. EvaluationDiagnostics ignora avisos de retiro como
  observaciones, manteniendo sus estadísticas de eventos/expiraciones.
- min_zone_frames cuenta observaciones en la zona candidata. Una ausencia dentro
  del TTL conserva hits; zona neutra/retorno al lado estable sí los borra. No se
  promete consecutividad de frames del video ni se cambia tolerancia/algoritmo.

## Correcciones de auditoría — backpressure, 2026-10-10

- ThreadedSource usa put_nowait para frames live. Una cola llena retira el frame
  antiguo inmediatamente, sin esperar 100 ms. Inspeccionar/retirar bajo el lock
  de Queue evita que una lectura concurrente haga descartar error/fin. Solo se
  espera si la cabeza es una señal de control; archivos y controles conservan
  put con timeout y revisión de stop para cerrar sin productor bloqueado.
- No se ajustan buffers del dispositivo/driver/FFmpeg: pueden introducir latencia
  adicional antes de esta cola. Una webcam cuyo read queda bloqueado sigue
  requiriendo que su backend responda; close informa si supera el timeout.

## Preparación independiente — 2026-10-10

- next-video.yaml conserva defaults de dataclasses, tripwire y ROI completo como
  punto de partida sin calibración validada. No hereda default.yaml ni perfiles
  históricos. La ruta PENDIENTE nunca se abre durante esta tarea; 720p/30 fps/30°
  son previsiones, no una medición. No se añade perspectiva/oblicuas ni parámetro
  FPS inexistente al dispositivo. min_zone_frames ya está aclarado sin algoritmo nuevo.
- Benchmark --video opcional usa source.path del perfil (antes default demo1.mov);
  --real-only evita necesitar otra entrada. Comparación/barrido históricos siguen
  disponibles explícitamente. Pruebas CLI simulan medición y validan elección de
  ruta, una pasada sin realtime y escritura exclusiva de JSON a destino nuevo.
- Webcam solicita width/height; archivo/stream usan dimensiones de frame reales.
  CAP_PROP_FPS es información nominal del backend, no promesa efectiva; no se
  solicita 30 fps. OV3660 no decide transporte. Contador sigue usando timestamps
  de captura/contenido, ByteTrack actualizaciones y demo promedios de pared.
- Mantener privacidad, API/MJPEG loopback, stack y dependencias. Ningún resultado
  histórico se sobrescribe, ningún video privado se procesa y ningún peso se
  descarga. Validación real de precisión/cámara/rendimiento queda para después.

## Evaluación experimental demo3 — 2026-10-10

- La instrucción actual excluye commits y cambios de producción, contador,
  detector, tracker, filtros o memoria. Se crean solo perfil propio, evidencia
  numérica local ignorada y este registro; defaults e históricos se conservan.
- Usar next-video.yaml como baseline independiente previsto para el nuevo montaje,
  con ruta CLI explícita. No copiar el dual_zone/640/.10/ROI/TTL/stitching de demo2:
  son otra geometría y alterarían varias variables simultáneamente.
- En el código, horizontal selecciona Y y positive equivale a down. Demo3 explicita
  horizontal/down para movimiento vertical de imagen; OUT es up. Una configuración
  vertical/down sería inválida y representaría el eje incorrecto.
- Medir el archivo entregado, no asumir 720p: OpenCV aplica la matriz MOV y entrega
  848×476. source.width/height solo documentan ese tamaño; no redimensionan archivo.
  FFprobe/OpenCV coinciden en 1686; no se necesita --verified-frames.
- No desplazar línea, banda o ROI para recuperar totales. La puerta carece de
  referencia geométrica confirmada en esta evaluación; solicitar Y mediante la
  vista local existente y conservar y=.50/±.04 hasta justificar otra geometría.
  La creación de demo3.yaml no constituye calibración validada.
- Distinguir salida YOLO, caja después de ByteTrack y track admitido por área.
  Diez rechazos .85 ocurren sobre estimaciones rastreadas, no cajas YOLO originales.
  Nueve producen dos huecos que caducan el contador; ByteTrack mantiene los IDs.
  Las confianzas altas descartan bajar conf como solución sustentada para esos casos.
- Replay antes del filtro es control de entrada numérico con algoritmo y parámetros
  idénticos, no nuevo perfil ni resultado calibrado. Recupera OUT16/OUT29 y deja
  iguales los otros diez eventos. Su 6/6 no demuestra precisión individual; faltan
  timestamps manuales y correspondencia visual completa. No aplicar el control
  en producción ni elevar .85 durante esta tarea.
- Propuesta futura: evaluar el área de la detección YOLO asociada frente al área
  suavizada del tracker, con casos sintéticos de cambio rápido de aspecto y bordes,
  seguida de auditoría de eventos reales. La interacción actual queda reproducida;
  no se declara un bug independiente del algoritmo puro ni una corrección validada.
- Privacidad: no enviar imágenes del video a herramientas externas ni persistir
  capturas. Vista OpenCV, overlay/JPEG y comprobación HTTP quedan locales y en RAM.
  El perfil normal mantiene stream/debug apagados; YAML auxiliar ignorado habilita
  explícitamente la vista en loopback. Todos los procesos propios se cierran.
- Benchmark solo demo3, 320/stride1/auto, tres repeticiones sin/con overlay/JPEG,
  sin otra inferencia ni tests concurrentes. No confundir FPS nominales del archivo,
  capacidad de procesamiento, tasa JPEG y latencia. Los tiempos de sus ventanas
  excluyen warmup; la evaluación completa conserva el arranque de inferencia.

## Nueva evidencia de calibración demo3 — 2026-10-10

- La instrucción nueva autoriza guardar .60 únicamente en demo3.yaml. Conservar
  todos los demás parámetros y el YAML auxiliar histórico sin cambios; no tocar
  la sesión abierta del usuario. No implementar todavía la propuesta sobre área.
- Comprobar configuración efectiva con API numérica, no asumir que un cambio de
  controles se guardó. Productor/dashboard apuntan al YAML auxiliar con .50 en
  disco; RAM declara .6106, revisión 3 aplicada. Registrar la diferencia respecto
  de la posición .60 descrita por el usuario sin interpretar un snapshot parcial
  de conteos en loop como resultado final.
- Evaluar .60 exacto por CLI: 6/5, no 6/6. Contrastar también .6106 leído del
  productor en una pasada con override de dataclass exclusivamente en RAM y la
  misma CLI: 6/6. El perfil guardado sigue .60. No hay barrido ni optimización.
- Emparejar eventos por trayectoria numérica/ID/sentido con tracks históricos;
  ambas pasadas coinciden con esos replays. Retienen los diez pares anteriores;
  .60 añade OUT16 y .6106 también OUT29. Esto restringe la hipótesis de que otro
  ID compensó los omitidos, pero no certifica identidad física ni precision/recall.
- La línea más baja confirma OUT antes del hueco de área; no mejora detección ni
  asociación. Diez rechazos continúan. ID29 se confirma con solo 2,681 píxeles de
  margen y una observación antes del rechazo con .6106. Sensibilidad del centroide
  ±1/±3 píxeles sobre datos congelados documenta fragilidad sin cambiar perfiles.
- Mantener .60 como configuración experimental pedida, no como calibración
  plenamente validada. No cambiar automáticamente a .6106 para conseguir totales.
  Revisar referencia física y anotar cruces antes de decidir si el filtro requiere
  corrección de código. No inferir que deja de ser un problema por obtener 6/6.
## Organización de resultados JSON — 2026-10-10

- Separar las cuatro mediciones de rendimiento en `docs/benchmarks/` y las ocho
  evaluaciones y validaciones en `docs/evaluations/`. Clasificar por contenido:
  `benchmark-evaluation.json` evalúa conteos y `benchmark-validation.json` valida
  las pasadas, por lo que ambos pertenecen a evaluaciones.
- Conservar cada JSON byte por byte. Sus rutas internas anteriores son evidencia
  histórica y permanecen intactas; los enlaces y comandos Markdown usan las rutas
  nuevas. No hay referencias anteriores en scripts, configuraciones ni tests.
