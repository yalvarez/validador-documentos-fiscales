# Certificados de confianza (anclas)

Cada certificado de esta carpeta es un ancla: se compara por huella SHA-256 exacta, nunca por nombre.
Lista oficial consultada el 2026-11-10: https://indotel.gob.do/firma-digital/entidades-de-certificacion/

## Incluidos

| Archivo | Sujeto | SHA-256 | Fuente (descargada 2026-11-10) | Vence |
|---|---|---|---|---|
| viafirma-dominicana.pem | CN=VIAFIRMA QUALIFIED CERTIFICATES, OU=VIAFIRMA DOMINICANA, O=VIAFIRMA, C=DO | c7d04abe8f58d6b59caf14670e426e60b83aa63d152ed6cfcac3a423ae876021 | https://cps.viafirma.do/viafirmaqtspsubca008.crt (AIA del certificado de la muestra) | 2033-09-08 |
| digito-root-ca.pem | CN=Digito Root CA, O=Digito Group, C=DO | a855459dccb649db801d52b5fdf63988e98ad3970f7c6c345116223a688896bb | http://pki.digito.do/CAs/DigitoRootCA.crt (enlazado en la lista INDOTEL, Digito Financial Technology Group, Res. 115-2025) | 2046-06-17 |

Viafirma: el ancla es el intermedio dominicano, no la raíz española `VIAFIRMA QTSP ROOT CA`, que emite también para otros países.

## Pendientes (no se pudo obtener un certificado emisor dominicano por descarga directa)

La lista de INDOTEL no menciona a Viafirma por nombre; entre las entidades listadas esta la descarga directa solo existe para Digito y Lleidanet.

- Lleidanet Dominicana: https://certs.esigna.es/root/ca_root_indenova_sl.crt es la raíz española `Root Indenova SL` (multipaís); falta identificar y descargar el intermedio dominicano. No se agregó la raíz.
- AVANSI (https://www.avansi.com.do/certificados), Cámara de Comercio de Santo Domingo / Digifirma (https://camarasantodomingo.do/digifirma/Certificados-Raiz.html), OGTIC (https://ca.ogtic.gob.do/ra/ogtic/), Novosit (https://novofirma.com/RootCertificate), ABA (https://firmadigital.aba.org.do/): las páginas responden HTML sin enlace directo a un .crt; hay que localizar el certificado a mano.
- Thomas Signe Copel: la lista no publica enlace de descarga.
- Revisar la vigencia de la autorización de cada entidad (varias aparecen con fecha de expiración pasada o en renovación).
