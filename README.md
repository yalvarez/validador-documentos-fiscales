# Validador de Documentos Fiscales

Este proyecto detecta correos con facturas, descarga adjuntos (PDF y XML), extrae la URL de consulta desde el QR del PDF, realiza web scraping o consulta API para validar el comprobante fiscal y registra los resultados.

## Estructura
- `src/email_monitor`: Monitoreo de correos
- `src/attachment_handler`: Descarga de adjuntos
- `src/pdf_processor`: Procesamiento de PDF y QR
- `src/xml_processor`: Procesamiento de XML
- `src/validator`: Validación de comprobante
- `src/logger`: Registro/log

## Instalación
1. Instala dependencias:
   ```bash
   pip install -r requirements.txt
   ```
2. Configura los datos de acceso al correo y parámetros de validación.

## Uso
Próximamente se agregará el script principal y ejemplos de uso.
