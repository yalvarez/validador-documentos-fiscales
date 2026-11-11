"""Un ciclo del worker: consulta a la DGII los comprobantes vencidos y aplica las reglas de transición."""
import logging
import time
from datetime import datetime
from typing import Callable

from common.ecf.dgii import RespuestaDGII, consultar_dgii
from common.ecf.modelos import ERROR_CONSULTA, NO_VERIFICABLE
from common.ecf.registro import campos_de_validacion
from common.ecf.seguimiento import ConfigSeguimiento, Evento, decidir
from common.ecf.validacion import ConfigValidacion, validar_xml


def _procesar(db, fila: dict, ahora: datetime, cfg: ConfigSeguimiento, config_validacion: ConfigValidacion,
              consultar: Callable[[str], RespuestaDGII]) -> None:
    try:
        resp = consultar(fila['url_consulta'])
    except Exception as e:  # noqa: BLE001 - un fallo inesperado cuenta como error de consulta
        resp = RespuestaDGII('ERROR', detalle=repr(e))
    dec = decidir(fila, resp, ahora, cfg)

    if fila['revocacion'] == NO_VERIFICABLE:
        try:
            r = validar_xml(bytes(fila['xml_contenido']), fila['qr_params'], config_validacion, ahora)
            dec.campos.update(campos_de_validacion(r))
        except Exception as e:  # noqa: BLE001 - la revalidación fallida no impide registrar la consulta
            logging.exception('Falla al revalidar el comprobante %s', fila['id'])
            dec.eventos.append(Evento(ERROR_CONSULTA, detalle=repr(e)))

    with db.transaccion():
        db.update_comprobante(fila['id'], dec.campos)
        for e in dec.eventos:
            db.insert_historial(fila['id'], e.tipo, e.estado_anterior, e.estado_nuevo,
                                e.estado_dgii_texto, e.detalle, fecha=ahora)


def procesar_ciclo(db, ahora: datetime, cfg: ConfigSeguimiento, config_validacion: ConfigValidacion,
                   consultar: Callable[[str], RespuestaDGII] = consultar_dgii,
                   dormir: Callable[[float], None] = time.sleep) -> int:
    """Procesa los comprobantes con consulta vencida y devuelve cuántos se procesaron."""
    filas = db.get_comprobantes_por_consultar(ahora)
    for i, fila in enumerate(filas):
        if i:
            dormir(1)
        try:
            _procesar(db, fila, ahora, cfg, config_validacion, consultar)
        except Exception:  # noqa: BLE001 - un comprobante no debe detener el ciclo
            logging.exception('Falla al procesar el comprobante %s', fila.get('id'))
    return len(filas)
