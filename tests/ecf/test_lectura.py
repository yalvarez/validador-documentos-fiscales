from datetime import datetime
from decimal import Decimal

import pytest

from ayudantes import MUESTRA_XML, XML_SIN_FIRMA, muestra_en
from common.ecf.lectura import ErrorLecturaECF, leer_ecf
from common.ecf.modelos import ZONA_RD


def test_lee_muestra():
    d = leer_ecf(MUESTRA_XML)
    assert (d.rnc_emisor, d.encf, d.rnc_comprador, d.tipo_ecf) == ('101616202', 'E310000002882', '101107146', '31')
    assert d.monto_total == Decimal('1250') and d.fecha_firma_texto == '10-02-2026 09:22:21'
    assert d.fecha_firma == datetime(2026, 2, 10, 9, 22, 21, tzinfo=ZONA_RD)
    assert d.codigo_seguridad == 'BuLkvC' and len(d.certificados_der) == 1


@pytest.mark.parametrize('b', [b'\xef\xbb\xbf' + MUESTRA_XML, b'  \n' + MUESTRA_XML, muestra_en('ISO-8859-1')])  # Foco 1
def test_variantes_de_codificacion(b):
    assert leer_ecf(b).encf == 'E310000002882'


def test_iso_realmente_recodificado():
    assert b'encoding="ISO-8859-1"' in muestra_en('ISO-8859-1')


def test_sin_certificado_ni_fecha_firma():
    d = leer_ecf(XML_SIN_FIRMA.replace(b'<FechaHoraFirma>10-02-2026 09:22:21</FechaHoraFirma>', b''))
    assert d.certificados_der == [] and d.fecha_firma is None and d.codigo_seguridad is None


def test_xml_mal_formado():
    with pytest.raises(ErrorLecturaECF):
        leer_ecf(b'<ECF><Encabezado>')
