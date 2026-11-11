import dataclasses

import pytest

from ayudantes import MUESTRA_PDF, MUESTRA_XML, QR_MUESTRA, zbar_disponible
from common.ecf.lectura import leer_ecf
from common.ecf.modelos import FALLO, NO_VERIFICABLE, OK
from common.ecf.verificaciones.cruce import verificar_comprador, verificar_cruce
from common.pdf_processor.extractor import PDFProcessor

D = leer_ecf(MUESTRA_XML)


def test_cruce_muestra_ok():
    assert verificar_cruce(D, QR_MUESTRA).resultado == OK


def test_cruce_monto_distinto():
    v = verificar_cruce(D, {**QR_MUESTRA, 'MontoTotal': '9999'})
    assert v.resultado == FALLO and v.detalle == 'Discrepan: MontoTotal'


def test_cruce_formatos_equivalentes():  # Foco 2
    q = {k.lower(): val for k, val in QR_MUESTRA.items()}
    q.update(montototal='1,250.00', fechafirma='10-02-2026%2009%3A22%3A21')
    assert verificar_cruce(D, q).resultado == OK


def test_cruce_mas_convertido_en_espacio():  # Foco 2
    d = dataclasses.replace(D, codigo_seguridad='Bu+kvC')
    assert verificar_cruce(d, {**QR_MUESTRA, 'CodigoSeguridad': 'Bu kvC'}).resultado == OK


def test_cruce_sin_pdf():
    assert verificar_cruce(D, None).detalle == 'Sin PDF'
    assert verificar_cruce(D, {}).resultado == NO_VERIFICABLE


def test_cruce_campo_opcional_ausente_no_discrepa():
    q = {k: v for k, v in QR_MUESTRA.items() if k not in ('RncComprador', 'FechaEmision', 'FechaFirma')}
    assert set(q) == {'RncEmisor', 'ENCF', 'MontoTotal', 'CodigoSeguridad'}  # forma FC
    assert verificar_cruce(D, q).resultado == OK


def test_cruce_qr_sin_campos_requeridos():
    v = verificar_cruce(D, {'otro': 'x'})
    assert v.resultado == FALLO and v.detalle == 'QR sin campos requeridos: RncEmisor, ENCF, MontoTotal, CodigoSeguridad'
    q = {k: val for k, val in QR_MUESTRA.items() if k != 'CodigoSeguridad'}
    v = verificar_cruce(D, q)
    assert v.resultado == FALLO and v.detalle == 'QR sin campos requeridos: CodigoSeguridad'


def test_cruce_varias_discrepancias_con_nombres_del_qr():
    v = verificar_cruce(D, {**QR_MUESTRA, 'ENCF': 'E310000000001', 'RncEmisor': '1'})
    assert v.resultado == FALLO and v.detalle == 'Discrepan: RncEmisor, ENCF'


def test_cruce_rnc_y_encf_normalizados():
    assert verificar_cruce(D, {**QR_MUESTRA, 'ENCF': ' e310000002882 '}).resultado == OK


@pytest.mark.skipif(not zbar_disponible(), reason='zbar no instalado')
def test_cruce_contra_pdf_real():
    assert verificar_cruce(D, PDFProcessor(str(MUESTRA_PDF)).extract_qr_params()).resultado == OK


def test_comprador():
    assert verificar_comprador(D, '101107146').resultado == OK
    assert verificar_comprador(D, '130000000').resultado == FALLO
    assert verificar_comprador(D, None).resultado == NO_VERIFICABLE
    assert verificar_comprador(D, '').resultado == NO_VERIFICABLE
