import os
import time
import json
import tempfile
from dotenv import load_dotenv
from api.parametros_manager import ParametrosManager
from db.db_factory import get_db_wrapper
from email_watcher.email_monitor.monitor import EmailMonitor
from email_watcher.attachment_handler.handler import AttachmentHandler
from email_watcher.logger.logger import setup_logger


def get_db_config_from_env():
    db_engine = os.getenv('DB_ENGINE', 'sqlite')
    db_conn_str = os.getenv('DB_CONNECTION_STRING', './db.sqlite3')
    if db_engine == 'sqlite':
        return db_engine, {'db_path': db_conn_str}
    elif db_engine == 'mysql':
        return db_engine, db_conn_str
    elif db_engine == 'sqlserver':
        return db_engine, db_conn_str
    else:
        raise ValueError('DB_ENGINE no soportado')



def main():
    db_type, db_config = get_db_config_from_env()
    from email_watcher.logger.db_logger import DBLogger
    db = DBLogger(db_type, db_config)
    parametros = ParametrosManager(db.db)

    EMAIL_PROVIDER = parametros.get('EMAIL_PROVIDER', '')
    EMAIL_USER = parametros.get('EMAIL_USER', '')
    EMAIL_PASS = parametros.get('EMAIL_PASS', '')
    
    email_monitor = EmailMonitor(EMAIL_PROVIDER, EMAIL_USER, EMAIL_PASS)    
    logger = setup_logger()
    logger.info('Iniciando watcher de correo...')
    
    while True:
        logger.info('Revisando bandeja de entrada...')
        messages = email_monitor.get_unread_inbox_messages()
        logger.info(f'Se encontraron {len(messages)} correos no leídos.')
        for msg in messages:
            logger.info(f'Leyendo correo: subject={msg.get("subject")}, from={msg.get("from")}, id={msg.get("id")}, date={msg.get("date")}.')
            if db.is_message_processed(msg['id']):
                logger.info(f'Correo ya procesado: {msg["subject"]}')
                email_monitor.mark_as_read(msg['id'])
                continue
            logger.info(f'Procesando correo: {msg["subject"]}')
            db.insert_mensaje(str(msg['id']), str(msg['from']), str(msg['subject']))
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
            from email_watcher.pdf_processor.extractor import PDFProcessor
            pdf_part = next((a for a in attachments if a.get_filename() and a.get_filename().lower().endswith('.pdf')), None)
            pdf_params = {}
            qr_url = None
            if pdf_part:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_pdf:
                    tmp_pdf.write(pdf_part.get_payload(decode=True))
                    tmp_pdf.flush()
                    pdf_proc = PDFProcessor(tmp_pdf.name)
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
            #xml_part = next((a for a in attachments if a.get_filename() and a.get_filename().lower().endswith('.xml')), None)
            #xml_params = {}
            #if xml_part:
            #    with tempfile.NamedTemporaryFile(delete=False, suffix='.xml') as tmp_xml:
            #        tmp_xml.write(xml_part.get_payload(decode=True))
            #        tmp_xml.flush()
            #        from email_watcher.xml_processor.parser import XMLProcessor
            #        xml_proc = XMLProcessor(tmp_xml.name)
            #        xml_params = xml_proc.extract_params()
            #        logger.info(f'Parámetros extraídos del XML: {xml_params}')
            #factura_json = {**pdf_params, **xml_params}
            factura_json = {**pdf_params}
            # Asegura que message_id y url_validacion estén presentes para el insert
            factura_json['message_id'] = str(msg['id'])
            factura_json['url_validacion'] = qr_url
            estado_web = None
            razon_social_emisor = None
            if qr_url:
                from email_watcher.validator.web_validator import WebValidator
                web_validator = WebValidator()
                web_result = web_validator.validate(qr_url)
                if isinstance(web_result, dict):
                    estado_web = web_result.get('estado')
                    razon_social_emisor = web_result.get('razon_social_emisor')
                else:
                    estado_web = web_result
                logger.info(f'Estado web validado: {estado_web}, Razón social emisor: {razon_social_emisor}')

            if factura_json.get('RncEmisor') and factura_json.get('ENCF') and factura_json.get('CodigoSeguridad'):
                if razon_social_emisor:
                    factura_json['razon_social_emisor'] = razon_social_emisor
                logger.info(f'Insertando factura consolidada: {json.dumps(factura_json, ensure_ascii=False, indent=2)}')
                db.insert_factura(factura_json, str(estado_web) if estado_web is not None else None)
                db.update_factura_estado(msg['id'], 'validado')
            
            WEBHOOK_URL = parametros.get('WEBHOOK_URL')
            
            if factura_json.get('rncemisor') and factura_json.get('ncfelectronico') and factura_json.get('codigoseguridad'):
                if estado_web and str(estado_web).strip().lower() == 'aceptado' and WEBHOOK_URL:
                    import requests
                    try:
                        resp = requests.post(WEBHOOK_URL, json=factura_json, timeout=10)
                        logger.info(f'Webhook enviado. Status: {resp.status_code}, Response: {resp.text}')
                        db.update_factura_envio(msg['id'], 'EXITOSO', None)
                    except Exception as e:
                        logger.error(f'Error enviando al webhook: {e}')
                        db.update_factura_envio(msg['id'], 'FALLIDO', str(e))
                else:
                    db.update_factura_envio(msg['id'], 'NO ENVIADO', None)
            logger.info(f'Marcando correo como leído: {msg["id"]}')
            email_monitor.mark_as_read(msg['id'])
        logger.info('Ciclo de revisión finalizado. Esperando para la próxima revisión...')
        time.sleep(60)

if __name__ == "__main__":
    main()