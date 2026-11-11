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


NS = {'ds': 'http://www.w3.org/2000/09/xmldsig#'}


def _firmado_con_objeto_falso():
    """Firma válida, movida al inicio, con un ds:Object que contiene datos falsos."""
    from lxml import etree
    raiz = etree.fromstring(ecf_de_prueba('E310000000001'))
    firma = raiz.xpath('ds:Signature', namespaces=NS)[0]
    obj = etree.SubElement(firma, '{%s}Object' % NS['ds'])
    fake = etree.SubElement(obj, 'ECF')
    etree.SubElement(fake, 'eNCF').text = 'E319999999999'
    etree.SubElement(fake, 'RNCEmisor').text = '999999999'
    raiz.insert(0, firma)
    return raiz


def test_leer_ecf_ignora_datos_dentro_de_la_firma():
    from lxml import etree
    from common.ecf.lectura import leer_ecf
    d = leer_ecf(etree.tostring(_firmado_con_objeto_falso()))
    assert d.encf == 'E310000000001' and d.rnc_emisor == '101616202'
    assert d.signature_value and len(d.certificados_der) == 1


def test_segunda_firma_inyectada_es_fallo():
    import copy
    from lxml import etree
    raiz = etree.fromstring(ecf_de_prueba('E310000000001'))
    firma = raiz.xpath('ds:Signature', namespaces=NS)[0]
    raiz.insert(0, copy.deepcopy(firma))
    r = verificar_integridad(etree.tostring(raiz))
    assert r.resultado == FALLO and 'exactamente una firma' in r.detalle


def test_firma_no_hija_directa_es_fallo():
    from lxml import etree
    raiz = etree.fromstring(ecf_de_prueba('E310000000001'))
    firma = raiz.xpath('ds:Signature', namespaces=NS)[0]
    envoltorio = etree.Element('Envoltorio')
    envoltorio.append(firma)
    raiz.append(envoltorio)
    r = verificar_integridad(etree.tostring(raiz))
    assert r.resultado == FALLO and 'hija directa' in r.detalle


def test_certificado_suelto_fuera_de_keyinfo_no_se_lee():
    from lxml import etree
    from common.ecf.lectura import leer_ecf
    raiz = etree.fromstring(ecf_de_prueba('E310000000001'))
    suelto = etree.Element('{%s}X509Certificate' % NS['ds'])
    suelto.text = 'AAAA'
    raiz.insert(0, suelto)
    otro = etree.SubElement(raiz, 'X509Certificate')
    otro.text = 'BBBB'
    d = leer_ecf(etree.tostring(raiz))
    assert len(d.certificados_der) == 1 and d.certificados_der[0] != b'\x00\x00\x00'


def test_comentarios_en_campos_no_truncan_la_lectura():
    from decimal import Decimal
    from common.ecf.lectura import leer_ecf
    xml = ecf_de_prueba('E310000000001')
    assert b'<MontoTotal>1250</MontoTotal>' in xml
    alterado = xml.replace(b'<MontoTotal>1250</MontoTotal>', b'<MontoTotal>1<!---->250</MontoTotal>')
    alterado = alterado.replace(b'<eNCF>E310000000001</eNCF>', b'<eNCF>E31<!--x-->0000000001</eNCF>')
    assert verificar_integridad(alterado).resultado == OK  # los comentarios no los cubre la firma
    d = leer_ecf(alterado)
    assert d.monto_total == Decimal('1250') and d.encf == 'E310000000001'


def _con_doctype(xml: bytes, doctype: bytes) -> bytes:
    return doctype + b'\n' + xml


def test_dtd_con_entidad_rechazado():
    import pytest as _p
    from common.ecf.lectura import ErrorLecturaECF, leer_ecf
    xml = ecf_de_prueba('E310000000001')
    alterado = xml.replace(b'<MontoTotal>1250</MontoTotal>', b'<MontoTotal>1&x;250</MontoTotal>')
    assert alterado != xml
    doc = _con_doctype(alterado, b'<!DOCTYPE ECF [<!ENTITY x "9">]>')
    with _p.raises(ErrorLecturaECF, match='DTD o entidades'):
        leer_ecf(doc)
    r = verificar_integridad(doc)
    assert r.resultado == FALLO and 'DTD o entidades' in r.detalle


def test_dtd_sin_entidades_rechazado():
    import pytest as _p
    from common.ecf.lectura import ErrorLecturaECF, leer_ecf
    doc = _con_doctype(ecf_de_prueba('E310000000001'), b'<!DOCTYPE ECF>')
    with _p.raises(ErrorLecturaECF, match='DTD o entidades'):
        leer_ecf(doc)
    assert verificar_integridad(doc).resultado == FALLO
