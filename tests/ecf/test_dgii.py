import dataclasses
from decimal import Decimal

import pytest
import requests

from ayudantes import MUESTRA_XML, fixture_dgii
from common.ecf.dgii import analizar_respuesta, construir_url_consulta, consultar_dgii, mapear_estado
from common.ecf.lectura import leer_ecf
from common.ecf.modelos import ACEPTADO, ACEPTADO_CONDICIONAL, DESCONOCIDO, PENDIENTE, RECHAZADO


def test_url_desde_xml_igual_al_qr():
    u = construir_url_consulta(leer_ecf(MUESTRA_XML))
    assert u == 'https://ecf.dgii.gov.do/eCF/ConsultaTimbre?RncEmisor=101616202&RncComprador=101107146&ENCF=E310000002882&FechaEmision=10-02-2026&MontoTotal=1250.00&FechaFirma=10-02-2026%2009%3A22%3A21&CodigoSeguridad=BuLkvC'


def tipo32(monto): return dataclasses.replace(leer_ecf(MUESTRA_XML), tipo_ecf='32', monto_total=Decimal(monto))


def test_url_fc(): assert construir_url_consulta(tipo32('1000')).startswith('https://ecf.dgii.gov.do/eCF/ConsultaTimbreFC?RncEmisor=101616202&ENCF=')


def test_url_tipo32_grande(): assert '/ConsultaTimbre?' in construir_url_consulta(tipo32('300000'))


def test_analiza_datos():
    r = analizar_respuesta(200, fixture_dgii('aceptado.html'))
    assert (r.tipo, r.estado_texto, r.razon_social) == ('DATOS', 'Aceptado', 'EMPRESAS ASAVIM S R L')


def test_analiza_no_encontrado(): assert analizar_respuesta(200, fixture_dgii('no_encontrado.html')).tipo == 'NO_ENCONTRADO'


def test_html_inesperado(): assert analizar_respuesta(200, '<html>mantenimiento</html>').tipo == 'ERROR'


def test_http_500(): assert analizar_respuesta(500, '').tipo == 'ERROR'


def test_timeout():
    def lanza(*a, **k): raise requests.Timeout()
    assert consultar_dgii('http://x', http_get=lanza).tipo == 'ERROR'


@pytest.mark.parametrize('texto,esperado', [('Aceptado', ACEPTADO), (' ACEPTADO ', ACEPTADO), ('Aceptado Condicional', ACEPTADO_CONDICIONAL),
    ('Rechazado', RECHAZADO), ('En Proceso', PENDIENTE), ('NO_ENCONTRADO', PENDIENTE), ('Algo raro', DESCONOCIDO), (None, DESCONOCIDO)])
def test_mapeo(texto, esperado): assert mapear_estado(texto) == esperado
