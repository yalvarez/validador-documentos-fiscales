
def build_api_params_from_attachments(attachments: list) -> dict:
    """
    Recibe una lista de adjuntos (Attachment de O365 o email.message.Message),
    guarda temporalmente el PDF y el XML, y extrae los parámetros para la consulta API.
    """
    import tempfile
    import os
    from xml_processor.parser import extract_api_params_from_xml
    from pdf_processor.extractor import PDFProcessor

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

    if not xml_path or not pdf_path:
        return {}
    params_xml = extract_api_params_from_xml(xml_path)
    pdf_proc = PDFProcessor(pdf_path)
    params_qr = pdf_proc.extract_qr_params()
    params = {**params_xml, **params_qr}

    # Limpieza de archivos temporales
    try:
        os.remove(xml_path)
        os.remove(pdf_path)
    except Exception:
        pass
    return params
import requests
from bs4 import BeautifulSoup


class WebValidator:
    def __init__(self, ambiente: str, rncemisor: str, ncfelectronico: str, rnccomprador: str = '', codigoseguridad: str = '', token: str = None):
        self.ambiente = ambiente  # 'testecf' o 'produccionecf'
        self.rncemisor = rncemisor
        self.ncfelectronico = ncfelectronico
        self.rnccomprador = rnccomprador
        self.codigoseguridad = codigoseguridad
        self.token = token  # Token JWT si es requerido

    def validate(self) -> dict:
        base_url = f"https://ecf.dgii.gov.do/{self.ambiente}/consultaestado/api/consultas/estado"
        params = {
            'rncemisor': self.rncemisor,
            'ncfelectronico': self.ncfelectronico,
        }
        if self.rnccomprador:
            params['rnccomprador'] = self.rnccomprador
        if self.codigoseguridad:
            params['codigoseguridad'] = self.codigoseguridad

        headers = {'accept': 'application/json'}
        if self.token:
            headers['Authorization'] = f'bearer {self.token}'

        resp = requests.get(base_url, params=params, headers=headers)
        if resp.status_code == 200:
            try:
                return resp.json()
            except Exception:
                return {'codigo': -1, 'estado': 'Respuesta no JSON', 'detalle': resp.text}
        else:
            return {'codigo': resp.status_code, 'estado': 'Error HTTP', 'detalle': resp.text}
