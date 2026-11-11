from datetime import timedelta

from ayudantes import (CONFIG_SIN_RED, DATOS_ACEPTADO, MUESTRA_XML, QR_MUESTRA, T0, ecf_de_prueba, fijo)
from common.ecf import registro
from common.ecf.dgii import RespuestaDGII
from common.ecf.modelos import ERROR_CONSULTA, NO_VERIFICABLE, OK, RECHAZADO, Verificacion, ResultadoValidacionXML
from common.ecf.registro import registrar_comprobante
from common.ecf.seguimiento import ConfigSeguimiento
from seguimiento import ciclo
from seguimiento.ciclo import procesar_ciclo

CFG = ConfigSeguimiento()
SIN_PAUSA = lambda s: None


def reg(db, xml, ahora=T0):
    return registrar_comprobante(db, xml, consultar=fijo(DATOS_ACEPTADO), ahora=ahora,
                                 config_validacion=CONFIG_SIN_RED, config_seguimiento=CFG)


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


def test_revocacion_actualiza_columna_y_json(db_pg, monkeypatch):
    reg(db_pg, ecf_de_prueba('E31A'))
    ok = ResultadoValidacionXML(*(Verificacion(OK) for _ in range(7)), None, None, None)
    monkeypatch.setattr(ciclo, 'validar_xml', lambda *a, **k: ok)
    procesar_ciclo(db_pg, T0 + timedelta(minutes=60), CFG, CONFIG_SIN_RED, fijo(DATOS_ACEPTADO), SIN_PAUSA)
    f = fila(db_pg, 'E31A'); assert f['revocacion'] == OK and f['validacion_detalle']['revocacion']['resultado'] == OK


def test_pausas(db_pg):
    for e in ('E31A', 'E31B', 'E31C'):
        reg(db_pg, ecf_de_prueba(e))
    pausas = []; procesar_ciclo(db_pg, T0 + timedelta(minutes=60), CFG, CONFIG_SIN_RED, fijo(DATOS_ACEPTADO), pausas.append)
    assert pausas == [1, 1]
