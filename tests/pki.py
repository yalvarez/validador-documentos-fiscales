"""PKI de prueba: CA, intermedios, hojas y firma de e-CF al estilo DGII."""
from datetime import datetime, timedelta

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509 import ocsp
from cryptography.x509.oid import AuthorityInformationAccessOID, ExtendedKeyUsageOID, NameOID
from lxml import etree
from signxml import XMLSigner, methods

from common.ecf.modelos import ZONA_RD

_NS_DSIG = 'http://www.w3.org/2000/09/xmldsig#'
_C14N = 'http://www.w3.org/TR/2001/REC-xml-c14n-20010315'
_INICIO = datetime(2020, 1, 1, tzinfo=ZONA_RD)
_FIN = datetime(2040, 1, 1, tzinfo=ZONA_RD)
_REFERENCIA = datetime(2026, 11, 10, 10, 0, tzinfo=ZONA_RD)  # = T0 de ayudantes; ancla de las respuestas OCSP/CRL


def _clave():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _nombre(cn: str, org: str, ou: str) -> x509.Name:
    return x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, 'DO'),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, org),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, ou),
        x509.NameAttribute(NameOID.COMMON_NAME, cn),
    ])


def _construir(sujeto, emisor_nombre, clave_pub, emisor_key, not_before, not_after,
               es_ca, emisor_pub, ocsp_url=None, crl_url=None, ca_issuers_url=None,
               path_length=None, key_cert_sign=True):
    b = (x509.CertificateBuilder()
         .subject_name(sujeto).issuer_name(emisor_nombre)
         .public_key(clave_pub)
         .serial_number(x509.random_serial_number())
         .not_valid_before(not_before).not_valid_after(not_after)
         .add_extension(x509.BasicConstraints(ca=es_ca, path_length=path_length if es_ca else None), critical=True)
         .add_extension(x509.SubjectKeyIdentifier.from_public_key(clave_pub), critical=False)
         .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(emisor_pub),
                        critical=False))
    if es_ca:
        b = b.add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=key_cert_sign, crl_sign=True,
            encipher_only=False, decipher_only=False), critical=True)
    aia = []
    if ocsp_url:
        aia.append(x509.AccessDescription(AuthorityInformationAccessOID.OCSP,
                                          x509.UniformResourceIdentifier(ocsp_url)))
    if ca_issuers_url:
        aia.append(x509.AccessDescription(AuthorityInformationAccessOID.CA_ISSUERS,
                                          x509.UniformResourceIdentifier(ca_issuers_url)))
    if aia:
        b = b.add_extension(x509.AuthorityInformationAccess(aia), critical=False)
    if crl_url:
        b = b.add_extension(x509.CRLDistributionPoints([x509.DistributionPoint(
            full_name=[x509.UniformResourceIdentifier(crl_url)], relative_name=None,
            reasons=None, crl_issuer=None)]), critical=False)
    return b.sign(emisor_key, hashes.SHA256())


def crear_ca(nombre: str, org: str = 'CA PRUEBA', ou: str = 'CA PRUEBA DOMINICANA'):
    key = _clave()
    n = _nombre(nombre, org, ou)
    cert = _construir(n, n, key.public_key(), key, _INICIO, _FIN, True, key.public_key())
    return key, cert


def crear_intermedio(ca_key, ca_cert, nombre, org='CA PRUEBA', ou='CA PRUEBA DOMINICANA',
                     ca_issuers_url: str | None = None):
    key = _clave()
    cert = _construir(_nombre(nombre, org, ou), ca_cert.subject, key.public_key(), ca_key,
                      _INICIO, _FIN, True, ca_cert.public_key(), ca_issuers_url=ca_issuers_url)
    return key, cert


def crear_hoja(emisor_key, emisor_cert, not_before: datetime, not_after: datetime,
               ocsp_url: str | None = None, crl_url: str | None = None,
               ca_issuers_url: str | None = None):
    key = _clave()
    cert = _construir(_nombre('FIRMANTE PRUEBA', 'PRUEBA', 'PERSONAS'), emisor_cert.subject,
                      key.public_key(), emisor_key, not_before, not_after, False,
                      emisor_cert.public_key(), ocsp_url, crl_url, ca_issuers_url)
    return key, cert


def firmar_ecf(xml_sin_firma: bytes, key, cert, fecha_firma: datetime) -> bytes:
    """Escribe FechaHoraFirma y firma enveloped con namespace por defecto, como la DGII."""
    raiz = etree.fromstring(xml_sin_firma)
    for n in raiz.xpath("//*[local-name()='FechaHoraFirma']"):
        n.getparent().remove(n)
    etree.SubElement(raiz, 'FechaHoraFirma').text = fecha_firma.strftime('%d-%m-%Y %H:%M:%S')
    firmador = XMLSigner(method=methods.enveloped, signature_algorithm='rsa-sha256',
                         digest_algorithm='sha256', c14n_algorithm=_C14N)
    firmador.namespaces = {None: _NS_DSIG}
    firmado = firmador.sign(raiz, key=key, cert=[cert.public_bytes(Encoding.PEM).decode()])
    return etree.tostring(firmado)


def crear_ca_con_subject(subject: x509.Name):
    """CA autofirmada con el subject indicado (para probar suplantación por nombre)."""
    key = _clave()
    cert = _construir(subject, subject, key.public_key(), key, _INICIO, _FIN, True,
                      key.public_key())
    return key, cert


def crear_subordinado(emisor_key, emisor_cert, nombre, es_ca=True, path_length=None,
                      key_cert_sign=True, not_before=None, not_after=None,
                      org='CA PRUEBA', ou='CA PRUEBA DOMINICANA'):
    """Certificado emitido por `emisor` con control de CA, pathlen, KeyUsage y vigencia."""
    key = _clave()
    cert = _construir(_nombre(nombre, org, ou), emisor_cert.subject, key.public_key(), emisor_key,
                      not_before or _INICIO, not_after or _FIN, es_ca, emisor_cert.public_key(),
                      path_length=path_length, key_cert_sign=key_cert_sign)
    return key, cert


def crear_delegado_ocsp(emisor_key, emisor_cert, con_eku: bool = True, nombre: str = 'RESPONDEDOR OCSP'):
    """Certificado de firma de respuestas OCSP emitido por `emisor` (EKU OCSPSigning si `con_eku`)."""
    key = _clave()
    b = (x509.CertificateBuilder()
         .subject_name(_nombre(nombre, 'CA PRUEBA', 'OCSP'))
         .issuer_name(emisor_cert.subject).public_key(key.public_key())
         .serial_number(x509.random_serial_number())
         .not_valid_before(_INICIO).not_valid_after(_FIN)
         .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True))
    if con_eku:
        b = b.add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.OCSP_SIGNING]), critical=False)
    return key, b.sign(emisor_key, hashes.SHA256())


def _clonar_con_serie(cert, serie: int, firmante_key):
    return (x509.CertificateBuilder()
            .subject_name(cert.subject).issuer_name(cert.issuer)
            .public_key(cert.public_key()).serial_number(serie)
            .not_valid_before(cert.not_valid_before_utc).not_valid_after(cert.not_valid_after_utc)
            .sign(firmante_key, hashes.SHA256()))


def responder_ocsp(firmante_key, firmante_cert, hoja, estado: str,
                   revocado_en: datetime | None = None, serie: int | None = None,
                   emisor=None, incluir_certificados=(), razon=None,
                   this_update: datetime | None = None, next_update=...) -> bytes:
    """Respuesta OCSP SUCCESSFUL para `hoja`, firmada con `firmante_key`, en DER."""
    emisor = emisor or firmante_cert
    objetivo = _clonar_con_serie(hoja, serie, firmante_key) if serie is not None else hoja
    ahora = _REFERENCIA
    b = ocsp.OCSPResponseBuilder().add_response(
        cert=objetivo, issuer=emisor, algorithm=hashes.SHA1(),
        cert_status=getattr(ocsp.OCSPCertStatus, estado),
        this_update=this_update or ahora - timedelta(minutes=1),
        next_update=ahora + timedelta(days=1) if next_update is ... else next_update,
        revocation_time=revocado_en if estado == 'REVOKED' else None,
        revocation_reason=razon)
    b = b.responder_id(ocsp.OCSPResponderEncoding.HASH, firmante_cert)
    if incluir_certificados:
        b = b.certificates(list(incluir_certificados))
    return b.sign(firmante_key, hashes.SHA256()).public_bytes(Encoding.DER)


def firmar_crl(firmante_key, firmante_cert, revocados: dict, next_update: datetime | None,
               razones: dict | None = None, pem: bool = False, last_update: datetime | None = None) -> bytes:
    """CRL en DER con los `revocados` ({serie: fecha})."""
    ahora = _REFERENCIA
    b = (x509.CertificateRevocationListBuilder()
         .issuer_name(firmante_cert.subject)
         .last_update(last_update or ahora - timedelta(hours=1)))
    if next_update is not None:
        b = b.next_update(next_update)
    for serie, fecha in revocados.items():
        rb = x509.RevokedCertificateBuilder().serial_number(serie).revocation_date(fecha)
        if razones and serie in razones:
            rb = rb.add_extension(x509.CRLReason(razones[serie]), critical=False)
        b = b.add_revoked_certificate(rb.build())
    return b.sign(firmante_key, hashes.SHA256()).public_bytes(Encoding.PEM if pem else Encoding.DER)
