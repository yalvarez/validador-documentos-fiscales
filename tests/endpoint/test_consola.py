"""Endpoints de lectura y parámetros que usa la consola web (/client)."""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from api import backend
from ayudantes import (CONFIG_SIN_RED, DATOS_ACEPTADO, ERROR_R, MUESTRA_XML, T0, ecf_de_prueba, fijo)
from common.ecf.registro import registrar_comprobante
from common.ecf.seguimiento import ConfigSeguimiento

KEY = {'x-api-key': 'clave-prueba'}


@pytest.fixture
def cliente(db_pg, monkeypatch):
    monkeypatch.setattr(backend, 'API_KEYS', ['clave-prueba'])
    monkeypatch.setattr(backend, 'get_db', lambda: db_pg)
    monkeypatch.setattr(db_pg, 'close', lambda: None)
    monkeypatch.setenv('DB_ENGINE', 'postgres')
    return TestClient(backend.app)


def reg(db, xml=MUESTRA_XML, ahora=T0, consultar=fijo(DATOS_ACEPTADO)):
    return registrar_comprobante(db, xml, consultar=consultar, ahora=ahora,
                                 config_validacion=CONFIG_SIN_RED, config_seguimiento=ConfigSeguimiento())


# --- GET /comprobantes ---

def test_lista_vacia(cliente, db_pg):
    r = cliente.get('/comprobantes', headers=KEY)
    assert r.status_code == 200 and r.json() == {'total': 0, 'items': []}


def test_lista_resumen_y_orden_mas_reciente_primero(cliente, db_pg):
    reg(db_pg)
    reg(db_pg, ecf_de_prueba('E310000000101'), ahora=T0 + timedelta(hours=1), consultar=fijo(ERROR_R))
    j = cliente.get('/comprobantes', headers=KEY).json()
    assert j['total'] == 2 and [i['encf'] for i in j['items']] == ['E310000000101', 'E310000002882']
    muestra = j['items'][1]
    assert muestra['estado'] == 'ACEPTADO' and muestra['razon_social_emisor'] == 'EMPRESAS ASAVIM S R L'
    assert muestra['monto_total'] == '1250.00' and muestra['tipo_ecf'] == '31' and muestra['origen'] == 'api'
    assert list(muestra['verificaciones']) == ['estructura', 'integridad', 'vigencia', 'entidad_certificadora',
                                               'revocacion', 'cruce', 'comprador']
    assert muestra['verificaciones']['integridad'] == 'OK'
    assert muestra['creado_en'].endswith('-04:00')
    assert 'xml_contenido' not in muestra


def test_lista_filtros(cliente, db_pg):
    reg(db_pg)
    reg(db_pg, ecf_de_prueba('E310000000102'), consultar=fijo(ERROR_R))  # CA de prueba: entidad = FALLO
    assert [i['encf'] for i in cliente.get('/comprobantes?estado=PENDIENTE', headers=KEY).json()['items']] == ['E310000000102']
    assert cliente.get('/comprobantes?con_fallo=true', headers=KEY).json()['total'] == 1
    assert cliente.get('/comprobantes?q=asavim', headers=KEY).json()['total'] == 2
    assert [i['encf'] for i in cliente.get('/comprobantes?q=2882', headers=KEY).json()['items']] == ['E310000002882']
    assert cliente.get('/comprobantes?q=101616202', headers=KEY).json()['total'] == 2


def test_lista_paginada(cliente, db_pg):
    for n in range(3):
        reg(db_pg, ecf_de_prueba(f'E31000000020{n}'), ahora=T0 + timedelta(minutes=n), consultar=fijo(ERROR_R))
    j = cliente.get('/comprobantes?limite=2&desde=2', headers=KEY).json()
    assert j['total'] == 3 and [i['encf'] for i in j['items']] == ['E310000000200']


@pytest.mark.parametrize('qs', ['limite=0', 'limite=201', 'desde=-1'])
def test_lista_rechaza_paginacion_invalida(cliente, qs):
    assert cliente.get(f'/comprobantes?{qs}', headers=KEY).status_code == 422


def test_lista_sin_api_key(cliente):
    assert cliente.get('/comprobantes').status_code in (401, 422)


# --- GET /comprobantes/{rnc}/{encf}/historial ---

def test_historial(cliente, db_pg):
    reg(db_pg)
    r = cliente.get('/comprobantes/101616202/e310000002882/historial', headers=KEY)
    assert r.status_code == 200
    eventos = r.json()
    assert [e['tipo'] for e in eventos] == ['REGISTRO', 'CONSULTA', 'CAMBIO_ESTADO']
    assert eventos[2]['estado_nuevo'] == 'ACEPTADO' and eventos[0]['fecha'].endswith('-04:00')


def test_historial_404(cliente, db_pg):
    r = cliente.get('/comprobantes/1/E31/historial', headers=KEY)
    assert r.status_code == 404 and r.json() == {'registrado': False}


# --- /parametros ---

def test_parametros_lista_con_defaults(cliente, db_pg):
    j = {p['clave']: p for p in cliente.get('/parametros', headers=KEY).json()}
    assert set(j) == {'RNC_TERPEL', 'SEGUIMIENTO_INTERVALO_INICIAL_MIN', 'SEGUIMIENTO_FACTOR',
                      'SEGUIMIENTO_INTERVALO_MAX_MIN', 'SEGUIMIENTO_DURACION_MAX_HORAS', 'SEGUIMIENTO_CICLO_SEG'}
    assert j['SEGUIMIENTO_FACTOR']['valor'] is None and j['SEGUIMIENTO_FACTOR']['por_defecto'] == '2.0'
    assert j['RNC_TERPEL']['descripcion']


def test_parametro_actualizar_y_leer(cliente, db_pg):
    r = cliente.put('/parametros/RNC_TERPEL', headers=KEY, json={'valor': ' 101016681 '})
    assert r.status_code == 200 and r.json()['valor'] == '101016681'
    assert db_pg.get_param('RNC_TERPEL') == '101016681'
    j = {p['clave']: p for p in cliente.get('/parametros', headers=KEY).json()}
    assert j['RNC_TERPEL']['valor'] == '101016681' and j['RNC_TERPEL']['ultima_actualizacion']


def test_parametro_vacio_vuelve_al_defecto(cliente, db_pg):
    cliente.put('/parametros/SEGUIMIENTO_CICLO_SEG', headers=KEY, json={'valor': '600'})
    assert cliente.put('/parametros/SEGUIMIENTO_CICLO_SEG', headers=KEY, json={'valor': ''}).status_code == 200
    assert db_pg.get_param('SEGUIMIENTO_CICLO_SEG') is None


@pytest.mark.parametrize('clave,valor', [
    ('RNC_TERPEL', '12345'), ('RNC_TERPEL', 'abcdefghi'),
    ('SEGUIMIENTO_FACTOR', '0.5'), ('SEGUIMIENTO_FACTOR', 'nan'), ('SEGUIMIENTO_INTERVALO_INICIAL_MIN', '0'),
    ('SEGUIMIENTO_INTERVALO_INICIAL_MIN', '1.5'), ('SEGUIMIENTO_CICLO_SEG', '-3')])
def test_parametro_invalido_422(cliente, db_pg, clave, valor):
    r = cliente.put(f'/parametros/{clave}', headers=KEY, json={'valor': valor})
    assert r.status_code == 422 and db_pg.get_param(clave) is None


def test_parametro_no_editable_404(cliente, db_pg):
    r = cliente.put('/parametros/CA_CONFIANZA_DIR', headers=KEY, json={'valor': '/tmp'})
    assert r.status_code == 404 and db_pg.get_param('CA_CONFIANZA_DIR') is None


def test_busqueda_trata_comodines_como_texto(cliente, db_pg):
    reg(db_pg)
    assert cliente.get('/comprobantes', params={'q': '%'}, headers=KEY).json()['total'] == 0
    assert cliente.get('/comprobantes', params={'q': '_'}, headers=KEY).json()['total'] == 0
