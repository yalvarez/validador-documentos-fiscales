"""Verificación de revocación del certificado del firmante a la fecha de firma.

OCSP primero, CRL como respaldo. Solo se aceptan respuestas autenticadas por el emisor
(o por un respondedor delegado emitido por él con EKU OCSPSigning).
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Callable

from cryptography import x509
from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509 import ocsp
from cryptography.x509.oid import CRLEntryExtensionOID, ExtendedKeyUsageOID, ExtensionOID

from common.ecf.modelos import FALLO, NO_VERIFICABLE, OK, Verificacion

log = logging.getLogger(__name__)

_TOLERANCIA = timedelta(minutes=5)
_CRITICAS_CRL = (ExtensionOID.ISSUING_DISTRIBUTION_POINT, ExtensionOID.CRL_NUMBER,
                ExtensionOID.AUTHORITY_KEY_IDENTIFIER)
_CRITICAS_ENTRADA = (CRLEntryExtensionOID.CRL_REASON, CRLEntryExtensionOID.INVALIDITY_DATE)
_COMPROMISO = (x509.ReasonFlags.key_compromise, x509.ReasonFlags.ca_compromise)

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


def _ocsp_fresca(resp: ocsp.OCSPResponse, ahora: datetime) -> bool:
    if resp.this_update_utc > ahora + _TOLERANCIA:
        return False
    if resp.next_update_utc is not None:
        return resp.next_update_utc >= ahora
    return resp.this_update_utc >= ahora - timedelta(days=7)


def _respuesta_autenticada(resp: ocsp.OCSPResponse, hoja: x509.Certificate,
                           emisor: x509.Certificate, ahora: datetime) -> bool:
    if resp.response_status != ocsp.OCSPResponseStatus.SUCCESSFUL:
        return False
    if resp.serial_number != hoja.serial_number:
        return False
    try:
        esperado = ocsp.OCSPRequestBuilder().add_certificate(hoja, emisor, resp.hash_algorithm).build()
    except (ValueError, TypeError, UnsupportedAlgorithm):
        return False
    if (resp.issuer_key_hash != esperado.issuer_key_hash
            or resp.issuer_name_hash != esperado.issuer_name_hash):
        return False
    if not _ocsp_fresca(resp, ahora):
        return False
    if _verificar_firma_ocsp(resp, emisor.public_key()):
        return True
    for delegado in resp.certificates:
        if _delegado_valido(delegado, emisor, ahora) and _verificar_firma_ocsp(resp, delegado.public_key()):
            return True
    return False


def _con_fecha(revocado_utc: datetime, fecha_firma: datetime, origen: str, razon=None) -> Verificacion:
    if razon in _COMPROMISO:
        return Verificacion(FALLO, f'Revocado por compromiso de clave el {revocado_utc.date().isoformat()}')
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
                return _con_fecha(resp.revocation_time_utc, fecha_firma, 'OCSP', resp.revocation_reason)
        except Exception as e:  # red, HTTP != 200 o respuesta malformada: se pasa a CRL
            log.warning('OCSP %s falló: %s', url, e)
    return None


def _cargar_crl(datos: bytes) -> x509.CertificateRevocationList:
    try:
        return x509.load_der_x509_crl(datos)
    except ValueError:
        return x509.load_pem_x509_crl(datos)


def _crl_aceptable(crl, url: str) -> bool:
    """Rechaza CRL delta, parciales/con alcance distinto al del certificado y con extensiones críticas ignoradas."""
    for ext in crl.extensions:
        if ext.oid == ExtensionOID.DELTA_CRL_INDICATOR:
            return False  # sin importar si es crítica
        if ext.oid == ExtensionOID.ISSUING_DISTRIBUTION_POINT:
            idp = ext.value
            if (idp.only_contains_ca_certs or idp.only_contains_attribute_certs or idp.indirect_crl
                    or idp.only_some_reasons or idp.relative_name is not None):
                return False
            if idp.full_name is not None and url not in [
                    n.value for n in idp.full_name if isinstance(n, x509.UniformResourceIdentifier)]:
                return False
        elif ext.critical and ext.oid not in _CRITICAS_CRL:
            return False  # incluye DeltaCRLIndicator
    for entrada in crl:
        for ext in entrada.extensions:
            if ext.critical and ext.oid not in _CRITICAS_ENTRADA:
                return False
    return True


def _crl_de(url, emisor, descargar, ahora) -> x509.CertificateRevocationList | None:
    en_cache = _CACHE_CRL.get(url)
    if en_cache and ahora < en_cache[1] and en_cache[2] == _huella(emisor):
        return en_cache[0]
    crl = _cargar_crl(descargar(url))
    if not crl.is_signature_valid(emisor.public_key()) or crl.issuer != emisor.subject:
        return None
    if crl.last_update_utc > ahora + _TOLERANCIA:
        return None
    if crl.next_update_utc is not None and crl.next_update_utc < ahora:
        return None
    if not _crl_aceptable(crl, url):
        return None
    hasta = crl.next_update_utc.astimezone(ahora.tzinfo) if crl.next_update_utc else ahora + timedelta(hours=1)
    _CACHE_CRL[url] = (crl, hasta, _huella(emisor))
    return crl


def _razon_crl(entrada):
    try:
        return entrada.extensions.get_extension_for_class(x509.CRLReason).value.reason
    except x509.ExtensionNotFound:
        return None


def _por_crl(hoja, emisor, fecha_firma, descargar, ahora) -> Verificacion | None:
    for url in _urls_crl(hoja):
        try:
            crl = _crl_de(url, emisor, descargar, ahora)
            if crl is None:
                continue
            entrada = crl.get_revoked_certificate_by_serial_number(hoja.serial_number)
            if entrada is None:
                return Verificacion(OK, 'CRL: no revocado')
            return _con_fecha(entrada.revocation_date_utc, fecha_firma, 'CRL', _razon_crl(entrada))
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
