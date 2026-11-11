"""Verificaciones del certificado del firmante: vigencia y entidad certificadora autorizada."""
import logging
from datetime import datetime
from pathlib import Path
from typing import Callable

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.x509.oid import AuthorityInformationAccessOID, NameOID

from common.ecf.modelos import FALLO, OK, Verificacion

logger = logging.getLogger(__name__)

_MAX_PROFUNDIDAD = 8
_EXTENSIONES_CA = ('.pem', '.crt', '.cer', '.der')

# Caché de certificados descargados por la URL CA Issuers del AIA
_cache_aia: dict[str, x509.Certificate] = {}


def limpiar_caches() -> None:
    _cache_aia.clear()


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


def _urls_ca_issuers(cert: x509.Certificate) -> list[str]:
    try:
        aia = cert.extensions.get_extension_for_class(x509.AuthorityInformationAccess).value
    except x509.ExtensionNotFound:
        return []
    return [d.access_location.value for d in aia
            if d.access_method == AuthorityInformationAccessOID.CA_ISSUERS
            and isinstance(d.access_location, x509.UniformResourceIdentifier)]


def _descargar_emisor(cert, descargar: Callable[[str], bytes] | None):
    if descargar is None:
        return None
    for url in _urls_ca_issuers(cert):
        if url in _cache_aia:
            return _cache_aia[url]
        try:
            emisor = cargar_certificado(descargar(url))
        except Exception:  # noqa: BLE001 - red o formato: la cadena simplemente no se completa
            logger.warning('No se pudo descargar el emisor AIA %s', url)
            continue
        _cache_aia[url] = emisor
        return emisor
    return None


def verificar_entidad_certificadora(
        cert: x509.Certificate | None, incrustados: list[x509.Certificate], ca_dir: Path,
        descargar: Callable[[str], bytes] | None = None,
) -> tuple[Verificacion, list[x509.Certificate] | None]:
    """OK si la cadena de `cert` contiene, por huella SHA-256, un ancla de `ca_dir`.

    Los `incrustados` no están cubiertos por la firma: solo ayudan a armar la cadena.
    """
    if cert is None:
        return Verificacion(FALLO, 'Sin certificado'), None
    anclas = _cargar_anclas(ca_dir)
    if not anclas:
        return Verificacion(FALLO, 'Sin certificados de confianza configurados'), None
    huellas = {_huella(a): a for a in anclas}
    otros = list(incrustados)

    cadena = [cert]
    actual = cert
    for _ in range(_MAX_PROFUNDIDAD):
        padre = next((a for a in anclas if _emitido_por(actual, a)), None)
        if padre is None:
            padre = next((c for c in otros if _emitido_por(actual, c)), None)
        if padre is None:
            padre = _descargar_emisor(actual, descargar)
            if padre is not None and not _emitido_por(actual, padre):
                padre = None
        if padre is None or any(_huella(padre) == _huella(c) for c in cadena):
            break
        cadena.append(padre)
        if _huella(padre) in huellas:
            ancla = huellas[_huella(padre)]
            detalle = (f"{_atributo(ancla.subject, NameOID.ORGANIZATION_NAME)}, "
                       f"{_atributo(ancla.subject, NameOID.ORGANIZATIONAL_UNIT_NAME)}")
            return Verificacion(OK, detalle), cadena
        actual = padre
    return Verificacion(FALLO, 'La cadena no llega a una entidad certificadora autorizada'), None
