from datetime import datetime, timedelta
from pathlib import Path

from cryptography.hazmat.primitives.serialization import Encoding

from ayudantes import AYER, MANANA, MUESTRA_XML, T0
from common.ecf.lectura import leer_ecf
from common.ecf.modelos import FALLO, OK, ZONA_RD
from common.ecf.verificaciones import certificado
from common.ecf.verificaciones.certificado import (
    cargar_certificado, descripcion_certificado, verificar_entidad_certificadora,
    verificar_vigencia)
from pki import (crear_ca, crear_ca_con_subject, crear_hoja, crear_intermedio,
                 crear_subordinado)

CONFIANZA_DIR = Path(certificado.__file__).parents[1] / 'confianza'


def hoja_muestra():
    return cargar_certificado(leer_ecf(MUESTRA_XML).certificados_der[0])


def test_muestra_vigente():
    v = verificar_vigencia(hoja_muestra(), leer_ecf(MUESTRA_XML).fecha_firma)
    assert v.resultado == OK and v.detalle == 'Vigente 2026-01-12 a 2027-01-12'


def test_muestra_entidad_autorizada():
    v, cadena = verificar_entidad_certificadora(hoja_muestra(), [], CONFIANZA_DIR)
    assert v.resultado == OK and 'VIAFIRMA DOMINICANA' in v.detalle and len(cadena) == 2


def test_fuera_de_vigencia():
    _, c = crear_hoja(*crear_ca('CA'), datetime(2025, 1, 1, tzinfo=ZONA_RD),
                      datetime(2025, 6, 1, tzinfo=ZONA_RD))
    assert verificar_vigencia(c, datetime(2025, 7, 1, tzinfo=ZONA_RD)).resultado == FALLO


def test_sin_certificado():
    assert verificar_vigencia(None, T0).resultado == FALLO


def test_sin_fecha_firma():
    v = verificar_vigencia(hoja_muestra(), None)
    assert v.resultado == FALLO and v.detalle == 'Sin FechaHoraFirma'


def test_carpeta_vacia(tmp_path):
    v, cadena = verificar_entidad_certificadora(hoja_muestra(), [], tmp_path)
    assert v.resultado == FALLO and cadena is None


def test_ca_falsa_con_el_mismo_nombre():
    ancla = cargar_certificado((CONFIANZA_DIR / 'viafirma-dominicana.pem').read_bytes())
    k, falsa = crear_ca_con_subject(ancla.subject)
    _, hoja = crear_hoja(k, falsa, AYER, MANANA)
    assert verificar_entidad_certificadora(hoja, [falsa], CONFIANZA_DIR)[0].resultado == FALLO


def test_ancla_incrustada_con_firma_invalida_no_pasa():
    # Hoja firmada por otra clave que dice ser emitida por el ancla: la firma no verifica
    ancla = cargar_certificado((CONFIANZA_DIR / 'viafirma-dominicana.pem').read_bytes())
    k, falsa = crear_ca_con_subject(ancla.subject)
    _, hoja = crear_hoja(k, falsa, AYER, MANANA)
    v, cadena = verificar_entidad_certificadora(hoja, [ancla], CONFIANZA_DIR)
    assert v.resultado == FALLO and cadena is None


def test_intermedio_descargado_por_aia(tmp_path):
    ca_k, ca = crear_ca('Raiz')
    int_k, inter = crear_intermedio(ca_k, ca, 'Emisora')
    (tmp_path / 'raiz.pem').write_bytes(ca.public_bytes(Encoding.PEM))  # el ancla es la raíz; el intermedio se descarga
    _, hoja = crear_hoja(int_k, inter, AYER, MANANA, ca_issuers_url='http://aia.prueba/emisora.crt')
    descargas = []

    def descargar(u):
        descargas.append(u)
        return inter.public_bytes(Encoding.DER)

    v, cadena = verificar_entidad_certificadora(hoja, [], tmp_path, descargar)
    assert v.resultado == OK and cadena[1] == inter
    assert descargas == ['http://aia.prueba/emisora.crt']


def test_cadena_hasta_ancla_con_incrustados(tmp_path):
    ca_k, ca = crear_ca('Raiz')
    int_k, inter = crear_intermedio(ca_k, ca, 'Emisora')
    (tmp_path / 'raiz.pem').write_bytes(ca.public_bytes(Encoding.PEM))
    _, hoja = crear_hoja(int_k, inter, AYER, MANANA)
    v, cadena = verificar_entidad_certificadora(hoja, [inter], tmp_path)
    assert v.resultado == OK and cadena == [hoja, inter, ca]


def test_descripcion_certificado():
    titular, emisor, serie = descripcion_certificado(hoja_muestra())
    assert titular == 'AURELIO ALCANTARA FAMILIA'
    assert emisor == 'VIAFIRMA QUALIFIED CERTIFICATES'
    assert serie == format(hoja_muestra().serial_number, 'x')


def _ancla_en(tmp_path, ca):
    (tmp_path / 'ancla.pem').write_bytes(ca.public_bytes(Encoding.PEM))


def test_hoja_falsificada_con_certificado_que_no_es_ca(tmp_path):
    ca_k, ca = crear_ca('Raiz')
    _ancla_en(tmp_path, ca)
    legit_k, legit = crear_subordinado(ca_k, ca, 'Legit', es_ca=False)
    _, falsa = crear_hoja(legit_k, legit, AYER, MANANA)
    v, cadena = verificar_entidad_certificadora(falsa, [legit], tmp_path)
    assert v.resultado == FALLO and cadena is None


def test_emisor_sin_key_cert_sign(tmp_path):
    ca_k, ca = crear_ca('Raiz')
    _ancla_en(tmp_path, ca)
    i_k, inter = crear_subordinado(ca_k, ca, 'SinFirma', key_cert_sign=False)
    _, hoja = crear_hoja(i_k, inter, AYER, MANANA)
    assert verificar_entidad_certificadora(hoja, [inter], tmp_path)[0].resultado == FALLO


def test_pathlen_cero_con_otro_intermedio_debajo(tmp_path):
    ca_k, ca = crear_ca('Raiz')
    _ancla_en(tmp_path, ca)
    a_k, a = crear_subordinado(ca_k, ca, 'A', path_length=0)
    b_k, b = crear_subordinado(a_k, a, 'B')
    _, hoja = crear_hoja(b_k, b, AYER, MANANA)
    assert verificar_entidad_certificadora(hoja, [a, b], tmp_path)[0].resultado == FALLO
    a_k, a = crear_subordinado(ca_k, ca, 'A', path_length=1)
    b_k, b = crear_subordinado(a_k, a, 'B')
    _, hoja = crear_hoja(b_k, b, AYER, MANANA)
    assert verificar_entidad_certificadora(hoja, [a, b], tmp_path)[0].resultado == OK


def test_intermedio_vencido_al_firmar(tmp_path):
    ca_k, ca = crear_ca('Raiz')
    _ancla_en(tmp_path, ca)
    i_k, inter = crear_subordinado(ca_k, ca, 'Vencido', not_before=T0 - timedelta(days=400),
                                   not_after=T0 - timedelta(days=100))
    _, hoja = crear_hoja(i_k, inter, T0 - timedelta(days=300), T0 + timedelta(days=30))
    v, cadena = verificar_entidad_certificadora(hoja, [inter], tmp_path, fecha_firma=T0)
    assert v.resultado == FALLO and 'Vencido' in v.detalle and cadena is None
    v, _ = verificar_entidad_certificadora(hoja, [inter], tmp_path,
                                           fecha_firma=T0 - timedelta(days=200))
    assert v.resultado == OK


def test_ancla_vencida_al_firmar(tmp_path):
    k, ca = crear_ca('Raiz')
    _ancla_en(tmp_path, ca)
    _, hoja = crear_hoja(k, ca, AYER, MANANA)
    futura = datetime(2045, 1, 1, tzinfo=ZONA_RD)
    assert verificar_entidad_certificadora(hoja, [], tmp_path, fecha_firma=futura)[0].resultado == FALLO


def test_muestra_con_su_fecha_firma():
    v, _ = verificar_entidad_certificadora(hoja_muestra(), [], CONFIANZA_DIR,
                                           fecha_firma=leer_ecf(MUESTRA_XML).fecha_firma)
    assert v.resultado == OK


def test_aia_solo_http(tmp_path):
    ca_k, ca = crear_ca('Raiz')
    int_k, inter = crear_intermedio(ca_k, ca, 'Emisora')
    _ancla_en(tmp_path, ca)
    _, hoja = crear_hoja(int_k, inter, AYER, MANANA, ca_issuers_url='ldap://aia.prueba/x')
    llamadas = []
    v, _ = verificar_entidad_certificadora(hoja, [], tmp_path,
                                           lambda u: llamadas.append(u) or b'')
    assert v.resultado == FALLO and llamadas == []


import pytest  # noqa: E402
from cryptography.x509.oid import ExtendedKeyUsageOID as EKU  # noqa: E402

from pki import crear_hoja_con_usos  # noqa: E402


def _entidad_con_usos(tmp_path, **usos):
    ca_k, ca_c = crear_ca('CA USOS')
    (tmp_path / 'ca.pem').write_bytes(ca_c.public_bytes(Encoding.PEM))
    _, hoja = crear_hoja_con_usos(ca_k, ca_c, **usos)
    return verificar_entidad_certificadora(hoja, [], tmp_path)[0]


@pytest.mark.parametrize('usos', [
    dict(key_usage={'key_encipherment': True}),
    dict(key_usage={'key_cert_sign': True, 'crl_sign': True}),
    dict(eku=[EKU.SERVER_AUTH]),
    dict(eku=[EKU.OCSP_SIGNING]),
    dict(eku=[EKU.SERVER_AUTH, EKU.OCSP_SIGNING]),
    dict(key_usage={'digital_signature': True}, eku=[EKU.SERVER_AUTH]),
])
def test_uso_de_clave_no_apto_para_firma(tmp_path, usos):  # M10
    v = _entidad_con_usos(tmp_path, **usos)
    assert v.resultado == FALLO and v.detalle == 'Uso de clave no apto para firma'


@pytest.mark.parametrize('usos', [
    dict(),
    dict(key_usage={'digital_signature': True}),
    dict(key_usage={'content_commitment': True}),
    dict(eku=[EKU.CLIENT_AUTH, EKU.EMAIL_PROTECTION]),
    dict(key_usage={'content_commitment': True}, eku=[EKU.SERVER_AUTH, EKU.CLIENT_AUTH]),
])
def test_uso_de_clave_apto_para_firma(tmp_path, usos):  # M10
    assert _entidad_con_usos(tmp_path, **usos).resultado == OK


def _aia_escenario(tmp_path):
    ca_k, ca = crear_ca('Raiz')
    int_k, inter = crear_intermedio(ca_k, ca, 'Emisora')
    (tmp_path / 'raiz.pem').write_bytes(ca.public_bytes(Encoding.PEM))
    _, hoja = crear_hoja(int_k, inter, AYER, MANANA, ca_issuers_url='http://aia.prueba/emisora.crt')
    descargas = []

    def descargar(u):
        descargas.append(u)
        return inter.public_bytes(Encoding.DER)
    return hoja, descargar, descargas


def test_cache_aia_expira_a_las_24h(tmp_path, monkeypatch):  # M11
    hoja, descargar, descargas = _aia_escenario(tmp_path)
    instante = [1000.0]
    monkeypatch.setattr(certificado, '_reloj', lambda: instante[0])
    verificar_entidad_certificadora(hoja, [], tmp_path, descargar)
    instante[0] += 24 * 3600 - 1
    verificar_entidad_certificadora(hoja, [], tmp_path, descargar)
    assert len(descargas) == 1
    instante[0] += 1
    v, _ = verificar_entidad_certificadora(hoja, [], tmp_path, descargar)
    assert v.resultado == OK and len(descargas) == 2


def test_cache_aia_acotada_descarta_la_mas_antigua(tmp_path):  # M11
    hoja, descargar, descargas = _aia_escenario(tmp_path)
    verificar_entidad_certificadora(hoja, [], tmp_path, descargar)
    _, otro = crear_ca('Otro')
    for i in range(certificado._MAX_CACHE_AIA):
        certificado._a_cache_aia(f'http://aia.prueba/{i}.crt', otro)
    assert len(certificado._cache_aia) == certificado._MAX_CACHE_AIA
    assert 'http://aia.prueba/emisora.crt' not in certificado._cache_aia
    verificar_entidad_certificadora(hoja, [], tmp_path, descargar)
    assert len(descargas) == 2 and len(certificado._cache_aia) == certificado._MAX_CACHE_AIA
