import base64
import binascii
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation

from lxml import etree

from common.ecf.modelos import ZONA_RD


class ErrorLecturaECF(Exception):
    """XML mal formado, o sin RNCEmisor o eNCF."""


def normalizar_xml_bytes(b: bytes) -> bytes:
    return b.removeprefix(b'\xef\xbb\xbf').strip()


def parsear_ecf(xml_bytes: bytes):
    """Parsea el XML (bytes normalizados); rechaza DTD y entidades. Devuelve la raíz."""
    try:
        parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
        raiz = etree.fromstring(normalizar_xml_bytes(xml_bytes), parser)
    except (etree.XMLSyntaxError, ValueError) as e:
        raise ErrorLecturaECF(f'XML mal formado: {e}') from e
    info = raiz.getroottree().docinfo
    if info.doctype or info.internalDTD is not None or any(True for _ in raiz.iter(etree.Entity)):
        raise ErrorLecturaECF('El XML contiene DTD o entidades, no permitido')
    return raiz


@dataclass
class DatosECF:
    rnc_emisor: str
    encf: str
    rnc_comprador: str | None = None
    tipo_ecf: str | None = None
    fecha_emision_texto: str | None = None
    monto_total: Decimal | None = None
    fecha_firma_texto: str | None = None
    fecha_firma: datetime | None = None
    razon_social_emisor: str | None = None
    signature_value: str | None = None
    codigo_seguridad: str | None = None
    certificados_der: list[bytes] = field(default_factory=list)


_SIN_FIRMA = "[not(ancestor::*[local-name()='Signature'])]"
_NS = {'ds': 'http://www.w3.org/2000/09/xmldsig#'}
_RUTA_FIRMA = 'ds:Signature[1]'  # hija directa de la raíz, en el namespace dsig
_RUTA_CERTS = f'{_RUTA_FIRMA}/ds:KeyInfo/ds:X509Data/ds:X509Certificate'


def texto_completo(nodo) -> str:
    """Texto completo del elemento; los comentarios y PI no lo truncan (no los cubre la firma)."""
    return ''.join(nodo.xpath('.//text()')).strip()


def _texto(raiz, nombre: str) -> str | None:
    """Campo de negocio: ignora todo lo que esté dentro de una Signature (no firmado)."""
    nodos = raiz.xpath(f"//*[local-name()='{nombre}']{_SIN_FIRMA}")
    if not nodos:
        return None
    return texto_completo(nodos[0]) or None


def decodificar_base64_estricto(texto: str | None) -> bytes:
    """Base64 estricto (validate=True) tras quitar espacios en blanco; vacío o inválido lanza ValueError."""
    limpio = ''.join((texto or '').split())
    if not limpio:
        raise ValueError('Base64 vacío')
    try:
        return base64.b64decode(limpio, validate=True)
    except binascii.Error as e:
        raise ValueError(f'Base64 inválido: {e}') from e


def certificados_keyinfo(raiz) -> list[bytes]:
    """DER de los X509Certificate del KeyInfo de la Signature raíz; el primero es el del firmante.

    Única fuente de verdad del certificado firmante (integridad, vigencia, entidad y revocación).
    Si el primero falta, está vacío o no es base64 válido, devuelve [] (nunca se salta al siguiente).
    Los siguientes inválidos (solo ayudan a armar la cadena) se omiten.
    """
    nodos = raiz.xpath(_RUTA_CERTS, namespaces=_NS)
    if not nodos:
        return []
    try:
        certs = [decodificar_base64_estricto(texto_completo(nodos[0]))]
    except ValueError:
        return []
    for nodo in nodos[1:]:
        try:
            certs.append(decodificar_base64_estricto(texto_completo(nodo)))
        except ValueError:
            continue
    return certs


def leer_ecf(xml_bytes: bytes) -> DatosECF:
    raiz = parsear_ecf(xml_bytes)

    rnc = _texto(raiz, 'RNCEmisor')
    encf = _texto(raiz, 'eNCF')
    if not rnc or not encf:
        raise ErrorLecturaECF('Falta RNCEmisor o eNCF')

    monto = None
    monto_txt = _texto(raiz, 'MontoTotal')
    if monto_txt:
        try:
            monto = Decimal(monto_txt)
        except InvalidOperation:
            monto = None

    fecha_firma_texto = _texto(raiz, 'FechaHoraFirma')
    fecha_firma = None
    if fecha_firma_texto:
        try:
            fecha_firma = datetime.strptime(fecha_firma_texto, '%d-%m-%Y %H:%M:%S').replace(tzinfo=ZONA_RD)
        except ValueError:
            fecha_firma = None

    # Solo la Signature hija directa de la raíz (la única que integridad acepta).
    nodos_sig = raiz.xpath(f'{_RUTA_FIRMA}/ds:SignatureValue', namespaces=_NS)
    sig = texto_completo(nodos_sig[0]) if nodos_sig else None
    sig = ''.join(sig.split()) if sig else None

    certs = certificados_keyinfo(raiz)

    return DatosECF(
        rnc_emisor=rnc.strip().upper(),
        encf=encf.strip().upper(),
        rnc_comprador=_texto(raiz, 'RNCComprador'),
        tipo_ecf=_texto(raiz, 'TipoeCF'),
        fecha_emision_texto=_texto(raiz, 'FechaEmision'),
        monto_total=monto,
        fecha_firma_texto=fecha_firma_texto,
        fecha_firma=fecha_firma,
        razon_social_emisor=_texto(raiz, 'RazonSocialEmisor'),
        signature_value=sig,
        codigo_seguridad=sig[:6] if sig else None,
        certificados_der=certs,
    )
