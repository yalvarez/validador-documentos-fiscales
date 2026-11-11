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


ORDEN_CANONICO = ['estructura', 'integridad', 'vigencia', 'entidad_certificadora', 'revocacion', 'cruce',
                  'comprador']


def test_validacion_en_orden_canonico(cliente, db_pg):  # M12a
    registrar_muestra(db_pg)
    j = cliente.get('/comprobantes/101616202/E310000002882', headers=KEY).json()
    assert list(j['validacion']) == ORDEN_CANONICO


class _DBFalsa:
    def __init__(self):
        self.cerrada = 0
        self.facturas = []

    def insert_factura(self, f):
        self.facturas.append(f)

    def close(self):
        self.cerrada += 1


class _PDFSinQR:
    def __init__(self, ruta):
        pass

    def extract_qr_url(self):
        return None

    def extract_qr_params(self):
        return {}


def test_endpoints_pdf_cierran_la_conexion(monkeypatch):  # M8
    import base64 as b64
    monkeypatch.setattr(backend, 'API_KEYS', ['clave-prueba'])
    monkeypatch.setattr(backend, 'PDFProcessor', _PDFSinQR)
    dbs = []
    monkeypatch.setattr(backend, 'get_db', lambda: dbs.append(_DBFalsa()) or dbs[-1])
    c = TestClient(backend.app)
    r1 = c.post('/validar-factura-pdf-base64', headers=KEY,
                json={'pdf_base64': b64.b64encode(b'%PDF').decode()})
    r2 = c.post('/validar-factura-pdf-multipart', headers=KEY, files={'file': ('a.pdf', b'%PDF')})
    assert r1.status_code == 200 and r2.status_code == 200
    assert [d.cerrada for d in dbs] == [1, 1] and all(len(d.facturas) == 1 for d in dbs)
