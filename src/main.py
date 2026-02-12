from reportes import validar_ncf_por_url
# main.py
"""
Script principal para el validador de documentos fiscales.
"""


from email_monitor.monitor import EmailMonitor
from attachment_handler.handler import AttachmentHandler
from pdf_processor.extractor import PDFProcessor
import os
from xml_processor.parser import XMLProcessor
from validator.web_validator import WebValidator, build_api_params_from_attachments

from logger.logger import setup_logger
from logger.db_logger import DBLogger

import logging
import time
from dotenv import load_dotenv
import time
from dotenv import load_dotenv
load_dotenv()

def main():

    # Configuración para pruebas con Gmail
    EMAIL_PROVIDER = os.getenv('EMAIL_PROVIDER', 'gmail')
    EMAIL_USER = os.getenv('EMAIL_USER', 'tu_email@gmail.com')
    EMAIL_PASS = os.getenv('EMAIL_PASS', 'tu_app_password')

    logger = setup_logger()
    db_logger = DBLogger()
    email_monitor = EmailMonitor(EMAIL_PROVIDER, EMAIL_USER, EMAIL_PASS)
    att_handler = AttachmentHandler()

    logger.info('Iniciando monitor de correo...')

    while True:
        logger.info('Revisando bandeja de entrada...')
        messages = email_monitor.get_unread_inbox_messages()
        logger.info(f'Se encontraron {len(messages)} correos no leídos.')
        for msg in messages:
            logger.info(f'Leyendo correo: subject={msg.get("subject")}, from={msg.get("from")}, id={msg.get("id")}, date={msg.get("date")}.')
            # Deduplicación por message_id
            if db_logger.is_message_processed(msg['id']):
                logger.info(f'Correo ya procesado: {msg["subject"]}')
                email_monitor.mark_as_read(msg['id'])
                continue
            logger.info(f'Procesando correo: {msg["subject"]}')

            # Extraer adjuntos del mensaje (email.message.Message)
            attachments = []
            if hasattr(msg['raw'], 'walk'):
                for part in msg['raw'].walk():
                    if part.get_content_maintype() == 'multipart':
                        continue
                    filename = part.get_filename()
                    logger.info(f'Encontrado adjunto: {filename}')
                    if filename and (filename.lower().endswith('.pdf') or filename.lower().endswith('.xml')):
                        attachments.append(part)

            logger.info(f'Cantidad de adjuntos PDF/XML encontrados: {len(attachments)}')
            if not attachments:
                logger.warning('Correo ignorado: no se encontraron adjuntos PDF o XML.')
                email_monitor.mark_as_read(msg['id'])
                continue


            # Extraer parámetros para la consulta API desde los adjuntos
            from pdf_processor.extractor import PDFProcessor
            pdf_part = next((a for a in attachments if a.get_filename() and a.get_filename().lower().endswith('.pdf')), None)
            pdf_params = {}
            qr_url = None
            if pdf_part:
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_pdf:
                    tmp_pdf.write(pdf_part.get_payload(decode=True))
                    tmp_pdf.flush()
                    pdf_proc = PDFProcessor(tmp_pdf.name)
                    # Guardar imagen del QR extraído en un archivo temporal
                    qr_img_path = tmp_pdf.name.replace('.pdf', '_qr.png')
                    qr_url = pdf_proc.extract_qr_url(save_qr_image=True, qr_image_path=qr_img_path, logger=logger)
                    if qr_url:
                        logger.info(f'URL extraída del QR en PDF: {qr_url} (longitud: {len(qr_url)})')
                        if os.path.exists(qr_img_path):
                            logger.info(f'Imagen del QR extraído guardada en: {qr_img_path}')
                    else:
                        logger.warning('No se pudo extraer la URL del QR en el PDF.')
                    pdf_params = pdf_proc.extract_qr_params()
                    logger.info(f'Parámetros extraídos del QR en PDF: {pdf_params}')


            # Normalizar claves a minúsculas para evitar problemas de mayúsculas/minúsculas
            api_params = {k.lower(): v for k, v in build_api_params_from_attachments(attachments).items()}
            logger.info(f'Parámetros extraídos de adjuntos (XML+PDF): {api_params}')
            if not api_params.get('rncemisor') or not api_params.get('ncfelectronico') or not api_params.get('codigoseguridad'):
                logger.warning('Correo ignorado: faltan datos requeridos para la validación.')
                email_monitor.mark_as_read(msg['id'])
                continue

            # Construir la URL de consulta web
            url = (
                f"https://ecf.dgii.gov.do/eCF/ConsultaTimbre?"
                f"RncEmisor={api_params.get('rncemisor')}"
                f"&RncComprador={api_params.get('rnccomprador','')}"
                f"&ENCF={api_params.get('ncfelectronico')}"
                f"&CodigoSeguridad={api_params.get('codigoseguridad')}"
            )
            logger.info(f'Consultando web DGII: {url}')
            resultado_json = validar_ncf_por_url(url)
            logger.info(f'Resultado de validación web: {resultado_json}')

            # Registrar en base de datos (puedes ajustar los campos según tu modelo)
            # Extraer el estado del JSON de validación web
            import json
            estado_web = json.loads(resultado_json).get('estado')
            db_logger.log_validacion(
                message_id=msg['id'],
                subject=msg['subject'],
                sender=msg['from'],
                pdf_path=None,
                xml_path=None,
                qr_url=None,
                resultado=str(estado_web)
            )

            # Marcar correo como leído
            logger.info(f'Marcando correo como leído: {msg["id"]}')
            email_monitor.mark_as_read(msg['id'])
        logger.info('Ciclo de revisión finalizado. Esperando para la próxima revisión...')
        time.sleep(60)

if __name__ == "__main__":
    main()
