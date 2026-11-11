import os
from pathlib import Path

import pytest

from ayudantes import MUESTRA_XML, muestra_en
from common.ecf.modelos import FALLO, NO_VERIFICABLE, OK
from common.ecf.verificaciones import estructura
from common.ecf.verificaciones.estructura import XSD_DIR, verificar_estructura

XSD_PRUEBA = Path(__file__).parent / 'fixtures' / 'xsd'
requiere_xsd_oficial = pytest.mark.skipif(
    not (XSD_DIR / 'e-CF-31.xsd').exists(),
    reason='XSD oficiales de la DGII no instaladas (ver src/common/ecf/xsd/FUENTE.md)')
SIN_MONTO = MUESTRA_XML.replace(b'<MontoTotal>1250</MontoTotal>', b'')


@requiere_xsd_oficial
def test_muestra_valida():
    assert verificar_estructura(MUESTRA_XML, '31').resultado == OK


@requiere_xsd_oficial
def test_muestra_iso():
    assert verificar_estructura(muestra_en('ISO-8859-1'), '31').resultado == OK


@requiere_xsd_oficial
def test_falta_nodo_obligatorio():
    v = verificar_estructura(SIN_MONTO, '31')
    assert v.resultado == FALLO and 'MontoTotal' in v.detalle


def test_tipo_sin_xsd(tmp_path):
    assert verificar_estructura(MUESTRA_XML, '31', xsd_dir=tmp_path).resultado == NO_VERIFICABLE


def test_tipo_desconocido():
    assert verificar_estructura(MUESTRA_XML, None).resultado == NO_VERIFICABLE


def test_muestra_valida_con_esquema_de_prueba():
    assert verificar_estructura(MUESTRA_XML, '31', xsd_dir=XSD_PRUEBA).resultado == OK


def test_muestra_iso_con_esquema_de_prueba():
    assert verificar_estructura(muestra_en('ISO-8859-1'), '31', xsd_dir=XSD_PRUEBA).resultado == OK


def test_muestra_con_bom_con_esquema_de_prueba():
    assert verificar_estructura(b'\xef\xbb\xbf  ' + MUESTRA_XML, '31', xsd_dir=XSD_PRUEBA).resultado == OK


def test_falta_montototal_con_esquema_de_prueba():
    v = verificar_estructura(SIN_MONTO, '31', xsd_dir=XSD_PRUEBA)
    assert v.resultado == FALLO and 'MontoTotal' in v.detalle


def test_xml_ilegible_es_fallo():
    assert verificar_estructura(b'<ECF><x>', '31', xsd_dir=XSD_PRUEBA).resultado == FALLO


def test_tipo_con_caracteres_raros_no_sale_del_directorio(tmp_path):
    assert verificar_estructura(MUESTRA_XML, '../31', xsd_dir=tmp_path).resultado == NO_VERIFICABLE


def test_esquema_en_cache(monkeypatch):
    estructura._ESQUEMAS.clear()
    construidos = []
    original = estructura.etree.XMLSchema
    monkeypatch.setattr(estructura.etree, 'XMLSchema', lambda doc: construidos.append(1) or original(doc))
    for _ in range(3):
        assert verificar_estructura(MUESTRA_XML, '31', xsd_dir=XSD_PRUEBA).resultado == OK
    assert len(construidos) == 1


def test_xsd_con_import_por_url_no_verificable():
    v = verificar_estructura(MUESTRA_XML, '32', xsd_dir=XSD_PRUEBA)
    assert v.resultado == NO_VERIFICABLE
    assert 'http://ejemplo.invalid/otro.xsd' in v.detalle and 'externos' in v.detalle


def test_xsd_con_include_local_hermano_ok():
    assert verificar_estructura(MUESTRA_XML, '33', xsd_dir=XSD_PRUEBA).resultado == OK


@pytest.mark.parametrize('ref', ['../fuera.xsd', '/etc/x.xsd', 'file:///x.xsd', 'ftp://h/x.xsd', 'C:/x.xsd'])
def test_xsd_con_referencias_fuera_de_la_carpeta(tmp_path, ref):
    (tmp_path / 'e-CF-31.xsd').write_text(
        '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">'
        f'<xs:include schemaLocation="{ref}"/></xs:schema>')
    v = verificar_estructura(MUESTRA_XML, '31', xsd_dir=tmp_path)
    assert v.resultado == NO_VERIFICABLE and ref in v.detalle


FIRMA_FALSA = b'<ds:Signature xmlns:ds="http://www.w3.org/2000/09/xmldsig#"/>'


def test_firma_en_otra_posicion_es_fallo():
    xml = MUESTRA_XML.replace(b'<MontoTotal>', FIRMA_FALSA + b'<MontoTotal>', 1)
    v = verificar_estructura(xml, '31', xsd_dir=XSD_PRUEBA)
    assert v.resultado == FALLO and 'posición no permitida' in v.detalle


def test_segunda_firma_en_la_raiz_es_fallo():
    xml = MUESTRA_XML.replace(b'</ECF>', FIRMA_FALSA + b'</ECF>')
    assert verificar_estructura(xml, '31', xsd_dir=XSD_PRUEBA).resultado == FALLO


def test_raiz_es_firma_es_fallo():
    assert verificar_estructura(FIRMA_FALSA, '31', xsd_dir=XSD_PRUEBA).resultado == FALLO


def test_tipo_con_salto_de_linea_no_verificable():
    assert verificar_estructura(MUESTRA_XML, '31\n', xsd_dir=XSD_PRUEBA).resultado == NO_VERIFICABLE


def test_elemento_local_llamado_signature_no_cuenta_como_firma():
    # e-CF-34.xsd declara un Signature sin namespace: la firma dsig se debe quitar igual
    assert verificar_estructura(MUESTRA_XML, '34', xsd_dir=XSD_PRUEBA).resultado == OK


def test_cambio_del_xsd_se_recarga(tmp_path):
    ruta = tmp_path / 'e-CF-31.xsd'
    ruta.write_bytes((XSD_PRUEBA / 'e-CF-31.xsd').read_bytes())
    assert verificar_estructura(MUESTRA_XML, '31', xsd_dir=tmp_path).resultado == OK
    ruta.write_text(ruta.read_text(encoding='utf-8').replace('name="MontoTotal"', 'name="OtroMonto"'),
                    encoding='utf-8')
    st = ruta.stat()
    os.utime(ruta, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000))
    assert verificar_estructura(MUESTRA_XML, '31', xsd_dir=tmp_path).resultado == FALLO
