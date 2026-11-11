import base64

from lxml import etree
from signxml import XMLVerifier

from common.ecf.lectura import normalizar_xml_bytes
from common.ecf.modelos import FALLO, OK, Verificacion

NS_DSIG = 'http://www.w3.org/2000/09/xmldsig#'


def verificar_integridad(xml_bytes: bytes) -> Verificacion:
    """Verifica la firma XMLDSig del e-CF contra el certificado incrustado.

    No evalúa la confianza del certificado (eso es `entidad_certificadora`).
    """
    try:
        xml = normalizar_xml_bytes(xml_bytes)
        raiz = etree.fromstring(xml)
        nodos = raiz.xpath('//ds:X509Certificate', namespaces={'ds': NS_DSIG})
        if not nodos or not (nodos[0].text or '').strip():
            return Verificacion(FALLO, 'Sin certificado incrustado')
        der = base64.b64decode(''.join(nodos[0].text.split()))
        pem = (b'-----BEGIN CERTIFICATE-----\n'
               + base64.encodebytes(der) + b'-----END CERTIFICATE-----\n')
        verificador = XMLVerifier()
        # Obligatorio: sin esto la firma real de la DGII no verifica (signxml #193).
        verificador.excise_empty_xmlns_declarations = True
        verificador.verify(xml, x509_cert=pem)
        return Verificacion(OK, 'Firma íntegra')
    except Exception as e:
        return Verificacion(FALLO, f'{type(e).__name__}: {e}')
