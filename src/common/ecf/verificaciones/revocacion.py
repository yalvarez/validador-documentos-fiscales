"""Verificación de revocación del certificado del firmante a la fecha de firma.

OCSP primero, CRL como respaldo. Solo se aceptan respuestas autenticadas por el emisor
(o por un respondedor delegado emitido por él con EKU OCSPSigning).
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Callable

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509 import ocsp
from cryptography.x509.oid import ExtendedKeyUsageOID

from common.ecf.modelos import FALLO, NO_VERIFICABLE, OK, Verificacion

log = logging.getLogger(__name__)

# url -> (crl, vigente_hasta, huella_del_emisor)
_CACHE_CRL: dict[str, tuple[x509.CertificateRevocationList, datetime, bytes]] = {}


def limpiar_caches() -> None:
    _CACHE_CRL.clear()


def _huella(cert: x509.Certificate) -> bytes:
    return cert.fingerprint(hashes.SHA256())


def _urls_ocsp(hoja: x509.Certificate) -> list[str]:
    try:
        aia = hoja.extensions.get_extension_for_class(x509.AuthorityInformationAccess).value
    except x509.ExtensionNotFound:
        return []
    return [d.access_location.value for d in aia
            if d.access_method == x509.oid.AuthorityInformationAccessOID.OCSP
            and isinstance(d.access_location, x509.UniformResourceIdentifier)]


def _urls_crl(hoja: x509.Certificate) -> list[str]:
    try:
        puntos = hoja.extensions.get_extension_for_class(x509.CRLDistributionPoints).value
    except x509.ExtensionNotFound:
        return []
    return [n.value for p in puntos for n in (p.full_name or [])
            if isinstance(n, x509.UniformResourceIdentifier)]


def _verificar_firma_ocsp(resp: ocsp.OCSPResponse, clave) -> bool:
    try:
        if isinstance(clave, rsa.RSAPublicKey):
            clave.verify(resp.signature, resp.tbs_response_bytes, padding.PKCS1v15(),
                         resp.signature_hash_algorithm)
        elif isinstance(clave, ec.EllipticCurvePublicKey):
            clave.verify(resp.signature, resp.tbs_response_bytes,
                         ec.ECDSA(resp.signature_hash_algorithm))
        else:
            return False
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def _delegado_valido(delegado: x509.Certificate, emisor: x509.Certificate, ahora: datetime) -> bool:
    try:
        delegado.verify_directly_issued_by(emisor)
        eku = delegado.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
    except (x509.ExtensionNotFound, ValueError, TypeError, InvalidSignature):
        return False
    if ExtendedKeyUsageOID.OCSP_SIGNING not in eku:
        return False
    return delegado.not_valid_before_utc <= ahora.astimezone(timezone.utc) <= delegado.not_valid_after_utc


def _respuesta_autenticada(resp: ocsp.OCSPResponse, hoja: x509.Certificate,
                           emisor: x509.Certificate, ahora: datetime) -> bool:
    if resp.response_status != ocsp.OCSPResponseStatus.SUCCESSFUL:
        return False
    if resp.serial_number != hoja.serial_number:
        return False
    if _verificar_firma_ocsp(resp, emisor.public_key()):
        return True
    for delegado in resp.certificates:
        if _delegado_valido(delegado, emisor, ahora) and _verificar_firma_ocsp(resp, delegado.public_key()):
            return True
    return False


def _con_fecha(revocado_utc: datetime, fecha_firma: datetime, origen: str) -> Verificacion:
    if revocado_utc <= fecha_firma.astimezone(timezone.utc):
        return Verificacion(FALLO, f'{origen}: revocado el {revocado_utc.date().isoformat()}, antes o al momento de la firma')
    return Verificacion(OK, f'Revocado el {revocado_utc.date().isoformat()}, después de la firma')


def _por_ocsp(hoja, emisor, fecha_firma, ocsp_post, ahora) -> Verificacion | None:
    peticion = ocsp.OCSPRequestBuilder().add_certificate(hoja, emisor, hashes.SHA1()).build()
    cuerpo = peticion.public_bytes(Encoding.DER)
    for url in _urls_ocsp(hoja):
        try:
            resp = ocsp.load_der_ocsp_response(ocsp_post(url, cuerpo))
            if not _respuesta_autenticada(resp, hoja, emisor, ahora):
                continue
            if resp.certificate_status == ocsp.OCSPCertStatus.GOOD:
                return Verificacion(OK, 'OCSP: good')
            if resp.certificate_status == ocsp.OCSPCertStatus.REVOKED:
                return _con_fecha(resp.revocation_time_utc, fecha_firma, 'OCSP')
        except Exception as e:  # red, HTTP != 200 o respuesta malformada: se pasa a CRL
            log.warning('OCSP %s falló: %s', url, e)
    return None


def _cargar_crl(datos: bytes) -> x509.CertificateRevocationList:
    try:
        return x509.load_der_x509_crl(datos)
    except ValueError:
        return x509.load_pem_x509_crl(datos)


def _crl_de(url, emisor, descargar, ahora) -> x509.CertificateRevocationList | None:
    en_cache = _CACHE_CRL.get(url)
    if en_cache and ahora < en_cache[1] and en_cache[2] == _huella(emisor):
        return en_cache[0]
    crl = _cargar_crl(descargar(url))
    if not crl.is_signature_valid(emisor.public_key()):
        return None
    hasta = crl.next_update_utc.astimezone(ahora.tzinfo) if crl.next_update_utc else ahora + timedelta(hours=1)
    _CACHE_CRL[url] = (crl, hasta, _huella(emisor))
    return crl


def _por_crl(hoja, emisor, fecha_firma, descargar, ahora) -> Verificacion | None:
    for url in _urls_crl(hoja):
        try:
            crl = _crl_de(url, emisor, descargar, ahora)
            if crl is None:
                continue
            entrada = crl.get_revoked_certificate_by_serial_number(hoja.serial_number)
            if entrada is None:
                return Verificacion(OK, 'CRL: no revocado')
            return _con_fecha(entrada.revocation_date_utc, fecha_firma, 'CRL')
        except Exception as e:
            log.warning('CRL %s falló: %s', url, e)
    return None


def verificar_revocacion(hoja: x509.Certificate, emisor: x509.Certificate, fecha_firma: datetime,
                         ocsp_post: Callable[[str, bytes], bytes],
                         descargar: Callable[[str], bytes], ahora: datetime) -> Verificacion:
    if not _urls_ocsp(hoja) and not _urls_crl(hoja):
        return Verificacion(NO_VERIFICABLE, 'Sin URL de revocación')
    return (_por_ocsp(hoja, emisor, fecha_firma, ocsp_post, ahora)
            or _por_crl(hoja, emisor, fecha_firma, descargar, ahora)
            or Verificacion(NO_VERIFICABLE, 'OCSP y CRL sin respuesta válida'))
