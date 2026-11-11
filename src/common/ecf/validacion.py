"""Orquestador de las 7 verificaciones del XML de un e-CF."""
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

import requests

import common.ecf as _paquete
from common.ecf.lectura import leer_ecf
from common.ecf.modelos import FALLO, NO_VERIFICABLE, ZONA_RD, ResultadoValidacionXML, Verificacion
from common.ecf.verificaciones.certificado import (cargar_certificado, descripcion_certificado,
                                                   verificar_entidad_certificadora, verificar_vigencia)
from common.ecf.verificaciones.cruce import verificar_comprador, verificar_cruce
from common.ecf.verificaciones.estructura import XSD_DIR, verificar_estructura
from common.ecf.verificaciones.integridad import verificar_integridad
from common.ecf.verificaciones.revocacion import verificar_revocacion

log = logging.getLogger(__name__)

TIMEOUT_HTTP = 5
MAX_DESCARGA = 2 * 1024 * 1024
MAX_OCSP = 64 * 1024
CONFIANZA_DIR = Path(_paquete.__file__).parent / 'confianza'


def _validar_url(url: str) -> None:
    if not isinstance(url, str) or not url.lower().startswith(('http://', 'https://')):
        raise ValueError(f'Solo se permiten URL http/https: {url!r}')


def _leer_acotado(resp, maximo: int) -> bytes:
    try:
        resp.raise_for_status()
        cuerpo = bytearray()
        for trozo in resp.iter_content(chunk_size=8192):
            cuerpo.extend(trozo)
            if len(cuerpo) > maximo:
                raise ValueError(f'La respuesta supera el máximo de {maximo} bytes')
        return bytes(cuerpo)
    finally:
        resp.close()


def http_descargar(url: str) -> bytes:
    _validar_url(url)
    return _leer_acotado(requests.get(url, timeout=TIMEOUT_HTTP, stream=True), MAX_DESCARGA)


def http_ocsp_post(url: str, cuerpo: bytes) -> bytes:
    _validar_url(url)
    resp = requests.post(url, data=cuerpo, headers={'Content-Type': 'application/ocsp-request'},
                         timeout=TIMEOUT_HTTP, stream=True)
    return _leer_acotado(resp, MAX_OCSP)


@dataclass
class ConfigValidacion:
    xsd_dir: Path
    ca_dir: Path
    rnc_terpel: str | None
    ocsp_post: Callable[[str, bytes], bytes]
    descargar: Callable[[str], bytes]

    @classmethod
    def por_defecto(cls) -> 'ConfigValidacion':
        return cls(XSD_DIR, CONFIANZA_DIR, None, ocsp_post=http_ocsp_post, descargar=http_descargar)


def config_validacion_desde_parametros(parametros) -> ConfigValidacion:
    """`parametros`: ParametrosManager (o cualquier objeto con `get(clave, default)`)."""
    cfg = ConfigValidacion.por_defecto()
    rnc = parametros.get('RNC_TERPEL')
    cfg.rnc_terpel = str(rnc).strip() or None if rnc is not None else None
    directorio = parametros.get('CA_CONFIANZA_DIR')
    if directorio and str(directorio).strip():
        cfg.ca_dir = Path(str(directorio).strip())
    return cfg


def _seguro(fn, *args, en_error: str = FALLO, **kwargs) -> Verificacion:
    """Ejecuta una verificación; una excepción inesperada se vuelve un resultado, nunca se propaga."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        log.exception('Falló la verificación %s', getattr(fn, '__name__', fn))
        return Verificacion(en_error, f'Error inesperado: {e}')


def _parsear_cert(der: bytes):
    try:
        return cargar_certificado(der)
    except Exception:
        return None


def validar_xml(xml_bytes: bytes, qr_params: dict | None = None,
                config: ConfigValidacion | None = None,
                ahora: datetime | None = None) -> ResultadoValidacionXML:
    try:
        return _validar(xml_bytes, qr_params, config or ConfigValidacion.por_defecto(),
                        ahora or datetime.now(ZONA_RD))
    except Exception as e:  # red de seguridad final: el contrato es no lanzar
        log.exception('Falló validar_xml')
        msg = f'Error inesperado: {e}'
        return ResultadoValidacionXML(
            Verificacion(FALLO, msg), Verificacion(FALLO, msg), Verificacion(FALLO, msg),
            Verificacion(FALLO, msg), Verificacion(NO_VERIFICABLE, msg),
            Verificacion(NO_VERIFICABLE, msg), Verificacion(NO_VERIFICABLE, msg))


def _validar(xml_bytes, qr_params, config, ahora) -> ResultadoValidacionXML:
    try:
        d = leer_ecf(xml_bytes)
    except Exception as e:  # ErrorLecturaECF u otro fallo de lectura
        msg = str(e) or e.__class__.__name__
        return ResultadoValidacionXML(
            Verificacion(FALLO, msg), Verificacion(FALLO, msg), Verificacion(FALLO, msg),
            Verificacion(FALLO, msg), Verificacion(NO_VERIFICABLE, msg),
            Verificacion(NO_VERIFICABLE, msg), Verificacion(NO_VERIFICABLE, msg))

    estructura = _seguro(verificar_estructura, xml_bytes, d.tipo_ecf, config.xsd_dir)
    integridad = _seguro(verificar_integridad, xml_bytes)
    cruce = _seguro(verificar_cruce, d, qr_params)
    comprador = _seguro(verificar_comprador, d, config.rnc_terpel)

    titular = emisor_cn = serie = None
    cadena = None
    if not d.certificados_der:
        vigencia = Verificacion(FALLO, 'Sin certificado')
        entidad = Verificacion(FALLO, 'Sin certificado')
        revocacion = Verificacion(NO_VERIFICABLE, 'Sin cadena de confianza')
    else:
        hoja = _parsear_cert(d.certificados_der[0])
        if hoja is None:
            vigencia = Verificacion(FALLO, 'Certificado del firmante ilegible')
            entidad = Verificacion(FALLO, 'Certificado del firmante ilegible')
        else:
            try:
                titular, emisor_cn, serie = descripcion_certificado(hoja)
            except Exception:
                log.exception('No se pudo describir el certificado')
            vigencia = _seguro(verificar_vigencia, hoja, d.fecha_firma)
            incrustados = [c for c in map(_parsear_cert, d.certificados_der[1:]) if c is not None]
            try:
                entidad, cadena = verificar_entidad_certificadora(
                    hoja, incrustados, config.ca_dir, config.descargar, fecha_firma=d.fecha_firma)
            except Exception as e:
                log.exception('Falló la verificación de la entidad certificadora')
                entidad, cadena = Verificacion(FALLO, f'Error inesperado: {e}'), None
        if cadena and len(cadena) >= 2:
            revocacion = _seguro(verificar_revocacion, cadena[0], cadena[1], d.fecha_firma,
                                 config.ocsp_post, config.descargar, ahora, en_error=NO_VERIFICABLE)
        else:
            revocacion = Verificacion(NO_VERIFICABLE, 'Sin cadena de confianza')

    return ResultadoValidacionXML(
        estructura, integridad, vigencia, entidad, revocacion, cruce, comprador,
        certificado_titular=titular, certificado_emisor=emisor_cn, certificado_serie=serie)
