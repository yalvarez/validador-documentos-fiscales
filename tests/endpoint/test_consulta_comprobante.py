import pytest
from fastapi.testclient import TestClient

from api import backend
from ayudantes import CONFIG_SIN_RED, DATOS_ACEPTADO, MUESTRA_XML, T0, fijo
from common.ecf.registro import registrar_comprobante
from common.ecf.seguimiento import ConfigSeguimiento

KEY = {'x-api-key': 'clave-prueba'}


@pytest.fixture
def cliente(db_pg, monkeypatch):
    monkeypatch.setattr(backend, 'API_KEYS', ['clave-prueba'])
    monkeypatch.setattr(backend, 'get_db', lambda: db_pg)
    monkeypatch.setattr(db_pg, 'close', lambda: None)  # la fixture db_pg cierra al final
    monkeypatch.setenv('DB_ENGINE', 'postgres')
    return TestClient(backend.app)


def registrar_muestra(db):
    return registrar_comprobante(db, MUESTRA_XML, consultar=fijo(DATOS_ACEPTADO), ahora=T0,
                                 config_validacion=CONFIG_SIN_RED, config_seguimiento=ConfigSeguimiento())


def test_200(cliente, db_pg):
    registrar_muestra(db_pg)
    r = cliente.get('/comprobantes/101616202/E310000002882', headers=KEY)
    j = r.json()
    assert r.status_code == 200 and j['registrado'] is True and j['estado'] == 'ACEPTADO' and j['estado_dgii_texto'] == 'Aceptado'
    assert set(j['validacion']) == {'estructura', 'integridad', 'vigencia', 'entidad_certificadora', 'revocacion', 'cruce', 'comprador'}
    assert j['seguimiento_hasta'] == '2026-11-13T10:00:00-04:00' and j['seguimiento_activo'] is True
    assert j['ultima_consulta_dgii'].endswith('-04:00')


def test_404(cliente, db_pg):
    r = cliente.get('/comprobantes/101616202/E319999999999', headers=KEY)
    assert r.status_code == 404 and r.json() == {'registrado': False}


def test_normaliza_ruta(cliente, db_pg):  # Foco 3
    registrar_muestra(db_pg)
    assert cliente.get('/comprobantes/ 101616202 /e310000002882', headers=KEY).status_code == 200


def test_sin_api_key(cliente):
    assert cliente.get('/comprobantes/1/E31').status_code in (401, 422)


def test_motor_no_postgres(cliente, monkeypatch):
    monkeypatch.setenv('DB_ENGINE', 'sqlite')
    r = cliente.get('/comprobantes/1/E31', headers=KEY)
    assert r.status_code == 503 and r.json() == {'detail': 'Requiere DB_ENGINE=postgres'}


def test_endpoints_existentes_siguen():
    assert {'/validar-factura-pdf-base64', '/validar-factura-pdf-multipart', '/validar-factura-params'} <= {r.path for r in backend.app.routes}
