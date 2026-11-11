"""Consulta a la DGII: URL, análisis de la página y mapeo de estados."""
import logging
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import quote, urlencode

import requests
from bs4 import BeautifulSoup

from common.ecf.lectura import DatosECF
from common.ecf.modelos import ACEPTADO, ACEPTADO_CONDICIONAL, DESCONOCIDO, NO_ENCONTRADO, PENDIENTE, RECHAZADO

URL_BASE = 'https://ecf.dgii.gov.do/eCF/'
LIMITE_FC = Decimal('250000')


@dataclass
class RespuestaDGII:
    tipo: str  # 'DATOS' | 'NO_ENCONTRADO' | 'ERROR'
    estado_texto: str | None = None
    razon_social: str | None = None
    detalle: str = ''


def construir_url_consulta(d: DatosECF) -> str:
    monto = None if d.monto_total is None else f'{d.monto_total:.2f}'
    if d.tipo_ecf == '32' and d.monto_total is not None and d.monto_total < LIMITE_FC:
        ruta = 'ConsultaTimbreFC'
        params = [('RncEmisor', d.rnc_emisor), ('ENCF', d.encf), ('MontoTotal', monto),
                  ('CodigoSeguridad', d.codigo_seguridad)]
    else:
        ruta = 'ConsultaTimbre'
        params = [('RncEmisor', d.rnc_emisor), ('RncComprador', d.rnc_comprador), ('ENCF', d.encf),
                  ('FechaEmision', d.fecha_emision_texto), ('MontoTotal', monto),
                  ('FechaFirma', d.fecha_firma_texto), ('CodigoSeguridad', d.codigo_seguridad)]
    params = [(k, v) for k, v in params if v is not None]
    return f'{URL_BASE}{ruta}?' + urlencode(params, quote_via=quote)


def _sin_acentos(texto: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')


def _norm(texto: str) -> str:
    return ' '.join(_sin_acentos(texto).casefold().split())


def analizar_respuesta(status: int, html: str) -> RespuestaDGII:
    if status != 200:
        return RespuestaDGII('ERROR', detalle=f'HTTP {status}')
    try:
        sopa = BeautifulSoup(html, 'html.parser')
        filas = {}
        for th in sopa.find_all('th'):
            td = th.find_next_sibling('td')
            if td is not None:
                filas[_norm(th.get_text())] = ' '.join(td.get_text().split())
        if 'estado' in filas and filas['estado']:
            return RespuestaDGII('DATOS', filas['estado'], filas.get('razon social emisor'))
        if 'no fue encontrada la factura' in _norm(sopa.get_text(' ')):
            return RespuestaDGII('NO_ENCONTRADO')
    except Exception as e:  # noqa: BLE001 - el analizador nunca debe lanzar
        return RespuestaDGII('ERROR', detalle=f'HTML inesperado: {e}')
    return RespuestaDGII('ERROR', detalle='HTML inesperado')


def consultar_dgii(url: str, http_get=requests.get, timeout: int = 15) -> RespuestaDGII:
    try:
        r = http_get(url, timeout=timeout)
        return analizar_respuesta(r.status_code, r.text)
    except Exception as e:  # noqa: BLE001 - nunca lanza
        return RespuestaDGII('ERROR', detalle=f'{type(e).__name__}: {e}')


_ESTADOS = {
    'aceptado': ACEPTADO,
    'aceptado condicional': ACEPTADO_CONDICIONAL,
    'rechazado': RECHAZADO,
    'en proceso': PENDIENTE,
    _norm(NO_ENCONTRADO): PENDIENTE,
}


def mapear_estado(texto: str | None) -> str:
    if texto is not None:
        estado = _ESTADOS.get(_norm(texto))
        if estado:
            return estado
    logging.warning('Estado de la DGII no reconocido: %r', texto)
    return DESCONOCIDO
