# API de Validación de Facturas

Este servicio expone endpoints para validar facturas electrónicas a partir de archivos PDF (enviado como archivo o base64) o mediante parámetros extraídos del comprobante.

---

## 1. Validar PDF (multipart)

**POST** `/validar-pdf`

- **Headers:**  
  `x-api-key: <API_KEY>`

- **Body (form-data):**
  - `file`: PDF a validar (tipo archivo)
  - `rnc_emisor` (opcional): RNC del emisor para validación cruzada

- **Respuesta:**
```json
{
  "rnc_emisor": "string",
  "razon_social_emisor": "string",
  "estado": "string"
}
```

---

## 2. Validar PDF en Base64

**POST** `/validar-pdf-base64`

- **Headers:**  
  `x-api-key: <API_KEY>`

- **Body (JSON):**
```json
{
  "pdf_base64": "string (PDF codificado en base64)",
  "rnc_emisor": "string (opcional)"
}
```

- **Respuesta:**
```json
{
  "rnc_emisor": "string",
  "razon_social_emisor": "string",
  "estado": "string"
}
```

---

## 3. Consulta por parámetros de factura

**POST** `/consulta-factura-params`

- **Headers:**  
  `x-api-key: <API_KEY>`

- **Body (JSON):**
```json
{
  "RncEmisor": "string",
  "RncComprador": "string (opcional)",
  "ENCF": "string",
  "FechaEmision": "string (opcional)",
  "MontoTotal": "string (opcional)",
  "FechaFirma": "string (opcional)",
  "CodigoSeguridad": "string (opcional)"
}
```

- **Respuesta:**
```json
{
  "rnc_emisor": "string",
  "razon_social_emisor": "string",
  "estado": "string"
}
```

---

## Notas
- Todos los endpoints requieren el header `x-api-key`.
- El campo `estado` puede indicar el resultado de la validación (ej: válido, inválido, rnc-no-coincide, etc).
- Para el endpoint base64, el PDF debe ser codificado en base64 estándar.

---

¿Dudas o problemas? Contacta al equipo de desarrollo.
