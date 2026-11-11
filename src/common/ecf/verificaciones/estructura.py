import re
from pathlib import Path

from lxml import etree

from common.ecf.lectura import ErrorLecturaECF, normalizar_xml_bytes, parsear_ecf
from common.ecf.modelos import FALLO, NO_VERIFICABLE, OK, Verificacion

XSD_DIR = Path(__file__).parents[1] / 'xsd'
NS_DSIG = 'http://www.w3.org/2000/09/xmldsig#'
_NS_XSD = {'xs': 'http://www.w3.org/2001/XMLSchema'}
_TIPO_VALIDO = re.compile(r'^\d{2}$')

# (ruta del XSD) -> (esquema, el XSD declara ds:Signature)
_ESQUEMAS: dict[Path, tuple[etree.XMLSchema, bool]] = {}


def _declara_firma(doc) -> bool:
    return bool(doc.xpath(
        f"//xs:element[@name='Signature' or @ref[substring-after(., ':')='Signature']]"
        f" | //xs:import[@namespace='{NS_DSIG}']", namespaces=_NS_XSD))


def _cargar_esquema(ruta: Path):
    if ruta not in _ESQUEMAS:
        parser = etree.XMLParser(no_network=True, resolve_entities=False, load_dtd=False)
        doc = etree.parse(str(ruta), parser)
        _ESQUEMAS[ruta] = (etree.XMLSchema(doc), _declara_firma(doc))
    return _ESQUEMAS[ruta]


def _sin_firma(raiz):
    """Copia del árbol sin los nodos ds:Signature (el XSD no los declara)."""
    copia = etree.fromstring(etree.tostring(raiz))
    for nodo in copia.xpath('//ds:Signature', namespaces={'ds': NS_DSIG}):
        nodo.getparent().remove(nodo)
    return copia


def verificar_estructura(xml_bytes: bytes, tipo_ecf: str | None, xsd_dir: Path = XSD_DIR) -> Verificacion:
    xml_bytes = normalizar_xml_bytes(xml_bytes)
    if not tipo_ecf:
        return Verificacion(NO_VERIFICABLE, 'No se pudo determinar el tipo de e-CF')
    if not _TIPO_VALIDO.match(tipo_ecf):
        return Verificacion(NO_VERIFICABLE, f'Tipo de e-CF no válido: {tipo_ecf!r}')
    ruta = Path(xsd_dir) / f'e-CF-{tipo_ecf}.xsd'
    if not ruta.is_file():
        return Verificacion(NO_VERIFICABLE, f'No hay XSD instalada para el tipo {tipo_ecf}')
    try:
        esquema, declara_firma = _cargar_esquema(ruta)
    except (etree.XMLSyntaxError, etree.XMLSchemaParseError, OSError) as e:
        return Verificacion(NO_VERIFICABLE, f'No se pudo cargar la XSD del tipo {tipo_ecf}: {e}')
    try:
        raiz = parsear_ecf(xml_bytes)
    except ErrorLecturaECF as e:
        return Verificacion(FALLO, str(e))
    if not declara_firma:
        raiz = _sin_firma(raiz)
    if esquema.validate(raiz):
        return Verificacion(OK, f'Cumple la XSD del e-CF tipo {tipo_ecf}')
    errores = '; '.join(f'línea {e.line}: {e.message}' for e in esquema.error_log)
    return Verificacion(FALLO, f'No cumple la XSD del e-CF tipo {tipo_ecf}: {errores}')
