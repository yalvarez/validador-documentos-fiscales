from datetime import timedelta
from decimal import Decimal

import pytest

from cryptography.hazmat.primitives.serialization import Encoding

from ayudantes import (CA_PRUEBA, HOJA_PRUEBA, HOJA_PRUEBA_KEY, XML_SIN_FIRMA, config_con, ecf_de_prueba,
                       CONFIG_SIN_RED, DATOS_ACEPTADO, ERROR_R, MUESTRA_XML, QR_MUESTRA, T0, fijo)
from common.ecf import registro
from common.ecf.dgii import construir_url_consulta
from common.ecf.lectura import ErrorLecturaECF, leer_ecf
from common.ecf.modelos import (ACEPTADO, CAMBIO_ESTADO, CONSULTA, DOCUMENTO_RECHAZADO, DOCUMENTO_REEMPLAZADO,
                                ERROR_CONSULTA,
                                FALLO, NO_VERIFICABLE, OK, PENDIENTE, RECHAZADO, REGISTRO)
from common.ecf.dgii import RespuestaDGII
from common.ecf.registro import registrar_comprobante
from pki import crear_ca, crear_hoja, firmar_ecf
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


def test_reenvio_distinto_invalido_se_rechaza(db_pg):
    a = reg(db_pg); alterado = MUESTRA_XML.replace(b'<MontoTotal>1250</MontoTotal>', b'<MontoTotal>9250</MontoTotal>')
    b = reg(db_pg, alterado, ahora=T0 + timedelta(hours=1))
    assert b['id'] == a['id'] and b['estado'] == ACEPTADO and b['monto_total'] == Decimal('1250')
    assert bytes(b['xml_contenido']) == MUESTRA_XML and b['integridad'] == OK
    assert b['proxima_consulta'] == a['proxima_consulta']
    assert tipos(db_pg, a['id'])[-1] == DOCUMENTO_RECHAZADO


def _confiando_en(ca, tmp_path):
    (tmp_path / 'ca.pem').write_bytes(ca.public_bytes(Encoding.PEM))
    return config_con(ca_dir=tmp_path)


def test_reemplazo_firmado_por_ca_no_confiable_se_rechaza(db_pg, tmp_path):
    cfg = _confiando_en(CA_PRUEBA, tmp_path)
    a = reg(db_pg, ecf_de_prueba('E310000000007'), config_validacion=cfg)
    assert a['entidad_certificadora'] == OK
    ca_k, ca_c = crear_ca('CA ATACANTE')
    hoja_k, hoja_c = crear_hoja(ca_k, ca_c, T0 - timedelta(days=30), T0 + timedelta(days=365))
    xml = XML_SIN_FIRMA.replace(b'<eNCF>E310000002882</eNCF>', b'<eNCF>E310000000007</eNCF>')
    xml = xml.replace(b'<MontoTotal>1250</MontoTotal>', b'<MontoTotal>1</MontoTotal>')
    b = reg(db_pg, firmar_ecf(xml, hoja_k, hoja_c, T0), config_validacion=cfg, ahora=T0 + timedelta(hours=1))
    assert b['xml_hash_sha256'] == a['xml_hash_sha256'] and b['monto_total'] == a['monto_total']
    assert tipos(db_pg, a['id'])[-1] == DOCUMENTO_RECHAZADO


def test_reemplazo_aceptado(db_pg, tmp_path):
    cfg = _confiando_en(CA_PRUEBA, tmp_path)
    a = reg(db_pg, ecf_de_prueba('E310000000008'), config_validacion=cfg, origen='email', referencia_origen='m1')
    assert a['estado'] == ACEPTADO
    xml = XML_SIN_FIRMA.replace(b'<eNCF>E310000002882</eNCF>', b'<eNCF>E310000000008</eNCF>')
    xml = xml.replace(b'<MontoTotal>1250</MontoTotal>', b'<MontoTotal>9250</MontoTotal>')
    ahora = T0 + timedelta(hours=1)
    b = reg(db_pg, firmar_ecf(xml, HOJA_PRUEBA_KEY, HOJA_PRUEBA, T0), config_validacion=cfg, ahora=ahora,
            origen='api', referencia_origen='otro')
    assert b['id'] == a['id'] and b['estado'] == ACEPTADO and b['proxima_consulta'] == ahora
    assert b['monto_total'] == Decimal('9250') and 'MontoTotal=9250.00' in b['url_consulta']
    assert b['seguimiento_hasta'] == a['seguimiento_hasta'] and b['intentos'] == a['intentos'] + 1
    assert b['intervalo_actual_min'] == a['intervalo_actual_min']
    assert (b['origen'], b['referencia_origen']) == ('email', 'm1')
    assert b['razon_social_emisor'] == a['razon_social_emisor']
    assert tipos(db_pg, a['id'])[-4:] == [CAMBIO_ESTADO, DOCUMENTO_REEMPLAZADO, CONSULTA, CAMBIO_ESTADO]


def test_reemplazo_aceptado_con_seguimiento_inactivo(db_pg, tmp_path):
    cfg = _confiando_en(CA_PRUEBA, tmp_path)
    a = reg(db_pg, ecf_de_prueba('E310000000009'), config_validacion=cfg)
    db_pg.update_comprobante(a['id'], {'seguimiento_activo': False})
    xml = XML_SIN_FIRMA.replace(b'<eNCF>E310000002882</eNCF>', b'<eNCF>E310000000009</eNCF>')
    xml = xml.replace(b'<MontoTotal>1250</MontoTotal>', b'<MontoTotal>9250</MontoTotal>')
    b = reg(db_pg, firmar_ecf(xml, HOJA_PRUEBA_KEY, HOJA_PRUEBA, T0), config_validacion=cfg,
            ahora=T0 + timedelta(hours=1), consultar=fijo(RespuestaDGII('DATOS', 'Rechazado')))
    assert b['estado'] == RECHAZADO and b['seguimiento_activo'] is False
    assert b['proxima_consulta'] == a['proxima_consulta'] and b['seguimiento_hasta'] == a['seguimiento_hasta']


def test_consultar_lanza_conserva_registro(db_pg):
    def falla(url): raise RuntimeError('boom')
    c = reg(db_pg, consultar=falla)
    assert c['estado'] == PENDIENTE and tipos(db_pg, c['id']) == [REGISTRO, ERROR_CONSULTA]
    assert 'boom' in db_pg.get_historial(c['id'])[-1]['detalle']
    reg(db_pg, consultar=falla)
    assert tipos(db_pg, c['id']) == [REGISTRO, ERROR_CONSULTA]


def test_reenvio_autocorrige_registro_faltante(db_pg):
    c = reg(db_pg)
    db_pg.execute("DELETE FROM comprobante_historial WHERE tipo = 'REGISTRO'")
    reg(db_pg)
    assert REGISTRO in tipos(db_pg, c['id'])


def test_normaliza_identificacion(db_pg):  # Foco 3
    xml = MUESTRA_XML.replace(b'<eNCF>E310000002882</eNCF>', b'<eNCF> e310000002882 </eNCF>')
    assert reg(db_pg, xml)['encf'] == 'E310000002882'


def test_xml_ilegible(db_pg):
    with pytest.raises(ErrorLecturaECF): reg(db_pg, b'basura')


def test_reenvio_sin_pdf_conserva_cruce_fallo(db_pg, monkeypatch):  # I2
    monkeypatch.setattr(registro, 'extraer_qr_params', lambda b: {**QR_MUESTRA, 'MontoTotal': '9999'})
    a = reg(db_pg, pdf_bytes=b'%PDF')
    assert a['validacion_detalle']['cruce']['resultado'] == FALLO
    b = reg(db_pg, ahora=T0 + timedelta(hours=1))
    assert b['validacion_detalle']['cruce']['resultado'] == FALLO
    assert b['qr_params'] == a['qr_params']


def _reemplazo(encf: str) -> bytes:
    xml = XML_SIN_FIRMA.replace(b'<eNCF>E310000002882</eNCF>', f'<eNCF>{encf}</eNCF>'.encode())
    xml = xml.replace(b'<MontoTotal>1250</MontoTotal>', b'<MontoTotal>9250</MontoTotal>')
    return firmar_ecf(xml, HOJA_PRUEBA_KEY, HOJA_PRUEBA, T0)


def test_reemplazo_sin_pdf_usa_qr_guardado(db_pg, tmp_path, monkeypatch):  # I2, rama de reemplazo
    cfg = _confiando_en(CA_PRUEBA, tmp_path)
    original = ecf_de_prueba('E310000000020')
    d = leer_ecf(original)
    qr = {'RncEmisor': d.rnc_emisor, 'RncComprador': d.rnc_comprador, 'ENCF': d.encf,
          'FechaEmision': d.fecha_emision_texto, 'MontoTotal': str(d.monto_total),
          'FechaFirma': d.fecha_firma_texto, 'CodigoSeguridad': d.codigo_seguridad}
    monkeypatch.setattr(registro, 'extraer_qr_params', lambda b: qr)
    a = reg(db_pg, original, config_validacion=cfg, pdf_bytes=b'%PDF')
    assert a['validacion_detalle']['cruce']['resultado'] == OK
    b = reg(db_pg, _reemplazo('E310000000020'), config_validacion=cfg, ahora=T0 + timedelta(hours=1))
    assert b['monto_total'] == Decimal('9250')
    assert b['validacion_detalle']['cruce']['resultado'] == FALLO and b['qr_params'] == a['qr_params']


def test_reemplazo_con_comprador_fallo_se_rechaza(db_pg, tmp_path):  # I3
    cfg = _confiando_en(CA_PRUEBA, tmp_path)
    a = reg(db_pg, ecf_de_prueba('E310000000021'), config_validacion=cfg)
    b = reg(db_pg, _reemplazo('E310000000021'), config_validacion=config_con(ca_dir=tmp_path, rnc_terpel='999999999'),
            ahora=T0 + timedelta(hours=1))
    assert b['xml_hash_sha256'] == a['xml_hash_sha256'] and b['monto_total'] == a['monto_total']
    assert tipos(db_pg, a['id'])[-1] == DOCUMENTO_RECHAZADO
    assert 'comprador=FALLO' in db_pg.get_historial(a['id'])[-1]['detalle']


def test_reemplazo_con_certificado_revocado_se_rechaza(db_pg, tmp_path):  # I3
    from ayudantes import CA_PRUEBA_KEY
    from pki import responder_ocsp
    cfg = _confiando_en(CA_PRUEBA, tmp_path)
    a = reg(db_pg, ecf_de_prueba('E310000000022'), config_validacion=cfg)
    revocado = config_con(ca_dir=tmp_path, ocsp_post=lambda u, b: responder_ocsp(
        CA_PRUEBA_KEY, CA_PRUEBA, HOJA_PRUEBA, 'REVOKED', revocado_en=T0 - timedelta(days=1)))
    b = reg(db_pg, _reemplazo('E310000000022'), config_validacion=revocado, ahora=T0 + timedelta(hours=1))
    assert b['xml_hash_sha256'] == a['xml_hash_sha256'] and b['monto_total'] == a['monto_total']
    assert tipos(db_pg, a['id'])[-1] == DOCUMENTO_RECHAZADO
    assert 'revocacion=FALLO' in db_pg.get_historial(a['id'])[-1]['detalle']


def test_reemplazo_con_revocacion_no_verificable_se_acepta(db_pg, tmp_path):  # I3
    cfg = _confiando_en(CA_PRUEBA, tmp_path)
    a = reg(db_pg, ecf_de_prueba('E310000000023'), config_validacion=cfg)
    b = reg(db_pg, _reemplazo('E310000000023'), config_validacion=cfg, ahora=T0 + timedelta(hours=1))
    assert b['revocacion'] == NO_VERIFICABLE and b['monto_total'] == Decimal('9250')
    assert DOCUMENTO_REEMPLAZADO in tipos(db_pg, a['id'])


def test_reemplazo_con_seguimiento_inactivo_y_dgii_caida_reactiva_cierre(db_pg, tmp_path):  # M9
    cfg = _confiando_en(CA_PRUEBA, tmp_path)
    a = reg(db_pg, ecf_de_prueba('E310000000024'), config_validacion=cfg)
    db_pg.update_comprobante(a['id'], {'seguimiento_activo': False})
    ahora = T0 + timedelta(hours=100)
    b = reg(db_pg, _reemplazo('E310000000024'), config_validacion=cfg, ahora=ahora, consultar=fijo(ERROR_R))
    assert b['estado'] == PENDIENTE and b['seguimiento_activo'] is True
    assert b['seguimiento_hasta'] == ahora and b['proxima_consulta'] == ahora
    assert tipos(db_pg, a['id'])[-1] == ERROR_CONSULTA
    assert [h['detalle'] for h in db_pg.get_historial(a['id'])].count('seguimiento cerrado sin consulta válida') == 0
