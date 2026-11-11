# XSD oficiales de la DGII (e-CF)

Esta carpeta debe contener las XSD oficiales, una por tipo de e-CF, con el nombre
`e-CF-<tipo>.xsd` (tipos 31, 32, 33, 34, 41, 43, 44, 45, 46 y 47).

**Estado actual: las XSD no están instaladas.** Sin el archivo de un tipo, la verificación
`estructura` de ese tipo devuelve `NO_VERIFICABLE`. No se incluyen XSD escritas a mano.

## Origen

Carpeta oficial (Comprobantes Fiscales Electrónicos > Documentación sobre e-CF > Documentación Técnica (XSD)):

https://www.dgii.gov.do/cicloContribuyente/facturacion/comprobantesFiscalesElectronicosE-CF/Documentacin%20sobre%20eCF/Documentaci%C3%B3n%20T%C3%A9cnica%20(XSD)/

Patrón de archivo en el sitio: `e-CF <tipo> v.1.0.xsd`.

Versiones y fechas de modificación publicadas (consultadas el 2026-11-10):

| Tipos | Versión | Modificado |
|-------|---------|------------|
| 31, 32, 41, 43, 44, 45, 46, 47 | v.1.0 | 16/10/2025 |
| 33, 34 | v.1.0 | 01/04/2026 |

## Cómo instalarlas

El sitio de la DGII responde HTTP 403 a las descargas automatizadas, así que hay que bajarlas
con un navegador y guardarlas aquí como `e-CF-<tipo>.xsd` (por ejemplo `e-CF 31 v.1.0.xsd` -> `e-CF-31.xsd`).
Al instalarlas, anotar abajo la fecha de descarga y el hash de cada archivo.

- Si la XSD **no declara `ds:Signature`**, la verificación valida una copia del XML sin la firma
  (la firma se verifica aparte en `integridad`).
- Si la XSD **importa esquemas externos** (por ejemplo xmldsig), guardarlos también en esta carpeta
  y reescribir su `schemaLocation` a rutas relativas dentro de esta carpeta. La verificación revisa los
  `import`/`include`/`redefine` y, si alguno apunta a una URL, a una ruta absoluta o fuera de esta
  carpeta, devuelve `NO_VERIFICABLE` sin cargar el esquema (libxml2 no respeta `no_network` al resolverlos).
- Con las XSD instaladas, los tests `test_muestra_valida`, `test_muestra_iso` y
  `test_falta_nodo_obligatorio` dejan de saltarse. Si la muestra no valida contra la XSD vigente,
  no aflojar la validación: reportarlo.
