# XSD oficiales de la DGII (e-CF)

Esta carpeta debe contener las XSD oficiales, una por tipo de e-CF, con el nombre
`e-CF-<tipo>.xsd` (tipos 31, 32, 33, 34, 41, 43, 44, 45, 46 y 47).

**Estado actual: instaladas las 10 XSD oficiales (descargadas con navegador el 2026-11-11).**
Sin el archivo de un tipo, la verificación `estructura` de ese tipo devuelve `NO_VERIFICABLE`.
No se incluyen XSD escritas a mano.

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

## Instaladas (2026-11-11)

| Archivo | SHA-256 | Estado |
|---|---|---|
| e-CF-31.xsd | `58b1b93309fc982a5a5ca6dda8f6d626a3d7f12df0361035c030a881043ef1e0` | corregida (original: `6f2909a93d84919518d2ae3c77fead4b35c3e8c95996b8af67b0040c2e2be298`) |
| e-CF-32.xsd | `151676df03c61335b4ac1eca97f99395488d57ea92793b49353602871e651f3c` | sin cambios |
| e-CF-33.xsd | `087cd71beba11c19cf548e22b96363cb4aa210dc6f5c3c8a62122a42c88d2866` | sin cambios |
| e-CF-34.xsd | `6c62ebabdea9a6f6d62ae85d9e1c2eb788f44f3f0b61945fe116700c4eaac2da` | sin cambios |
| e-CF-41.xsd | `eae1993c637375bc1cbe80932411d87f5680cd54e77e4d1b2752d72a6c8b2ab3` | sin cambios |
| e-CF-43.xsd | `776f030980c2c50cf0221e9263c55f367c8631727adff00ab45e2c7c1abafc52` | sin cambios |
| e-CF-44.xsd | `19834f37a9f0e2db40f00c80d07c2bf92f9019f23474480f32cef1ba06af4e67` | sin cambios |
| e-CF-45.xsd | `030492cc8ef7d1a09a89b16b241f8e5c4920dfd09c0b629b1db8e68406ecd6ca` | sin cambios |
| e-CF-46.xsd | `e7f8613ade25c7efb88e84d34d7c0ad330d1b22238ad9ef90c80aed01911d67b` | sin cambios |
| e-CF-47.xsd | `14daf18f52f63dd80e439a18fb60a102d74e71243ee90ee253367f61ce8e1994` | sin cambios |

### Corrección aplicada a `e-CF-31.xsd`

La XSD oficial del tipo 31 no compila: en la línea 476 el tipo se define como
`name=" IndicadorServicioTodoIncluidoType"` (con un espacio inicial), y el elemento de la línea 18
lo referencia sin espacio. Se quitó solo ese espacio; el resto del archivo queda byte a byte igual.
Si la DGII publica una versión corregida, reemplazar el archivo y actualizar esta tabla.

### La firma en las XSD oficiales

Las XSD de la DGII no declaran `ds:Signature`: la secuencia de `ECF` termina en
`<xs:any processContents="skip" minOccurs="1" maxOccurs="1"/>`, que es el lugar de la firma.
Con esas XSD la verificación valida el documento **con** su firma (un e-CF sin firma no cumple la XSD),
y sigue rechazando firmas en cualquier otra posición.
