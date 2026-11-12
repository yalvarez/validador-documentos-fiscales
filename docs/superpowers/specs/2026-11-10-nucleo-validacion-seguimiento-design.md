# Núcleo común: validación del XML, seguimiento del estado y consulta

Fecha: 2026-11-10
Estado: listo para aprobación

## 1. Intención

Terpel recibe facturas electrónicas (e-CF) de sus proveedores. Muchos sistemas de
proveedores envían el PDF y el XML **antes** de que la DGII haya respondido, así que en
el momento de recibirlos la factura todavía aparece "en proceso" o "no encontrada", o cambia
de estado horas después. Ahí ocurren la mayoría de los problemas.

Hoy la aplicación solo lee el QR del PDF, consulta una vez la página pública de la DGII y
guarda ese resultado como definitivo.

Este trabajo construye el **núcleo común** a los dos modelos de negocio cotizados
(Propuesta V1.2 por API y Propuesta V1.1 por email watcher):

1. **Validar el XML** del e-CF: estructura, integridad (que no haya sido alterado desde que se firmó), certificado del
   firmante (vigente, de una entidad autorizada por INDOTEL y no revocado al firmar) y
   coherencia con el PDF.
2. **Seguir el estado** del comprobante en la DGII de forma periódica, con intervalos
   crecientes, hasta un plazo máximo.
3. **Exponer el último estado conocido** a un sistema de terceros que consulta nuestra API.

La forma en que entran los documentos (endpoint que recibe archivos, o lectura de correo)
**no es parte de este trabajo**; se diseñará después. El núcleo expone una función de
registro que ambas vías usarán.

## 2. Objetivos

- Detectar si un XML fue alterado después de firmado.
- Detectar si el certificado del firmante no estaba vigente al firmar, no fue emitido por
  una entidad certificadora autorizada por INDOTEL, o estaba revocado al momento de firmar.
- Detectar inconsistencias entre el XML, el QR del PDF y la DGII.
- Mantener actualizado el estado DGII de cada comprobante registrado durante un periodo
  configurable, y guardar el historial de cada consulta.
- Permitir al sistema de terceros consultar, por RNC emisor + e-NCF, el último estado
  conocido, sin que esa consulta dependa de que la DGII esté disponible en ese momento.

## 3. No objetivos

- Recibir documentos por API o por correo (modelos A y B): se trabaja después.
- Registrar aprobación o rechazo comercial (ACECF): el sistema **solo consulta**.
- Notificar cambios activamente (webhook o correo). El tercero consulta; no se empuja nada.
- Usar los servicios web oficiales autenticados de la DGII. Se sigue consultando la página
  pública `ConsultaTimbre` (scraping), como hoy.
- Verificar que el titular del certificado corresponde al RNC emisor o está autorizado por
  él. Los e-CF suelen firmarlos personas autorizadas con su certificado personal (la muestra
  lo es: persona física, emitido por Viafirma Dominicana), y no hay forma pública de
  verificar esa autorización. **Decisión del usuario.**
- Atender a más de un cliente: el despliegue es exclusivo para los proveedores de Terpel.
- Frontend o pantallas.
- Arreglar los problemas existentes no relacionados (credenciales en el repo, endpoints
  comentados, bugs del email watcher), salvo lo imprescindible para este trabajo.

## 4. Anti-objetivos (fallas aunque "funcione")

- Marcar como inválida una factura que solo está pendiente en la DGII.
- Registrar un error de la DGII (HTTP 500, timeout, HTML inesperado) como si fuera un
  cambio de estado del comprobante.
- Reportar la firma como prueba de que el firmante estaba autorizado por el emisor. Cada
  verificación de la firma (`integridad`, `vigencia`, `entidad_certificadora`, `revocacion`)
  se reporta por separado con su propio nombre; no hay un "firma válida" que las mezcle.
- Que un servidor de revocación caído haga aparecer una factura como fraudulenta: eso es
  `NO_VERIFICABLE`, no `FALLO`.
- Romper los tres endpoints existentes (`/validar-factura-pdf-base64`,
  `/validar-factura-pdf-multipart`, `/validar-factura-params`).
- Que el contrato de respuesta al tercero cambie de forma sin aviso: los valores de estado
  son fijos y documentados.

## 5. Contexto técnico actual

- Python con FastAPI (`src/api/backend.py`). Imagen Docker `python:3.11-slim`.
- Capa de datos intercambiable (`src/db/`): SQLite, MySQL y SQL Server, cada uno con su
  wrapper y con la creación de tablas en código (`CREATE TABLE IF NOT EXISTS`).
- Configuración en la tabla `parametros`, leída con `ParametrosManager`.
- `common/pdf_processor/extractor.py` lee el QR del PDF.
- `common/validator/web_validator.py` hace el scraping de la DGII y devuelve `estado`
  y `razon_social_emisor`.
- `common/xml_processor/parser.py` existe (xmltodict) pero no se usa.
- Hay una muestra real firmada: `tests/samples/101616202E310000002882.xml` y su PDF. La
  firma es XMLDSig envolvente (enveloped), `rsa-sha256`, C14N 2001 y `Reference URI=""`,
  con el certificado X.509 incrustado. La fecha va en `FechaHoraFirma`, con formato
  `dd-MM-yyyy HH:mm:ss`.

## 6. Diseño

### 6.1 Validación del XML (`common/xml_validator/`)

Función de entrada: `validar_xml(xml_bytes, qr_params=None) -> ResultadoValidacionXML`.

Cada verificación devuelve un resultado independiente con `resultado` ∈
{`OK`, `FALLO`, `NO_VERIFICABLE`} y un `detalle` en texto. `NO_VERIFICABLE` significa que
no se pudo comprobar (falta la XSD del tipo, el servidor de revocación no responde, no hay
PDF para cruzar). **No equivale a un fallo.**

| Verificación | Qué comprueba |
|---|---|
| `estructura` | El XML valida contra la XSD oficial de la DGII del tipo de e-CF (`TipoeCF`: 31, 32, 33, 34, 41, 43, 44, 45, 46, 47). Las XSD se guardan en el repo. |
| `integridad` | El `DigestValue` coincide con el documento recalculado y el `SignatureValue` verifica con la llave pública del certificado incrustado en el propio XML. Cualquier alteración del documento después de firmado da `FALLO`. Un XML sin firma da `FALLO`. No se evalúa quién es el titular del certificado. |
| `vigencia` | `FechaHoraFirma` (zona horaria de RD) está entre `notBefore` y `notAfter` del certificado firmante. Se verifica sin conexión. Nota: la fecha la declara el firmante dentro de lo firmado; no hay sello de tiempo de un tercero. |
| `entidad_certificadora` | La cadena del certificado firmante llega a una raíz de la lista de confianza: certificados raíz e intermedios de las entidades autorizadas por INDOTEL, guardados como archivos en una carpeta configurable (parámetro `CA_CONFIANZA_DIR`). Agregar una entidad nueva = agregar su archivo, sin tocar el código. Se verifica sin conexión. Cada archivo de la carpeta es un **ancla de confianza** que debe coincidir byte a byte con un eslabón de la cadena (no basta el nombre). El ancla es el certificado de la entidad autorizada (por ejemplo, el intermedio "VIAFIRMA DOMINICANA"), no necesariamente la raíz, porque la raíz de Viafirma es española y también emite para otros países. Si falta un intermedio en la carpeta, se puede descargar desde la URL "CA Issuers" del propio certificado y guardarlo en caché. |
| `revocacion` | El certificado no estaba revocado en `FechaHoraFirma`. Se consulta primero OCSP y, si no responde, la CRL (las URLs vienen en el certificado). Una revocación **posterior** a la fecha de firma no invalida la factura: da `OK` con la fecha de revocación en el detalle. Si ni OCSP ni CRL responden: `NO_VERIFICABLE`. Las CRL se guardan en caché hasta su `nextUpdate`. |
| `cruce` | Solo si hay `qr_params`. Compara RNC emisor, RNC comprador, e-NCF, fecha de emisión, monto total, fecha de firma y código de seguridad entre el XML y el QR. El código de seguridad se compara con los 6 primeros caracteres del `SignatureValue`; el builder lo confirma primero contra la muestra real. |
| `comprador` | Si el parámetro `RNC_TERPEL` tiene valor, el `RNCComprador` del XML debe ser ese RNC. Si no tiene valor, `NO_VERIFICABLE`. *(Decisión de diseño: como el despliegue es solo para proveedores de Terpel, una factura a nombre de otro comprador es una señal de error o de fraude.)* |

### 6.2 Estados normalizados

El texto que devuelve la DGII se guarda tal cual (`estado_dgii_texto`). Además se asigna un
estado propio, que es el contrato con el tercero:

| Estado | Significado |
|---|---|
| `PENDIENTE` | La DGII aún no lo muestra, o lo muestra en proceso. |
| `ACEPTADO` | Aceptado por la DGII. |
| `ACEPTADO_CONDICIONAL` | Aceptado condicional por la DGII. |
| `RECHAZADO` | Rechazado por la DGII. |
| `NO_ENCONTRADO` | Terminó el plazo de seguimiento y nunca apareció en la DGII. |
| `DESCONOCIDO` | La DGII devolvió un texto que no está en la tabla de mapeo. Se registra una advertencia. |

El mapeo de texto DGII a estado propio vive en una tabla en el código. El builder la arma a
partir de respuestas reales.

**Transiciones:** el estado siempre refleja la **última respuesta válida** de la DGII,
también si retrocede (por ejemplo, de `ACEPTADO` a `PENDIENTE`). Así lo pidió el usuario:
"le damos el último estado que tenemos". Cada cambio queda como `CAMBIO_ESTADO` en el
historial.

**Respuesta válida vs. error:** el analizador de la página de la DGII distingue tres casos:
1. página con datos del comprobante → se mapea el estado;
2. página reconocible de "comprobante no encontrado" → `PENDIENTE`;
3. cualquier otra cosa (HTTP ≠ 200, timeout, HTML sin ninguna de las dos marcas) →
   `ERROR_CONSULTA`.

El builder identifica la marca del caso 2 consultando un e-NCF inexistente.
`WebValidator` hoy confunde los casos 2 y 3; el núcleo usa un analizador nuevo y deja
`WebValidator` intacto para los endpoints existentes. *(Decisión de diseño.)*

### 6.3 Modelo de datos

Hay dos tablas nuevas. La tabla `facturas` actual se mantiene como bitácora de los
endpoints existentes y no se modifica.

**`comprobantes`**: una fila por comprobante, con clave única (`rnc_emisor`, `encf`).
- Identificación: `rnc_emisor`, `encf`, `rnc_comprador`, `tipo_ecf`, `fecha_emision`,
  `monto_total`, `fecha_firma`, `codigo_seguridad`, `razon_social_emisor`, `url_consulta`.
- Documento: `xml_contenido` (los **bytes exactos** recibidos, en `BYTEA`, porque
  convertirlos a texto puede romper la firma al revalidar), `xml_hash_sha256`, `qr_params`
  (JSON con los parámetros del QR, si llegó PDF; permite revalidar sin perder el cruce),
  `origen` (`api` o `email`) y `referencia_origen` (por ejemplo, el id del correo).
- Validación: `validacion_detalle` (JSON con las 7 verificaciones). Además, cada una de
  las cuatro verificaciones de la firma (`integridad`, `vigencia`, `entidad_certificadora`,
  `revocacion`) tiene su propia columna, para poder filtrar por ella.
- Certificado: `certificado_titular`, `certificado_emisor` y `certificado_serie`, para
  auditoría.
- La revocación se vuelve a intentar en cada consulta de seguimiento mientras esté en
  `NO_VERIFICABLE`. *(Decisión de diseño.)*
- Estado: `estado`, `estado_dgii_texto` y `ultima_consulta_dgii`.
- Seguimiento: `seguimiento_activo`, `seguimiento_hasta`, `proxima_consulta`,
  `intervalo_actual_min` e `intentos`.
- `creado_en` y `actualizado_en`.

**`comprobante_historial`**: una fila por evento.
- `comprobante_id`, `fecha`, `tipo` (`REGISTRO`, `CONSULTA`, `CAMBIO_ESTADO`,
  `ERROR_CONSULTA` o `DOCUMENTO_REEMPLAZADO`), `estado_anterior`, `estado_nuevo`,
  `estado_dgii_texto` y `detalle`.

Si llega de nuevo un comprobante ya registrado:
- se vuelve a validar el XML;
- si el hash del XML cambió, ~~se registra `DOCUMENTO_REEMPLAZADO` y se guarda el XML nuevo~~
  **(cambio 2026-11-12, decisión del usuario)** el XML nuevo se descarta, se registra `DOCUMENTO_RECHAZADO`
  y lo guardado no cambia: un comprobante registrado no se reemplaza nunca, porque no se verifica que el
  titular del certificado sea el emisor y un reemplazo permitiría sustituir la factura de otro;
- el seguimiento **no** se reinicia.

### 6.4 Registro (punto de entrada común)

Las vías de ingesta llamarán, más adelante, a:

`registrar_comprobante(xml_bytes, pdf_bytes=None, origen, referencia_origen=None) -> Comprobante`

1. Lee el XML y extrae los campos de identificación.
2. Si hay PDF, extrae los parámetros del QR con `PDFProcessor`.
3. Ejecuta `validar_xml`.
4. Hace la primera consulta a la DGII con una URL construida **siempre desde el XML**
   (firmado), nunca desde el QR. El QR solo se usa para el cruce, así un PDF alterado no
   desvía la consulta. Para tipo 32 con monto total menor a RD$250,000 se usa
   `ConsultaTimbreFC`, con sus propios parámetros; para todo lo demás, `ConsultaTimbre`.
   *(Decisión de diseño.)*
5. Guarda o actualiza la fila de `comprobantes`, con su historial, y arma el calendario de
   seguimiento.

Si la primera consulta a la DGII falla, el comprobante igual se registra como `PENDIENTE`
y el seguimiento se encarga.

### 6.5 Seguimiento periódico

Lo hace un proceso separado (`src/seguimiento/worker_main.py`) con su propio servicio en
`docker-compose`. Se despierta cada `SEGUIMIENTO_CICLO_SEG`, toma los comprobantes con
`seguimiento_activo` y `proxima_consulta <= ahora`, y los consulta uno a uno.

Parámetros (tabla `parametros`, con valores por defecto si no existen):

| Clave | Por defecto | Uso |
|---|---|---|
| `SEGUIMIENTO_INTERVALO_INICIAL_MIN` | 60 | Primer intervalo después del registro. |
| `SEGUIMIENTO_FACTOR` | 2 | Multiplicador del intervalo en cada consulta (1 = intervalo fijo). |
| `SEGUIMIENTO_INTERVALO_MAX_MIN` | 1440 | Tope del intervalo. |
| `SEGUIMIENTO_DURACION_MAX_HORAS` | 72 | Tiempo desde el registro tras el cual se detiene el seguimiento. |
| `SEGUIMIENTO_CICLO_SEG` | 300 | Cada cuánto se despierta el worker. |

Reglas:
- **Calendario:** `proxima_consulta = ahora + intervalo_actual`, y luego
  `intervalo_actual = min(intervalo_actual × factor, intervalo_max)`.
- **Duración:** el seguimiento continúa durante todo el plazo **cualquiera que sea el
  estado**, incluso si ya está `ACEPTADO`. El objetivo es asegurarse de que no cambie.
- **Cierre:** cuando `ahora >= seguimiento_hasta`, se hace una última consulta. Si es
  válida, se aplica y se marca `seguimiento_activo = false`; si en ese momento el estado
  es `PENDIENTE` (la DGII respondió "no encontrado"), pasa a `NO_ENCONTRADO`.
- **Cierre con errores:** si la consulta de cierre da error, se reintenta en cada ciclo
  durante hasta 1 hora adicional. Si sigue fallando, se cierra **sin cambiar el estado** y
  se registra un `ERROR_CONSULTA` con el detalle "seguimiento cerrado sin consulta válida".
  Un `NO_ENCONTRADO` solo se asigna a partir de una respuesta válida de la DGII, nunca
  por errores. *(Decisión de diseño.)*
- **Errores de consulta:** un error (HTTP, timeout o HTML sin los campos esperados) se
  registra como `ERROR_CONSULTA` y **no cambia el estado**. La siguiente consulta se
  reintenta en el próximo ciclo del worker, sin avanzar el intervalo.
- **Ritmo:** se espera 1 segundo entre consultas para no saturar la DGII.

### 6.6 Endpoint de consulta

`GET /comprobantes/{rnc_emisor}/{encf}`, protegido con `x-api-key` igual que los demás.

Respuesta 200:

```json
{
  "registrado": true,
  "rnc_emisor": "101616202",
  "encf": "E310000002882",
  "razon_social_emisor": "EMPRESAS ASAVIM S R L",
  "estado": "ACEPTADO",
  "estado_dgii_texto": "Aceptado",
  "ultima_consulta_dgii": "2026-11-10T14:05:00-04:00",
  "seguimiento_activo": true,
  "seguimiento_hasta": "2026-11-13T10:00:00-04:00",
  "validacion": {
    "estructura": {"resultado": "OK", "detalle": ""},
    "integridad": {"resultado": "OK", "detalle": ""},
    "vigencia": {"resultado": "OK", "detalle": "Vigente 2026-01-12 a 2027-01-12"},
    "entidad_certificadora": {"resultado": "OK", "detalle": "VIAFIRMA DOMINICANA"},
    "revocacion": {"resultado": "OK", "detalle": "OCSP: good"},
    "cruce": {"resultado": "NO_VERIFICABLE", "detalle": "Sin PDF"},
    "comprador": {"resultado": "OK", "detalle": ""}
  }
}
```

Si el comprobante no se ha registrado: 404 con `{"registrado": false}`.

Fechas en ISO 8601 con zona horaria de RD (-04:00).

## 7. Restricciones

- Python 3.11 (imagen Docker). Dependencias nuevas en `src/api/requirements.txt`. Se
  sugiere `signxml` (usa `lxml` y `cryptography`); el builder puede elegir otra si la
  justifica.
- La API y el worker necesitan salida a internet hacia la DGII y hacia los servidores
  OCSP y CRL de las entidades certificadoras.
- **Base de datos: PostgreSQL** (decisión del usuario, porque el volumen va a crecer mucho).
  - Se agrega un `PostgresDBWrapper` en `src/db/`, con el mismo patrón que los demás:
    hereda de `BaseDBWrapper`, crea sus tablas al iniciar y se registra en `db_factory`
    como motor `postgres`. Implementa las tablas existentes (`facturas`, `mensajes_recibidos`,
    `parametros`) y las nuevas.
  - Las tablas nuevas **solo** se implementan para PostgreSQL. Los wrappers de SQLite,
    MySQL y SQL Server quedan como están, sin las tablas nuevas.
  - El motor y la conexión dejan de estar fijos en `backend.py` y se leen de variables de
    entorno (`DB_ENGINE`, `DB_CONNECTION_STRING`), tanto en la API como en el worker.
  - `docker-compose.yml` agrega un servicio `postgres` con un volumen persistente y el
    servicio `seguimiento`; la API y el worker apuntan a él.
  - Índices: único en (`rnc_emisor`, `encf`); en (`seguimiento_activo`, `proxima_consulta`)
    para el worker; y en `comprobante_historial.comprobante_id`.
  - Driver: `psycopg` (v3). *(Decisión de diseño.)*
- Los nombres del código y de los mensajes van en español, como el resto del proyecto.
- Los endpoints existentes siguen funcionando igual.

## 8. Pruebas mínimas

- La muestra real `tests/samples/101616202E310000002882.xml` da `integridad = OK`.
- Una copia con un campo cambiado (por ejemplo `MontoTotal`) da `integridad = FALLO`.
- `vigencia`: la muestra da `OK`; si el certificado no estaba vigente en `FechaHoraFirma`,
  `FALLO` (para la prueba se puede usar un certificado propio).
- `entidad_certificadora`: la muestra da `OK` con las raíces de Viafirma en la carpeta;
  con la carpeta vacía o un certificado autofirmado, `FALLO`.
- `revocacion`: OCSP y CRL simulados para cuatro casos: no revocado (`OK`), revocado antes
  de la firma (`FALLO`), revocado después de la firma (`OK` con la fecha) y servidores
  caídos (`NO_VERIFICABLE`).
- `comprador`: con `RNC_TERPEL` distinto al de la muestra da `FALLO`; sin el parámetro,
  `NO_VERIFICABLE`.
- Las pruebas de base de datos corren contra un PostgreSQL real (contenedor de
  docker-compose o equivalente); no se simula la base.
- `estructura` con la muestra es `OK`; con un XML sin un nodo obligatorio es `FALLO`.
- Cruce: la muestra contra su PDF da `OK`; un QR con un monto distinto da `FALLO`.
- Calendario de seguimiento con reloj simulado: intervalos 60, 120, 240… minutos, tope y
  fin a las 72 h; un error de consulta no cambia el estado ni avanza el intervalo; un
  `PENDIENTE` al final pasa a `NO_ENCONTRADO`.
- Endpoint de consulta: 200 con un comprobante registrado y 404 sin él. La DGII se simula
  (mock); las pruebas no salen a internet.

## 9. Queda a criterio del builder

- Librería de firma y de validación XSD.
- Dónde obtener las XSD oficiales de la DGII y cómo organizarlas en el repo.
- Dónde obtener los certificados raíz e intermedios de las entidades autorizadas por
  INDOTEL (lista oficial de INDOTEL) y cómo organizarlos. Como mínimo, Viafirma Dominicana,
  para que pase la muestra.
- Timeouts de OCSP y CRL (que sean cortos, para no frenar el registro).
- La tabla de mapeo de textos DGII a estados propios.
- La estructura interna de módulos y clases.
