"""Un ciclo del worker: consulta a la DGII los comprobantes vencidos y aplica las reglas de transición."""
import logging
import time
from datetime import datetime
from typing import Callable

from common.ecf.dgii import RespuestaDGII, consultar_dgii
from common.ecf.modelos import ERROR_CONSULTA, NO_VERIFICABLE, OK, ZONA_RD
from common.ecf.registro import campos_de_validacion
from common.ecf.seguimiento import ConfigSeguimiento, Evento, decidir
from common.ecf.validacion import ConfigValidacion, validar_xml


def _ahora_rd() -> datetime:
    return datetime.now(ZONA_RD)


def _procesar(db, fila: dict, ahora: datetime, cfg: ConfigSeguimiento, config_validacion: ConfigValidacion,
              consultar: Callable[[str], RespuestaDGII]) -> None:
    try:
        resp = consultar(fila['url_consulta'])
    except Exception as e:  # noqa: BLE001 - un fallo inesperado cuenta como error de consulta
        resp = RespuestaDGII('ERROR', detalle=repr(e))
    dec = decidir(fila, resp, ahora, cfg)

    # Solo tiene sentido reintentar la revocación si la cadena de confianza ya está armada.
    if fila['revocacion'] == NO_VERIFICABLE and fila['entidad_certificadora'] == OK:
        try:
            r = validar_xml(bytes(fila['xml_contenido']), fila['qr_params'], config_validacion, ahora)
            dec.campos.update(campos_de_validacion(r))
        except Exception as e:  # noqa: BLE001 - la revalidación fallida no impide registrar la consulta
            logging.exception('Falla al revalidar el comprobante %s', fila['id'])
            dec.eventos.append(Evento(ERROR_CONSULTA, detalle=repr(e)))

    with db.transaccion():
        actual = db.get_comprobante_por_id(fila['id'], bloquear=True)
        if actual is None or actual['xml_hash_sha256'] != fila['xml_hash_sha256']:
            # Se reemplazó (o desapareció) mientras se consultaba: la decisión es sobre una foto vieja.
            logging.warning('Comprobante %s cambió durante la consulta; no se aplica el resultado', fila['id'])
            return
        db.update_comprobante(fila['id'], dec.campos)
        for e in dec.eventos:
            db.insert_historial(fila['id'], e.tipo, e.estado_anterior, e.estado_nuevo,
                                e.estado_dgii_texto, e.detalle, fecha=ahora)


def procesar_ciclo(db, ahora: datetime | None, cfg: ConfigSeguimiento, config_validacion: ConfigValidacion,
                   consultar: Callable[[str], RespuestaDGII] = consultar_dgii,
                   dormir: Callable[[float], None] = time.sleep,
                   reloj: Callable[[], datetime] | None = None) -> int:
    """Procesa los comprobantes con consulta vencida y devuelve cuántos se procesaron.

    `ahora` fija el inicio del ciclo (qué comprobantes están vencidos). La hora de cada comprobante
    la da `reloj` si se pasa; si no, se usa `ahora` para todos (o la hora actual si `ahora` es None).
    """
    if ahora is None:
        ahora = _ahora_rd()
        reloj = reloj or _ahora_rd
    filas = db.get_comprobantes_por_consultar(ahora)
    for i, fila in enumerate(filas):
        if i:
            dormir(1)
        try:
            _procesar(db, fila, reloj() if reloj else ahora, cfg, config_validacion, consultar)
        except Exception:  # noqa: BLE001 - un comprobante no debe detener el ciclo
            logging.exception('Falla al procesar el comprobante %s', fila.get('id'))
    return len(filas)
