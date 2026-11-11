import re
from pathlib import Path

from lxml import etree

from common.ecf.lectura import ErrorLecturaECF, normalizar_xml_bytes, parsear_ecf
from common.ecf.modelos import FALLO, NO_VERIFICABLE, OK, Verificacion

XSD_DIR = Path(__file__).parents[1] / 'xsd'
NS_DSIG = 'http://www.w3.org/2000/09/xmldsig#'
_NS_XSD = {'xs': 'http://www.w3.org/2001/XMLSchema'}
_SCHEMA_EXTERNO = re.compile(r'^[A-Za-z][A-Za-z0-9+.-]*:')

# (ruta del XSD, st_mtime_ns) -> (esquema, el XSD declara ds:Signature)
_ESQUEMAS: dict[tuple[Path, int], tuple[etree.XMLSchema, bool]] = {}


class _XsdExterna(Exception):
    pass


def _declara_firma(doc) -> bool:
    raiz = doc.getroot()
    for el in doc.xpath('//xs:element[@ref]', namespaces=_NS_XSD):
        prefijo, _, local = el.get('ref').rpartition(':')
        if local == 'Signature' and el.nsmap.get(prefijo or None) == NS_DSIG:
            return True
    if raiz.get('targetNamespace') == NS_DSIG:
        return bool(doc.xpath('/xs:schema/xs:element[@name="Signature"]', namespaces=_NS_XSD))
    # XSD oficiales de la DGII: la firma ocupa un <xs:any> obligatorio al final de la secuencia de ECF.
    ultimo = doc.xpath('/xs:schema/xs:element[@name="ECF"]/xs:complexType/xs:sequence/*[last()]',
                       namespaces=_NS_XSD)
    return bool(ultimo) and ultimo[0].tag == '{%s}any' % _NS_XSD['xs']


def _revisar_referencias(ruta: Path, base: Path, visitados: set[Path]) -> None:
    """Rechaza import/include/redefine que apunten fuera de `base` (URL, ruta absoluta, '..')."""
    ruta = ruta.resolve()
    if ruta in visitados:
        return
    visitados.add(ruta)
    parser = etree.XMLParser(no_network=True, resolve_entities=False, load_dtd=False)
    doc = etree.parse(str(ruta), parser)
    for el in doc.xpath('//xs:import[@schemaLocation] | //xs:include[@schemaLocation]'
                        ' | //xs:redefine[@schemaLocation]', namespaces=_NS_XSD):
        valor = el.get('schemaLocation')
        if _SCHEMA_EXTERNO.match(valor) or valor.startswith(('/', '\\')) or Path(valor).is_absolute():
            raise _XsdExterna(valor)
        destino = (ruta.parent / valor).resolve()
        if not destino.is_relative_to(base):
            raise _XsdExterna(valor)
        if destino.is_file():
            _revisar_referencias(destino, base, visitados)


def _cargar_esquema(ruta: Path, base: Path):
    clave = (ruta.resolve(), ruta.stat().st_mtime_ns)
    if clave not in _ESQUEMAS:
        _revisar_referencias(ruta, base.resolve(), set())
        parser = etree.XMLParser(no_network=True, resolve_entities=False, load_dtd=False)
        doc = etree.parse(str(ruta), parser)
        _ESQUEMAS[clave] = (etree.XMLSchema(doc), _declara_firma(doc))
    return _ESQUEMAS[clave]


def _sin_firma(raiz):
    """Copia sin la ds:Signature envuelta hija de la raíz. None si hay firmas en otra posición."""
    copia = etree.fromstring(etree.tostring(raiz))
    firmas = copia.xpath('//ds:Signature', namespaces={'ds': NS_DSIG})
    if copia.tag == '{%s}Signature' % NS_DSIG or len(firmas) > 1 \
            or any(f.getparent() is not copia for f in firmas):
        return None
    for nodo in firmas:
        previo = nodo.getprevious()
        if nodo.tail:
            if previo is not None:
                previo.tail = (previo.tail or '') + nodo.tail
            else:
                copia.text = (copia.text or '') + nodo.tail
        copia.remove(nodo)
    return copia


def verificar_estructura(xml_bytes: bytes, tipo_ecf: str | None, xsd_dir: Path = XSD_DIR) -> Verificacion:
    xml_bytes = normalizar_xml_bytes(xml_bytes)
    if not tipo_ecf:
        return Verificacion(NO_VERIFICABLE, 'No se pudo determinar el tipo de e-CF')
    if not re.fullmatch(r'\d{2}', tipo_ecf, re.ASCII):
        return Verificacion(NO_VERIFICABLE, f'Tipo de e-CF no válido: {tipo_ecf!r}')
    ruta = Path(xsd_dir) / f'e-CF-{tipo_ecf}.xsd'
    if not ruta.is_file():
        return Verificacion(NO_VERIFICABLE, f'No hay XSD instalada para el tipo {tipo_ecf}')
    try:
        esquema, declara_firma = _cargar_esquema(ruta, Path(xsd_dir))
    except _XsdExterna as e:
        return Verificacion(NO_VERIFICABLE, f'La XSD referencia esquemas externos: {e}; descárguelos a la carpeta xsd')
    except (etree.XMLSyntaxError, etree.XMLSchemaParseError, OSError) as e:
        return Verificacion(NO_VERIFICABLE, f'No se pudo cargar la XSD del tipo {tipo_ecf}: {e}')
    try:
        raiz = parsear_ecf(xml_bytes)
    except ErrorLecturaECF as e:
        return Verificacion(FALLO, str(e))
    sin_firma = _sin_firma(raiz)
    if sin_firma is None:
        return Verificacion(FALLO, 'Firma en posición no permitida')
    if not declara_firma:
        raiz = sin_firma
    if esquema.validate(raiz):
        return Verificacion(OK, f'Cumple la XSD del e-CF tipo {tipo_ecf}')
    errores = '; '.join(f'línea {e.line}: {e.message}' for e in esquema.error_log)
    return Verificacion(FALLO, f'No cumple la XSD del e-CF tipo {tipo_ecf}: {errores}')
