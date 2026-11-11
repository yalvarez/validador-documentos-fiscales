from datetime import datetime, timedelta
from pathlib import Path

from lxml import etree

from common.ecf.modelos import ZONA_RD
from pki import crear_ca, crear_hoja, firmar_ecf

RAIZ = Path(__file__).parents[1]
MUESTRA_XML = (RAIZ / 'tests/samples/101616202E310000002882.xml').read_bytes()
MUESTRA_PDF = RAIZ / 'tests/samples/101616202E310000002882.pdf'
T0 = datetime(2026, 11, 10, 10, 0, tzinfo=ZONA_RD)


def _sin_firma() -> bytes:
    raiz = etree.fromstring(MUESTRA_XML)
    for nodo in raiz.xpath("//*[local-name()='Signature']"):
        nodo.getparent().remove(nodo)
    return etree.tostring(raiz)


XML_SIN_FIRMA = _sin_firma()


def muestra_en(encoding: str) -> bytes:
    """La muestra realmente codificada en `encoding`, con su declaración XML."""
    texto = MUESTRA_XML.decode('utf-8')
    return (f'<?xml version="1.0" encoding="{encoding}"?>' + texto).encode(encoding)


AYER = T0 - timedelta(days=1)
MANANA = T0 + timedelta(days=1)

CA_PRUEBA_KEY, CA_PRUEBA = crear_ca('CA PRUEBA')
HOJA_PRUEBA_KEY, HOJA_PRUEBA = crear_hoja(
    CA_PRUEBA_KEY, CA_PRUEBA, T0 - timedelta(days=30), T0 + timedelta(days=365),
    ocsp_url='http://ocsp.prueba', crl_url='http://crl.prueba/a.crl')


def ecf_de_prueba(encf: str, rnc_emisor: str = '101616202', fecha_firma: datetime = T0) -> bytes:
    """XML_SIN_FIRMA con otro e-NCF/RNC, firmado con HOJA_PRUEBA."""
    xml = XML_SIN_FIRMA.replace(b'<eNCF>E310000002882</eNCF>', f'<eNCF>{encf}</eNCF>'.encode())
    xml = xml.replace(b'<RNCEmisor>101616202</RNCEmisor>', f'<RNCEmisor>{rnc_emisor}</RNCEmisor>'.encode())
    return firmar_ecf(xml, HOJA_PRUEBA_KEY, HOJA_PRUEBA, fecha_firma)


# --- Tarea 8: consulta a la DGII ---
from typing import Callable  # noqa: E402

from common.ecf.dgii import RespuestaDGII  # noqa: E402

DATOS_ACEPTADO = RespuestaDGII('DATOS', 'Aceptado', 'EMPRESAS ASAVIM S R L')
NO_ENCONTRADO_R = RespuestaDGII('NO_ENCONTRADO')
ERROR_R = RespuestaDGII('ERROR', detalle='HTTP 500')


def fijo(r: RespuestaDGII) -> Callable[[str], RespuestaDGII]:
    """Consultor de DGII que devuelve siempre `r`."""
    return lambda url: r


def fixture_dgii(nombre: str) -> str:
    return (RAIZ / 'tests/ecf/fixtures/dgii' / nombre).read_text(encoding='utf-8')


# --- Tarea 9: comprobantes ---
def campos_minimos(encf: str = 'E310000002882', **cambios) -> dict:
    """Todas las columnas NOT NULL de `comprobantes`, con valores válidos."""
    campos = {
        'rnc_emisor': '101616202', 'encf': encf, 'xml_contenido': MUESTRA_XML,
        'xml_hash_sha256': 'a' * 64, 'origen': 'api', 'validacion_detalle': {},
        'estado': 'PENDIENTE', 'seguimiento_activo': True,
        'seguimiento_hasta': T0 + timedelta(hours=72),
        'proxima_consulta': T0 + timedelta(minutes=60), 'intervalo_actual_min': 120,
    }
    campos.update(cambios)
    return campos


# --- Tarea 7: cruce y orquestador ---
import dataclasses  # noqa: E402

import common.ecf as _paquete_ecf  # noqa: E402
from common.ecf.validacion import ConfigValidacion  # noqa: E402
from common.ecf.verificaciones.estructura import XSD_DIR  # noqa: E402

QR_MUESTRA = {
    'RncEmisor': '101616202', 'RncComprador': '101107146', 'ENCF': 'E310000002882',
    'FechaEmision': '10-02-2026', 'MontoTotal': '1250.00', 'FechaFirma': '10-02-2026 09:22:21',
    'CodigoSeguridad': 'BuLkvC',
}


def _lanza(*args, **kwargs):
    raise ConnectionError('sin red en pruebas')


CONFIG_SIN_RED = ConfigValidacion(
    XSD_DIR, Path(_paquete_ecf.__file__).parent / 'confianza', None,
    ocsp_post=_lanza, descargar=_lanza)


def config_con(**cambios) -> ConfigValidacion:
    return dataclasses.replace(CONFIG_SIN_RED, **cambios)


def zbar_disponible() -> bool:
    try:
        import pyzbar.pyzbar  # noqa: F401
        return True
    except Exception:
        return False
