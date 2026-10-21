# Cámara APC Metro · XIAO ESP32S3 Sense + OV3660

Firmware independiente basado en CameraWebServer oficial. La cámara transmite
JPEG/MJPEG por Wi-Fi; OpenCV, YOLO, ByteTrack y conteo siguen ejecutándose en el
Mac. No cambia código de producción Python ni defaults de conteo.

**Checkpoint físico confirmado por el usuario — 2026-10-21:** firmware propio
instalado; portal Wi-Fi funciona tras corregir Origin/CSRF, conecta al hotspot
del iPhone y LED amarillo queda fijo. Desde el Mac resuelven `apc-metro.local`,
`/capture` y `http://apc-metro.local:81/stream`. `check_stream.py` recibió **60
frames, 320×240, 2,232 s, 26,88 FPS**. Son FPS de recepción, no de YOLO/conteo.
Evidencia textual en [contexto de hardware](../../docs/APC_Metro_ESP32_Contexto_Hardware.md).

**Esperando carcasa:** conservar este firmware validado. No recompilar/subir ni
modificar calibración para preparar el software; detección física, estabilidad,
persistencia tras reinicio y precisión APC siguen pendientes. El agente no repitió
las pruebas del checkpoint ni abrió la cámara en esta etapa.

## Qué se conserva

- `CAMERA_MODEL_XIAO_ESP32S3`, OPI PSRAM, flash 8MB, USB CDC habilitado.
- Particiones `default_8MB`: aplicación de 3.342.336 bytes, igual a la selección
  «Default with spiffs (3MB APP/1.5MB SPIFFS)». No se monta SPIFFS ni microSD.
- Pines, reloj 20 MHz, JPEG, dos buffers en PSRAM, `CAMERA_GRAB_LATEST`, ajustes
  OV3660 (vflip=1, brillo=1, saturación=-2), QVGA inicial y Wi-Fi sin sleep.
- Panel oficial en `http://<IP>/`, controles y captura; stream directo en
  **`http://<IP>:81/stream`**, sin requerir pulsar Start Stream. La ruta/puerto
  están confirmados también por la prueba física del usuario del 21.
  El panel permite VGA/SVGA u otra resolución sin cambiar el contrato de APC.

`vendor/` conserva los originales sin claves y hashes verificables; leer su
[procedencia y alcance](vendor/README.md). `src/` contiene arranque, cámara y
configuración de red. El parche del servidor conserva el formato multipart y
añade parada/reinicio, timeouts HTTP y `no-store`, retirando CORS indiscriminado.
No se añaden reconocimiento facial, grabación, OTA ni bibliotecas externas.

## Compilar sin Arduino IDE

Ejecutar desde la raíz del repositorio. Requiere Python 3, Arduino CLI, `patch`
y el core **esp32:esp32@3.3.12**. Para pruebas nativas requiere C++17 (en Mac,
Command Line Tools de Xcode). La herramienta usa `arduino-cli` del PATH o,
si ya está instalado el IDE, su CLI interna sin abrir el IDE.

En este Mac ya están Arduino CLI 1.5.1 y el core correcto. Para una instalación
nueva: instalar [Arduino CLI](https://docs.arduino.cc/arduino-cli/installation/),
y luego:

```sh
arduino-cli core update-index --additional-urls https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
arduino-cli core install esp32:esp32@3.3.12 --additional-urls https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
```

En macOS el directorio del core es `~/Library/Arduino15`. En Linux/Windows
definir `ARDUINO_DATA_DIR` al directorio de datos de CLI. `ARDUINO_CLI` permite
indicar la ruta del ejecutable. El script comprueba la versión seleccionada y
falla si es distinta; no actualiza dependencias silenciosamente.

```sh
python3 firmware/esp32-camera/tools/manage.py secret
python3 firmware/esp32-camera/tools/manage.py build
python3 firmware/esp32-camera/tools/manage.py ports
```

`secret` crea una contraseña AP aleatoria de 128 bits, 32 dígitos hexadecimales,
en `firmware/esp32-camera/.private/setup_password.txt`, permisos 600. No la muestra
ni reemplaza si ya existe. Abrir ese archivo **solo localmente** en el editor,
guardar su clave en un gestor de contraseñas y usarla al unirse al AP. No pegar
el contenido en chat, logs, capturas, issues ni Git. No hay contraseña publicada
de respaldo. La compilación incorpora esta clave privada, nunca SSID/clave de
la red de casa o hotspot. `.private/` y `.build/` están ignorados; los binarios,
cachés y el header generado también contienen la clave AP: no compartirlos.

## Subir una vez por USB

Conectar la placa con cable de datos; cerrar el monitor del IDE. Sustituir el
puerto de ejemplo por el que devuelva `ports` (puede cambiar al reconectar):

```sh
python3 firmware/esp32-camera/tools/manage.py upload --port /dev/cu.usbmodem1101
python3 firmware/esp32-camera/tools/manage.py monitor --port /dev/cu.usbmodem1101
```

Upload usa exclusivamente un binario compilado correctamente y comprueba hashes
de fuentes/clave/binario; exige recompilar si cambiaron. No ejecuta erase-flash
ni permite un puerto IP. No subir hasta estar listo para reemplazar el ejemplo
actual; compilar o cerrar el IDE no modifica la placa. El monitor es a 115200;
Ctrl+C lo cierra. No se espera a abrir serial para arrancar con powerbank.

Si el puerto no aparece: verificar cable, volver a ejecutar `ports`; como
recuperación de carga mantener BOOT, pulsar/soltar RESET, soltar BOOT y buscar
el puerto del cargador. Subir y después pulsar RESET con BOOT libre.
El procedimiento USB de recuperación siempre permanece disponible.

### Historial de la corrección de «Guardar y conectar» (ya comprobada)

El usuario confirmó después de actualizar que Guardar y conectar funciona.
Las instrucciones siguientes quedan como referencia; no volver a subir firmware
para integrar APC ni mientras falte la carcasa.

El portal anterior enviaba `Referrer-Policy: no-referrer`. Para un POST HTML de
navegación, el [estándar Fetch](https://fetch.spec.whatwg.org/#append-a-request-origin-header)
puede convertir el encabezado en `Origin: null`, aunque el token oculto sea
correcto. Chrome local reprodujo exactamente esa combinación. El firmware cambia
la política a **same-origin** y conserva el rechazo de `null`/orígenes ajenos,
la comparación constante del CSRF, la exclusividad AP y el Host permitido.
No se amplía la lista de orígenes permitidos para hacer pasar la prueba.

El core 3.3.12 procesa este POST con `_parseRequest` y `_parseArguments` de
WebServer: `application/x-www-form-urlencoded` decodifica token/SSID/password
antes del handler. Se recolectan explícitamente **Origin y Content-Type**, ambos
formularios declaran el enctype y se distingue un campo vacío de uno ausente.
Los tests de navegador verifican token intacto y codificación de `+`, `&`, `=`,
`%` y UTF-8. No se modificó el parser del core. Esas pruebas usan un servidor
loopback del Mac; no sustituyen el parser/transporte real en la placa.

Desde la raíz, con USB conectado y cualquier otro monitor cerrado:

```sh
python3 firmware/esp32-camera/tools/manage.py build
python3 firmware/esp32-camera/tools/manage.py ports
python3 firmware/esp32-camera/tools/manage.py upload --port /dev/cu.usbmodem1101
python3 firmware/esp32-camera/tools/manage.py monitor --port /dev/cu.usbmodem1101
```

`/dev/cu.usbmodem1101` es el puerto registrado anteriormente, **no un puerto
detectado durante esta corrección**. Sustituirlo si `ports` muestra otro. No se
ha ejecutado upload en esta sesión. Se conserva la clave AP local existente,
la pareja NVS, los parámetros de cámara y los defaults de conteo.

Después de actualizar: abrir una página nueva en **http://192.168.4.1/**; no
reenviar el POST de una pestaña anterior ni de «Atrás» (su token puede pertenecer
a otra sesión). Seleccionar el hotspot, escribir la clave solo en el portal y
pulsar Guardar. Esperado por serial:

```text
[portal] post=accepted origin=local csrf=ok form=urlencoded
Wi-Fi: probando nueva red; solo se guarda al obtener IP.
```

Si el navegador omite Origin se admite como antes, siempre con AP/Host/token
correctos, y el diagnóstico dice `origin=absent`. Tras IP deben desaparecer el AP
y el parpadeo rápido; comprobar luego panel/stream y persistencia tras reinicio.
Si no ocurre, registrar únicamente el código de rechazo o los estados seriales,
nunca el cuerpo POST, token, SSID o contraseñas. No hace falta capturar tráfico.

| Diagnóstico de serial y respuesta | Qué falló |
| --- | --- |
| `origin_null` | Origen opaco; recargar una página nueva del firmware actualizado |
| `origin_foreign` | Origin distinto de la IP AP HTTP, puerto 80 |
| `csrf_missing` / `csrf_length` | Token ausente o mal formado en los argumentos POST |
| `csrf_mismatch` / `csrf_session` | Token distinto (página vieja) o sesión no válida |
| `post_type` | Content-Type no es application/x-www-form-urlencoded; HTTP 415 |
| `fields_missing` | Falta SSID o password; una clave vacía sí es un campo presente |
| `credentials_encoding` / `credentials_format` | Longitud, NUL o formato de credenciales inválido |
| `ap_inactive` / `ap_interface` / `ap_client` / `host` | Falló la restricción de acceso al AP |
| `busy` / `nvs_unavailable` | Operación pendiente o almacenamiento no disponible |

Los diagnósticos registran **códigos fijos**, sin valores de cabeceras, campos ni
tokens. Las pruebas locales ya no reproducen el rechazo con la política nueva;
**el rechazo físico de Guardar quedó resuelto según el checkpoint del usuario**,
con asociación al hotspot y video directo confirmados.

Para volver a la referencia oficial si la aceptación falla: ejecutar `manage.py
reference`, editar **solo** `.build/reference/CameraWebServer/CameraWebServer.ino`
localmente para introducir SSID/clave (nunca en vendor), compilar esa copia y
subirla por CLI. No repetir `reference` después de editar, porque restaura las
credenciales vacías. Con el CLI incluido en este Mac:

```sh
APC_CLI='/Applications/Arduino IDE.app/Contents/Resources/app/lib/backend/resources/arduino-cli'
"$APC_CLI" --config-file firmware/esp32-camera/.build/arduino-cli.yaml compile --fqbn 'esp32:esp32:XIAO_ESP32S3:PSRAM=opi,FlashSize=8M,CDCOnBoot=default,PartitionScheme=default_8MB,DebugLevel=none' --build-path "$PWD/firmware/esp32-camera/.build/rollback" firmware/esp32-camera/.build/reference/CameraWebServer
"$APC_CLI" --config-file firmware/esp32-camera/.build/arduino-cli.yaml upload --fqbn 'esp32:esp32:XIAO_ESP32S3:PSRAM=opi,FlashSize=8M,CDCOnBoot=default,PartitionScheme=default_8MB,DebugLevel=none' --port /dev/cu.usbmodem1101 --input-dir firmware/esp32-camera/.build/rollback firmware/esp32-camera/.build/reference/CameraWebServer
```

Si el CLI está en PATH usar `APC_CLI=arduino-cli`. Puerto según `ports`. Esta
subida manual es únicamente para rollback local; contiene claves en sketch y
binarios ignorados. Retirarlos localmente al terminar y no compartirlos. No se ha
ejecutado rollback ni upload durante esta sesión.

## Primer arranque y cambio de red

1. Encender con BOOT libre. Sin red NVS propia, aparece **APC-Metro-Setup**,
   protegido con WPA2-PSK y la clave privada del paso `secret`.
2. En el Mac unirse a ese AP aunque avise «sin Internet». Desactivar reconexión
   automática a otras redes durante la configuración si macOS abandona el AP.
3. Abrir **http://192.168.4.1/**, HTTP explícito. No hay DNS/portal cautivo
   automático. Seleccionar un SSID del escaneo o escribirlo (también red oculta),
   introducir su clave y pulsar **Guardar y conectar**. Solo admite 2,4 GHz,
   red abierta o WPA personal con clave ASCII de 8–63 caracteres; SSID de hasta
   32 bytes UTF-8. No se recortan espacios. No admite WPA empresarial/portal de
   universidad. Evitar una red destino que use también 192.168.4.0/24.
4. Intenta conectar durante 25 s. Solo después de obtener IP guarda un único
   registro NVS (Preferences). Cierra el AP/portal, enciende LED fijo y abre la
   cámara. Reconectar el Mac a la misma red elegida. Serial informa IP y estados,
   nunca SSID ni claves. Si falla asociación o NVS, vuelve al portal, conserva
   la red guardada anterior y registra el error por serial.
5. Abrir el panel o el endpoint directo. El AP nunca ofrece video. Solo se
   atiende el portal en su IP/interfaz AP; POST con token y comprobación de origen.

**BOOT durante ejecución:** esperar que la placa haya arrancado y observado el
botón libre; mantenerlo **3–9 s y soltar** abre configuración conservando la red.
Mantener **10 s o más y soltar** borra la red NVS propia y limpia también posibles
credenciales STA del ejemplo anterior, abre configuración y conserva la clave AP.
No hace reboot ni borra firmware. Un toque corto o rebote no ejecuta acciones.
El borrado reporta errores por serial; no se declara éxito si falla NVS.
El portal incluye también «Borrar credenciales Wi-Fi», disponible solo desde AP.

**No mantener BOOT mientras se enciende o pulsa RESET:** GPIO0 es un pin de
strapping. Eso entra al cargador ROM antes de ejecutar este programa; no se
puede cambiar desde firmware. Soltarlo y pulsar RESET recupera el arranque normal.
La lectura en ejecución es INPUT_PULLUP, sin escribir GPIO0 ni modificar eFuses.

Al reiniciar intenta la red guardada. Si desaparece durante streaming, detiene
video, intenta reconectar 25 s y abre el AP si no logra IP. Cada sesión AP dura
10 minutos: con red previa vuelve a intentar esa red; sin ella apaga el AP hasta
BOOT o un nuevo encendido. Tras desconexión, APC Python requiere reiniciar su
proceso de captura, como antes; no se ha añadido reconexión al pipeline Python.

## LED y microSD

| Estado de red | LED amarillo GPIO21, activo LOW |
| --- | --- |
| Buscando red guardada | Alterna cada 600 ms |
| Configuración / probando nueva red desde AP | Alterna cada 120 ms |
| Conectado con IP | Encendido fijo |
| AP expirado sin red / fallo al crear AP | Apagado; revisar serial |

Se usa `millis()` y una máquina de estados, sin `delay()` ni espera de conexión
en bucle. La cámara trabaja en tareas HTTP propias. En cambios de modo se cierran
lectores; un cliente lento puede demorar el cierre unos segundos por los timeouts
HTTP. El LED indica **red**, no certifica que sensor/servidor hayan iniciado:
esos errores se informan por serial, con reintento HTTP cada 10 s.

[Seeed documenta](https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/)
GPIO21/LED activo LOW, BOOT/GPIO0 y GPIO21 como CS microSD. No usar tarjeta ni
inicializar SD/SPI en este firmware; el LED conmutaría su CS. La cámara OV3660
usa otros pines según el mapa oficial XIAO preservado. El LED rojo de carga es
independiente. LED fijo conectado confirmado físicamente; patrones de parpadeo
y recuperación/borrado por BOOT aún no certificados por este checkpoint.

## Encontrar la cámara desde el Mac

Se anuncia `apc-metro.local`, HTTP 80 y servicio Bonjour `_apc-camera._tcp` 81 con
TXT `path=/stream`. Con Mac y cámara en la misma red:

```sh
dns-sd -B _apc-camera._tcp local.
dns-sd -L apc-metro _apc-camera._tcp local.
dns-sd -G v4 apc-metro.local
```

Usar el nombre de instancia mostrado por `-B` si Bonjour lo renombra. Ctrl+C
termina cada comando. Probar `http://apc-metro.local/` o usar la IP resuelta;
varias cámaras requieren nombres distintos (este firmware está pensado para una).

**Sin mDNS:** leer IP por serial USB o en la lista DHCP/dispositivos del router,
identificada por hostname `apc-metro`; una reserva DHCP evita cambios en casa.
No se hace barrido de direcciones ni se depende de una IP fija. En hotspot donde
el iPhone no muestre leases y mDNS falle, conectar USB al Mac para leer la IP;
después se puede volver a la powerbank. Serial informa la nueva IP en cada
reconexión. La disponibilidad Bonjour/aislamiento entre clientes depende de la red.

## Comprobar MJPEG/OpenCV sin guardar imágenes

Cerrar el streaming del navegador antes de usar OpenCV: el servidor oficial de
stream tiene un solo handler de larga duración; dos lectores pueden competir.
Sustituir el host por la IP encontrada si mDNS falla:

```sh
.venv/bin/python firmware/esp32-camera/tools/check_stream.py apc-metro.local --frames 60
```

Comprueba HTTP 200 + multipart/boundary y lee con **el StreamSource existente**.
Devuelve solo IP, dimensiones, frames, segundos y FPS recibidos. Conexión/cierre
están incluidos en el tiempo: no es benchmark de inferencia ni latencia ni una
promesa de >20 FPS con esta cámara. No muestra ni guarda frames y solo acepta
hosts locales. No ejecutar capturas de tráfico del POST Wi-Fi ni guardarlas.

Para APC, crear un perfil local ignorado, por ejemplo `data/esp32-demo.yaml`,
partiendo del perfil que se quiera calibrar, y sustituir únicamente `source` por:

```yaml
source:
  type: stream
  url: "http://apc-metro.local:81/stream"  # O IP actual; nunca SSID/clave aquí.
  queue_size: 2
  open_timeout_ms: 5000
  read_timeout_ms: 3000
```

Ejecutar `scripts/run_demo.py --config data/esp32-demo.yaml` con la venv.
Recordar que las rutas relativas del YAML se resuelven desde el padre de su
carpeta: desde `data/` siguen apuntando a la raíz. Usar `visualization.stream=false`
y `debug.show_video=false` para la prueba numérica. Recalibrar línea/sentido/áreas
para este encuadre en una tarea posterior; esto no valida precisión de conteo.

## Pruebas de aceptación que requieren la placa

**Checkpoint parcial confirmado:** portal, conexión al hotspot, LED fijo, mDNS,
capture y 60 frames MJPEG. La matriz conserva pruebas adicionales pendientes;
no se requieren ahora, mientras falte la carcasa. Registrar resultados sin SSID,
claves, imágenes ni rostros.

| Prueba | Procedimiento y resultado exigido |
| --- | --- |
| Casa | Red doméstica pendiente; con hotspot ya confirmados portal, asociación, LED fijo y 60 frames OpenCV |
| Reinicio/powerbank | Desconectar USB, encender powerbank con BOOT libre; sin portal si red guardada disponible; repetir OpenCV; comprobar varios reinicios |
| Cambio de red | Con video activo mantener BOOT 4 s y soltar; video se cierra, LED rápido, portal AP; nueva red conecta y persiste tras apagar |
| Clave incorrecta | Probar deliberadamente clave errónea; tras 25 s reaparece portal; reiniciar y comprobar que aún intenta la red anterior |
| Red ausente | Apagar el router/hotspot; LED lento y tras 25 s AP; reconfigurar o esperar ciclo de 10 min y verificar reconexión al volver la red |
| AP temporal | Sin red guardada esperar 10 min: AP apagado; BOOT 4 s y soltar lo reabre; con red guardada reintenta y recupera AP si no está |
| Borrado | BOOT 11 s y soltar (o botón del portal); serial confirma borrado; reinicio abre AP, sin borrar firmware ni cambiar clave AP |
| BOOT/arranque | Toque corto no hace nada; recuperación ROM mediante BOOT+RESET y posterior RESET con BOOT libre conserva firmware; no grabar de nuevo salvo necesidad |
| Aislamiento | Conectado normal no existe `/save` en LAN; en setup no hay cámara ni puerto 81; probar IP de STA durante asociación: no sirve portal; AP rechaza clave incorrecta |
| Cortes/estabilidad | Leer 600 frames, cortar/restaurar red y reiniciar lector; repetir cambios de modo; anotar errores y resets; no afirmar FPS/temperatura/autonomía sin medir |

Para **iPhone 16 Pro Max**: Ajustes → Compartir Internet → Permitir a otros
conectarse y **Maximizar compatibilidad**. Este modo limita el hotspot a 2,4 GHz,
según [Apple](https://support.apple.com/en-ca/guide/security/secfd166f620/web).
Mantener abierta esa pantalla durante la asociación. Desde el **Mac** entrar al
AP de la cámara, seleccionar/escribir el nombre real del hotspot solo en el
portal y su clave; después reconectar el Mac al hotspot y repetir panel/OpenCV.
El iPhone ofrece la red; no necesita unirse al AP de la cámara simultáneamente.
Repetir apagado/encendido del hotspot y de la powerbank. Si la cámara obtiene IP
pero el Mac no la alcanza, revisar aislamiento de clientes; no asumir compatibilidad
por la sola asociación Wi-Fi. Acceso Mac→ESP confirmado por el usuario en el
hotspot probado mediante capture/MJPEG; no certifica todos los hotspots.

Pruebas locales automatizadas desde la raíz:

```sh
.venv/bin/python -m pytest -q tests/test_esp32_firmware.py
.venv/bin/python -m pytest -q
python3 firmware/esp32-camera/tools/manage.py reference
```

## Límites y seguridad

La protección WPA2 y la exclusividad AP protegen la configuración por radio,
con token contra CSRF, comprobación Host/Origin y respuestas no-store. HTTP no
usa TLS: toda persona con la clave AP pertenece a la zona de confianza. No hay
registro de SSID/clave por aplicación. Preferences no está cifrado en flash:
acceso físico a NVS o al binario puede revelar credenciales. El borrado lógico
no equivale a borrado forense; no se activan eFuses/secure boot/flash encryption.

Video y panel conservan HTTP sin autenticación del ejemplo oficial en la LAN.
Usar una red privada de demostración; **no reenviar puertos, activar DMZ, túneles
ni publicar 80/81 en Internet**. No se implementan UPnP, routing/NAT ni servicios
cloud. No usar redes públicas o de terceros para transmitir personas. Mantener
el Mac/ESP en la misma LAN; IPv6, TLS, redes empresariales y captive portals de
red destino quedan fuera del alcance.

Una sola pareja Wi-Fi persistente, sin historial. La clave AP se recupera de la
copia local/gestor; si se pierde, regenerarla eliminando **solo** el archivo local
de clave y recompilar/subir por USB (el cambio de clave AP no borra la red NVS).
Para rotarla conservar la anterior hasta terminar de subir y verificar. Si falla
una prueba y no se resuelve, detener la aceptación y registrar el fallo en
`docs/PROGRESS.md`; no declarar preservado el funcionamiento físico por compilar.
