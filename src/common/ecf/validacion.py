"""Orquestador de las 7 verificaciones del XML de un e-CF."""
import ipaddress
import logging
import socket
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

import requests
from urllib3.util import parse_url

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
PLAZO_TOTAL = 15
MAX_FETCHES = 6
MAX_DESCARGA = 2 * 1024 * 1024
MAX_OCSP = 64 * 1024
CONFIANZA_DIR = Path(_paquete.__file__).parent / 'confianza'


def _resolver(host: str, puerto: int) -> list[str]:
    """Direcciones IP del host (inyectable en pruebas)."""
    return [info[4][0] for info in socket.getaddrinfo(host, puerto, proto=socket.IPPROTO_TCP)]


_reloj = time.monotonic


def _ip_permitida(texto: str) -> bool:
    try:
        ip = ipaddress.ip_address(texto.split('%')[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global and not (ip.is_multicast or ip.is_loopback or ip.is_link_local
                                 or ip.is_private or ip.is_reserved or ip.is_unspecified)


def _validar_url(url: str) -> str:
    """Solo http/https hacia destinos públicos: las URL vienen de certificados del XML recibido.

    Devuelve el host comprobado. Se comprueba el host de la URL tal como la entenderá urllib3.
    """
    if not isinstance(url, str) or not url.lower().startswith(('http://', 'https://')):
        raise ValueError(f'Solo se permiten URL http/https: {url!r}')
    if any(ord(c) < 0x21 or ord(c) >= 0x7f or c == chr(92) for c in url):
        raise ValueError(f'URL no permitida: {url!r}')
    try:
        partes = parse_url(url)
    except Exception as e:
        raise ValueError(f'URL no permitida: {url!r}') from e
    if partes.auth or '@' in (partes.netloc or ''):
        raise ValueError(f'URL no permitida: {url!r}')
    host = (partes.hostname or '').rstrip('.').lower()
    if not host:
        raise ValueError(f'URL sin host: {url!r}')
    puerto = partes.port or (443 if (partes.scheme or '').lower() == 'https' else 80)
    try:
        ipaddress.ip_address(host)
        direcciones = [host]
    except ValueError:
        try:
            direcciones = list(_resolver(host, puerto))
        except OSError as e:
            raise ValueError(f'No se pudo resolver {host}: {e}') from e
    if not direcciones or not all(_ip_permitida(d) for d in direcciones):
        raise ValueError(f'Destino no permitido: {host}')
    return host


def _enviar(metodo: str, url: str, maximo: int, **kw) -> bytes:
    """Prepara la petición, comprueba el destino de la URL ya preparada y envía ese mismo objeto."""
    _validar_url(url)
    inicio = _reloj()
    preparada = requests.Request(metodo, url, **kw).prepare()
    _validar_url(preparada.url)
    with requests.Session() as sesion:
        resp = sesion.send(preparada, allow_redirects=False, timeout=TIMEOUT_HTTP, stream=True)
        return _leer_acotado(resp, maximo, inicio)


def _leer_acotado(resp, maximo: int, inicio: float) -> bytes:
    try:
        if 300 <= resp.status_code < 400:
            raise ValueError(f'Redirección no permitida (HTTP {resp.status_code})')
        resp.raise_for_status()
        cuerpo = bytearray()
        for trozo in resp.iter_content(chunk_size=8192):
            cuerpo.extend(trozo)
            if len(cuerpo) > maximo:
                raise ValueError(f'La respuesta supera el máximo de {maximo} bytes')
            if _reloj() - inicio > PLAZO_TOTAL:
                raise ValueError(f'La descarga superó el plazo total de {PLAZO_TOTAL} s')
        if _reloj() - inicio > PLAZO_TOTAL:
            raise ValueError(f'La descarga superó el plazo total de {PLAZO_TOTAL} s')
        return bytes(cuerpo)
    finally:
        resp.close()


def http_descargar(url: str) -> bytes:
    return _enviar('GET', url, MAX_DESCARGA)


def http_ocsp_post(url: str, cuerpo: bytes) -> bytes:
    return _enviar('POST', url, MAX_OCSP, data=cuerpo, headers={'Content-Type': 'application/ocsp-request'})


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


def _con_tope(fn: Callable, contador: list[int]) -> Callable:
    """Envuelve un callable de red: como máximo MAX_FETCHES llamadas por validar_xml."""
    def envuelto(*args, **kwargs):
        contador[0] += 1
        if contador[0] > MAX_FETCHES:
            raise ConnectionError(f'Se superó el máximo de {MAX_FETCHES} descargas por validación')
        return fn(*args, **kwargs)
    return envuelto


def _validar(xml_bytes, qr_params, config, ahora) -> ResultadoValidacionXML:
    try:
        d = leer_ecf(xml_bytes)
    except Exception as e:  # ErrorLecturaECF u otro fallo de lectura
        msg = str(e) or e.__class__.__name__
        return ResultadoValidacionXML(
            Verificacion(FALLO, msg), Verificacion(FALLO, msg), Verificacion(FALLO, msg),
            Verificacion(FALLO, msg), Verificacion(NO_VERIFICABLE, msg),
            Verificacion(NO_VERIFICABLE, msg), Verificacion(NO_VERIFICABLE, msg))

    contador = [0]
    descargar = _con_tope(config.descargar, contador)
    ocsp_post = _con_tope(config.ocsp_post, contador)

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
                    hoja, incrustados, config.ca_dir, descargar, fecha_firma=d.fecha_firma)
            except Exception as e:
                log.exception('Falló la verificación de la entidad certificadora')
                entidad, cadena = Verificacion(FALLO, f'Error inesperado: {e}'), None
        if cadena and len(cadena) >= 2:
            revocacion = _seguro(verificar_revocacion, cadena[0], cadena[1], d.fecha_firma,
                                 ocsp_post, descargar, ahora, en_error=NO_VERIFICABLE)
        else:
            revocacion = Verificacion(NO_VERIFICABLE, 'Sin cadena de confianza')

    return ResultadoValidacionXML(
        estructura, integridad, vigencia, entidad, revocacion, cruce, comprador,
        certificado_titular=titular, certificado_emisor=emisor_cn, certificado_serie=serie)
