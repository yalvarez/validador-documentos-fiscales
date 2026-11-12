import pytest
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


def test_factor_menor_que_uno_usa_defecto(caplog):  # T10
    for valor in ('0.5', '0.99'):
        cfg = config_seguimiento_desde_parametros({'SEGUIMIENTO_FACTOR': valor})
        assert cfg.factor == 2.0
    assert 'SEGUIMIENTO_FACTOR' in caplog.text
    assert config_seguimiento_desde_parametros({'SEGUIMIENTO_FACTOR': '1'}).factor == 1.0
    assert config_seguimiento_desde_parametros({'SEGUIMIENTO_FACTOR': '1.5'}).factor == 1.5


@pytest.mark.parametrize('clave,valor', [
    ('SEGUIMIENTO_CICLO_SEG', '86401'), ('SEGUIMIENTO_CICLO_SEG', '99999999999'),
    ('SEGUIMIENTO_DURACION_MAX_HORAS', '8761'), ('SEGUIMIENTO_INTERVALO_INICIAL_MIN', '10081'),
    ('SEGUIMIENTO_INTERVALO_MAX_MIN', '10081'), ('SEGUIMIENTO_FACTOR', '10.5'), ('SEGUIMIENTO_FACTOR', '1e300')])
def test_valor_fuera_de_rango_usa_defecto(clave, valor, caplog):
    assert config_seguimiento_desde_parametros({clave: valor}) == ConfigSeguimiento()
    assert clave in caplog.text


def test_maximos_se_aceptan():
    cfg = config_seguimiento_desde_parametros({
        'SEGUIMIENTO_CICLO_SEG': '86400', 'SEGUIMIENTO_DURACION_MAX_HORAS': '8760',
        'SEGUIMIENTO_INTERVALO_INICIAL_MIN': '10080', 'SEGUIMIENTO_INTERVALO_MAX_MIN': '10080',
        'SEGUIMIENTO_FACTOR': '10'})
    assert (cfg.ciclo_seg, cfg.duracion_max_horas, cfg.intervalo_inicial_min, cfg.intervalo_max_min, cfg.factor) == \
        (86400, 8760, 10080, 10080, 10.0)


def test_digitos_no_ascii_se_rechazan():
    assert config_seguimiento_desde_parametros({'SEGUIMIENTO_CICLO_SEG': '٦٠٠'}).ciclo_seg == 300
