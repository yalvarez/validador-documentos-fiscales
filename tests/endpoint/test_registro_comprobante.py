import functools

import pytest
from fastapi.testclient import TestClient

from api import backend
from ayudantes import CONFIG_SIN_RED, DATOS_ACEPTADO, MUESTRA_PDF, MUESTRA_XML, T0, fijo
from common.ecf import registro
from common.ecf.seguimiento import ConfigSeguimiento

KEY = {'x-api-key': 'clave-prueba'}


@pytest.fixture
def cliente(db_pg, monkeypatch):
    monkeypatch.setattr(backend, 'API_KEYS', ['clave-prueba'])
    monkeypatch.setattr(backend, 'get_db', lambda: db_pg)
    monkeypatch.setattr(db_pg, 'close', lambda: None)
    monkeypatch.setenv('DB_ENGINE', 'postgres')
    monkeypatch.setattr(backend, 'registrar_comprobante', functools.partial(
        registro.registrar_comprobante, consultar=fijo(DATOS_ACEPTADO), ahora=T0,
        config_validacion=CONFIG_SIN_RED, config_seguimiento=ConfigSeguimiento()))
    return TestClient(backend.app)


def test_solo_xml_registra(cliente, db_pg):
    r = cliente.post('/comprobantes', headers=KEY, files={'xml': ('a.xml', MUESTRA_XML, 'application/xml')})
    j = r.json()
    assert r.status_code == 200, j
    assert j['registrado'] is True and j['rnc_emisor'] == '101616202' and j['encf'] == 'E310000002882'
    assert j['estado'] == 'ACEPTADO'
    assert j['validacion']['cruce']['resultado'] == 'NO_VERIFICABLE'
    assert db_pg.get_comprobante('101616202', 'E310000002882')['origen'] == 'api'
    # el GET devuelve lo mismo
    assert cliente.get('/comprobantes/101616202/E310000002882', headers=KEY).json() == j


def test_xml_y_pdf_cruza(cliente, db_pg):
    r = cliente.post('/comprobantes', headers=KEY, files={
        'xml': ('a.xml', MUESTRA_XML, 'application/xml'),
        'pdf': ('a.pdf', MUESTRA_PDF.read_bytes(), 'application/pdf')})
    assert r.status_code == 200, r.json()
    assert r.json()['validacion']['cruce']['resultado'] != 'NO_VERIFICABLE'
    assert db_pg.get_comprobante('101616202', 'E310000002882')['qr_params']


def test_xml_ilegible_422(cliente, db_pg):
    r = cliente.post('/comprobantes', headers=KEY, files={'xml': ('a.xml', b'<no-es-un-ecf/>', 'application/xml')})
    assert r.status_code == 422 and 'detail' in r.json()


def test_xml_no_es_xml_422(cliente, db_pg):
    r = cliente.post('/comprobantes', headers=KEY, files={'xml': ('a.xml', b'hola', 'application/xml')})
    assert r.status_code == 422


def test_sin_xml_422(cliente):
    assert cliente.post('/comprobantes', headers=KEY).status_code == 422


def test_archivo_muy_grande_413(cliente, monkeypatch):
    monkeypatch.setattr(backend, 'MAX_BYTES_ARCHIVO', 10)
    r = cliente.post('/comprobantes', headers=KEY, files={'xml': ('a.xml', MUESTRA_XML, 'application/xml')})
    assert r.status_code == 413


def test_sin_api_key(cliente):
    r = cliente.post('/comprobantes', files={'xml': ('a.xml', MUESTRA_XML, 'application/xml')})
    assert r.status_code in (401, 422)


def test_motor_no_postgres(cliente, monkeypatch):
    monkeypatch.setenv('DB_ENGINE', 'sqlite')
    r = cliente.post('/comprobantes', headers=KEY, files={'xml': ('a.xml', MUESTRA_XML, 'application/xml')})
    assert r.status_code == 503
