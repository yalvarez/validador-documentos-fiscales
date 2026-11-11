from datetime import timedelta

from cryptography.hazmat.primitives.serialization import Encoding

from ayudantes import (CA_PRUEBA, CONFIG_SIN_RED, DATOS_ACEPTADO, MUESTRA_XML, QR_MUESTRA, T0, config_con,
                       ecf_de_prueba, fijo)
from common.ecf import registro
from common.ecf.dgii import RespuestaDGII
from common.ecf.modelos import ERROR_CONSULTA, NO_VERIFICABLE, OK, RECHAZADO, Verificacion, ResultadoValidacionXML
from common.ecf.registro import registrar_comprobante
from common.ecf.seguimiento import ConfigSeguimiento
from seguimiento import ciclo
from seguimiento.ciclo import procesar_ciclo

CFG = ConfigSeguimiento()
SIN_PAUSA = lambda s: None


def reg(db, xml, ahora=T0, config_validacion=CONFIG_SIN_RED):
    return registrar_comprobante(db, xml, consultar=fijo(DATOS_ACEPTADO), ahora=ahora,
                                 config_validacion=config_validacion, config_seguimiento=CFG)


def confiando_en_ca_prueba(tmp_path):
    (tmp_path / 'ca.pem').write_bytes(CA_PRUEBA.public_bytes(Encoding.PEM))
    return config_con(ca_dir=tmp_path)


def fila(db, encf):
    return db.get_comprobante('101616202', encf)


def tipos(db, encf):
    return [h['tipo'] for h in db.get_historial(fila(db, encf)['id'])]


def test_solo_vencidos(db_pg):
    reg(db_pg, ecf_de_prueba('E31A')); reg(db_pg, ecf_de_prueba('E31B'), ahora=T0 + timedelta(minutes=50))
    assert procesar_ciclo(db_pg, T0 + timedelta(minutes=60), CFG, CONFIG_SIN_RED, fijo(DATOS_ACEPTADO), SIN_PAUSA) == 1
    assert fila(db_pg, 'E31A')['proxima_consulta'] == T0 + timedelta(minutes=180) and fila(db_pg, 'E31B')['intentos'] == 1


def test_excepcion_no_detiene_y_aplica_cierre(db_pg):  # Foco 4
    reg(db_pg, ecf_de_prueba('E31A')); reg(db_pg, ecf_de_prueba('E31B'))

    def consultar(u):
        if 'E31A' in u:
            raise RuntimeError('boom')
        return RespuestaDGII('DATOS', 'Rechazado')
    assert procesar_ciclo(db_pg, T0 + timedelta(minutes=60), CFG, CONFIG_SIN_RED, consultar, SIN_PAUSA) == 2
    assert fila(db_pg, 'E31B')['estado'] == RECHAZADO and tipos(db_pg, 'E31A')[-1] == ERROR_CONSULTA
    assert fila(db_pg, 'E31A')['intentos'] == 2   # 1 del registro + 1 del ciclo: la excepción pasó por decidir
    fin = T0 + timedelta(hours=73, minutes=1)
    procesar_ciclo(db_pg, fin, CFG, CONFIG_SIN_RED, consultar, SIN_PAUSA)
    assert fila(db_pg, 'E31A')['seguimiento_activo'] is False


def test_reintenta_revocacion_y_conserva_cruce(db_pg, monkeypatch):
    monkeypatch.setattr(registro, 'extraer_qr_params', lambda b: QR_MUESTRA)
    registrar_comprobante(db_pg, MUESTRA_XML, pdf_bytes=b'%PDF', consultar=fijo(DATOS_ACEPTADO), ahora=T0,
                          config_validacion=CONFIG_SIN_RED, config_seguimiento=CFG)
    assert fila(db_pg, 'E310000002882')['revocacion'] == NO_VERIFICABLE
    procesar_ciclo(db_pg, T0 + timedelta(minutes=60), CFG, CONFIG_SIN_RED, fijo(DATOS_ACEPTADO), SIN_PAUSA)
    f = fila(db_pg, 'E310000002882')
    assert f['validacion_detalle']['cruce']['resultado'] == OK          # el cruce no se pierde al revalidar
    assert f['revocacion'] == f['validacion_detalle']['revocacion']['resultado']


def test_revocacion_actualiza_columna_y_json(db_pg, monkeypatch, tmp_path):
    reg(db_pg, ecf_de_prueba('E31A'), config_validacion=confiando_en_ca_prueba(tmp_path))
    assert fila(db_pg, 'E31A')['entidad_certificadora'] == OK
    ok = ResultadoValidacionXML(*(Verificacion(OK) for _ in range(7)), None, None, None)
    monkeypatch.setattr(ciclo, 'validar_xml', lambda *a, **k: ok)
    procesar_ciclo(db_pg, T0 + timedelta(minutes=60), CFG, CONFIG_SIN_RED, fijo(DATOS_ACEPTADO), SIN_PAUSA)
    f = fila(db_pg, 'E31A'); assert f['revocacion'] == OK and f['validacion_detalle']['revocacion']['resultado'] == OK


def test_pausas(db_pg):
    for e in ('E31A', 'E31B', 'E31C'):
        reg(db_pg, ecf_de_prueba(e))
    pausas = []; procesar_ciclo(db_pg, T0 + timedelta(minutes=60), CFG, CONFIG_SIN_RED, fijo(DATOS_ACEPTADO), pausas.append)
    assert pausas == [1, 1]


def test_reloj_por_comprobante(db_pg, monkeypatch, tmp_path):  # M4
    cfg_val = confiando_en_ca_prueba(tmp_path)
    reg(db_pg, ecf_de_prueba('E31A'), config_validacion=cfg_val)
    reg(db_pg, ecf_de_prueba('E31B'), config_validacion=cfg_val)
    inicio = T0 + timedelta(minutes=60)
    marcas = iter([inicio + timedelta(minutes=10), inicio + timedelta(minutes=25)])
    vistos = []
    real = ciclo.validar_xml
    monkeypatch.setattr(ciclo, 'validar_xml', lambda x, q, c, ahora: vistos.append(ahora) or real(x, q, c, ahora))
    assert procesar_ciclo(db_pg, inicio, CFG, cfg_val, fijo(DATOS_ACEPTADO), SIN_PAUSA,
                          reloj=lambda: next(marcas)) == 2
    a, b = fila(db_pg, 'E31A'), fila(db_pg, 'E31B')
    assert a['ultima_consulta_dgii'] == inicio + timedelta(minutes=10)
    assert b['ultima_consulta_dgii'] == inicio + timedelta(minutes=25)
    assert vistos == [inicio + timedelta(minutes=10), inicio + timedelta(minutes=25)]
    assert db_pg.get_historial(b['id'])[-1]['fecha'] == inicio + timedelta(minutes=25)


def test_sin_reloj_usa_ahora_para_todos(db_pg):  # M4, compatibilidad
    reg(db_pg, ecf_de_prueba('E31A')); reg(db_pg, ecf_de_prueba('E31B'))
    inicio = T0 + timedelta(minutes=60)
    procesar_ciclo(db_pg, inicio, CFG, CONFIG_SIN_RED, fijo(DATOS_ACEPTADO), SIN_PAUSA)
    assert fila(db_pg, 'E31A')['ultima_consulta_dgii'] == fila(db_pg, 'E31B')['ultima_consulta_dgii'] == inicio


def test_fila_reemplazada_durante_la_consulta_no_se_pisa(db_pg):  # M5
    c = reg(db_pg, ecf_de_prueba('E31A'))
    antes = len(db_pg.get_historial(c['id']))

    def consultar(url):
        db_pg.update_comprobante(c['id'], {'xml_hash_sha256': 'b' * 64, 'intentos': 7})
        return RespuestaDGII('DATOS', 'Rechazado')
    assert procesar_ciclo(db_pg, T0 + timedelta(minutes=60), CFG, CONFIG_SIN_RED, consultar, SIN_PAUSA) == 1
    f = fila(db_pg, 'E31A')
    assert f['intentos'] == 7 and f['estado'] != RECHAZADO and f['xml_hash_sha256'] == 'b' * 64
    assert len(db_pg.get_historial(c['id'])) == antes


def test_no_revalida_si_entidad_no_es_ok(db_pg, monkeypatch):  # M6
    reg(db_pg, ecf_de_prueba('E31A'))
    f = fila(db_pg, 'E31A')
    assert f['revocacion'] == NO_VERIFICABLE and f['entidad_certificadora'] != OK
    llamadas = []
    monkeypatch.setattr(ciclo, 'validar_xml', lambda *a, **k: llamadas.append(a))
    procesar_ciclo(db_pg, T0 + timedelta(minutes=60), CFG, CONFIG_SIN_RED, fijo(DATOS_ACEPTADO), SIN_PAUSA)
    assert llamadas == [] and fila(db_pg, 'E31A')['intentos'] == 2
