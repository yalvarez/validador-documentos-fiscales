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
