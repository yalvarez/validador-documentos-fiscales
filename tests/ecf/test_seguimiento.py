from datetime import timedelta

from ayudantes import DATOS_ACEPTADO, ERROR_R, NO_ENCONTRADO_R, T0
from api.parametros_manager import ParametrosManager
from common.ecf.dgii import RespuestaDGII
from common.ecf.modelos import (ACEPTADO, CAMBIO_ESTADO, CONSULTA, ERROR_CONSULTA, NO_ENCONTRADO,
                                PENDIENTE)
from common.ecf.seguimiento import (ConfigSeguimiento, calendario_inicial,
                                    config_seguimiento_desde_parametros, decidir)

CFG = ConfigSeguimiento()


def base(estado=PENDIENTE):
    return {'estado': estado, **calendario_inicial(T0, CFG)}


def recorrer(cfg, respuesta=DATOS_ACEPTADO):
    c = {'estado': PENDIENTE, **calendario_inicial(T0, cfg)}
    ahora = c['proxima_consulta']
    gaps = []
    while c['seguimiento_activo']:
        c.update(decidir(c, respuesta, ahora, cfg).campos)
        if c['seguimiento_activo']:
            gaps.append((c['proxima_consulta'] - ahora).total_seconds() / 60)
            ahora = c['proxima_consulta']
    return c, ahora, gaps


def test_intervalos_crecientes():
    c, fin, gaps = recorrer(CFG)
    assert gaps == [120, 240, 480, 960, 1440, 1020] and fin == T0 + timedelta(hours=72) and c['estado'] == ACEPTADO


def test_factor_1():
    assert set(recorrer(ConfigSeguimiento(factor=1))[2]) == {60}


def test_error_no_cambia_estado_ni_avanza():
    d = decidir(base(ACEPTADO), ERROR_R, T0 + timedelta(hours=1), CFG)
    assert d.campos == {'intentos': 1} and [e.tipo for e in d.eventos] == [ERROR_CONSULTA]


def test_no_encontrado_al_cierre():
    d = decidir(base(), NO_ENCONTRADO_R, T0 + timedelta(hours=72), CFG)
    assert d.campos['estado'] == NO_ENCONTRADO and d.campos['seguimiento_activo'] is False


def test_en_proceso_al_cierre_queda_pendiente():
    d = decidir(base(), RespuestaDGII('DATOS', 'En Proceso'), T0 + timedelta(hours=72), CFG)
    assert d.campos['estado'] == PENDIENTE and d.campos['seguimiento_activo'] is False


def test_error_al_cierre():
    hasta = T0 + timedelta(hours=72)
    assert 'seguimiento_activo' not in decidir(base(), ERROR_R, hasta + timedelta(minutes=30), CFG).campos
    d = decidir(base(ACEPTADO), ERROR_R, hasta + timedelta(minutes=61), CFG)
    assert d.campos['seguimiento_activo'] is False and 'estado' not in d.campos
    assert d.eventos[-1].detalle == 'seguimiento cerrado sin consulta válida'


def test_retroceso():
    d = decidir(base(ACEPTADO), NO_ENCONTRADO_R, T0 + timedelta(hours=5), CFG)
    assert d.campos['estado'] == PENDIENTE and [e.tipo for e in d.eventos] == [CONSULTA, CAMBIO_ESTADO]


def test_parametros(db_pg):
    db_pg.set_param('SEGUIMIENTO_FACTOR', 'abc')
    db_pg.set_param('SEGUIMIENTO_DURACION_MAX_HORAS', '24')
    cfg = config_seguimiento_desde_parametros(ParametrosManager(db_pg))
    assert cfg.factor == 2.0 and cfg.duracion_max_horas == 24
