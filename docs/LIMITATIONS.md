# Limitaciones

- La calibración y el overlay se inspeccionaron en Chrome con el MOV local el
  2026-10-03, además de AppTest/HTTP. La validación de fuente USB/webcam/HTTP/RTSP
  durante cambios de geometría usa captura y detector simulados; no certifica una
  cámara física nueva ni RTSP real. El HTTP real de transporte sí está en la suite.
- MJPEG y overlay agregan trabajo de CPU y tráfico loopback. El hito 5 registra
  mediciones de overlay/JPEG en RAM; no mide tráfico ni navegador.
  Bajar calidad JPEG/FPS puede reducir esa carga.
- El video demo puede mostrar rostros si se activa sobre una cámara real. No se
  anonimiza. Úselo localmente con autorización de quienes aparecen. La app no graba,
  pero no puede impedir que otro programa o el navegador capture lo mostrado.
- La leyenda de uso local corresponde al servidor ligado a 127.0.0.1 y dashboard
  local: no exponerlos mediante proxies, túneles o un despliegue remoto. Cualquier
  proceso local con acceso al puerto puede leer el stream optativo.
- El navegador debe soportar MJPEG; AppTest valida la estructura del panel pero
  no decodifica el video como un navegador. Las pruebas HTTP sí decodifican JPEG.

- Prototipo de aula; no se ha validado en trenes ni con cámara definitiva.
- La meta de más de 20 FPS no está certificada de forma general. Hay mediciones
  locales del hito 5 en este equipo: todas superan 20 en las tres pasadas, y todas
  salvo 416/stride 3 alcanzan 25. No garantizan la misma tasa en otra máquina.
- YOLO/ByteTrack puede fallar con oclusiones, contraluz, aglomeraciones y cambios de ID.
- Filtros de área y confianza requieren calibración con la posición real de cámara.
- No se guarda video. Los archivos de entrada deben proporcionarse con consentimiento.
- La distribución comercial requiere revisar las licencias de Ultralytics y sus pesos.
- Un cambio de ID durante el cruce puede perder el evento; no hay ReID por aspecto.
  La compuerta ofrece unión geométrica optativa, con rechazos conservadores.
  La banda y la vida mínima pueden omitir cruces extremadamente rápidos.
- Falta validar webcam física y RTSP/celular/cámara definitiva. El soporte depende
  de codecs y backend de OpenCV. La resolución de webcam es una solicitud al dispositivo.
- Algunos drivers de webcam pueden bloquear `read()`; el cierre informa si el hilo
  no responde en cinco segundos. Los streams FFmpeg sí tienen timeout configurable.
- Red lenta y descarte de frames pueden omitir cruces. Una desconexión exige reiniciar
  la sesión y revisar la calibración. No versionar URLs con credenciales.
- La API es local y de una sola sesión, sin autenticación ni persistencia;
  no está diseñada para publicarse en una red. Al terminar el proceso se pierde el estado.
- La demo de cámara publica un solo vagón; los múltiples vagones son simulación.
  Agregar varias cámaras/puertas reales y agregar sus conteos queda fuera de estos hitos.
- Las pruebas sintéticas no miden precisión APC sobre personas. Se requiere una
  validación con compañeros, conteo manual y consentimiento antes de presentar métricas.

## Alcance del hito 5

- OpenCV declara 1.308 frames de `data/demo1.mov`, pero las 72 pasadas del MOV
  entregaron 1.307; las 72 sintéticas se limitaron al mismo número observado.
  La igualdad exacta anterior se sustituyó por tolerancia **±2 con advertencia**,
  autorizada por el usuario para estos metadatos MOV. No se convierten ni rellenan
  frames; se evalúan los realmente entregados. Diferencias mayores siguen fallando.
- **El conteo anterior a la calibración fue insuficiente.** Por defecto: IN=0/OUT=0
  frente a 6/6, 100% de error agregado. Entre las alternativas evaluadas, 416/1
  dio 0/2 y 83,33% de error. No se corrigieron línea, banda ni confianza con este
  único clip; las propuestas y resultados completos están en BENCHMARK.md.
- El bucle resetea tracker y contadores y no acumula pasadas. Ese reinicio no
  impone la referencia manual 6/6. La nueva demo local se verificó durante 1.400
  frames, con puertos libres porque 8765/8501 estaban ocupados. Los comandos del
  README requieren liberar esos puertos o configurar otros. Se preservaron los
  procesos previos y se cerraron los de prueba.
- Un video de 21,81 s y una referencia agregada de 6 entradas / 6 salidas no validan
  precisión general. Coincidir en los totales tampoco demuestra que se detectaron
  los mismos eventos: falsos positivos y negativos pueden compensarse. Faltan
  anotaciones temporales, variedad de escenas y validación independiente.
- El benchmark corre en este equipo, con aplicaciones de fondo; no controla
  temperatura, estado energético ni throttling. Tres pasadas cortas no representan
  una jornada de operación ni certifican FPS en otra CPU.
- El AVI sintético preexistente tiene otra resolución y no contiene personas:
  sus FPS no predicen el coste de tracking con aglomeraciones ni aíslan el efecto
  del contenido respecto de la resolución y el códec.
- La medición del stream cubre overlay y JPEG en RAM, con el límite de 10 FPS;
  excluye transporte HTTP y navegador. Las estelas están apagadas en el barrido
  y activas en las configuraciones de demostración.
- `vid_stride` omite inferencias, pero el lector sigue decodificando los frames
  del archivo. Su tasa de origen no es la tasa de imágenes realmente analizadas;
  aumentar stride puede perder identidades, vida mínima o cruces rápidos.
- `--realtime` usa el FPS informado por OpenCV y no los PTS individuales de un
  archivo de tasa variable. No acelera un pipeline lento ni elimina frames para
  recuperar retraso. `--loop` reinicia identidades y conteos al rebobinar.
- Los temporizadores de inferencia y el callback de tracking corresponden a
  Ultralytics 8.3.253. Un cambio de API requiere revisar esa instrumentación;
  el programa informa si no encuentra el callback, en lugar de inventar latencias.

## Evaluación real con calibración visual — 2026-10-03

Perfil `configs/video-demo.yaml`: vertical, x=0.64, semiancho=0.04, IN izquierda,
OUT derecha; mínimos 3 observaciones, máximo 2 frames ausentes. La posición se
eligió mirando el marco real antes de evaluar; banda [0.60,0.68] para histéresis.
No se buscaron parámetros que produzcan 6/6: detección queda en imgsz=320,
conf=0.35, stride=1, hilos automáticos y áreas [0.005,0.85].

Una pasada completa del evaluador produjo **IN=1, OUT=0**, con 1307 frames
procesados. Respecto de la referencia entregada **6/6**, error absoluto **IN=5,
OUT=6, total=11 (91,67%)**. Una pasada diagnóstica sin cambiar parámetros confirmó
1/0: YOLO produjo personas sobre el umbral de confianza en **136 frames**, con
tracks válidos en **123** y **cero rechazos por área**. No es una medida de recall,
pues no hay anotación de presencia por frame. El evento aceptado fue ID 4,
frame procesado **345** (base cero, aproximadamente 5.75 s).

Estos intervalos de detección se contrastaron con el original en un visor local;
no son una anotación temporal exhaustiva de la referencia:

| Intervalo aproximado | Cruce | Track | Resultado y evidencia |
| --- | --- | --- | --- |
| 2.28–2.50 s | IN | 1 | Perdido: llega a banda en frame 143; caduca 146 y reaparece a izquierda en 150, sin recordar el lado derecho. |
| 5.50–6.30 s | IN | 4 | Contado en frame 345: x=0.6808 → 0.5944 y vida suficiente. |
| 9.32–9.85 s | OUT | 5 | Perdido: hueco de 12 frames, caduca 581; reaparece a derecha en 591 como estado nuevo. |
| 10.40–10.75 s | OUT | 7 → 8 | Perdido: cambio de ID y observaciones aisladas; no llega un track estable al lado derecho. |
| 13.81–14.59 s | IN | 9 | Perdido: caduca a derecha en 833/840; reaparece a izquierda en 853. |
| 13.9–14.9 s | IN, segunda persona junto a la anterior | Sin track separado | Solapamiento visible: no se obtiene otra trayectoria independiente. |
| 17.92–18.12 s | OUT | 11 | Perdido: detecciones solo x=0.18–0.31; caduca 1090 antes de alcanzar banda. La persona sigue a derecha en el visor. |
| 20.53–21.39 s | OUT | 13 | Perdido: hueco de 4 frames, caduca 1259; reaparece en banda 1261 y alcanza derecha 1265 sin estado izquierdo. |

Se identificaron ocho trayectorias completas visibles, incluidas dos personas
juntas, y siete omisiones concretas. La referencia **6/6 es agregada y no aporta
timestamps**: no se localizaron inequívocamente las otras dos IN y dos OUT. Hay
tránsitos parciales en el borde derecho, incluido 11.8–13.0 s, sin centroide
rastreable ni dirección certificable. No se inventa una correspondencia para
esos cuatro eventos ni se sustituye la referencia. Hace falta anotación temporal
manual completa para atribuir los once errores a eventos específicos.

El fallo confirmado predominante es la pérdida de detecciones y la caducidad del
estado, incluso con el **mismo ID**; aumentar tolerancia no arreglaría todos los
casos sin track separado. La vista cenital, el blur visible, los cuerpos cortados
en los bordes y el solapamiento dificultan YOLOv8n; son factores observados, no
causas aisladas demostradas para cada frame. El marco también está oblicuo y la
cámara se mueve: una línea vertical fija aproxima el umbral, sin seguir su
perspectiva ni estabilizar la imagen. La calibración visual corrige la orientación
original, pero no resuelve esa geometría ni la falta de detecciones.

Cambiar un control válido reinicia conteos/ocupación al valor inicial, y opera
sobre la sesión compartida del backend: use una sola interfaz de calibración y
termine de ajustarla antes de medir. MJPEG tiene su propio límite de FPS; la vista
cambia en el siguiente frame disponible, no puede reaccionar sin señal. YAML
counting en formato compacto o con alias se rechaza al guardar para preservar
comentarios y otras secciones. El prototipo no tiene reidentificación, seguimiento
del umbral ni capacidad certificada para el pitch o explotación comercial.

Evidencia numérica: [calibration-evaluation.json](evaluations/calibration-evaluation.json).

## Montaje fijo demo2 — etapa tripwire anterior, 2026-10-06

Baseline **0/0**; perfil diagnóstico de esa etapa **4/1 frente a 12/13**, error agregado
**80%**. Los cinco eventos aceptados son consistentes con cruces en revisión
local, pero no se anotaron exhaustivamente los 25 eventos manuales. No se calcula
precision/recall ni se interpreta la diferencia agregada como 20 FN certificados.
No se conocen duplicados, inversiones o falsos eventos entre los cinco revisados;
ese alcance no garantiza ausencia en otras escenas.

La cámara fija corrige la geometría inestable de demo1, pero a esta distancia
cenital las personas llenan/cortan gran parte del encuadre. YOLOv8n pierde cajas
alrededor del umbral; confianza .10, resolución 416 y asociación sin fuse_score
mejoran continuidad, sin resolverla. Tres rechazos por área fueron registrados,
con atribución temporal pendiente; no se demuestra que el filtro sea causa principal.
Once IDs observados en ambos lados expiran sin evento, con huecos máximos
7–19 frames. Son candidatos numéricos para revisar, no etiquetas manuales.

Cinco ausencias recuperan IN concretos con el mismo ID; no hay reidentificación
ni extrapolación por desaparecer en un borde. Frames ausentes dependen de FPS y
stride: reajustar presupuesto al cambiar de fuente/cadencia. ByteTrack conserva
30 actualizaciones, pero el contador no conserva un lado durante todo ese tiempo:
una memoria tan larga exige validar retornos/oclusiones antes de adoptarla.

El perfil nuevo no tiene dos pasadas de validación final ni verificación integrada
de dashboard: se detuvo antes por precisión insuficiente, como pidió el usuario.
Los tests sintéticos y los 52.48 FPS del evaluador no resuelven la precisión.
ROI y TTA fueron exploraciones descartadas. Para continuar hacen falta anotación
por tiempo y un encuadre que deje observar suficiente cuerpo; no forzar 12/13.

OpenCV declara 2053 muestras, reproduce 2038; FFprobe verifica el efecto de una
lista de edición (2053 al ignorarla). --verified-frames usa un total independiente,
conserva el declarado y aplica ±2 contra la referencia; no acepta cualquier
lectura incompleta. Ese valor de 2038 no corresponde a otros videos. Se conservan
originales y evaluaciones anteriores intactos; solo JSON numérico nuevo.

## Compuerta cenital demo2 — reanudación, 2026-10-06

Resultado actual **8/12 frente a 12/13**, error agregado **20%**. Mejora el 4/1
anterior, pero está por debajo del objetivo de ≥95% de cruces correctos. No se
convierte el error agregado en recall: no existe correspondencia exhaustiva de
los 25 eventos ni se descarta compensación entre FP/FN. La auditoría local confirma
IN de la persona gris f632–645, OUT gris ID52 alrededor de f1052, OUT de personas
distintas IDs84/88 y OUT98 en f1968. No se conocen FP/duplicados/inversiones en
esos cinco; no es garantía global.

Tres entradas omitidas están contrastadas: persona gris f380→410 (IDs16→20/21),
persona burgundy f635→670 (ID35→33), burgundy f1017→1068 (ID51/54).
En la primera, el fragmento nuevo nace muy
profundo en B, fuera del radio/corredor conservador. En la segunda, el antiguo 33
de la persona gris se asigna a la otra persona, después de la unión 33→37.
El salto .378 supera radio .35: se rechaza heredar historia y empieza un fragmento
independiente. No ampliar radio ni unir personas por tener IDs/tiempos cercanos.
Los otros dos déficits agregados no tienen etiqueta temporal suficiente.
Hay pérdidas de detección y fragmentación/cambio de ID observables; no se atribuye
todo automáticamente a ByteTrack. La mejora no conserva todos los eventos antiguos:
la entrada alrededor de 13.4 s detectada antes se omite con esta inferencia/ROI.

YOLOv8n sigue perdiendo cuerpos cenitales/cortados cerca de la puerta aun a 640.
ROI conserva ancho completo, pero recorta .10 superior/.05 inferior y puede sesgar
cajas/centroides allí; cambiarlo requiere revisar geometría, no copiarlo a otra
cámara. Hay 15 rechazos de área; no están etiquetados como cruces perdidos. El
centroide de una caja parcial puede desplazarse respecto del centro real de una
persona. No se estima una cabeza ni se añade entrenamiento/ReID.

Stitching usa geometría de imagen, no identidad comprobada por aspecto. Puede
rechazar al pasajero correcto si pierde demasiada trayectoria o cambia de dirección;
también puede equivocarse si dos personas próximas cumplen los mismos criterios.
Se rechazan candidatos ambiguos/simultáneos y alias con salto incompatible. La
presencia profunda recupera desapariciones por borde, pero un outlier profundo
del detector todavía podría emitir un evento: los tests sintéticos no certifican
escenas reales. No contar desapariciones sin presencia medida en ambos lados.

TTL .9 s conserva OUT84 tras hueco .833 s; .8 lo pierde, 1.0 no añade eventos en
el replay. Archivo usa tiempo del contenido/FPS fallback; webcam/HTTP/RTSP usan
captura. ByteTrack usa buffer derivado de FPS/stride y supone cadencia nominal;
colas vivas con descartes pueden hacerlo durar más. FPS inválido en vivo usa
estimación 30 para ese buffer, no para el reloj del contador. La configuración
de segundos exige timestamps finitos no decrecientes y reinicio por vuelta.

Dashboard comprobado con fuente real, zonas/anchor correctos y calibración A/B;
tests solo sintéticos. El smoke de 900 frames logró 22.83 FPS con overlay/JPEG;
no demuestra mínimo sostenido en otras laptops o cámaras. La pasada aislada a640
  se mide sin streaming. Las revisiones simultáneas de varios decodificadores
pueden perjudicar FPS: una pasada con visor activo dio 16.59, no se usa como
medición aislada. Video/frames no se guardan, ni se suben, convierten o renombran.

Dos pasadas finales de 2038 frames: **8/12**, mismos 20 eventos por frame, IDs y
dirección, **26.913/26.158 FPS**. 1880 cajas, 1265 observaciones, 54 IDs físicos,
54 identidades temporales (no equivalen a 54 pasajeros), 53 expiraciones; 12 con
última caja en borde de imagen. Una unión y un alias rechazado; ningún candidato
sin evento que alcance ambas zonas. Esto no detecta los fragmentos que nunca
logran ver ambos lados y no demuestra que no haya más omisiones.

Control adicional en tracks idénticos: tripwire con TTL .9 produce **10/14**,
error agregado menor (12%), pero alrededor de 35 s asigna ID54 de la persona
gris a la burgundy y cuenta OUT54 f1035 y OUT52 f1051 para la misma salida gris.
La compuerta conserva solo OUT52 y omite el IN burgundy: hay un intercambio real
de sensibilidad y rechazo de errores, no una prueba de superioridad por totales.
No escoger parámetros por acercarse a 12/13 ni afirmar que todo evento agregado
adicional sea correcto. Se requieren anotaciones completas para comparar métodos.

Siguiente trabajo: anotar los 25 cruces, revisar encuadre/distancia para observar
trayectorias completas y validar cámara final. El montaje sigue siendo un prototipo
diagnóstico mejorado; no se declara una demo de conteo suficientemente fiable.

## Latencia de fuentes live — corrección 2026-10-10

La cola Python reemplaza inmediatamente frames antiguos cuando está llena; eso
no elimina los buffers del dispositivo, driver, red o FFmpeg. Puede existir
latencia antes de timestamp/read y no se ha medido con una cámara física.
El cierre deja sin hilos los backends que responden a read/timeouts; no puede
interrumpir de manera segura un driver que bloquee indefinidamente. Ese caso
continúa informando error de cierre, como antes de la corrección.

## Próximo montaje y contrato — 2026-10-10

- Video pendiente (~1280×720/30 fps/30°): geometría del perfil de ejemplo sin
  validar. La inclinación es información de montaje; no hay rectificación de
  perspectiva ni líneas/franjas oblicuas. Recalibrar en la puerta nueva.
- position/band_half_width se usan en tripwire; dual_zone utiliza A/B. Los perfiles
  independientes usan defaults de dataclasses, sin heredar default.yaml.
  min_zone_frames cuenta observaciones de zona, conservables en una ausencia
  tolerada; no necesariamente frames consecutivos. No se cambia el TTL actual.
- FPS de demo/dashboard no certifica capacidad sostenida ni latencia. ByteTrack
  vence por actualizaciones; descartar frames altera la equivalencia con segundos.
  Ninguna cámara definitiva está probada, ni se prometen 30 fps efectivos.
- Width/height son solicitudes a webcam/USB; archivo/stream usan frame decodificado.
  Los timeouts de FFmpeg requieren soporte del backend. CAP_PROP_FPS puede ser
  nominal/incorrecto. OV3660 es un sensor: confirmar el transporte del equipo.
- Telemetría añade green_below/red_above numéricos; el cliente nuevo admite
  productores anteriores con umbrales desconocidos. Consumidores antiguos que
  rechazan claves adicionales deben actualizarse. Calibración añade session_id
  (del productor, no persona) y expected opcional para rechazar POST obsoletos.
  Con un productor antiguo sin session_id no se distingue todo reinicio idéntico.
- La regresión 720p es sintética con detector simulado; verifica coordenadas,
  eventos y ausencia de mutación del frame. No prueba recall YOLO, identidad de
  personas, precisión APC ni hardware físico. La precisión sigue pendiente.

## Firmware propio de cámara — 2026-10-21

- Checkpoint físico comunicado por el usuario el 21-10: firmware propio instalado,
  portal corregido conecta al hotspot, LED fijo, mDNS, capture y MJPEG funcionan.
  check_stream/StreamSource recibe 60 frames 320×240 en 2,232 s (26,88 FPS),
  **sin medir YOLO ni conteo**. Esperando carcasa: no se exigen nuevas pruebas
  físicas ni se cambia firmware/calibración. Matriz de pruebas adicionales en
  [la guía](../firmware/esp32-camera/README.md): casa, iPhone 16 Pro Max, arranque
  powerbank, LED/BOOT, cambios de red, ausencia, borrado, aislamiento y estabilidad.
- `/stream` en 81 confirmado en fuente y por el usuario en OV3660 real. El agente
  solo ejecutó transporte sintético en el Mac. Faltan tasa sostenida, inferencia
  física, latencia, calidad/encuadre APC, consumo, autonomía y temperatura.
  QVGA inicial reproduce el ejemplo; no garantiza resolución suficiente para YOLO.
- No se conoce versión/sketch exacto del firmware anterior grabado. Se conserva
  referencia oficial 3.3.12 reproducible, no copia binaria exacta de la flash.
- LED comparte GPIO21 con CS microSD: tarjeta/SD excluidos. BOOT/GPIO0 también
  selecciona modo ROM al reset: solo debe mantenerse 3/10 s **en ejecución** y
  soltarse para actuar. No hay firmware que impida el strapping previo al arranque.
- Una sola red persistente. Wi-Fi 2,4 GHz, personal o abierta; sin WPA Enterprise,
  portales de red destino, TLS, IPv6 ni roaming multirred. Evitar red destino
  192.168.4.0/24 por conflicto con AP. Escaneo es una instantánea; recargar/reabrir
  setup para actualizarlo, o escribir SSID manualmente. No hay portal cautivo DNS.
- La clave AP privada reside en el binario y las de redes en NVS **sin cifrado**;
  lectura física de flash puede exponerlas. Borrado es lógico, no forense. Quien
  conoce la clave AP tiene acceso al portal; HTTP no añade TLS. No se activan
  secure boot/eFuses. Cambiar clave AP perdida requiere recompilar/subir por USB.
- Video/panel HTTP sin autenticación en la LAN, igual que el ejemplo. Usar red
  privada y sin reenvíos de 80/81, DMZ ni túneles. No ofrece aislamiento de usuarios
  dentro de esa LAN. El firmware no configura firewall del router ni puede
  garantizar su configuración. No se añaden cloud, UPnP, routing ni NAT.
- Bonjour depende de multicast y del router; `.local` no garantiza descubrimiento.
  Serial y lista DHCP del router son los respaldos. Hotspot del iPhone requiere
  Maximizar compatibilidad para 2,4 GHz; acceso Mac→ESP confirmado en el hotspot
  del checkpoint. La prueba no garantiza disponibilidad en otras redes.
- HTTP de streaming oficial sirve un lector prolongado por servidor: cerrar
  streaming del navegador antes de abrir APC. Cerrar un lector lento al entrar
  en setup puede tardar unos segundos por timeout; no afecta la temporización
  del LED durante streaming estable. Reintentos HTTP no corrigen fallos de sensor.
  StreamSource Python conserva su contrato de terminar ante caída: reiniciar APC
  después de recuperar Wi-Fi; no hay reconexión transparente añadida al pipeline.
- POST del portal: reproducido en Chrome local el origen null inducido por
  no-referrer, corregida la política a same-origin sin aceptar null ni retirar
  CSRF. No se conoce el encabezado exacto del intento físico previo; ese mecanismo
  explica el rechazo local. La prueba posterior del usuario confirma conexión y
  video con la corrección. Reabrir la página tras upload; páginas de sesiones anteriores
  se rechazan por token distinto. Los códigos de rechazo permiten confirmar la
  causa sin capturar cabeceras/cuerpo ni publicar credenciales.
- Los tests con Chrome usan datos sintéticos y el formulario/cabeceras del
  controlador real, pero un servidor HTTP del Mac decodifica el POST. El parser
  WebServer del core fue inspeccionado y compilado para ESP32, no ejecutado en
  hardware durante esta corrección. Si Chrome/Chromium no está instalado, esos
  dos tests adicionales se omiten; los tests C++ de validación se mantienen.

## Integración preparada mientras falta carcasa — 2026-10-21

- Configuración ESP32 lista sobre el StreamSource existente. Sin nueva sesión
  física del agente: recepción del checkpoint es evidencia del usuario. YOLO/
  ByteTrack se ejecutaron con MJPEG sintético en CPU, no personas de esta cámara.
  Cajas/IDs/cruces/estelas se comprobaron con respuestas de detector simuladas y
  el resto del pipeline real, incluida API y AppTest; no se certifica recall ni
  identidad física. Pesos locales requeridos, sin descarga automática; el test
  real YOLO se omite si no existen (en este Mac sí existen).
- Esperar carcasa antes de detección física, latencia/estabilidad y evaluación de
  encuadre. Conteos del perfil usan valores sin calibración y son provisionales.
  No se ajustaron líneas, bandas, sentidos, ROI, filtros ni tracker. Controles del
  dashboard disponibles, pero no mover/guardar en esta etapa. Video local opcional
  por perfil; sin guardado de frames. Firmware validado sin tocar.
- --metrics ofrece tasas estimadas: capture_fps usa delta índice/timestamp de
  captura entre frames recibidos por el consumidor; incluye reemplazos de cola
  en ese intervalo, no frames previos al primero ni posteriores al último. No es
  FPS del sensor ni latencia; timestamp Unix puede saltar y sesgarlo (no creciente
  produce null). inference_fps es throughput observado, con espera/primera
  inferencia, mientras yolo_inference_ms_mean mide solo la etapa Ultralytics.
  Tracking inicial puede ser cero hasta instalar el wrapper del callback.
- No hay benchmark vivo con warmup ni nuevos resultados físicos de inferencia.
  Los FPS del dashboard conservan el promedio histórico; publicación JPEG local
  a 10 FPS no limita la captura ni certifica visualización a la misma tasa.
  Usar un lector de stream a la vez; no abrir check_stream simultáneo a APC.
