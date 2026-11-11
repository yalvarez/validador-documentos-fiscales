# Fixtures de la DGII

Capturadas el 2026-11-10 con `curl`/`requests` (sin cabeceras especiales) contra
`https://ecf.dgii.gov.do/eCF/ConsultaTimbre`.

- `aceptado.html`: URL del QR de la muestra
  `?RncEmisor=101616202&RncComprador=101107146&ENCF=E310000002882&FechaEmision=10-02-2026&MontoTotal=1250.00&FechaFirma=10-02-2026%2009%3A22%3A21&CodigoSeguridad=BuLkvC`.
  Tabla `th`/`td` con `Estado => Aceptado`, `Razón social emisor => EMPRESAS ASAVIM S R L`, `Monto Total => 1,250`.
  La página codifica los acentos como entidades (`Raz&#xF3;n`).
- `no_encontrado.html`: misma URL con `ENCF=E319999999999` y `CodigoSeguridad=AAAAAA`. HTTP 200 con
  `<td colspan="2">No fue encontrada la factura (e-CF).</td>`.
- No se capturó variante FC (`ConsultaTimbreFC`, tipo 32 menor a 250 mil).

## Codificación de la URL

La DGII acepta `FechaFirma` con los dos puntos codificados (`%3A`) y el espacio como `%20`
(HTTP 200 con la tabla de datos), por eso se usa `urlencode(..., quote_via=quote)`.

## Textos de estado

Solo "Aceptado" y el marcador de no encontrado se observaron en vivo. "Aceptado Condicional",
"Rechazado" y "En Proceso" son los textos esperados según la documentación y no se verificaron
contra la página; cualquier otro texto se mapea a `DESCONOCIDO` con un aviso en el log.
