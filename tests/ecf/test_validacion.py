import dataclasses

import pytest
import requests
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
PUBLICA = '93.184.216.34'


@pytest.fixture(autouse=True)
def _dns_publico(monkeypatch):
    monkeypatch.setattr(validacion, '_resolver', lambda host, puerto: [PUBLICA])


class _Resp:
    def __init__(self, cuerpo: bytes, status_code: int = 200, trozos_lentos=None):
        self.cuerpo, self.status_code, self.trozos_lentos = cuerpo, status_code, trozos_lentos

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size=8192):
        if self.trozos_lentos:
            yield from self.trozos_lentos()
            return
        for i in range(0, len(self.cuerpo), chunk_size):
            yield self.cuerpo[i:i + chunk_size]

    def close(self):
        pass


class _Requests:
    def __init__(self, cuerpo=b'ok', status_code=200, trozos_lentos=None):
        self.llamadas, self.cuerpo = [], cuerpo
        self.status_code, self.trozos_lentos = status_code, trozos_lentos

    Request = requests.Request  # solo prepara la petición, sin red

    def Session(self):
        return self

    def mount(self, prefijo, adaptador):
        self.adaptadores = {**getattr(self, 'adaptadores', {}), prefijo: adaptador}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def close(self):
        pass

    def send(self, prepared, **kw):
        self.llamadas.append((prepared.method.lower(), prepared.url, {**kw, 'prepared': prepared}))
        return _Resp(self.cuerpo, self.status_code, self.trozos_lentos)


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
    assert kw['prepared'].headers['Content-Type'] == 'application/ocsp-request'
    assert kw['timeout'] == 5 and kw['prepared'].body == b'req'
    monkeypatch.setattr(validacion, 'requests', _Requests(b'a' * (64 * 1024 + 1)))
    with pytest.raises(ValueError):
        http_ocsp_post('http://ocsp.x/o', b'req')


@pytest.mark.parametrize('url', [
    'http://127.0.0.1/x', 'http://10.0.0.5/x', 'http://169.254.169.254/latest/meta-data',
    'http://[::1]/x', 'http://[::ffff:127.0.0.1]/x', 'http://0.0.0.0/x', 'http://192.168.1.1:8080/x',
    'http://localhost./x', 'http:///sin-host'])
def test_http_rechaza_destinos_no_publicos(monkeypatch, url):
    falso = _Requests()
    monkeypatch.setattr(validacion, 'requests', falso)
    monkeypatch.setattr(validacion, '_resolver', lambda h, p: ['127.0.0.1'])
    with pytest.raises(ValueError):
        http_descargar(url)
    with pytest.raises(ValueError):
        http_ocsp_post(url, b'x')
    assert falso.llamadas == []


def test_http_rechaza_hostname_que_resuelve_a_ip_privada(monkeypatch):
    falso = _Requests()
    monkeypatch.setattr(validacion, 'requests', falso)
    monkeypatch.setattr(validacion, '_resolver', lambda h, p: [PUBLICA, '10.1.2.3'])
    with pytest.raises(ValueError, match='Destino no permitido: interno.ejemplo.com'):
        http_descargar('http://Interno.Ejemplo.com./a.crt')
    assert falso.llamadas == []


def test_http_destino_publico_sin_redirecciones(monkeypatch):
    falso = _Requests(b'ok')
    monkeypatch.setattr(validacion, 'requests', falso)
    assert http_descargar('http://cps.viafirma.do/a.crt') == b'ok'
    assert http_ocsp_post('http://ocsp.viafirma.do/o', b'q') == b'ok'
    assert all(ll[2]['allow_redirects'] is False for ll in falso.llamadas) and len(falso.llamadas) == 2


def test_http_redireccion_es_error(monkeypatch):
    monkeypatch.setattr(validacion, 'requests', _Requests(b'', status_code=302))
    with pytest.raises(ValueError, match='Redirección'):
        http_descargar('http://cps.viafirma.do/a.crt')
    with pytest.raises(ValueError, match='Redirección'):
        http_ocsp_post('http://ocsp.viafirma.do/o', b'q')


def test_http_plazo_total_excedido(monkeypatch):
    ahora = [0.0]
    monkeypatch.setattr(validacion, '_reloj', lambda: ahora[0])

    def lento():
        for _ in range(10):
            ahora[0] += 4  # cada trozo tarda 4 s: dentro del timeout por operación, pero acumula
            yield b'a'

    monkeypatch.setattr(validacion, 'requests', _Requests(trozos_lentos=lento))
    with pytest.raises(ValueError, match='plazo total'):
        http_descargar('http://cps.viafirma.do/a.crt')


def test_tope_de_descargas_por_validacion():
    contador = [0]
    llamadas = []
    f = validacion._con_tope(lambda u: llamadas.append(u) or b'x', contador)
    for _ in range(validacion.MAX_FETCHES):
        f('u')
    with pytest.raises(ConnectionError):
        f('u')
    assert len(llamadas) == validacion.MAX_FETCHES


def test_validar_xml_degrada_al_superar_tope_de_descargas(tmp_path):
    (tmp_path / 'ca.pem').write_bytes(CA_PRUEBA.public_bytes(Encoding.PEM))
    veces = []

    def ocsp(u, b):
        veces.append(u)
        raise ConnectionError('caído')

    def crl(u):
        veces.append(u)
        raise ConnectionError('caído')

    cfg = config_con(ca_dir=tmp_path, ocsp_post=ocsp, descargar=crl)
    r = validar_xml(ecf_de_prueba('E310000000002'), None, cfg, ahora=T0)
    assert r.revocacion.resultado == NO_VERIFICABLE
    assert len(veces) <= validacion.MAX_FETCHES


@pytest.mark.parametrize('url', [
    'http://127.0.0.1\\@example.com/x', 'http://evil@127.0.0.1/', 'http://user:pw@example.com/x',
    'http://example.com/a b', 'http://example.com/a\tb', 'http://example.com/\x00', 'http://exámple.com/x',
    'http://example.com/\n'])
def test_http_rechaza_urls_ambiguas(monkeypatch, url):
    falso = _Requests()
    monkeypatch.setattr(validacion, 'requests', falso)
    with pytest.raises(ValueError, match='URL no permitida'):
        http_descargar(url)
    with pytest.raises(ValueError, match='URL no permitida'):
        http_ocsp_post(url, b'x')
    assert falso.llamadas == []


def test_http_comprueba_el_host_de_la_peticion_preparada(monkeypatch):
    """Lo comprobado y lo conectado es el mismo objeto: si el host preparado es privado, no se envía."""
    falso = _Requests()
    monkeypatch.setattr(validacion, 'requests', falso)
    monkeypatch.setattr(validacion, '_resolver', lambda h, p: ['10.0.0.1'] if h == 'interno.x' else [PUBLICA])
    with pytest.raises(ValueError, match='Destino no permitido'):
        http_descargar('http://interno.x/a')
    assert falso.llamadas == []
    assert http_descargar('http://publico.x/a') == b'ok'
    assert falso.llamadas[0][1] == f'http://{PUBLICA}/a'
    assert falso.llamadas[0][2]['prepared'].headers['Host'] == 'publico.x'


def test_http_ignora_proxies_del_entorno(monkeypatch):  # T7
    class _SinEntorno(_Requests):
        trust_env = True

        def send(self, prepared, **kw):
            self.trust_env_al_enviar = self.trust_env
            return super().send(prepared, **kw)
    falso = _SinEntorno(b'ok')
    monkeypatch.setattr(validacion, 'requests', falso)
    assert http_descargar('http://cps.viafirma.do/a.crt') == b'ok'
    assert falso.trust_env_al_enviar is False


def test_http_conecta_a_la_ip_validada_aunque_el_dns_cambie(monkeypatch):
    """DNS rebinding: la segunda resolución apunta a loopback, pero la conexión usa la IP ya validada."""
    respuestas = iter([[PUBLICA], ['127.0.0.1'], ['127.0.0.1']])
    monkeypatch.setattr(validacion, '_resolver', lambda h, p: next(respuestas))
    falso = _Requests(b'ok')
    monkeypatch.setattr(validacion, 'requests', falso)
    assert http_ocsp_post('http://ocsp.rebind.x:8080/o?a=1', b'q') == b'ok'
    metodo, url, kw = falso.llamadas[0]
    assert url == f'http://{PUBLICA}:8080/o?a=1'
    assert kw['prepared'].headers['Host'] == 'ocsp.rebind.x:8080'


def test_https_fija_ip_con_sni_y_verificacion_del_nombre_original(monkeypatch):
    falso = _Requests(b'ok')
    monkeypatch.setattr(validacion, 'requests', falso)
    assert http_descargar('https://cps.viafirma.do/x.crt') == b'ok'
    assert falso.llamadas[0][1] == f'https://{PUBLICA}/x.crt'
    adaptador = falso.adaptadores['https://']
    kw = adaptador.poolmanager.connection_pool_kw
    assert kw['server_hostname'] == 'cps.viafirma.do' and kw['assert_hostname'] == 'cps.viafirma.do'


def test_http_ipv6_publica_entre_corchetes(monkeypatch):
    monkeypatch.setattr(validacion, '_resolver', lambda h, p: ['2606:2800:220:1::248'])
    falso = _Requests(b'ok')
    monkeypatch.setattr(validacion, 'requests', falso)
    assert http_descargar('http://v6.x/a') == b'ok'
    assert falso.llamadas[0][1] == 'http://[2606:2800:220:1::248]/a'
