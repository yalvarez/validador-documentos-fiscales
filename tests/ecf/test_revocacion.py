from datetime import timedelta

from ayudantes import AYER, MANANA, T0
from common.ecf.modelos import FALLO, NO_VERIFICABLE, OK
from common.ecf.verificaciones.revocacion import verificar_revocacion
from pki import crear_ca, crear_delegado_ocsp, crear_hoja, firmar_crl, responder_ocsp

FIRMA = T0
ca_k, ca = crear_ca('CA Rev')
hoja_k, hoja = crear_hoja(ca_k, ca, AYER - timedelta(days=30), MANANA, ocsp_url='http://ocsp.prueba', crl_url='http://crl.prueba/a.crl')
_, hoja_sin_urls = crear_hoja(ca_k, ca, AYER, MANANA)
def resp_ocsp(estado, revocado_en=None, firmante=None, serie=None, incluir=()):
    fk, fc = firmante or (ca_k, ca)
    return responder_ocsp(fk, fc, hoja, estado, revocado_en, serie, emisor=ca, incluir_certificados=incluir)
def crl(revocados, firmante=None, next_update=T0 + timedelta(days=4)):
    fk, fc = firmante or (ca_k, ca)
    return firmar_crl(fk, fc, revocados, next_update)
def lanza(*a): raise ConnectionError('caído')
def revisar(ocsp_post=lanza, descargar=lanza, h=hoja): return verificar_revocacion(h, ca, FIRMA, ocsp_post, descargar, T0)

def test_ocsp_good(): assert revisar(lambda u, b: resp_ocsp('GOOD')).detalle == 'OCSP: good'
def test_ocsp_revocado_antes(): assert revisar(lambda u, b: resp_ocsp('REVOKED', FIRMA - timedelta(days=1))).resultado == FALLO
def test_ocsp_revocado_despues():
    r = revisar(lambda u, b: resp_ocsp('REVOKED', FIRMA + timedelta(days=1)))
    assert r.resultado == OK and (FIRMA + timedelta(days=1)).date().isoformat() in r.detalle
def test_ocsp_firmado_por_otra_ca_se_ignora():
    otra = crear_ca('Otra')
    assert revisar(lambda u, b: resp_ocsp('GOOD', firmante=otra)).resultado == NO_VERIFICABLE
def test_ocsp_serie_distinta_se_ignora(): assert revisar(lambda u, b: resp_ocsp('GOOD', serie=12345)).resultado == NO_VERIFICABLE
def test_ocsp_delegado_emitido_por_emisor_se_acepta():
    dk, dc = crear_delegado_ocsp(ca_k, ca)
    r = revisar(lambda u, b: resp_ocsp('GOOD', firmante=(dk, dc), incluir=[dc]))
    assert r.resultado == OK and r.detalle == 'OCSP: good'
def test_ocsp_delegado_de_otra_ca_se_rechaza():
    ok_, oc = crear_ca('Otra')
    dk, dc = crear_delegado_ocsp(ok_, oc)
    assert revisar(lambda u, b: resp_ocsp('GOOD', firmante=(dk, dc), incluir=[dc])).resultado == NO_VERIFICABLE
def test_ocsp_delegado_sin_eku_se_rechaza():
    dk, dc = crear_delegado_ocsp(ca_k, ca, con_eku=False)
    assert revisar(lambda u, b: resp_ocsp('GOOD', firmante=(dk, dc), incluir=[dc])).resultado == NO_VERIFICABLE
def test_ocsp_caido_usa_crl_revocado():
    assert revisar(descargar=lambda u: crl({hoja.serial_number: FIRMA - timedelta(days=1)})).resultado == FALLO
def test_crl_no_revocado(): assert revisar(descargar=lambda u: crl({})).detalle == 'CRL: no revocado'
def test_crl_firmada_por_otra_ca_se_ignora():
    assert revisar(descargar=lambda u: crl({}, firmante=crear_ca('Otra'))).resultado == NO_VERIFICABLE
def test_ambos_caidos(): assert revisar().resultado == NO_VERIFICABLE
def test_sin_urls(): assert revisar(h=hoja_sin_urls).detalle == 'Sin URL de revocación'
def test_crl_en_cache():
    llamadas = []
    def d(u): llamadas.append(u); return crl({})
    revisar(descargar=d); revisar(descargar=d); assert len(llamadas) == 1


# --- ronda de correcciones: frescura, CertID, CRL, compromiso de clave ---
from cryptography import x509
RF = x509.ReasonFlags
def _ro(estado='GOOD', revocado_en=None, emisor=ca, **kw):
    return lambda u, b: responder_ocsp(ca_k, ca, hoja, estado, revocado_en, emisor=emisor, **kw)
def _crl_de(revocados, next_update=T0 + timedelta(days=4), **kw):
    return lambda u: firmar_crl(ca_k, ca, revocados, next_update, **kw)
VIEJA = dict(this_update=T0 - timedelta(days=3), next_update=T0 - timedelta(days=1))

def test_ocsp_vencida_no_se_acepta(): assert revisar(_ro(**VIEJA)).resultado == NO_VERIFICABLE
def test_ocsp_vencida_cae_a_crl(): assert revisar(_ro(**VIEJA), _crl_de({})).detalle == 'CRL: no revocado'
def test_ocsp_this_update_futuro_no_se_acepta():
    assert revisar(_ro(this_update=T0 + timedelta(hours=1))).resultado == NO_VERIFICABLE
def test_ocsp_sin_next_update_antigua_no_se_acepta():
    assert revisar(_ro(this_update=T0 - timedelta(days=8), next_update=None)).resultado == NO_VERIFICABLE
def test_ocsp_sin_next_update_reciente_se_acepta():
    assert revisar(_ro(this_update=T0 - timedelta(days=1), next_update=None)).resultado == OK
def test_ocsp_certid_de_otro_emisor_no_se_acepta():
    _, otra = crear_ca('Otra')
    assert revisar(_ro(emisor=otra)).resultado == NO_VERIFICABLE
def test_crl_vencida_no_se_acepta():
    assert revisar(descargar=_crl_de({}, next_update=T0 - timedelta(hours=1))).resultado == NO_VERIFICABLE
def test_crl_con_otro_nombre_de_emisor_no_se_acepta():
    _, otra = crear_ca('Otra')
    assert revisar(descargar=lambda u: firmar_crl(ca_k, otra, {}, T0 + timedelta(days=4))).resultado == NO_VERIFICABLE
def test_crl_last_update_futuro_no_se_acepta():
    assert revisar(descargar=_crl_de({}, last_update=T0 + timedelta(hours=1))).resultado == NO_VERIFICABLE
def test_compromiso_de_clave_ocsp_falla_aunque_sea_posterior():
    r = revisar(_ro('REVOKED', FIRMA + timedelta(days=1), razon=RF.key_compromise))
    assert r.resultado == FALLO and r.detalle.startswith('Revocado por compromiso de clave el ')
def test_compromiso_de_clave_crl_falla_aunque_sea_posterior():
    s = hoja.serial_number
    assert revisar(descargar=_crl_de({s: FIRMA + timedelta(days=1)}, razones={s: RF.ca_compromise})).resultado == FALLO
def test_superseded_posterior_ocsp_ok():
    assert revisar(_ro('REVOKED', FIRMA + timedelta(days=1), razon=RF.superseded)).resultado == OK
def test_superseded_posterior_crl_ok():
    s = hoja.serial_number
    assert revisar(descargar=_crl_de({s: FIRMA + timedelta(days=1)}, razones={s: RF.superseded})).resultado == OK
def test_crl_pem(): assert revisar(descargar=_crl_de({}, pem=True)).detalle == 'CRL: no revocado'
def test_crl_sin_next_update_cache_una_hora(monkeypatch):
    # el constructor de cryptography exige next_update: se simula una CRL sin él
    from common.ecf.verificaciones import revocacion as rev
    real = rev._cargar_crl
    class SinNext:
        def __init__(self, c): self._c = c
        next_update_utc = None
        def __getattr__(self, n): return getattr(self._c, n)
        def __iter__(self): return iter(self._c)
    monkeypatch.setattr(rev, '_cargar_crl', lambda datos: SinNext(real(datos)))
    llamadas = []
    def d(u): llamadas.append(u); return firmar_crl(ca_k, ca, {}, T0 + timedelta(days=4))
    verificar_revocacion(hoja, ca, FIRMA, lanza, d, T0)
    verificar_revocacion(hoja, ca, FIRMA, lanza, d, T0 + timedelta(minutes=59))
    assert len(llamadas) == 1
    verificar_revocacion(hoja, ca, FIRMA, lanza, d, T0 + timedelta(minutes=61))
    assert len(llamadas) == 2


# --- ronda 2: CRL con alcance restringido ---
URL_CRL = 'http://crl.prueba/a.crl'
def _idp(**campos): return _crl_de({}, idp=campos)

def test_crl_solo_de_ca_no_se_acepta():
    assert revisar(descargar=_idp(only_contains_ca_certs=True)).resultado == NO_VERIFICABLE
def test_crl_indirecta_no_se_acepta():
    assert revisar(descargar=_idp(indirect_crl=True)).resultado == NO_VERIFICABLE
def test_crl_solo_de_atributos_no_se_acepta():
    assert revisar(descargar=_idp(only_contains_attribute_certs=True)).resultado == NO_VERIFICABLE
def test_crl_solo_algunas_razones_no_se_acepta():
    assert revisar(descargar=_idp(only_some_reasons=frozenset([RF.key_compromise]))).resultado == NO_VERIFICABLE
def test_crl_idp_de_otra_url_no_se_acepta():
    f = [x509.UniformResourceIdentifier('http://otra.prueba/b.crl')]
    assert revisar(descargar=_idp(full_name=f)).resultado == NO_VERIFICABLE
def test_crl_idp_de_la_misma_url_se_acepta():
    f = [x509.UniformResourceIdentifier(URL_CRL)]
    assert revisar(descargar=_idp(full_name=f)).detalle == 'CRL: no revocado'


# --- ronda 3 ---
def test_crl_idp_con_relative_name_no_se_acepta():
    rn = x509.RelativeDistinguishedName([x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, 'particion')])
    assert revisar(descargar=_idp(relative_name=rn)).resultado == NO_VERIFICABLE
def test_crl_delta_critica_no_se_acepta():
    assert revisar(descargar=_crl_de({}, delta=1)).resultado == NO_VERIFICABLE
def test_crl_delta_no_critica_no_se_acepta():
    assert revisar(descargar=_crl_de({}, delta=1, delta_critica=False)).resultado == NO_VERIFICABLE
