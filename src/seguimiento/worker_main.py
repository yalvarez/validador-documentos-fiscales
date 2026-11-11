"""Proceso del worker: ejecuta ciclos de seguimiento indefinidamente."""
import logging
import time
from datetime import datetime

from api.parametros_manager import ParametrosManager
from common.ecf.modelos import ZONA_RD
from common.ecf.seguimiento import config_seguimiento_desde_parametros
from common.ecf.validacion import config_validacion_desde_parametros
from db.config import leer_config_db
from db.db_factory import get_db_wrapper
from seguimiento.ciclo import procesar_ciclo


def _cerrar(db) -> None:
    try:
        if db is not None:
            db.close()
    except Exception:  # noqa: BLE001
        pass


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    db = None
    espera = 300
    while True:
        try:
            if db is None:
                db = get_db_wrapper(*leer_config_db())
            parametros = ParametrosManager(db)
            cfg = config_seguimiento_desde_parametros(parametros)
            espera = cfg.ciclo_seg
            n = procesar_ciclo(db, datetime.now(ZONA_RD), cfg, config_validacion_desde_parametros(parametros),
                               reloj=lambda: datetime.now(ZONA_RD))
            logging.info('Ciclo: %d comprobantes', n)
        except Exception:  # noqa: BLE001 - el worker nunca debe morir
            logging.exception('Falla en el ciclo de seguimiento')
            _cerrar(db)
            db = None
        time.sleep(espera)


if __name__ == '__main__':
    main()
