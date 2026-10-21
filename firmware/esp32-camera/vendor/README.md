# Referencia oficial preservada

Origen: [CameraWebServer, Arduino-ESP32 3.3.12 de Espressif](https://github.com/espressif/arduino-esp32/tree/3.3.12/libraries/ESP32/examples/Camera/CameraWebServer).
Extraída del archivo oficial instalado `esp32-core-3.3.12.zip`, cuyo SHA-256
coincide con el índice del paquete:
`87401004f279a206781e368b66098a8383b7cf87cce7811a6afd0163503fa78f`.

`manifest.json` registra hashes originales y preservados. Única sanitización:
`ssid` y `password` del `.ino` quedan vacíos. Los otros cuatro archivos se
conservan byte por byte, incluidos avisos de licencia. Se incluye Apache 2.0,
licencia indicada en `app_httpd.cpp`.

La sesión de hardware registró placa/opciones/modelo, pero **no la versión del
core ni una copia del sketch/binario que se subió**. Esta es una referencia
oficial reproducible del core encontrado en este Mac, no una afirmación de
identidad binaria con el firmware de la placa. No se leyó ni modificó su flash.
No se buscó ni copió ningún sketch privado que pudiera contener claves.

Desde la raíz: `python3 firmware/esp32-camera/tools/manage.py reference` compila
esta referencia con el único cambio de modelo en `board_config.h`: XIAO ESP32S3.
Mantiene OPI PSRAM, 8MB y CDC. Al tener credenciales vacías **no conectará**;
no subirla como firmware operativo. Para volver al comportamiento oficial se
puede adaptar únicamente la copia ignorada de `.build/reference/CameraWebServer`
con credenciales locales y recompilar/subir por CLI, siguiendo el README padre.
Nunca editar ni versionar claves en `vendor/`.

El firmware nuevo copia estos archivos en una carpeta de compilación ignorada,
aplica `patches/app_httpd.patch` con contexto exacto y sustituye el arranque por
`src/`. No se edita esta referencia al evolucionar el firmware.
