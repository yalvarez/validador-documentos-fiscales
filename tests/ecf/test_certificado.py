from datetime import datetime
from pathlib import Path

from cryptography.hazmat.primitives.serialization import Encoding

from ayudantes import AYER, MANANA, MUESTRA_XML, T0
from common.ecf.lectura import leer_ecf
from common.ecf.modelos import FALLO, OK, ZONA_RD
from common.ecf.verificaciones import certificado
from common.ecf.verificaciones.certificado import (
    cargar_certificado, descripcion_certificado, verificar_entidad_certificadora,
    verificar_vigencia)
from pki import crear_ca, crear_ca_con_subject, crear_hoja, crear_intermedio

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


def test_ancla_incrustada_con_firma_invalida_no_pasa(tmp_path):
    # Hoja firmada por otra clave que dice ser emitida por el ancla: la firma no verifica
    ancla = cargar_certificado((CONFIANZA_DIR / 'viafirma-dominicana.pem').read_bytes())
    k, falsa = crear_ca_con_subject(ancla.subject)
    _, hoja = crear_hoja(k, falsa, AYER, MANANA)
    v, cadena = verificar_entidad_certificadora(hoja, [ancla], CONFIANZA_DIR)
    assert v.resultado == FALLO and cadena is None


def test_intermedio_descargado_por_aia(tmp_path):
    ca_k, ca = crear_ca('Raiz')
    int_k, inter = crear_intermedio(ca_k, ca, 'Emisora')
    (tmp_path / 'emisora.pem').write_bytes(inter.public_bytes(Encoding.PEM))
    _, hoja = crear_hoja(int_k, inter, AYER, MANANA, ca_issuers_url='http://aia.prueba/emisora.crt')
    descargas = []

    def descargar(u):
        descargas.append(u)
        return inter.public_bytes(Encoding.DER)

    v, cadena = verificar_entidad_certificadora(hoja, [], tmp_path, descargar)
    assert v.resultado == OK and cadena[1] == inter


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
