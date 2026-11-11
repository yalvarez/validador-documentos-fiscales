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
_RUTA_CERTS = ("*[local-name()='Signature'][1]/*[local-name()='KeyInfo']"
               "/*[local-name()='X509Data']/*[local-name()='X509Certificate']")


def _texto(raiz, nombre: str) -> str | None:
    """Campo de negocio: ignora todo lo que esté dentro de una Signature (no firmado)."""
    nodos = raiz.xpath(f"//*[local-name()='{nombre}']{_SIN_FIRMA}")
    if not nodos or nodos[0].text is None:
        return None
    t = nodos[0].text.strip()
    return t or None


def leer_ecf(xml_bytes: bytes) -> DatosECF:
    try:
        parser = etree.XMLParser(resolve_entities=False, no_network=True)
        raiz = etree.fromstring(normalizar_xml_bytes(xml_bytes), parser)
    except (etree.XMLSyntaxError, ValueError) as e:
        raise ErrorLecturaECF(f'XML mal formado: {e}') from e

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
    nodos_sig = raiz.xpath("*[local-name()='Signature'][1]/*[local-name()='SignatureValue']")
    sig = (nodos_sig[0].text or '').strip() if nodos_sig else None
    sig = ''.join(sig.split()) if sig else None

    certs = []
    for nodo in raiz.xpath(_RUTA_CERTS):
        try:
            certs.append(base64.b64decode(''.join((nodo.text or '').split()), validate=True))
        except (binascii.Error, ValueError):
            continue

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
