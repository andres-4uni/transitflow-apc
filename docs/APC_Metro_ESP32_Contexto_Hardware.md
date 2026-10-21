# APC Metro — Contexto de hardware ESP32S3 Sense

**Checkpoint actualizado:** 21 de octubre de 2026; conserva el historial del 17.
**Estado:** firmware propio, configuración Wi-Fi y recepción MJPEG comprobados por el usuario; detección/conteo con montaje final pendientes de la carcasa.
**Documento complementario a:** `contexto_apc_metro_para_chatgpt.md` (arquitectura, reglas de trabajo con Codex y problemas previos de conteo).

> **Para un futuro ChatGPT:** actúa como líder técnico. El usuario quiere instrucciones claras y específicas, sin microgestionar cada clic. No escribe directamente el software del repositorio: tú redactas prompts y **Codex, local en VS Code**, inspecciona e implementa. Prioriza información **verificada** y no supongas que el estado del repositorio sigue siendo el de esta fecha.

## Checkpoint físico confirmado — 21 de octubre de 2026

Evidencia textual comunicada por el usuario; el agente no repitió estas pruebas.
Sin imágenes, SSID ni contraseñas guardados. Este estado reemplaza los pendientes
de transporte del historial inferior; no certifica precisión APC.

| Elemento | Resultado físico confirmado |
| --- | --- |
| Hardware | Seeed Studio XIAO ESP32S3 Sense + OV3660 |
| Firmware instalado | Propio de `firmware/esp32-camera`, posterior a la corrección Origin/CSRF |
| Portal | APC-Metro-Setup permite configurar Wi-Fi y guardar/conectar |
| Red | Conexión al hotspot del iPhone exitosa; LED amarillo fijo |
| Nombre desde Mac | `apc-metro.local` resuelve |
| Imagen individual | `/capture` funciona |
| MJPEG | `http://apc-metro.local:81/stream` funciona |
| Recepción mediante `check_stream.py` | 60 frames, 320×240, 2,232 s, **26,88 FPS recibidos** |

```text
.venv/bin/python firmware/esp32-camera/tools/check_stream.py apc-metro.local --frames 60
Resultado reportado: frames=60, width=320, height=240, seconds=2.232, received_fps=26.88
```

Son FPS de recepción/decodificación mediante StreamSource en el Mac, no de YOLO,
ByteTrack, dashboard ni conteo. No se proporcionó referencia de cruces ni medida
de latencia. No inferir persistencia tras reinicio, autonomía o estabilidad prolongada.

**Restricción actual:** el equipo termina la carcasa física. Preparar software,
perfil y comandos sin abrir la cámara ni pedir pruebas físicas de detección.
No cambiar firmware ni calibración. Tras la carcasa se retomarán detección en
escena real, encuadre, rendimiento y validación de conteo por separado.

## Historial de puesta en marcha — 17 de octubre de 2026

Las secciones siguientes conservan el contexto anterior. Los pendientes de
endpoint directo/firmware propio quedan reemplazados por el checkpoint superior.

## 1. Resumen ejecutivo

Se puso en marcha una **Seeed Studio XIAO ESP32S3 Sense** con cámara **OV3660**:

- **Probado:** programación desde Arduino IDE en MacBook Air M2 mediante USB-C.
- **Probado:** cámara inicializada, ESP32 conectado a Wi-Fi y panel `CameraWebServer` accesible desde el navegador del Mac.
- **Probado:** `Start Stream` presenta **video en vivo** de la cámara.
- **Probado:** desconectado del Mac y alimentado mediante **powerbank**, el ESP32 sigue sirviendo el video al Mac por Wi-Fi.
- **Pendiente el 17:** apertura del MJPEG directo. **Confirmada el 21** mediante
  check_stream/StreamSource; estabilidad prolongada, detección y conteo siguen pendientes.

**Arquitectura objetivo:**

```text
Powerbank USB ──5 V──> XIAO ESP32S3 Sense + OV3660
                                │
                                └── Wi-Fi / MJPEG ──> MacBook Air M2
                                                       │
                                                Python/OpenCV
                                                       │
                                               YOLOv8n + ByteTrack
                                                       │
                                            conteo IN/OUT + Streamlit
```

El **ESP32 solo captura y transmite**; la inferencia y el seguimiento continúan en el **Mac**, sin rediseñar el stack. La powerbank suministra energía: **la placa no trae una batería integrada**.

## 2. Hardware y montaje

| Elemento | Identificación / estado |
|---|---|
| Placa | **Seeed Studio XIAO ESP32S3 Sense** |
| Sensor | **OV3660**, conectado mediante expansión Sense y cable flexible de cámara |
| Antena | Externa Wi-Fi/Bluetooth de Seeed, conectada al pequeño conector **U.FL/I-PEX** de la placa principal |
| Alimentación comprobada | USB-C desde MacBook; posteriormente USB-C desde una **powerbank** convencional |
| Computador | MacBook Air M2, macOS Apple Silicon |
| Cable | Cable USB-C original Apple de iPhone 16, con transferencia de datos funcional |

**Notas prácticas:**

- El conector USB-C inicialmente parecía no entrar por completo; finalmente encajó con un **clic** y el Mac reconoció el dispositivo. No aplicar fuerza excesiva ni movimientos laterales.
- El conector **U.FL** de antena fue muy difícil de encajar (~40 minutos); **ya está conectado**. Evitar extraerlo, forzar el coaxial o tirar del cable.
- La lámina negra con texto `Seeed Studio` es **la antena**, no un protector para retirar. La película que cubre el adhesivo trasero es opcional.
- El módulo de cámara/expansión fue reinstalado; mantener la cámara apoyada, sin tensionar el cable flexible, y la antena sin quedar pinzada.
- Los LED rojo/amarillo cambiaron de estado durante las pruebas; **no utilizarlos como único indicador de funcionamiento**. La comunicación USB y el video fueron indicadores directos más fiables.
- Se notó cierto calentamiento durante el uso; no se midió temperatura. Vigilar calor excesivo, olor anormal o reinicios; mantener ventilación.

## 3. Configuración confirmada de Arduino

- Aplicación usada: **Arduino IDE 2.3.10** (vista en la sesión).
- URL adicional de Boards Manager:

```text
https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
```

- Paquete instalado: **esp32 by Espressif Systems** (versión concreta no registrada).
- Board seleccionada: **`XIAO_ESP32S3`** (NO `AI Thinker ESP32-CAM`).
- Puerto observado en la sesión: **`/dev/cu.usbmodem1101`**; puede cambiar tras reconectar.
- `USB CDC On Boot`: **Enabled**.
- `PSRAM`: **OPI PSRAM** (estaba Disabled; se cambió).
- `Flash Size`: **8MB (64Mb)**.
- `Partition Scheme`: **Default with spiffs (3MB APP/1.5MB SPIFFS)**.
- `Serial Monitor`: **115200 baud**.

**Prueba básica superada:** se cargó un sketch simple que imprimía `ESP32 CONECTADO CORRECTAMENTE`, `APC METRO - SISTEMA INICIADO` y periódicamente `ESP32 FUNCIONANDO...` en el monitor serial.

### Firmware grabado el 17 (referencia histórica)

El programa cargado en esa sesión fue el **ejemplo oficial de Arduino-ESP32**.
El firmware actual es el propio validado en el checkpoint del 21; no volver a
subir este ejemplo para preparar la integración. Referencia histórica:

```text
File > Examples > ESP32 > Camera > CameraWebServer
```

En la pestaña `board_config.h` se dejaron estos modelos:

```cpp
//#define CAMERA_MODEL_ESP_EYE // Has PSRAM
#define CAMERA_MODEL_XIAO_ESP32S3 // Has PSRAM
```

Todos los otros `CAMERA_MODEL_...` deben permanecer desactivados. En `CameraWebServer.ino` se configuraron `ssid` y `password` con las credenciales de la red Wi-Fi, **que NO se incluyen en este archivo**.

> **Seguridad:** no copiar credenciales a prompts, documentación, repositorios ni capturas compartidas. Durante la sesión una captura llegó a mostrar la contraseña; es prudente cambiarla si la imagen salió de un entorno privado. Cuidado con firmware/sketches que incluyan claves en texto claro.

Se comprobó `Upload` satisfactorio (`Writing ... 100%`, verificación del hash, reinicio). El monitor serial mostró conexión a Wi-Fi y `Camera Ready!` con una URL local. Abrir un ejemplo en el IDE **no** cambia el firmware hasta subirlo; cerrar Arduino IDE **no** borra lo grabado.

## 4. Red, direcciones y pruebas realizadas

**Comprobado en esta red, en la fecha indicada:**

```text
http://192.168.100.135/
```

- La interfaz web `CameraWebServer` cargó en el navegador del Mac.
- Al presionar **Start Stream**, apareció video real y actualizado de la cámara.
- Se repitió la prueba con el ESP32 **alimentado por powerbank** en vez de por el Mac, con resultado satisfactorio.
- El Mac y el ESP32 estaban en la misma red local. ESP32S3 emplea Wi-Fi de **2,4 GHz**.
- Esta IP es **dinámica y local**; puede cambiar al reiniciar o cambiar de red. No hardcodearla como definitiva.

**Endpoint propuesto el 17; confirmado el 21 con hostname:** el ejemplo
`CameraWebServer` entrega MJPEG en el puerto `81`. IP histórica, no permanente:

```text
http://192.168.100.135:81/stream
```

En la sesión del 17 no se abrió directamente. El 21 el usuario confirmó
`http://apc-metro.local:81/stream` mediante StreamSource/OpenCV. Eso valida
recepción, no el pipeline completo de detección/conteo en hardware.

**Medido el 21:** 26,88 FPS de recepción en 60 frames. **Aún no medidos:** FPS
de inferencia en la escena física, latencia extremo a extremo, pérdidas prolongadas,
autonomía, consumo, calidad de conteo y estabilidad durante horas.

## 5. Relación con APC Metro (contexto previo, no nueva validación)

Repositorio actual: **andres-4uni/transitflow-apc**, público; carpeta local
`transport-cam-counter`. Historial desarrollado por Codex local en VS Code.

La arquitectura existente contempla fuentes intercambiables de **archivo, webcam y HTTP/RTSP** seleccionadas por YAML, procesamiento local por **Python 3.11 + OpenCV + YOLOv8n (`person`) + ByteTrack**, conteo por cruce de línea/banda, telemetría numérica y dashboard Streamlit. Existe un modo opcional/local de visualización anotada para la demo. **Confirmar implementación y estado actuales leyendo código y `docs/PROGRESS.md`.**

**Problema previo no resuelto por esta puesta en marcha:** el video de prueba `data/demo1.mov` permitía detectar/tracking, pero tenía **IN=0, OUT=0** pese a **6 entradas y 6 salidas** contadas manualmente. Las mejoras de configuración/diagnóstico del conteo se describen en el documento general. No confundir el éxito de la cámara con que el algoritmo de conteo ya esté validado.

## 6. Próximos pasos técnicos (prioridad)

1. **Fuente directa confirmada el 21:** no repetir ahora; conservar endpoint
   `http://apc-metro.local:81/stream` y respaldo por IP actual.
2. **Inspección del repositorio por Codex, antes de editar:** revisar `AGENTS.md`, `docs/PROGRESS.md`, código de fuentes HTTP/RTSP y la estructura de YAML. Confirmar si la fuente ya acepta directamente ese MJPEG.
3. **Integración mínima y reversible:** crear **configuración específica para ESP32** (sin cambiar `configs/default.yaml` ni reemplazar fuentes previas), IP/URL configurable, parámetros de resolución/FPS y reconexión solo si son necesarios y justificados.
4. **Después de la carcasa:** prueba OV3660 → OpenCV/YOLOv8n/ByteTrack → dashboard.
   No se requiere ni se ejecuta ahora detección física; medir FPS/latencia real al retomar.
5. **Etapa posterior:** cruces controlados y referencia manual sin guardar frames.
   No modificar ahora sentido/línea ni otros parámetros de conteo.
6. **Documentar límites:** oclusión, resolución/ángulo, cortes Wi-Fi, direcciones IP cambiantes, encendido de powerbank, temperatura/ventilación, duración de batería externa, privacidad y condiciones de demostración.

**Restricciones de proyecto que se mantienen:** no rehacer arquitectura, no introducir dependencias salvo justificación, imágenes/IDs solo en modo demo local y opcional (sin grabarlas a disco); no copiar/subir `data/demo1.mov` ni frames; respetar `AGENTS.md`, tests y documentación.

## 7. Prompt histórico del 17 (superado por checkpoint del 21)

No ejecutar la solicitud de pruebas físicas de este prompt mientras falte la
carcasa. Su hipótesis de endpoint ya está confirmada; se conserva solo como historial.

> Lee primero `AGENTS.md`, `README.md`, `docs/PROGRESS.md`, `docs/DECISIONS.md`, `docs/LIMITATIONS.md` y el código real de captura/configuración. Tenemos una **Seeed Studio XIAO ESP32S3 Sense con OV3660** que ya sirve video en navegador mediante `CameraWebServer` por Wi-Fi y funciona alimentada por powerbank. IP usada en la prueba: `192.168.100.135`, **no permanente**. La ruta `http://<IP>:81/stream` es una **hipótesis de endpoint MJPEG aún por verificar directamente**.
>
> **Objetivo:** integrar esta cámara como una fuente HTTP/MJPEG configurable en **APC Metro**, reutilizando la arquitectura existente de OpenCV/YOLOv8n/ByteTrack y el dashboard. Primero diagnostica si la fuente HTTP actual ya puede consumirla, y prueba/explica qué falta antes de modificar código. Implementa solo los cambios imprescindibles; deja una config específica, documentación de encendido, IP, `Start Stream` si aplica, conexión/reconexión y validación observable. No supongas que la integración o el conteo ya funcionan.
>
> Respeta privacidad (no imágenes ni credenciales en repositorio; sin escribir frames a disco), `data/` ignorado, sin alterar defaults globales ni romper otras fuentes. Corre tests pertinentes y luego suite completa, y reporta resultados reales. **Si un test falla y no puedes resolverlo, detente, regístralo en `docs/PROGRESS.md` y no avances.** Actualiza README/DECISIONS/LIMITATIONS/PROGRESS según corresponda; commits pequeños y `git push` al finalizar, conforme `AGENTS.md`. Entrega instrucciones cortas para que el usuario pruebe físicamente el ESP32 conectado a su powerbank.

## 8. Referencias y mantenimiento de este archivo

- Guía oficial Seeed para XIAO ESP32S3: <https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/>
- Guía oficial de cámara Sense: <https://wiki.seeedstudio.com/xiao_esp32s3_camera_usage/>
- Archivo base del proyecto: `contexto_apc_metro_para_chatgpt.md`.

**Al retomar tras la carcasa:** registrar perfil usado, rendimiento de inferencia
y resultados de detección/conteo, sin confundirlos con los FPS de recepción ya
confirmados. No sobrescribir «pendiente» como «comprobado» sin evidencia.
