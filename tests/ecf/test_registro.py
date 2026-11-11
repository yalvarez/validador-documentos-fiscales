from datetime import timedelta
from decimal import Decimal

import pytest

from ayudantes import (CONFIG_SIN_RED, DATOS_ACEPTADO, ERROR_R, MUESTRA_XML, QR_MUESTRA, T0, fijo)
from common.ecf import registro
from common.ecf.dgii import construir_url_consulta
from common.ecf.lectura import ErrorLecturaECF, leer_ecf
from common.ecf.modelos import (ACEPTADO, CAMBIO_ESTADO, CONSULTA, DOCUMENTO_REEMPLAZADO, ERROR_CONSULTA,
                                FALLO, NO_VERIFICABLE, OK, PENDIENTE, REGISTRO)
from common.ecf.registro import registrar_comprobante
from common.ecf.seguimiento import ConfigSeguimiento


def reg(db, xml=MUESTRA_XML, **kw):
    kw.setdefault('consultar', fijo(DATOS_ACEPTADO)); kw.setdefault('ahora', T0)
    kw.setdefault('config_validacion', CONFIG_SIN_RED); kw.setdefault('config_seguimiento', ConfigSeguimiento())
    return registrar_comprobante(db, xml, **kw)


def tipos(db, cid): return [h['tipo'] for h in db.get_historial(cid)]


def test_nuevo_aceptado(db_pg):
    c = reg(db_pg)
    assert (c['estado'], c['seguimiento_activo'], c['proxima_consulta'], c['intentos']) == (ACEPTADO, True, T0 + timedelta(minutes=60), 1)
    assert c['integridad'] == OK and bytes(c['xml_contenido']) == MUESTRA_XML
    assert tipos(db_pg, c['id']) == [REGISTRO, CONSULTA, CAMBIO_ESTADO]


def test_url_viene_del_xml_no_del_qr(db_pg, monkeypatch):
    monkeypatch.setattr(registro, 'extraer_qr_params', lambda b: {**QR_MUESTRA, 'MontoTotal': '9999'})
    urls = []
    c = reg(db_pg, pdf_bytes=b'%PDF', consultar=lambda u: urls.append(u) or DATOS_ACEPTADO)
    assert urls == [construir_url_consulta(leer_ecf(MUESTRA_XML))] and c['validacion_detalle']['cruce']['resultado'] == FALLO


def test_pdf_corrupto_no_aborta(db_pg): assert reg(db_pg, pdf_bytes=b'no es pdf')['validacion_detalle']['cruce']['resultado'] == NO_VERIFICABLE


def test_dgii_caida(db_pg):
    c = reg(db_pg, consultar=fijo(ERROR_R)); assert c['estado'] == PENDIENTE and tipos(db_pg, c['id']) == [REGISTRO, ERROR_CONSULTA]


def test_reenvio_identico(db_pg):  # Foco 5
    a = reg(db_pg); b = reg(db_pg, ahora=T0 + timedelta(hours=5), consultar=fijo(ERROR_R))
    assert a['id'] == b['id'] and b['proxima_consulta'] == a['proxima_consulta'] and b['estado'] == ACEPTADO
    assert DOCUMENTO_REEMPLAZADO not in tipos(db_pg, a['id'])


def test_reenvio_distinto(db_pg):
    a = reg(db_pg); alterado = MUESTRA_XML.replace(b'<MontoTotal>1250</MontoTotal>', b'<MontoTotal>9250</MontoTotal>')
    b = reg(db_pg, alterado, ahora=T0 + timedelta(hours=1))
    assert b['id'] == a['id'] and b['integridad'] == FALLO and b['proxima_consulta'] == a['proxima_consulta']
    assert b['monto_total'] == Decimal('9250') and 'MontoTotal=9250.00' in b['url_consulta']
    assert tipos(db_pg, a['id'])[-1] == DOCUMENTO_REEMPLAZADO


def test_normaliza_identificacion(db_pg):  # Foco 3
    xml = MUESTRA_XML.replace(b'<eNCF>E310000002882</eNCF>', b'<eNCF> e310000002882 </eNCF>')
    assert reg(db_pg, xml)['encf'] == 'E310000002882'


def test_xml_ilegible(db_pg):
    with pytest.raises(ErrorLecturaECF): reg(db_pg, b'basura')
