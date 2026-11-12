"""Punto de entrada común para registrar un e-CF: valida, guarda con su historial y hace la primera consulta."""
import hashlib
import logging
import os
import tempfile
from datetime import datetime
from typing import Callable

from api.parametros_manager import ParametrosManager
from common.ecf.dgii import RespuestaDGII, construir_url_consulta, consultar_dgii
from common.ecf.lectura import leer_ecf
from common.ecf.modelos import (DOCUMENTO_RECHAZADO, PENDIENTE, REGISTRO, ZONA_RD,
                                ResultadoValidacionXML)
from common.ecf.seguimiento import (ConfigSeguimiento, calendario_inicial, config_seguimiento_desde_parametros,
                                    decidir)
from common.ecf.validacion import ConfigValidacion, config_validacion_desde_parametros, validar_xml
from common.pdf_processor.extractor import PDFProcessor

_CAMPOS_PRIMERA_CONSULTA = ('estado', 'estado_dgii_texto', 'ultima_consulta_dgii', 'razon_social_emisor', 'intentos')
_COLUMNAS_VALIDACION = ('validacion_detalle', 'integridad', 'vigencia', 'entidad_certificadora', 'revocacion',
                        'certificado_titular', 'certificado_emisor', 'certificado_serie')


def extraer_qr_params(pdf_bytes: bytes) -> dict | None:
    """Parámetros del QR del PDF; cualquier fallo o resultado vacío da None."""
    ruta = None
    try:
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            ruta = f.name
            f.write(pdf_bytes)
        return PDFProcessor(ruta).extract_qr_params() or None
    except Exception as e:  # noqa: BLE001 - el PDF es opcional, nunca debe abortar el registro
        logging.warning('No se pudo extraer el QR del PDF: %s', e)
        return None
    finally:
        if ruta:
            try:
                os.remove(ruta)
            except OSError:
                pass


def campos_de_validacion(r: ResultadoValidacionXML) -> dict:
    return {
        'validacion_detalle': r.a_dict(),
        'integridad': r.integridad.resultado,
        'vigencia': r.vigencia.resultado,
        'entidad_certificadora': r.entidad_certificadora.resultado,
        'revocacion': r.revocacion.resultado,
        'certificado_titular': r.certificado_titular,
        'certificado_emisor': r.certificado_emisor,
        'certificado_serie': r.certificado_serie,
    }


def _consultar_y_aplicar(db, cid, d, url, consultar, ahora, cfg) -> None:
    """Consulta la DGII fuera de toda transacción y aplica el resultado (sin tocar el calendario)."""
    try:
        resp = consultar(url)
    except Exception as e:  # noqa: BLE001 - un fallo inesperado no debe perder el registro
        logging.exception('Falla inesperada al consultar la DGII')
        resp = RespuestaDGII('ERROR', detalle=repr(e))
    with db.transaccion():
        fila = db.get_comprobante(d.rnc_emisor, d.encf)
        dec = decidir(fila, resp, ahora, cfg)
        cambios = {k: v for k, v in dec.campos.items() if k in _CAMPOS_PRIMERA_CONSULTA}
        db.update_comprobante(cid, cambios)
        for e in dec.eventos:
            db.insert_historial(cid, e.tipo, e.estado_anterior, e.estado_nuevo,
                                e.estado_dgii_texto, e.detalle, fecha=ahora)


def registrar_comprobante(db, xml_bytes: bytes, pdf_bytes: bytes | None = None, origen: str = 'api',
                          referencia_origen: str | None = None, *,
                          config_validacion: ConfigValidacion | None = None,
                          config_seguimiento: ConfigSeguimiento | None = None,
                          consultar: Callable[[str], RespuestaDGII] = consultar_dgii,
                          ahora: datetime | None = None) -> dict:
    """Registra el e-CF y devuelve la fila final de `comprobantes`. Lanza ErrorLecturaECF si no hay RNC/e-NCF."""
    ahora = ahora or datetime.now(ZONA_RD)
    parametros = None
    if config_validacion is None or config_seguimiento is None:
        parametros = ParametrosManager(db)
    cfg_val = config_validacion or config_validacion_desde_parametros(parametros)
    cfg = config_seguimiento or config_seguimiento_desde_parametros(parametros)

    d = leer_ecf(xml_bytes)
    qr = extraer_qr_params(pdf_bytes) if pdf_bytes else None
    if qr is None:
        # Sin PDF nuevo se cruza contra el QR ya guardado: un reenvío sin PDF no borra un cruce previo.
        existente = db.get_comprobante(d.rnc_emisor, d.encf)
        qr_validacion = existente['qr_params'] if existente else None
    else:
        qr_validacion = qr
    r = validar_xml(xml_bytes, qr_validacion, cfg_val, ahora)

    url = construir_url_consulta(d)
    hash_nuevo = hashlib.sha256(xml_bytes).hexdigest()
    campos = {
        'rnc_emisor': d.rnc_emisor, 'encf': d.encf, 'rnc_comprador': d.rnc_comprador, 'tipo_ecf': d.tipo_ecf,
        'fecha_emision': d.fecha_emision_texto, 'monto_total': d.monto_total, 'fecha_firma': d.fecha_firma,
        'codigo_seguridad': d.codigo_seguridad, 'razon_social_emisor': d.razon_social_emisor,
        'url_consulta': url, 'xml_contenido': xml_bytes, 'xml_hash_sha256': hash_nuevo,
        'qr_params': qr, 'origen': origen, 'referencia_origen': referencia_origen,
        **campos_de_validacion(r),
    }

    with db.transaccion():
        nuevo_id = db.insert_comprobante({**campos, 'estado': PENDIENTE, **calendario_inicial(ahora, cfg)})
        if nuevo_id is not None:
            db.insert_historial(nuevo_id, REGISTRO, fecha=ahora)

    if nuevo_id is not None:
        _consultar_y_aplicar(db, nuevo_id, d, url, consultar, ahora, cfg)
        return db.get_comprobante(d.rnc_emisor, d.encf)

    with db.transaccion():
        fila = db.get_comprobante(d.rnc_emisor, d.encf)
        cid = fila['id']
        if not any(h['tipo'] == REGISTRO for h in db.get_historial(cid)):
            db.insert_historial(cid, REGISTRO, fecha=ahora)  # autocorrección de un registro incompleto
        if fila['xml_hash_sha256'] == hash_nuevo:
            cambios = {c: campos[c] for c in _COLUMNAS_VALIDACION}
            if qr:
                cambios['qr_params'] = qr
            db.update_comprobante(cid, cambios)
        else:
            # Un comprobante registrado no se reemplaza nunca: el XML distinto se descarta y se deja constancia.
            detalle = (f"XML distinto descartado (no se reemplaza): hash guardado {fila['xml_hash_sha256'][:8]}, "
                       f"recibido {hash_nuevo[:8]}; integridad={r.integridad.resultado}; "
                       f"vigencia={r.vigencia.resultado}; "
                       f"entidad_certificadora={r.entidad_certificadora.resultado}; "
                       f"revocacion={r.revocacion.resultado}; comprador={r.comprador.resultado}")
            db.insert_historial(cid, DOCUMENTO_RECHAZADO, detalle=detalle, fecha=ahora)
    return db.get_comprobante(d.rnc_emisor, d.encf)
