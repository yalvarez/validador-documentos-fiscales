
def build_api_params_from_attachments(attachments: list) -> dict:
    """
    Recibe una lista de adjuntos (Attachment de O365 o email.message.Message),
    guarda temporalmente el PDF y el XML, y extrae los parámetros para la consulta API.
    """
    import tempfile
    import os
    from ..xml_processor.parser import extract_api_params_from_xml
    from ..pdf_processor.extractor import PDFProcessor

    xml_path, pdf_path = None, None
    for att in attachments:
        filename = att.name.lower() if hasattr(att, 'name') else att.get_filename().lower()
        suffix = os.path.splitext(filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            if hasattr(att, 'content'):  # O365
                tmp.write(att.content)
            else:  # email.message.Message
                tmp.write(att.get_payload(decode=True))
            tmp.flush()
            if filename.endswith('.xml'):
                xml_path = tmp.name
            elif filename.endswith('.pdf'):
                pdf_path = tmp.name

    #if not xml_path or not pdf_path:
    #    return {}
    #params_xml = extract_api_params_from_xml(xml_path)
    pdf_proc = PDFProcessor(pdf_path)
    params_qr = pdf_proc.extract_qr_params()
    params = {**params_qr}
    #params = {**params_xml, **params_qr}

    # Limpieza de archivos temporales
    try:
        #os.remove(xml_path)
        os.remove(pdf_path)
    except Exception:
        pass
    return params
import requests
from bs4 import BeautifulSoup

class WebValidator:
    def __init__(self):
        pass

    def validate(self, qr_url: str) -> dict:
        resp = requests.get(qr_url)
        razon_social_emisor = None
        estado = None
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            for th in soup.find_all('th'):
                th_text = th.get_text(strip=True).lower()
                if th_text == 'razón social emisor':
                    td = th.find_next_sibling('td')
                    if td:
                        razon_social_emisor = td.get_text(strip=True)
                if th_text == 'estado':
                    td = th.find_next_sibling('td')
                    if td:
                        estado = td.get_text(strip=True)
            return {'estado': estado or 'No encontrado', 'razon_social_emisor': razon_social_emisor}
        else:
            return {'estado': f'Error HTTP: {resp.status_code}', 'razon_social_emisor': None}