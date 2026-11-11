"""Cruce de los datos del XML contra los parámetros del QR del PDF, y verificación del comprador."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import unquote_plus

from common.ecf.lectura import DatosECF
from common.ecf.modelos import FALLO, NO_VERIFICABLE, OK, Verificacion

_FMT_FECHA = '%d-%m-%Y'
_FMT_FECHA_HORA = '%d-%m-%Y %H:%M:%S'

# Nombres canónicos del QR, en el orden en que se informan las discrepancias.
_CAMPOS = ('RncEmisor', 'RncComprador', 'ENCF', 'FechaEmision', 'MontoTotal', 'FechaFirma', 'CodigoSeguridad')


# Mínimo que identifica la factura; los demás campos del QR son opcionales (la variante FC no los trae).
_REQUERIDOS = ('RncEmisor', 'ENCF', 'MontoTotal', 'CodigoSeguridad')


def _rnc(valor) -> str | None:
    return str(valor).strip().upper() if valor is not None else None


def _monto(valor) -> Decimal | None:
    if valor is None:
        return None
    try:
        return Decimal(str(valor).replace(',', '').strip())
    except InvalidOperation:
        return None


def _decodificar(valor) -> str:
    texto = str(valor)
    return unquote_plus(texto).strip() if '%' in texto else texto.strip()


def _fecha(valor, formato: str) -> date | datetime | str | None:
    """Fecha como objeto comparable; si no se puede interpretar, el texto crudo."""
    if valor is None:
        return None
    texto = _decodificar(valor)
    try:
        momento = datetime.strptime(texto, formato)
    except ValueError:
        return texto
    return momento.date() if formato == _FMT_FECHA else momento


def _normalizar_codigo(valor) -> str:
    return str(valor).replace(' ', '+')


def verificar_cruce(d: DatosECF, qr_params: dict | None) -> Verificacion:
    if not qr_params:
        return Verificacion(NO_VERIFICABLE, 'Sin PDF')
    qr = {str(k).strip().lower(): v for k, v in qr_params.items()}
    comparadores = {
        'RncEmisor': lambda v: _rnc(v) == _rnc(d.rnc_emisor),
        'RncComprador': lambda v: _rnc(v) == _rnc(d.rnc_comprador),
        'ENCF': lambda v: _rnc(v) == _rnc(d.encf),
        'FechaEmision': lambda v: _fecha(v, _FMT_FECHA) == _fecha(d.fecha_emision_texto, _FMT_FECHA),
        'MontoTotal': lambda v: _monto(v) is not None and _monto(v) == d.monto_total,
        'FechaFirma': lambda v: _fecha(v, _FMT_FECHA_HORA) == _fecha(d.fecha_firma_texto, _FMT_FECHA_HORA),
        'CodigoSeguridad': lambda v: _normalizar_codigo(v) == d.codigo_seguridad,
    }
    faltan = [c for c in _REQUERIDOS if c.lower() not in qr]
    if faltan:
        return Verificacion(FALLO, 'QR sin campos requeridos: ' + ', '.join(faltan))
    discrepan = [c for c in _CAMPOS if c.lower() in qr and not comparadores[c](qr[c.lower()])]
    if discrepan:
        return Verificacion(FALLO, 'Discrepan: ' + ', '.join(discrepan))
    return Verificacion(OK)


def verificar_comprador(d: DatosECF, rnc_terpel: str | None) -> Verificacion:
    esperado = _rnc(rnc_terpel)
    if not esperado:
        return Verificacion(NO_VERIFICABLE, 'RNC de Terpel no configurado')
    if _rnc(d.rnc_comprador) == esperado:
        return Verificacion(OK)
    return Verificacion(FALLO, f"El comprador del XML ({d.rnc_comprador or 'ausente'}) no es Terpel")
