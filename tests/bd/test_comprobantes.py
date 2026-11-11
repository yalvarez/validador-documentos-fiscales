from datetime import timedelta

import pytest

from ayudantes import MUESTRA_XML, T0, campos_minimos


def test_insert_get_y_conflicto(db_pg):
    cid = db_pg.insert_comprobante(campos_minimos())
    assert db_pg.get_comprobante(' 101616202 ', 'e310000002882')['id'] == cid
    assert db_pg.insert_comprobante(campos_minimos()) is None


def test_bytes_y_json_ida_y_vuelta(db_pg):
    db_pg.insert_comprobante(campos_minimos(validacion_detalle={'integridad': {'resultado': 'OK', 'detalle': ''}}))
    c = db_pg.get_comprobante('101616202', 'E310000002882')
    assert bytes(c['xml_contenido']) == MUESTRA_XML and c['validacion_detalle']['integridad']['resultado'] == 'OK'


def test_columna_desconocida(db_pg):
    with pytest.raises(ValueError):
        db_pg.insert_comprobante({**campos_minimos(), 'hack; DROP': 1})


def test_por_consultar(db_pg):
    db_pg.insert_comprobante(campos_minimos('E31A', proxima_consulta=T0))
    db_pg.insert_comprobante(campos_minimos('E31B', proxima_consulta=T0 + timedelta(hours=1)))
    db_pg.insert_comprobante(campos_minimos('E31C', proxima_consulta=T0, seguimiento_activo=False))
    assert [c['encf'] for c in db_pg.get_comprobantes_por_consultar(T0)] == ['E31A']


def test_historial_ordenado(db_pg):
    cid = db_pg.insert_comprobante(campos_minimos())
    db_pg.insert_historial(cid, 'CONSULTA', fecha=T0 + timedelta(hours=1))
    db_pg.insert_historial(cid, 'REGISTRO', fecha=T0)
    assert [h['tipo'] for h in db_pg.get_historial(cid)] == ['REGISTRO', 'CONSULTA']


def test_transaccion_revierte(db_pg):
    cid = db_pg.insert_comprobante(campos_minimos())
    with pytest.raises(RuntimeError):
        with db_pg.transaccion():
            db_pg.update_comprobante(cid, {'estado': 'ACEPTADO'})
            raise RuntimeError()
    assert db_pg.get_comprobante('101616202', 'E310000002882')['estado'] == 'PENDIENTE'
