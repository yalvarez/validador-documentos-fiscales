"""PKI de prueba: CA, intermedios, hojas y firma de e-CF al estilo DGII."""
from datetime import datetime, timedelta

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509.oid import AuthorityInformationAccessOID, NameOID
from lxml import etree
from signxml import XMLSigner, methods

from common.ecf.modelos import ZONA_RD

_NS_DSIG = 'http://www.w3.org/2000/09/xmldsig#'
_C14N = 'http://www.w3.org/TR/2001/REC-xml-c14n-20010315'
_INICIO = datetime(2020, 1, 1, tzinfo=ZONA_RD)
_FIN = datetime(2040, 1, 1, tzinfo=ZONA_RD)


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
               es_ca, emisor_pub, ocsp_url=None, crl_url=None, ca_issuers_url=None):
    b = (x509.CertificateBuilder()
         .subject_name(sujeto).issuer_name(emisor_nombre)
         .public_key(clave_pub)
         .serial_number(x509.random_serial_number())
         .not_valid_before(not_before).not_valid_after(not_after)
         .add_extension(x509.BasicConstraints(ca=es_ca, path_length=None), critical=True)
         .add_extension(x509.SubjectKeyIdentifier.from_public_key(clave_pub), critical=False)
         .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(emisor_pub),
                        critical=False))
    if es_ca:
        b = b.add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=True, crl_sign=True,
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
