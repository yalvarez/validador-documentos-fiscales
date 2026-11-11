"""Calendario de seguimiento y reglas de transición de estado (funciones puras)."""
import logging
from dataclasses import dataclass, field, fields
from datetime import datetime, timedelta

from common.ecf.dgii import RespuestaDGII, mapear_estado
from common.ecf.modelos import (CAMBIO_ESTADO, CONSULTA, ERROR_CONSULTA, NO_ENCONTRADO,
                                PENDIENTE)

MARGEN_CIERRE_ERRORES_MIN = 60


@dataclass
class ConfigSeguimiento:
    intervalo_inicial_min: int = 60
    factor: float = 2.0
    intervalo_max_min: int = 1440
    duracion_max_horas: int = 72
    ciclo_seg: int = 300


_PARAMETROS = {
    'intervalo_inicial_min': ('SEGUIMIENTO_INTERVALO_INICIAL_MIN', int),
    'factor': ('SEGUIMIENTO_FACTOR', float),
    'intervalo_max_min': ('SEGUIMIENTO_INTERVALO_MAX_MIN', int),
    'duracion_max_horas': ('SEGUIMIENTO_DURACION_MAX_HORAS', int),
    'ciclo_seg': ('SEGUIMIENTO_CICLO_SEG', int),
}


def config_seguimiento_desde_parametros(parametros) -> ConfigSeguimiento:
    """Lee la configuración; un valor ausente o inválido usa el por defecto (con aviso)."""
    cfg = ConfigSeguimiento()
    for f in fields(cfg):
        clave, tipo = _PARAMETROS[f.name]
        crudo = parametros.get(clave, None)
        if crudo is None or str(crudo).strip() == '':
            continue
        try:
            valor = tipo(str(crudo).strip())
            if not valor > 0 or valor != valor or valor == float('inf'):
                raise ValueError('debe ser positivo y finito')
        except (ValueError, TypeError) as e:
            logging.warning('Parámetro %s inválido (%r): %s; se usa %r', clave, crudo, e, getattr(cfg, f.name))
            continue
        setattr(cfg, f.name, valor)
    return cfg


def _siguiente_intervalo(actual_min, cfg: ConfigSeguimiento) -> int:
    return int(round(min(actual_min * cfg.factor, cfg.intervalo_max_min)))


def calendario_inicial(ahora: datetime, cfg: ConfigSeguimiento) -> dict:
    return {
        'seguimiento_activo': True,
        'seguimiento_hasta': ahora + timedelta(hours=cfg.duracion_max_horas),
        'proxima_consulta': ahora + timedelta(minutes=cfg.intervalo_inicial_min),
        'intervalo_actual_min': _siguiente_intervalo(cfg.intervalo_inicial_min, cfg),
        'intentos': 0,
    }


@dataclass
class Evento:
    tipo: str
    estado_anterior: str | None = None
    estado_nuevo: str | None = None
    estado_dgii_texto: str | None = None
    detalle: str | None = None


@dataclass
class Decision:
    campos: dict = field(default_factory=dict)
    eventos: list = field(default_factory=list)


def decidir(c: dict, r: RespuestaDGII, ahora: datetime, cfg: ConfigSeguimiento) -> Decision:
    hasta = c['seguimiento_hasta']
    campos: dict = {'intentos': c['intentos'] + 1}
    eventos: list[Evento] = []

    if r.tipo == 'ERROR':
        eventos.append(Evento(ERROR_CONSULTA, detalle=r.detalle))
        if ahora >= hasta + timedelta(minutes=MARGEN_CIERRE_ERRORES_MIN):
            campos['seguimiento_activo'] = False
            eventos.append(Evento(ERROR_CONSULTA, detalle='seguimiento cerrado sin consulta válida'))
        return Decision(campos, eventos)

    nuevo = mapear_estado(r.estado_texto) if r.tipo == 'DATOS' else PENDIENTE
    campos['estado_dgii_texto'] = r.estado_texto
    campos['ultima_consulta_dgii'] = ahora
    if r.razon_social is not None:
        campos['razon_social_emisor'] = r.razon_social
    eventos.append(Evento(CONSULTA, estado_dgii_texto=r.estado_texto))

    if ahora >= hasta:
        campos['seguimiento_activo'] = False
        if r.tipo == 'NO_ENCONTRADO':
            nuevo = NO_ENCONTRADO
    else:
        campos['proxima_consulta'] = min(ahora + timedelta(minutes=c['intervalo_actual_min']), hasta)
        campos['intervalo_actual_min'] = _siguiente_intervalo(c['intervalo_actual_min'], cfg)
    campos['estado'] = nuevo
    if nuevo != c['estado']:
        eventos.append(Evento(CAMBIO_ESTADO, estado_anterior=c['estado'], estado_nuevo=nuevo))
    return Decision(campos, eventos)
