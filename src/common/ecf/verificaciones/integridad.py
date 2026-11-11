import base64

from signxml import XMLVerifier

from common.ecf.lectura import ErrorLecturaECF, certificados_keyinfo, normalizar_xml_bytes, parsear_ecf
from common.ecf.modelos import FALLO, OK, Verificacion

NS_DSIG = 'http://www.w3.org/2000/09/xmldsig#'

# Únicos Transforms admitidos en la Reference (signxml ignora en silencio los desconocidos
# y aplica otros como xmldsig#base64, que cambian lo que la firma cubre).
TRANSFORMS_PERMITIDOS = frozenset({
    'http://www.w3.org/2000/09/xmldsig#enveloped-signature',
    'http://www.w3.org/TR/2001/REC-xml-c14n-20010315',
    'http://www.w3.org/TR/2001/REC-xml-c14n-20010315#WithComments',
    'http://www.w3.org/2006/12/xml-c14n11',
    'http://www.w3.org/2006/12/xml-c14n11#WithComments',
    'http://www.w3.org/2001/10/xml-exc-c14n#',
    'http://www.w3.org/2001/10/xml-exc-c14n#WithComments',
})


def verificar_integridad(xml_bytes: bytes, certificado_der: bytes | None = None) -> Verificacion:
    """Verifica la firma XMLDSig del e-CF contra el certificado firmante incrustado.

    El certificado firmante es el primero del KeyInfo (`lectura.certificados_keyinfo`), el mismo
    que usan vigencia, entidad y revocación. Si se pasa `certificado_der`, debe ser ese mismo.
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
        referencias = firma[0].xpath('ds:SignedInfo/ds:Reference', namespaces=ns)
        uris = [r.get('URI') for r in referencias]
        if uris != ['']:
            return Verificacion(
                FALLO, f'La firma no cubre el documento completo (Reference URI={uris})')
        for t in referencias[0].xpath('ds:Transforms/ds:Transform', namespaces=ns):
            if t.get('Algorithm') not in TRANSFORMS_PERMITIDOS:
                return Verificacion(FALLO, f"Transform no permitido: {t.get('Algorithm')}")
        certs = certificados_keyinfo(raiz)
        if not certs:
            return Verificacion(FALLO, 'Sin certificado incrustado válido')
        der = certs[0]
        if certificado_der is not None and certificado_der != der:
            return Verificacion(FALLO, 'El certificado indicado no es el del firmante')
        pem = (b'-----BEGIN CERTIFICATE-----\n'
               + base64.encodebytes(der) + b'-----END CERTIFICATE-----\n')
        verificador = XMLVerifier()
        # Obligatorio: sin esto la firma real de la DGII no verifica (signxml #193).
        verificador.excise_empty_xmlns_declarations = True
        verificador.verify(xml, x509_cert=pem)
        return Verificacion(OK, 'Firma íntegra')
    except Exception as e:
        return Verificacion(FALLO, f'{type(e).__name__}: {e}')
