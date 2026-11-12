
# Validador de Documentos Fiscales

API para validar facturas electrónicas en PDF. Permite extraer datos del QR, validar el comprobante y verificar que el RNC del emisor coincida con el proporcionado.

## Instalación y ejecución

1. Clona el repositorio y navega al directorio del proyecto.
2. Asegúrate de tener Docker y Docker Compose instalados.
3. Inicializa la base de datos ejecutando los scripts SQL en `src/db` si es necesario.
4. Levanta los servicios:

```bash
docker compose build --no-cache backend
docker compose up -d backend
```

## Endpoint principal

### POST `/validar-pdf`

Valida una factura PDF y verifica el RNC del emisor.

#### Headers
- `x-api-key`: API Key de acceso

#### Parámetros (multipart/form-data)
- `file`: Archivo PDF de la factura
- `rnc_emisor`: RNC del emisor a validar

#### Ejemplo de request (curl)

```bash
curl -X POST "http://localhost:7000/validar-pdf" \
   -H "x-api-key: TU_API_KEY" \
   -F "file=@/ruta/a/tu/factura.pdf" \
   -F "rnc_emisor=123456789"
```

#### Ejemplo de respuesta

```json
{
   "rncemisor": "123456789",
   "razon_social_emisor": "EMPRESA EJEMPLO",
   "estado": "valida" // o "rnc-no-coincide", "invalida", etc.
}
```

## Registro de un e-CF (XML y PDF)

### POST `/comprobantes`

`multipart/form-data` con el header `x-api-key`:

- `xml` (obligatorio): el e-CF firmado. De él sale todo lo necesario para validar y para consultar la DGII
  (RNC emisor y comprador, e-NCF, fecha, monto, fecha de firma y código de seguridad, que son los 6 primeros
  caracteres del `SignatureValue`).
- `pdf` (opcional): la representación impresa. Si viene, los datos de su QR se cruzan con el XML (verificación
  `cruce`), lo que detecta un PDF que no corresponde a su XML. Sin PDF, `cruce` da `NO_VERIFICABLE`.

Valida el XML, hace la primera consulta a la DGII y deja el comprobante en seguimiento. Responde lo mismo que el
`GET` de abajo. Reenviar el mismo e-CF no lo duplica. Errores: `422` si el XML no es un e-CF legible, `413` si un
archivo supera 10 MB.

```bash
curl -X POST "https://validador-fe.ysalabs.work/comprobantes"   -H "x-api-key: TU_API_KEY"   -F "xml=@101616202E310000002882.xml"   -F "pdf=@101616202E310000002882.pdf"
```

## Consulta del estado de un e-CF

### GET `/comprobantes/{rnc_emisor}/{encf}`

Devuelve el último estado conocido de un e-CF registrado en el sistema. El `rnc_emisor` y el `encf`
se normalizan (se quitan espacios y se pasa a mayúsculas), de modo que `e310000002882` encuentra `E310000002882`.

Requiere el header `x-api-key`. Solo funciona con PostgreSQL (`DB_ENGINE=postgres`); con otro motor responde `503`
con `{"detail": "Requiere DB_ENGINE=postgres"}`.

```bash
curl "http://localhost:7000/comprobantes/101616202/E310000002882" -H "x-api-key: TU_API_KEY"
```

Respuesta `200`:

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

Las fechas van en ISO 8601 con la zona horaria de RD (`-04:00`). `ultima_consulta_dgii` es `null` si aún no se consultó.

Respuesta `404` (el comprobante no se ha registrado):

```json
{"registrado": false}
```

#### Valores de `estado`

| Estado | Significado |
|---|---|
| `PENDIENTE` | Registrado; la DGII todavía no ha dado un resultado. |
| `ACEPTADO` | La DGII lo aceptó. |
| `ACEPTADO_CONDICIONAL` | La DGII lo aceptó con condiciones. |
| `RECHAZADO` | La DGII lo rechazó. |
| `NO_ENCONTRADO` | La DGII no encontró el e-CF. |
| `DESCONOCIDO` | No se pudo interpretar la respuesta de la DGII. |

Mientras `seguimiento_activo` sea `true`, el sistema sigue consultando a la DGII con intervalos crecientes hasta `seguimiento_hasta`.

#### Resultados de `validacion`

Cada verificación (`estructura`, `integridad`, `vigencia`, `entidad_certificadora`, `revocacion`, `cruce`, `comprador`)
trae un `resultado` y un `detalle`:

| Resultado | Significado |
|---|---|
| `OK` | La verificación se hizo y pasó. |
| `FALLO` | La verificación se hizo y no pasó; el `detalle` dice por qué. |
| `NO_VERIFICABLE` | No se pudo comprobar (falta la XSD, no hay PDF, el servidor OCSP/CRL no respondió, no está configurado `RNC_TERPEL`, etc.). No es un fallo. |

## Configuración del núcleo de validación y seguimiento

### Base de datos

El motor y la conexión se leen de variables de entorno (por defecto `sqlite` y `./db.sqlite3`):

- `DB_ENGINE`: `sqlite` (por defecto), `postgres`, etc. El endpoint nuevo y el seguimiento exigen `postgres`.
- `DB_CONNECTION_STRING`: por ejemplo `postgresql://validador:CLAVE@postgres:5432/validador`.
- `POSTGRES_PASSWORD`: clave del servicio `postgres` de `docker-compose.yml`; se define en el archivo `.env` (ver `.env.example`). Como `docker-compose.yml` la inserta sin codificar en `DB_CONNECTION_STRING`, debe usar solo letras, dígitos, `-`, `_` y `.` (caracteres como `@`, `:`, `/`, `?`, `#` o `%` rompen la URL de conexión).

Con PostgreSQL, la bitácora `facturas` de los endpoints existentes (`/validar-factura-*`) también vive en Postgres.

### Parámetros (tabla `parametros`)

Si faltan o no son válidos se usa el valor por defecto y se registra un aviso en el log.

| Parámetro | Por defecto | Descripción |
|---|---|---|
| `SEGUIMIENTO_INTERVALO_INICIAL_MIN` | 60 | Minutos hasta la segunda consulta a la DGII. |
| `SEGUIMIENTO_FACTOR` | 2 | Factor por el que crece el intervalo. |
| `SEGUIMIENTO_INTERVALO_MAX_MIN` | 1440 | Intervalo máximo entre consultas, en minutos. |
| `SEGUIMIENTO_DURACION_MAX_HORAS` | 72 | Duración máxima del seguimiento. |
| `SEGUIMIENTO_CICLO_SEG` | 300 | Cada cuántos segundos el worker busca comprobantes por consultar. |
| `RNC_TERPEL` | vacío | RNC esperado del comprador; vacío = la verificación `comprador` da `NO_VERIFICABLE`. |
| `CA_CONFIANZA_DIR` | `src/common/ecf/confianza/` | Carpeta con los certificados de las entidades certificadoras de confianza. |

### Agregar una entidad certificadora

Hoy se confía en las tres entidades que la DGII indica como emisoras de certificados para e-CF:
Viafirma, Digifirma (Cámara de Comercio y Producción de Santo Domingo) y Novofirma (Novosit).
El detalle y la fuente están en `src/common/ecf/confianza/FUENTE.md`. Si la DGII agrega otra:

1. Obtener el certificado (formato PEM o DER) de la entidad certificadora dominicana que emite los certificados de firma (el intermedio dominicano, no una raíz extranjera compartida) desde una fuente oficial.
2. Guardarlo en `src/common/ecf/confianza/` (o en la carpeta de `CA_CONFIANZA_DIR`) como `<entidad>.pem`.
3. Anotar en `src/common/ecf/confianza/FUENTE.md` el sujeto, el SHA-256, la fuente y la fecha de descarga.

Cada certificado de la carpeta es un ancla que se compara por huella SHA-256 exacta, nunca por nombre.

### Instalar las XSD oficiales de la DGII

Las 10 XSD oficiales (tipos 31, 32, 33, 34, 41, 43, 44, 45, 46 y 47) están instaladas en `src/common/ecf/xsd/`
como `e-CF-<tipo>.xsd` (descargadas el 2026-11-11). La del tipo 31 lleva una corrección mínima porque la publicada
no compila. Para actualizarlas, descargarlas con un navegador desde el sitio de la DGII y reemplazar los archivos;
sin la XSD de un tipo, la verificación `estructura` de ese tipo da `NO_VERIFICABLE`.
Las instrucciones completas, incluido el manejo de esquemas importados, están en `src/common/ecf/xsd/FUENTE.md`.

## Despliegue en producción (illuminatis-vps)

El VPS corre el repo en `/root/apps/validador-documentos-fiscales` con un `.env` local (no versionado) que define
`POSTGRES_PASSWORD` y `API_KEYS`. El override `docker-compose.prod.yml` deja el backend solo en `127.0.0.1:7000`
y lo une a la red `lab-router_default`, desde donde Traefik lo publica por HTTPS (`http://validador-backend:8000`).

```bash
ssh root@illuminatis-vps 'cd /root/apps/validador-documentos-fiscales && git pull --ff-only origin main   && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build'
```

## Ejemplos de consumo

### Python (requests)
```python
import requests

url = "http://localhost:7000/validar-pdf"
headers = {"x-api-key": "TU_API_KEY"}
files = {"file": open("factura.pdf", "rb")}
data = {"rnc_emisor": "123456789"}

response = requests.post(url, headers=headers, files=files, data=data)
print(response.json())
```

### Node.js (axios)
```javascript
const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');

const form = new FormData();
form.append('rnc_emisor', '123456789');
form.append('file', fs.createReadStream('factura.pdf'));

axios.post('http://localhost:7000/validar-pdf', form, {
   headers: {
      ...form.getHeaders(),
      'x-api-key': 'TU_API_KEY'
   }
})
.then(res => {
   console.log(res.data);
})
.catch(err => {
   console.error(err.response ? err.response.data : err.message);
});
```

### C# (HttpClient)
```csharp
using System.Net.Http;
using System.Net.Http.Headers;
using System.Threading.Tasks;

var client = new HttpClient();
client.DefaultRequestHeaders.Add("x-api-key", "TU_API_KEY");

var form = new MultipartFormDataContent();
form.Add(new StringContent("123456789"), "rnc_emisor");
form.Add(new StreamContent(File.OpenRead("factura.pdf")), "file", "factura.pdf");

var response = await client.PostAsync("http://localhost:7000/validar-pdf", form);
string result = await response.Content.ReadAsStringAsync();
Console.WriteLine(result);
```

## Otros endpoints

- `GET /facturas/`: Lista todas las facturas validadas.
- `GET /parametros/`: Lista parámetros de configuración.

## Notas
- Si el RNC proporcionado no coincide con el del PDF, el campo `estado` será `"rnc-no-coincide"`.
- El API requiere autenticación por API Key.

---

¿Dudas? Contacta al equipo de desarrollo.
