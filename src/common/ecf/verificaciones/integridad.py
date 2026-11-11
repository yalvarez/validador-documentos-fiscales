import base64

from lxml import etree
from signxml import XMLVerifier

from common.ecf.lectura import ErrorLecturaECF, normalizar_xml_bytes, parsear_ecf, texto_completo
from common.ecf.modelos import FALLO, OK, Verificacion

NS_DSIG = 'http://www.w3.org/2000/09/xmldsig#'


def verificar_integridad(xml_bytes: bytes) -> Verificacion:
    """Verifica la firma XMLDSig del e-CF contra el certificado incrustado.

    No evalúa la confianza del certificado (eso es `entidad_certificadora`).
    """
    try:
        xml = normalizar_xml_bytes(xml_bytes)
        try:
            raiz = parsear_ecf(xml)
        except ErrorLecturaECF as e:
            return Verificacion(FALLO, str(e))
        ns = {'ds': NS_DSIG}
        if len(raiz.xpath('//ds:Signature', namespaces=ns)) != 1:
            return Verificacion(FALLO, 'Debe haber exactamente una firma en el documento')
        firma = raiz.xpath('ds:Signature', namespaces=ns)
        if len(firma) != 1:
            return Verificacion(FALLO, 'La firma no es hija directa del elemento raíz')
        uris = [r.get('URI') for r in firma[0].xpath('ds:SignedInfo/ds:Reference', namespaces=ns)]
        if uris != ['']:
            return Verificacion(
                FALLO, f'La firma no cubre el documento completo (Reference URI={uris})')
        nodos = firma[0].xpath('ds:KeyInfo/ds:X509Data/ds:X509Certificate', namespaces=ns)
        if not nodos or not texto_completo(nodos[0]):
            return Verificacion(FALLO, 'Sin certificado incrustado')
        der = base64.b64decode(''.join(texto_completo(nodos[0]).split()))
        pem = (b'-----BEGIN CERTIFICATE-----\n'
               + base64.encodebytes(der) + b'-----END CERTIFICATE-----\n')
        verificador = XMLVerifier()
        # Obligatorio: sin esto la firma real de la DGII no verifica (signxml #193).
        verificador.excise_empty_xmlns_declarations = True
        verificador.verify(xml, x509_cert=pem)
        return Verificacion(OK, 'Firma íntegra')
    except Exception as e:
        return Verificacion(FALLO, f'{type(e).__name__}: {e}')
