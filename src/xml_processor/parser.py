def extract_api_params_from_xml(xml_path: str) -> dict:
    """
    Extrae los parámetros requeridos para la consulta API desde el XML.
    """
    proc = XMLProcessor(xml_path)
    data = proc.parse()
    enc = data.get('ECF', {}).get('Encabezado', {})
    emisor = enc.get('Emisor', {})
    comprador = enc.get('Comprador', {})
    iddoc = enc.get('IdDoc', {})
    return {
        'rncemisor': emisor.get('RNCEmisor', ''),
        'ncfelectronico': iddoc.get('eNCF', ''),
        'rnccomprador': comprador.get('RNCComprador', ''),
    }
import xmltodict

class XMLProcessor:
    def __init__(self, xml_path):
        self.xml_path = xml_path

    def parse(self):
        with open(self.xml_path, 'r', encoding='utf-8') as f:
            data = xmltodict.parse(f.read())
        return data
