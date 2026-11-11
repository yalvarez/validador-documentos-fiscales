import pytest

from ayudantes import MUESTRA_XML, XML_SIN_FIRMA, ecf_de_prueba, muestra_en
from common.ecf.modelos import FALLO, OK
from common.ecf.verificaciones.integridad import verificar_integridad


def test_muestra_integra():
    assert verificar_integridad(MUESTRA_XML).resultado == OK


@pytest.mark.parametrize('b', [b'\xef\xbb\xbf' + MUESTRA_XML, b'  \n' + MUESTRA_XML,
                               muestra_en('ISO-8859-1')])  # Foco 1
def test_variantes_integras(b):
    assert verificar_integridad(b).resultado == OK


def test_contenido_alterado():
    alterado = MUESTRA_XML.replace(b'<MontoTotal>1250</MontoTotal>', b'<MontoTotal>9250</MontoTotal>')
    assert verificar_integridad(alterado).resultado == FALLO


def test_signedinfo_alterado():
    assert verificar_integridad(MUESTRA_XML.replace(b'q5C5ueQp', b'q5C5ueQq')).resultado == FALLO


def test_sin_firma():
    assert verificar_integridad(XML_SIN_FIRMA).resultado == FALLO


def test_firmado_con_pki_de_prueba():
    assert verificar_integridad(ecf_de_prueba('E310000000001')).resultado == OK


def test_firma_sobre_subelemento_no_cubre_documento():
    from cryptography.hazmat.primitives.serialization import Encoding
    from lxml import etree
    from signxml import XMLSigner, methods
    from ayudantes import HOJA_PRUEBA, HOJA_PRUEBA_KEY
    raiz = etree.fromstring(XML_SIN_FIRMA)
    raiz.xpath('//Encabezado')[0].set('Id', 'enc')
    firmador = XMLSigner(method=methods.enveloped, signature_algorithm='rsa-sha256',
                         digest_algorithm='sha256',
                         c14n_algorithm='http://www.w3.org/TR/2001/REC-xml-c14n-20010315')
    firmador.namespaces = {None: 'http://www.w3.org/2000/09/xmldsig#'}
    firmado = etree.tostring(firmador.sign(
        raiz, key=HOJA_PRUEBA_KEY, cert=[HOJA_PRUEBA.public_bytes(Encoding.PEM).decode()],
        reference_uri='#enc'))
    r = verificar_integridad(firmado.replace(b'<MontoTotal>1250</MontoTotal>',
                                             b'<MontoTotal>9250</MontoTotal>'))
    assert firmado.count(b'<MontoTotal>1250</MontoTotal>') == 1
    assert r.resultado == FALLO and 'no cubre el documento completo' in r.detalle
