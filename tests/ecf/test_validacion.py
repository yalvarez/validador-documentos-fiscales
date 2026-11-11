import dataclasses

import pytest
from cryptography.hazmat.primitives.serialization import Encoding

import common.ecf.validacion as validacion
from ayudantes import (CA_PRUEBA, CA_PRUEBA_KEY, CONFIG_SIN_RED, HOJA_PRUEBA, MUESTRA_XML, QR_MUESTRA, T0,
                       config_con, ecf_de_prueba)
from common.ecf.lectura import leer_ecf
from common.ecf.modelos import FALLO, NO_VERIFICABLE, OK
from common.ecf.validacion import (ConfigValidacion, config_validacion_desde_parametros, http_descargar,
                                   http_ocsp_post, validar_xml)
from common.ecf.verificaciones.estructura import XSD_DIR
from pki import responder_ocsp


def test_validar_xml_muestra():
    r = validar_xml(MUESTRA_XML, QR_MUESTRA, config_con(rnc_terpel='101107146'), ahora=T0)
    esperado_estructura = OK if (XSD_DIR / 'e-CF-31.xsd').exists() else NO_VERIFICABLE
    assert {k: v['resultado'] for k, v in r.a_dict().items()} == {
        'estructura': esperado_estructura, 'integridad': OK, 'vigencia': OK, 'entidad_certificadora': OK,
        'revocacion': NO_VERIFICABLE, 'cruce': OK, 'comprador': OK}
    assert r.certificado_titular == 'AURELIO ALCANTARA FAMILIA'


def test_validar_xml_basura():
    r = validar_xml(b'no es xml', None, CONFIG_SIN_RED, ahora=T0)
    assert r.integridad.resultado == FALLO and r.cruce.resultado == NO_VERIFICABLE
    assert r.estructura.resultado == FALLO and r.vigencia.resultado == FALLO
    assert r.entidad_certificadora.resultado == FALLO
    assert r.revocacion.resultado == NO_VERIFICABLE and r.comprador.resultado == NO_VERIFICABLE


def test_validar_xml_revocacion_con_red_simulada(tmp_path):
    (tmp_path / 'ca.pem').write_bytes(CA_PRUEBA.public_bytes(Encoding.PEM))
    cfg = config_con(ca_dir=tmp_path,
                     ocsp_post=lambda u, b: responder_ocsp(CA_PRUEBA_KEY, CA_PRUEBA, HOJA_PRUEBA, 'GOOD'))
    r = validar_xml(ecf_de_prueba('E310000000001'), None, cfg, ahora=T0)
    assert r.entidad_certificadora.resultado == OK and r.revocacion.resultado == OK


def test_validar_xml_sin_certificado(monkeypatch):
    monkeypatch.setattr(validacion, 'leer_ecf',
                        lambda b: dataclasses.replace(leer_ecf(b), certificados_der=[]))
    r = validar_xml(MUESTRA_XML, None, CONFIG_SIN_RED, ahora=T0)
    assert r.vigencia.resultado == FALLO and r.vigencia.detalle == 'Sin certificado'
    assert r.entidad_certificadora.resultado == FALLO
    assert r.revocacion.resultado == NO_VERIFICABLE and r.revocacion.detalle == 'Sin cadena de confianza'


def test_validar_xml_nunca_lanza(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError('explotó')
    monkeypatch.setattr(validacion, 'verificar_integridad', boom)
    monkeypatch.setattr(validacion, 'verificar_revocacion', boom)
    r = validar_xml(MUESTRA_XML, QR_MUESTRA, CONFIG_SIN_RED, ahora=T0)
    assert r.integridad.resultado == FALLO and 'explotó' in r.integridad.detalle
    assert r.revocacion.resultado == NO_VERIFICABLE and 'explotó' in r.revocacion.detalle
    assert r.vigencia.resultado == OK


def test_por_defecto():
    cfg = ConfigValidacion.por_defecto()
    assert cfg.xsd_dir == XSD_DIR and cfg.ca_dir.name == 'confianza' and cfg.rnc_terpel is None
    assert cfg.ca_dir.is_absolute()
    assert cfg.descargar is http_descargar and cfg.ocsp_post is http_ocsp_post


class _Params:
    def __init__(self, d):
        self.d = d

    def get(self, clave, default=None):
        return self.d.get(clave, default)


def test_config_desde_parametros(tmp_path):
    cfg = config_validacion_desde_parametros(
        _Params({'RNC_TERPEL': ' 101107146 ', 'CA_CONFIANZA_DIR': str(tmp_path)}))
    assert cfg.rnc_terpel == '101107146' and cfg.ca_dir == tmp_path
    vacio = config_validacion_desde_parametros(_Params({}))
    assert vacio.rnc_terpel is None and vacio.ca_dir.name == 'confianza'


# --- HTTP real, con requests simulado ---
class _Resp:
    def __init__(self, cuerpo: bytes):
        self.cuerpo = cuerpo

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size=8192):
        for i in range(0, len(self.cuerpo), chunk_size):
            yield self.cuerpo[i:i + chunk_size]

    def close(self):
        pass


class _Requests:
    def __init__(self, cuerpo=b'ok'):
        self.llamadas, self.cuerpo = [], cuerpo

    def get(self, url, **kw):
        self.llamadas.append(('get', url, kw))
        return _Resp(self.cuerpo)

    def post(self, url, **kw):
        self.llamadas.append(('post', url, kw))
        return _Resp(self.cuerpo)


@pytest.mark.parametrize('url', ['file:///etc/passwd', 'ftp://x/y', 'gopher://x', '/ruta', ''])
def test_http_rechaza_esquemas_no_http(monkeypatch, url):
    falso = _Requests()
    monkeypatch.setattr(validacion, 'requests', falso)
    with pytest.raises(ValueError):
        http_descargar(url)
    with pytest.raises(ValueError):
        http_ocsp_post(url, b'x')
    assert falso.llamadas == []


def test_http_descargar_timeout_y_cuerpo(monkeypatch):
    falso = _Requests(b'datos')
    monkeypatch.setattr(validacion, 'requests', falso)
    assert http_descargar('https://cps.viafirma.do/x.crt') == b'datos'
    assert falso.llamadas[0][2]['timeout'] == 5 and falso.llamadas[0][2]['stream'] is True


def test_http_descargar_tope_2mb(monkeypatch):
    monkeypatch.setattr(validacion, 'requests', _Requests(b'a' * (2 * 1024 * 1024 + 1)))
    with pytest.raises(ValueError):
        http_descargar('http://x/y')
    monkeypatch.setattr(validacion, 'requests', _Requests(b'a' * (2 * 1024 * 1024)))
    assert len(http_descargar('http://x/y')) == 2 * 1024 * 1024


def test_http_ocsp_post_cabecera_timeout_y_tope(monkeypatch):
    falso = _Requests(b'resp')
    monkeypatch.setattr(validacion, 'requests', falso)
    assert http_ocsp_post('http://ocsp.x/o', b'req') == b'resp'
    kw = falso.llamadas[0][2]
    assert kw['headers'] == {'Content-Type': 'application/ocsp-request'}
    assert kw['timeout'] == 5 and kw['data'] == b'req'
    monkeypatch.setattr(validacion, 'requests', _Requests(b'a' * (64 * 1024 + 1)))
    with pytest.raises(ValueError):
        http_ocsp_post('http://ocsp.x/o', b'req')
