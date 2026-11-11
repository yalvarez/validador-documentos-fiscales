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
