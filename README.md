
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
