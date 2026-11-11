"""El certificado firmante es uno solo: el primer X509Certificate del KeyInfo de la Signature raíz,
decodificado en base64 estricto. Integridad, vigencia, entidad y revocación usan exactamente ese DER."""
import base64

from lxml import etree

from ayudantes import CONFIG_SIN_RED, MUESTRA_XML, T0, XML_SIN_FIRMA, ecf_de_prueba
from common.ecf.lectura import leer_ecf
from common.ecf.modelos import FALLO, OK
from common.ecf.validacion import validar_xml
from common.ecf.verificaciones.integridad import verificar_integridad
from pki import crear_ca, firmar_ecf

NS = 'http://www.w3.org/2000/09/xmldsig#'
_NSM = {'ds': NS}


def _cert_muestra_b64() -> str:
    return etree.fromstring(MUESTRA_XML).xpath('//ds:X509Certificate', namespaces=_NSM)[0].text


def _falsificado_con_cert_legitimo_detras(texto_primero) -> bytes:
    """PoC: factura alterada firmada por un atacante; su certificado queda primero (alterado por
    `texto_primero`) y detrás se copia el certificado legítimo de Viafirma de la muestra."""
    legit = leer_ecf(MUESTRA_XML)
    raiz = etree.fromstring(XML_SIN_FIRMA)
    for n in raiz.xpath("//*[local-name()='MontoTotal']"):
        n.text = '1.00'
    key, cert = crear_ca('ATACANTE')
    doc = etree.fromstring(firmar_ecf(etree.tostring(raiz), key, cert, legit.fecha_firma.replace(tzinfo=None)))
    x509data = doc.xpath('//ds:X509Data', namespaces=_NSM)[0]
    nodo_a = x509data.xpath('ds:X509Certificate', namespaces=_NSM)[0]
    nodo_a.text = texto_primero(''.join(nodo_a.text.split()))
    etree.SubElement(x509data, f'{{{NS}}}X509Certificate').text = _cert_muestra_b64()
    return etree.tostring(doc)


def test_poc_certificado_con_caracter_invalido_no_suplanta_al_firmante():
    xml = _falsificado_con_cert_legitimo_detras(lambda t: t[:40] + '!' + t[40:])
    assert leer_ecf(xml).certificados_der == []
    r = validar_xml(xml, None, CONFIG_SIN_RED, ahora=T0)
    assert r.integridad.resultado == FALLO
    assert r.vigencia.resultado == FALLO
    assert r.entidad_certificadora.resultado == FALLO
    assert r.certificado_titular is None


def test_x509certificate_vacio_es_fallo_y_no_se_salta():
    xml = _falsificado_con_cert_legitimo_detras(lambda t: '')
    assert leer_ecf(xml).certificados_der == []
    r = validar_xml(xml, None, CONFIG_SIN_RED, ahora=T0)
    assert r.integridad.resultado == FALLO
    assert r.vigencia.resultado == FALLO and r.vigencia.detalle == 'Sin certificado'
    assert r.entidad_certificadora.resultado == FALLO


def test_primero_invalido_no_salta_al_segundo_aunque_sea_el_firmante():
    """Aunque el segundo sea el certificado que realmente firmó, el primero manda."""
    xml = etree.fromstring(ecf_de_prueba('E310000000001'))
    x509data = xml.xpath('//ds:X509Data', namespaces=_NSM)[0]
    nodo = x509data.xpath('ds:X509Certificate', namespaces=_NSM)[0]
    bueno = ''.join(nodo.text.split())
    nodo.text = bueno[:10] + '*' + bueno[10:]
    etree.SubElement(x509data, f'{{{NS}}}X509Certificate').text = bueno
    b = etree.tostring(xml)
    assert leer_ecf(b).certificados_der == []
    assert verificar_integridad(b).resultado == FALLO


def test_espacios_en_blanco_en_el_base64_se_aceptan():
    assert verificar_integridad(MUESTRA_XML).resultado == OK
    assert leer_ecf(MUESTRA_XML).certificados_der[0] == base64.b64decode(''.join(_cert_muestra_b64().split()))


def test_integridad_con_der_distinto_al_firmante_es_fallo():
    otro = leer_ecf(MUESTRA_XML).certificados_der[0]
    r = verificar_integridad(ecf_de_prueba('E310000000001'), certificado_der=otro)
    assert r.resultado == FALLO


def test_muestra_real_sigue_ok():
    r = validar_xml(MUESTRA_XML, None, CONFIG_SIN_RED, ahora=T0)
    assert (r.integridad.resultado, r.vigencia.resultado, r.entidad_certificadora.resultado) == (OK, OK, OK)
