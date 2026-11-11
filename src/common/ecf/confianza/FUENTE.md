# Certificados de confianza (anclas)

Cada certificado de esta carpeta es un ancla: se compara por huella SHA-256 exacta, nunca por nombre.

## Criterio

La DGII indica que las entidades que emiten los certificados para e-CF son **Viafirma, Digifirma y Novofirma**
("Solicitud Usuario Administrador de e-CF", versión final de mayo 2026, pág. 3:
https://dgii.gov.do/cicloContribuyente/facturacion/comprobantesFiscalesElectronicosE-CF/Documentacin%20sobre%20eCF/Instructivos%20sobre%20Facturaci%C3%B3n%20Electr%C3%B3nica/Solicitud%20Usuario%20Administrador%20de%20e-CF.pdf).
Se confían solo esas tres, aunque la lista general de INDOTEL
(https://indotel.gob.do/firma-digital/entidades-de-certificacion/) incluya otras. Si la DGII amplía la lista,
agregar aquí el certificado emisor dominicano de la nueva entidad y anotar su huella y fuente.

Para cada entidad se usa el emisor dominicano, no una raíz extranjera multipaís (Viafirma y Novosit cuelgan
de raíces españolas que emiten también para otros países).

## Incluidos

| Archivo | Sujeto | SHA-256 | Fuente | Vence |
|---|---|---|---|---|
| viafirma-dominicana.pem | CN=VIAFIRMA QUALIFIED CERTIFICATES, OU=VIAFIRMA DOMINICANA, O=VIAFIRMA, C=DO | c7d04abe8f58d6b59caf14670e426e60b83aa63d152ed6cfcac3a423ae876021 | https://cps.viafirma.do/viafirmaqtspsubca008.crt (AIA del certificado de la muestra) | 2033-09-08 |
| digifirma-ca-raiz.pem | CN=digifirma CA Raíz, OU=digifirma, O=Cámara de Comercio y Producción de Santo Domingo, C=DO (autofirmado) | 4f26113cb37ff08773a788dbfe409e361d80f46755b2ffd6fa61c6f4392d9bf6 | https://digi.camarasantodomingo.do/assets/documents/certificado-raiz/digifirma-ca-raiz.crt (descargado con navegador 2026-11-11) | 2046-07-26 |
| digifirma-ca-subordinada-1.pem | CN=digifirma CA Subordinada 1, OU=digifirma, O=Cámara de Comercio y Producción de Santo Domingo, C=DO (emitido por digifirma CA Raíz, pathlen 0) | 4b6c87d188e7809354f6ea965e87d7c4f8fe7fbcc0224705d569039b59086095 | https://digi.camarasantodomingo.do/assets/documents/certificado-raiz/digifirma-ca-subordinada-1.crt (descargado con navegador 2026-11-11) | 2034-07-23 |
| novosit-ca1.pem | CN=NOVOSIT CA1, OU=Entidad de Certificación de NOVOSIT, O=Novosit SRL, C=DO (emitido por UANATACA ROOT 2016, pathlen 0) | 426aec058f4926ffb7a891d9720ab38189a4b4653580e2bf95bed0e82c148243 | https://novofirma.com/img/Certificates/NOVOSIT_CA1.crt (botón "Certificado Principal Novosit" de https://novofirma.com/RootCertificate, descargado 2026-11-11) | 2033-10-16 |

- Viafirma: el ancla es el intermedio dominicano, no la raíz española `VIAFIRMA QTSP ROOT CA`.
- Digifirma (Cámara de Comercio y Producción de Santo Domingo): raíz y subordinada 1, ambas exclusivamente dominicanas.
  La subordinada permite validar sin descargar la cadena; la raíz cubre futuras subordinadas.
  Página oficial: https://digi.camarasantodomingo.do/informacion-adicional/certificados-raiz/
- Novofirma (Novosit): el ancla es `NOVOSIT CA1`. No se incluyen `UANATACA ROOT 2016` (raíz española multipaís)
  ni `NOVOSIT_TSU` (certificado de sello de tiempo, no es CA), publicados en la misma página.

## Retirados

- `digito-root-ca.pem` (Digito Root CA, SHA-256 a855459dccb649db801d52b5fdf63988e98ad3970f7c6c345116223a688896bb):
  figura en la lista de INDOTEL, pero la DGII no la nombra como emisora de certificados para e-CF. Retirado el 2026-11-11.
