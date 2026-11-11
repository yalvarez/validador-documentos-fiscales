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
