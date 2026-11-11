"""Verificaciones del certificado del firmante: vigencia y entidad certificadora autorizada."""
import logging
import time
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Callable

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.x509.oid import AuthorityInformationAccessOID, ExtendedKeyUsageOID, NameOID

from common.ecf.modelos import FALLO, OK, Verificacion

logger = logging.getLogger(__name__)

_MAX_PROFUNDIDAD = 8
_EXTENSIONES_CA = ('.pem', '.crt', '.cer', '.der')

# Caché acotada de certificados descargados por la URL CA Issuers del AIA:
# url -> (certificado, instante de descarga). Se descarta la más antigua y expira a las 24 h.
_MAX_CACHE_AIA = 256
_EXPIRACION_AIA_SEG = 24 * 3600
_cache_aia: 'OrderedDict[str, tuple[x509.Certificate, float]]' = OrderedDict()
_reloj = time.monotonic


def limpiar_caches() -> None:
    _cache_aia.clear()


def _de_cache_aia(url: str) -> x509.Certificate | None:
    entrada = _cache_aia.get(url)
    if entrada is None:
        return None
    if _reloj() - entrada[1] >= _EXPIRACION_AIA_SEG:
        del _cache_aia[url]
        return None
    return entrada[0]


def _a_cache_aia(url: str, cert: x509.Certificate) -> None:
    _cache_aia.pop(url, None)
    _cache_aia[url] = (cert, _reloj())
    while len(_cache_aia) > _MAX_CACHE_AIA:
        _cache_aia.popitem(last=False)


def cargar_certificado(data: bytes) -> x509.Certificate:
    """Carga un certificado en DER o PEM."""
    if data.lstrip().startswith(b'-----BEGIN'):
        return x509.load_pem_x509_certificate(data)
    return x509.load_der_x509_certificate(data)


def _atributo(nombre: x509.Name, oid) -> str:
    atributos = nombre.get_attributes_for_oid(oid)
    return atributos[0].value if atributos else ''


def descripcion_certificado(cert: x509.Certificate) -> tuple[str, str, str]:
    """CN del titular, CN del emisor y serie en hexadecimal."""
    return (_atributo(cert.subject, NameOID.COMMON_NAME),
            _atributo(cert.issuer, NameOID.COMMON_NAME),
            format(cert.serial_number, 'x'))


def verificar_vigencia(cert: x509.Certificate | None, fecha_firma: datetime | None) -> Verificacion:
    if cert is None:
        return Verificacion(FALLO, 'Sin certificado')
    if fecha_firma is None:
        return Verificacion(FALLO, 'Sin FechaHoraFirma')
    desde, hasta = cert.not_valid_before_utc, cert.not_valid_after_utc
    rango = f'{desde:%Y-%m-%d} a {hasta:%Y-%m-%d}'
    if desde <= fecha_firma <= hasta:
        return Verificacion(OK, f'Vigente {rango}')
    return Verificacion(FALLO, f'Certificado fuera de vigencia al firmar ({rango})')


def _huella(cert: x509.Certificate) -> bytes:
    return cert.fingerprint(hashes.SHA256())


def _cargar_anclas(ca_dir: Path) -> list[x509.Certificate]:
    anclas = []
    try:
        archivos = sorted(p for p in Path(ca_dir).iterdir()
                          if p.is_file() and p.suffix.lower() in _EXTENSIONES_CA)
    except OSError:
        logger.warning('No se pudo leer la carpeta de confianza %s', ca_dir)
        return anclas
    for p in archivos:
        try:
            anclas.append(cargar_certificado(p.read_bytes()))
        except (OSError, ValueError):
            logger.warning('Certificado de confianza ilegible: %s', p)
    return anclas


def _emitido_por(hijo: x509.Certificate, padre: x509.Certificate) -> bool:
    if hijo.issuer != padre.subject:
        return False
    try:
        hijo.verify_directly_issued_by(padre)
    except (ValueError, TypeError, InvalidSignature):
        return False
    return True


def _puede_emitir(padre: x509.Certificate, debajo: int) -> bool:
    """`padre` es CA, puede firmar certificados y su pathlen admite `debajo` intermedios."""
    try:
        bc = padre.extensions.get_extension_for_class(x509.BasicConstraints).value
    except x509.ExtensionNotFound:
        return False
    if not bc.ca:
        return False
    try:
        ku = padre.extensions.get_extension_for_class(x509.KeyUsage).value
        if not ku.key_cert_sign:
            return False
    except x509.ExtensionNotFound:
        pass
    return bc.path_length is None or debajo <= bc.path_length


_EKU_NO_FIRMA = frozenset({ExtendedKeyUsageOID.SERVER_AUTH, ExtendedKeyUsageOID.OCSP_SIGNING})


def _apto_para_firma(cert: x509.Certificate) -> bool:
    """KeyUsage (si existe) con digitalSignature o nonRepudiation; EKU (si existe) no solo serverAuth/OCSPSigning."""
    try:
        ku = cert.extensions.get_extension_for_class(x509.KeyUsage).value
        if not (ku.digital_signature or ku.content_commitment):
            return False
    except x509.ExtensionNotFound:
        pass
    try:
        eku = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
        if set(eku) <= _EKU_NO_FIRMA:
            return False
    except x509.ExtensionNotFound:
        pass
    return True


def _urls_ca_issuers(cert: x509.Certificate) -> list[str]:
    try:
        aia = cert.extensions.get_extension_for_class(x509.AuthorityInformationAccess).value
    except x509.ExtensionNotFound:
        return []
    return [d.access_location.value for d in aia
            if d.access_method == AuthorityInformationAccessOID.CA_ISSUERS
            and isinstance(d.access_location, x509.UniformResourceIdentifier)
            and d.access_location.value.lower().startswith(('http://', 'https://'))]


def _emisores_aia(cert, descargar: Callable[[str], bytes] | None):
    """Certificados descargados de cada URL CA Issuers del AIA (con caché)."""
    if descargar is None:
        return
    for url in _urls_ca_issuers(cert):
        emisor = _de_cache_aia(url)
        if emisor is None:
            try:
                emisor = cargar_certificado(descargar(url))
            except Exception:  # noqa: BLE001 - red o formato: la cadena simplemente no se completa
                logger.warning('No se pudo descargar el emisor AIA %s', url)
                continue
            _a_cache_aia(url, emisor)
        yield emisor


def verificar_entidad_certificadora(
        cert: x509.Certificate | None, incrustados: list[x509.Certificate], ca_dir: Path,
        descargar: Callable[[str], bytes] | None = None,
        fecha_firma: datetime | None = None,
) -> tuple[Verificacion, list[x509.Certificate] | None]:
    """OK si la cadena de `cert` contiene, por huella SHA-256, un ancla de `ca_dir`.

    Los `incrustados` no están cubiertos por la firma: solo ayudan a armar la cadena.
    """
    if cert is None:
        return Verificacion(FALLO, 'Sin certificado'), None
    if not _apto_para_firma(cert):
        return Verificacion(FALLO, 'Uso de clave no apto para firma'), None
    anclas = _cargar_anclas(ca_dir)
    if not anclas:
        return Verificacion(FALLO, 'Sin certificados de confianza configurados'), None
    huellas = {_huella(a): a for a in anclas}
    otros = list(incrustados)

    motivos: list[str] = []

    def admisible(actual, padre, cadena) -> bool:
        if not _emitido_por(actual, padre):
            return False
        debajo = sum(1 for c in cadena[1:] if c.issuer != c.subject)
        if not _puede_emitir(padre, debajo):
            return False
        if fecha_firma is not None and not (
                padre.not_valid_before_utc <= fecha_firma <= padre.not_valid_after_utc):
            motivos.append(f"'{_atributo(padre.subject, NameOID.COMMON_NAME)}' fuera de vigencia "
                           f"al firmar")
            return False
        return True

    cadena = [cert]
    actual = cert
    for _ in range(_MAX_PROFUNDIDAD):
        padre = next((a for a in anclas if admisible(actual, a, cadena)), None)
        if padre is None:
            padre = next((c for c in otros if admisible(actual, c, cadena)), None)
        if padre is None:
            padre = next((c for c in _emisores_aia(actual, descargar)
                          if admisible(actual, c, cadena)), None)
        if padre is None or any(_huella(padre) == _huella(c) for c in cadena):
            break
        cadena.append(padre)
        if _huella(padre) in huellas:
            ancla = huellas[_huella(padre)]
            detalle = (f"{_atributo(ancla.subject, NameOID.ORGANIZATION_NAME)}, "
                       f"{_atributo(ancla.subject, NameOID.ORGANIZATIONAL_UNIT_NAME)}")
            return Verificacion(OK, detalle), cadena
        actual = padre
    detalle = 'La cadena no llega a una entidad certificadora autorizada'
    if motivos:
        detalle += ': ' + '; '.join(dict.fromkeys(motivos))
    return Verificacion(FALLO, detalle), None
