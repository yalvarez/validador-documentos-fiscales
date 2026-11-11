# Núcleo común: validación del XML, seguimiento y consulta — Plan de implementación

> **Para agentes:** SUB-SKILL REQUERIDA: usar superpowers:subagent-driven-development (recomendado) o superpowers:executing-plans para implementar este plan tarea por tarea. Los pasos usan casillas (`- [ ]`) para seguimiento.

**Objetivo:** construir el núcleo común a los dos modelos de ingesta:
- validar el XML de un e-CF (estructura, firma, certificado, cruce y comprador);
- registrar el comprobante en PostgreSQL;
- seguir su estado en la DGII con intervalos crecientes;
- exponer el último estado por API.

**Arquitectura:**
- **Paquete nuevo `src/common/ecf/`**, con funciones pequeñas y casi todas puras: lectura, verificaciones, DGII y calendario. La spec lo llama `common/xml_validator/`; la spec §9 deja la estructura al builder y aquí se elige `common/ecf/` porque el paquete cubre más que la validación.
- **Wrapper nuevo de PostgreSQL** en `src/db/`.
- **Worker separado** en `src/seguimiento/`.
- **Endpoint GET** en `src/api/backend.py`.
- **E/S externa inyectada:** toda llamada externa (HTTP a la DGII, OCSP/CRL/AIA, reloj, `sleep`) entra como parámetro, para que las pruebas no salgan a internet.

**Stack:** Python 3.11 (Docker) / 3.12 (local, Windows), FastAPI, PostgreSQL 16 + `psycopg[binary]>=3.1`, `signxml>=4`, `lxml`, `cryptography>=43`, `requests`, `beautifulsoup4`, `pytest`, `httpx`.

**Spec:** `docs/superpowers/specs/2026-11-10-nucleo-validacion-seguimiento-design.md`. Léela antes de cada tarea.

## Restricciones globales

**Entorno y dependencias**
- Imagen `python:3.11-slim`: no usar sintaxis posterior a 3.11. En local, los comandos se ejecutan en **Bash** (Git Bash), con el intérprete `.venv/Scripts/python`.
- `src/api/requirements.txt` agrega: `signxml>=4`, `cryptography>=43`, `psycopg[binary]>=3.1`.
- `requirements-dev.txt` (raíz): `-r src/api/requirements.txt`, `pytest`, `httpx`.

**Contrato y convenciones**
- Nombres de código, mensajes y detalles en español.
- Valores del contrato, exactos:
  - resultados: `OK`, `FALLO`, `NO_VERIFICABLE`;
  - estados: `PENDIENTE`, `ACEPTADO`, `ACEPTADO_CONDICIONAL`, `RECHAZADO`, `NO_ENCONTRADO`, `DESCONOCIDO`;
  - eventos: `REGISTRO`, `CONSULTA`, `CAMBIO_ESTADO`, `ERROR_CONSULTA`, `DOCUMENTO_REEMPLAZADO`.
- **Fechas:**
  - `ZONA_RD = timezone(timedelta(hours=-4))`. Todo `datetime` es *aware*: nunca `datetime.now()` sin zona; usar `datetime.now(ZONA_RD)`.
  - En la base, `TIMESTAMPTZ`.
  - La API convierte con `.astimezone(ZONA_RD)` antes de serializar, para que salga `-04:00`.

**Parámetros** (tabla `parametros`; si faltan o no son válidos, se usa el valor por defecto con `logging.warning`):
- `SEGUIMIENTO_INTERVALO_INICIAL_MIN=60`
- `SEGUIMIENTO_FACTOR=2`
- `SEGUIMIENTO_INTERVALO_MAX_MIN=1440`
- `SEGUIMIENTO_DURACION_MAX_HORAS=72`
- `SEGUIMIENTO_CICLO_SEG=300`
- `RNC_TERPEL` (vacío = `NO_VERIFICABLE`)
- `CA_CONFIANZA_DIR` (por defecto `Path(common.ecf.__file__).parent / 'confianza'`, **nunca** una ruta relativa al directorio de trabajo)

**Bytes del XML**
- El XML se maneja **siempre como bytes**. Se guarda en `BYTEA`, se hashea y se revalida con los bytes exactos recibidos.
- Toda función que reciba el XML lo pasa primero por `normalizar_xml_bytes()` (Tarea 2).

**Base de datos**
- El motor y la conexión se leen de las variables de entorno `DB_ENGINE` y `DB_CONNECTION_STRING`. Por defecto, `sqlite` y `./db.sqlite3`, que es el comportamiento actual.
- Las tablas nuevas solo existen en PostgreSQL. Con otro motor, el endpoint nuevo responde 503.

**Lo que no se toca**
- Los endpoints `/validar-factura-pdf-base64`, `/validar-factura-pdf-multipart` y `/validar-factura-params` no cambian de comportamiento.
- `WebValidator` no se modifica.

**Pruebas**
- Ninguna prueba sale a internet. La base es un PostgreSQL real (`docker compose up -d postgres`) en `TEST_DATABASE_URL`, por defecto `postgresql://validador:validador@localhost:5433/validador_test`.
- `pytest.ini` en la raíz:
  ```ini
  [pytest]
  pythonpath = src tests
  addopts = --import-mode=importlib
  testpaths = tests/bd tests/ecf tests/worker tests/endpoint
  ```
  Las carpetas de prueba **no** llevan `__init__.py` y **no** se llaman como paquetes de `src/` (`db`, `api`, `seguimiento`).
- Los ayudantes de prueba compartidos viven en `tests/ayudantes.py`. Cada tarea agrega lo suyo ahí, con las definiciones exactas que indica. Las pruebas los importan con `from ayudantes import ...`.

**Ritmo del worker:** espera 1 segundo entre comprobantes, también después de uno que falló.

## Hechos verificados (2026-11-10)

Estos datos se comprobaron con la muestra real y no hace falta volver a investigarlos:
- **Firma de la muestra:** `signxml.XMLVerifier` falla con la firma real por un defecto de C14N de lxml/libxml2 cuando el `Signature` usa namespace por defecto (issue #193 de signxml). Con `verifier.excise_empty_xmlns_declarations = True`:
  - la muestra da OK;
  - `MontoTotal` alterado → `InvalidDigest`;
  - `SignedInfo` alterado → `InvalidSignature`;
  - la muestra recodificada a ISO-8859-1 da OK.
- **QR del PDF de muestra:**
  `{'RncEmisor': '101616202', 'RncComprador': '101107146', 'ENCF': 'E310000002882', 'FechaEmision': '10-02-2026', 'MontoTotal': '1250.00', 'FechaFirma': '10-02-2026 09:22:21', 'CodigoSeguridad': 'BuLkvC'}`.
  `CodigoSeguridad == SignatureValue[:6]` ✔.
- **Certificado del firmante:**
  - `CN=AURELIO ALCANTARA FAMILIA`, persona física;
  - emisor `CN=VIAFIRMA QUALIFIED CERTIFICATES, OU=VIAFIRMA DOMINICANA, O=VIAFIRMA` (AIA: `https://cps.viafirma.do/viafirmaqtspsubca008.crt`);
  - ese intermedio lo emite `CN=VIAFIRMA QTSP ROOT CA, O=VIAFIRMA SOCIEDAD LIMITADA, C=ES` (AIA: `https://cps.viafirma.do/viafirmaqtsproot.crt`);
  - OCSP `http://ocsp.viafirma.do/ocsp008` responde `good`;
  - CRL `http://crl.viafirma.do/viafirmaqtspsubca008.crl` (DER, unos 90 KB, vigencia de 4 días).
- **Página de la DGII:**
  - la muestra devuelve una tabla `th`/`td` con `Estado => Aceptado` y `Monto Total => 1,250`;
  - un e-NCF inexistente devuelve HTTP 200 con la fila `<td colspan="2">No fue encontrada la factura (e-CF).</td>`.
- **XSD:** la DGII publicó varias versiones (formato v1.0 de 2024 y actualización v1.6). Se usa la vigente publicada en dgii.gov.do.

## Foco de revisión

1. **XML con BOM, con espacios antes de `<?xml` o codificado de verdad en ISO-8859-1:** debe leerse, validarse y verificar la firma igual que la muestra. → Tareas 2 y 4.
2. **Valores del QR con otro formato que el XML:** `MontoTotal=1250.00` contra `1250`, claves con otra capitalización, `FechaFirma` codificada en la URL, o `+` del código de seguridad convertido en espacio por `parse_qs`. El cruce debe dar `OK`. → Tarea 7.
3. **El tercero consulta con `e310000002882` en minúsculas o con espacios en la ruta:** debe encontrar el comprobante. → Tareas 11 y 13.
4. **Un comprobante que lanza excepción en cada ciclo, o una caída de la base:** no detiene el resto del ciclo ni mata el proceso. El comprobante sigue el mismo cierre por errores (hasta + 60 min). → Tarea 12.
5. **El mismo comprobante reenviado con el XML idéntico, o registrado dos veces a la vez:** no duplica, no marca reemplazo y no reinicia el seguimiento. → Tarea 11.

---

### Tarea 1: Infraestructura de pruebas, wrapper PostgreSQL y configuración por entorno

**Archivos:**
- Crear: `src/db/postgres_db_wrapper.py`, `src/db/config.py`, `docker/postgres-init/01-test-db.sql`, `pytest.ini`, `requirements-dev.txt`, `tests/conftest.py`, `tests/ayudantes.py`, `tests/bd/test_postgres_wrapper.py`
- Modificar: `src/db/db_factory.py`, `src/api/backend.py:15-38`, `src/api/requirements.txt`, `docker-compose.yml`, `.gitignore` (agregar `.venv/`)

**Interfaces:**
- Produce:
  - `PostgresDBWrapper(conn_str: str)`:
    - abre `psycopg.connect(conn_str, autocommit=True)`;
    - crea `facturas`, `mensajes_recibidos` y `parametros` (mismas columnas que en SQLite, con tipos de Postgres);
    - implementa todos los métodos de `BaseDBWrapper` más `is_message_processed` y `close()`;
    - en `__init__` reintenta la creación de tablas hasta 3 veces ante `psycopg.errors.UniqueViolation`, porque la API y el worker pueden arrancar a la vez.
  - `get_db_wrapper('postgres', conn_str)`.
  - `db.config.leer_config_db() -> tuple[str, dict | str]`.
  - En `tests/conftest.py`:
    - fixture `db_pg`: conecta a `TEST_DATABASE_URL`, **falla** si el nombre de la base no termina en `_test`, vacía todas las tablas del esquema `public` (lista dinámica de `pg_tables`, `TRUNCATE ... RESTART IDENTITY CASCADE`), entrega el wrapper y lo cierra al final;
    - fixture `autouse` `limpiar_caches_ecf`: llama a las funciones `limpiar_caches()` de los módulos que existan (Tareas 5 y 6). Usar `importlib.util.find_spec`, para que funcione aunque esos módulos aún no existan.
  - `tests/ayudantes.py`, con:
    - `RAIZ = Path(__file__).parents[1]`
    - `MUESTRA_XML = (RAIZ / 'tests/samples/101616202E310000002882.xml').read_bytes()`
    - `MUESTRA_PDF = RAIZ / 'tests/samples/101616202E310000002882.pdf'`
    - `T0 = datetime(2026, 11, 10, 10, 0, tzinfo=ZONA_RD)`. `ZONA_RD` se define aquí como `timezone(timedelta(hours=-4))` hasta que exista `common.ecf.modelos`; desde la Tarea 2 se importa de allí.

- [ ] **Paso 1:** en `docker-compose.yml`:
  - **servicio `postgres`:**
    - imagen `postgres:16`; usuario, clave y base `validador`; puerto `5433:5432`;
    - volumen `pgdata`;
    - montar `./docker/postgres-init:/docker-entrypoint-initdb.d`; el SQL hace `CREATE DATABASE validador_test;`;
    - `healthcheck`: `pg_isready -U validador`.
  - **servicio `backend`:** `DB_ENGINE=postgres`, `DB_CONNECTION_STRING=postgresql://validador:validador@postgres:5432/validador` y `depends_on: postgres: condition: service_healthy`.

  Ejecutar `docker compose up -d postgres && docker compose ps`. Esperado: `postgres` `healthy`.
- [ ] **Paso 2:** `python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt`. Esperado: termina sin errores.
- [ ] **Paso 3: escribir las pruebas que fallan**

```python
def test_parametros_ida_y_vuelta(db_pg):
    db_pg.set_param('X', '1', 'd'); db_pg.set_param('X', '2', 'd2')
    assert db_pg.get_param('X') == '2' and db_pg.get_param('NO_EXISTE') is None

def test_insert_factura_y_mensaje(db_pg):
    db_pg.insert_factura({'rncemisor': '101616202', 'estado': 'Aceptado'})
    assert db_pg.fetchall('SELECT rncemisor, estado FROM facturas') == [('101616202', 'Aceptado')]
    db_pg.insert_mensaje('m1', 'a@b.c', 'asunto')
    assert db_pg.is_message_processed('m1') is True

def test_config_db_por_defecto_es_sqlite(monkeypatch):
    monkeypatch.delenv('DB_ENGINE', raising=False); monkeypatch.delenv('DB_CONNECTION_STRING', raising=False)
    assert leer_config_db() == ('sqlite', {'db_path': './db.sqlite3'})

def test_config_db_postgres(monkeypatch):
    monkeypatch.setenv('DB_ENGINE', 'postgres'); monkeypatch.setenv('DB_CONNECTION_STRING', 'postgresql://u:p@h/d')
    assert leer_config_db() == ('postgres', 'postgresql://u:p@h/d')
```

- [ ] **Paso 4:** `.venv/Scripts/python -m pytest tests/bd -v`. Esperado: FALLA (`ModuleNotFoundError`).
- [ ] **Paso 5:** implementar. En `backend.py`, `get_db()` usa `leer_config_db()`. El resto de `backend.py` no cambia.
- [ ] **Paso 6:** `.venv/Scripts/python -m pytest tests/bd -v`. Esperado: PASA.
- [ ] **Paso 7:** commit — `feat(db): wrapper PostgreSQL y configuración de BD por entorno`.

---

### Tarea 2: Lectura del e-CF y tipos de resultado

**Archivos:**
- Crear: `src/common/ecf/__init__.py`, `src/common/ecf/modelos.py`, `src/common/ecf/lectura.py`, `tests/ecf/test_lectura.py`
- Modificar: `tests/ayudantes.py`

**Interfaces:**
- Produce, en `modelos.py`:
  - constantes `OK`, `FALLO`, `NO_VERIFICABLE`, los 6 estados y los 5 tipos de evento (cada constante tiene como valor su propio nombre);
  - `ZONA_RD`;
  - `@dataclass Verificacion(resultado: str, detalle: str = '')`;
  - `@dataclass ResultadoValidacionXML`:
    - campos `estructura`, `integridad`, `vigencia`, `entidad_certificadora`, `revocacion`, `cruce` y `comprador` (todos `Verificacion`);
    - `certificado_titular`, `certificado_emisor` y `certificado_serie` (`str | None`);
    - `a_dict() -> dict[str, dict[str, str]]` con los 7 campos.
- Produce, en `lectura.py`:
  - `normalizar_xml_bytes(b: bytes) -> bytes`: quita el prefijo BOM con `removeprefix(b'\xef\xbb\xbf')` y luego los espacios en blanco iniciales y finales.
  - `@dataclass DatosECF`:
    - `rnc_emisor: str`, `encf: str`, ambos en `strip().upper()`;
    - `rnc_comprador: str | None`, `tipo_ecf: str | None`;
    - `fecha_emision_texto: str | None`, `monto_total: Decimal | None`, `fecha_firma_texto: str | None`, tal como vienen en el XML;
    - `fecha_firma: datetime | None` (con `ZONA_RD`; `None` si falta o no se puede leer);
    - `razon_social_emisor: str | None`;
    - `signature_value: str | None` (sin espacios), `codigo_seguridad: str | None` (sus primeros 6 caracteres);
    - `certificados_der: list[bytes]`, en orden de aparición.
  - `leer_ecf(xml_bytes: bytes) -> DatosECF`.
  - `ErrorLecturaECF(Exception)`: XML mal formado, o sin `RNCEmisor` o `eNCF`.
- Agrega a `ayudantes.py`:
  - `XML_SIN_FIRMA` = `MUESTRA_XML` sin el nodo `Signature`, quitado con lxml y reserializado;
  - `muestra_en(encoding: str) -> bytes` = la muestra con la declaración `<?xml version="1.0" encoding="<encoding>"?>` y el contenido recodificado.

- [ ] **Paso 1: escribir las pruebas que fallan**

```python
def test_lee_muestra():
    d = leer_ecf(MUESTRA_XML)
    assert (d.rnc_emisor, d.encf, d.rnc_comprador, d.tipo_ecf) == ('101616202', 'E310000002882', '101107146', '31')
    assert d.monto_total == Decimal('1250') and d.fecha_firma_texto == '10-02-2026 09:22:21'
    assert d.fecha_firma == datetime(2026, 2, 10, 9, 22, 21, tzinfo=ZONA_RD)
    assert d.codigo_seguridad == 'BuLkvC' and len(d.certificados_der) == 1

@pytest.mark.parametrize('b', [b'\xef\xbb\xbf' + MUESTRA_XML, b'  \n' + MUESTRA_XML, muestra_en('ISO-8859-1')])  # Foco 1
def test_variantes_de_codificacion(b):
    assert leer_ecf(b).encf == 'E310000002882'

def test_sin_certificado_ni_fecha_firma():
    d = leer_ecf(XML_SIN_FIRMA.replace(b'<FechaHoraFirma>10-02-2026 09:22:21</FechaHoraFirma>', b''))
    assert d.certificados_der == [] and d.fecha_firma is None and d.codigo_seguridad is None

def test_xml_mal_formado():
    with pytest.raises(ErrorLecturaECF): leer_ecf(b'<ECF><Encabezado>')
```

- [ ] **Paso 2:** `.venv/Scripts/python -m pytest tests/ecf/test_lectura.py -v`. Esperado: FALLA.
- [ ] **Paso 3:** implementar con `lxml.etree.fromstring(normalizar_xml_bytes(b), XMLParser(resolve_entities=False, no_network=True))` y XPath con `local-name()`.
- [ ] **Paso 4:** `.venv/Scripts/python -m pytest tests/ecf/test_lectura.py -v`. Esperado: PASA.
- [ ] **Paso 5:** commit — `feat(ecf): lectura del XML e-CF y tipos de resultado`.

---

### Tarea 3: Verificación `estructura` (XSD de la DGII)

**Archivos:**
- Crear: `src/common/ecf/xsd/` (XSD y `FUENTE.md`), `src/common/ecf/verificaciones/__init__.py`, `src/common/ecf/verificaciones/estructura.py`, `tests/ecf/test_estructura.py`

**Interfaces:**
- Produce: `verificar_estructura(xml_bytes: bytes, tipo_ecf: str | None, xsd_dir: Path = XSD_DIR) -> Verificacion`, con `XSD_DIR = Path(__file__).parents[1] / 'xsd'`.

- [ ] **Paso 1:** descargar de dgii.gov.do (Comprobantes Fiscales Electrónicos › Documentación sobre e-CF › Formatos XML) la **versión vigente** de las XSD de los tipos 31, 32, 33, 34, 41, 43, 44, 45, 46 y 47. Guardarlas como `e-CF-<tipo>.xsd`.
  - Si importan otros esquemas por URL (por ejemplo xmldsig), guardar también esos archivos y reescribir `schemaLocation` a rutas locales, porque el parser va con `no_network=True`.
  - En `FUENTE.md` anotar las URL, la versión y la fecha.
- [ ] **Paso 2: escribir las pruebas que fallan**

```python
def test_muestra_valida(): assert verificar_estructura(MUESTRA_XML, '31').resultado == OK
def test_muestra_iso(): assert verificar_estructura(muestra_en('ISO-8859-1'), '31').resultado == OK
def test_falta_nodo_obligatorio():
    v = verificar_estructura(MUESTRA_XML.replace(b'<MontoTotal>1250</MontoTotal>', b''), '31')
    assert v.resultado == FALLO and 'MontoTotal' in v.detalle
def test_tipo_sin_xsd(tmp_path): assert verificar_estructura(MUESTRA_XML, '31', xsd_dir=tmp_path).resultado == NO_VERIFICABLE
def test_tipo_desconocido(): assert verificar_estructura(MUESTRA_XML, None).resultado == NO_VERIFICABLE
```

- [ ] **Paso 3:** `.venv/Scripts/python -m pytest tests/ecf/test_estructura.py -v`. Esperado: FALLA.
- [ ] **Paso 4:** implementar con `lxml.etree.XMLSchema`, guardando el esquema en caché por tipo. Si la XSD no declara el nodo `Signature`, se valida una copia del árbol sin él. **Si la muestra no valida contra la XSD vigente, detenerse y reportarlo**: no aflojar la validación.
- [ ] **Paso 5:** `.venv/Scripts/python -m pytest tests/ecf/test_estructura.py -v`. Esperado: PASA.
- [ ] **Paso 6:** commit — `feat(ecf): validación de estructura contra XSD de la DGII`.

---

### Tarea 4: Verificación `integridad` (firma XMLDSig) y PKI de prueba

**Archivos:**
- Crear: `src/common/ecf/verificaciones/integridad.py`, `tests/pki.py`, `tests/ecf/test_integridad.py`
- Modificar: `tests/ayudantes.py`

**Interfaces:**
- Produce:
  - `verificar_integridad(xml_bytes: bytes) -> Verificacion`.
  - `tests/pki.py`:
    - `crear_ca(nombre: str, org: str = 'CA PRUEBA', ou: str = 'CA PRUEBA DOMINICANA') -> tuple[key, cert]`;
    - `crear_intermedio(ca_key, ca_cert, nombre, org='CA PRUEBA', ou='CA PRUEBA DOMINICANA', ca_issuers_url: str | None = None) -> tuple[key, cert]`;
    - `crear_hoja(emisor_key, emisor_cert, not_before: datetime, not_after: datetime, ocsp_url: str | None = None, crl_url: str | None = None, ca_issuers_url: str | None = None) -> tuple[key, cert]`;
    - `firmar_ecf(xml_sin_firma: bytes, key, cert, fecha_firma: datetime) -> bytes`: escribe `<FechaHoraFirma>` con `fecha_firma` en formato `%d-%m-%Y %H:%M:%S` dentro de `ECF`, y firma con `signxml.XMLSigner(method=enveloped, signature_algorithm='rsa-sha256', digest_algorithm='sha256', c14n_algorithm='http://www.w3.org/TR/2001/REC-xml-c14n-20010315')`, con namespace por defecto (sin prefijo `ds:`), igual que la DGII.
  - Agrega a `ayudantes.py`:
    - `AYER = T0 - timedelta(days=1)`, `MANANA = T0 + timedelta(days=1)`;
    - `CA_PRUEBA_KEY, CA_PRUEBA = crear_ca('CA PRUEBA')` y `HOJA_PRUEBA_KEY, HOJA_PRUEBA = crear_hoja(CA_PRUEBA_KEY, CA_PRUEBA, T0 - timedelta(days=30), T0 + timedelta(days=365), ocsp_url='http://ocsp.prueba', crl_url='http://crl.prueba/a.crl')`, creados una sola vez al importar el módulo;
    - `ecf_de_prueba(encf: str, rnc_emisor: str = '101616202', fecha_firma: datetime = T0) -> bytes`: toma `XML_SIN_FIRMA`, reemplaza `<eNCF>` y `<RNCEmisor>` y lo firma con `HOJA_PRUEBA`. Su `entidad_certificadora` dará `FALLO` contra la carpeta real, y eso es lo esperado.

- [ ] **Paso 1: escribir las pruebas que fallan**

```python
def test_muestra_integra(): assert verificar_integridad(MUESTRA_XML).resultado == OK
@pytest.mark.parametrize('b', [b'\xef\xbb\xbf' + MUESTRA_XML, b'  \n' + MUESTRA_XML, muestra_en('ISO-8859-1')])  # Foco 1
def test_variantes_integras(b): assert verificar_integridad(b).resultado == OK
def test_contenido_alterado():
    assert verificar_integridad(MUESTRA_XML.replace(b'<MontoTotal>1250</MontoTotal>', b'<MontoTotal>9250</MontoTotal>')).resultado == FALLO
def test_signedinfo_alterado():
    assert verificar_integridad(MUESTRA_XML.replace(b'q5C5ueQp', b'q5C5ueQq')).resultado == FALLO
def test_sin_firma(): assert verificar_integridad(XML_SIN_FIRMA).resultado == FALLO
def test_firmado_con_pki_de_prueba(): assert verificar_integridad(ecf_de_prueba('E310000000001')).resultado == OK
```

- [ ] **Paso 2:** `.venv/Scripts/python -m pytest tests/ecf/test_integridad.py -v`. Esperado: FALLA.
- [ ] **Paso 3:** implementar.
  - Verificar así:
    ```python
    v = XMLVerifier()
    v.excise_empty_xmlns_declarations = True   # obligatorio: sin esto la firma real de la DGII no verifica
    v.verify(normalizar_xml_bytes(xml_bytes), x509_cert=<pem del primer X509Certificate>)
    ```
  - Pasar `x509_cert` hace que signxml no evalúe la confianza; esa es la Tarea 5.
  - Cualquier excepción da `FALLO` con `type(e).__name__` y el mensaje en `detalle`. Sin certificado incrustado da `FALLO` con `"Sin certificado incrustado"`.
- [ ] **Paso 4:** `.venv/Scripts/python -m pytest tests/ecf/test_integridad.py -v`. Esperado: PASA.
- [ ] **Paso 5:** commit — `feat(ecf): verificación de integridad de la firma XMLDSig`.

---

### Tarea 5: Verificaciones `vigencia` y `entidad_certificadora`

**Archivos:**
- Crear: `src/common/ecf/confianza/` (PEM y `FUENTE.md`), `src/common/ecf/verificaciones/certificado.py`, `tests/ecf/test_certificado.py`

**Interfaces:**
- Produce:
  - `cargar_certificado(data: bytes) -> x509.Certificate`: acepta DER o PEM.
  - `verificar_vigencia(cert: x509.Certificate | None, fecha_firma: datetime | None) -> Verificacion`:
    - si `cert` es `None` → `FALLO` con `"Sin certificado"`;
    - si `fecha_firma` es `None` → `FALLO` con `"Sin FechaHoraFirma"`;
    - con `OK`, el detalle es `"Vigente AAAA-MM-DD a AAAA-MM-DD"`.
  - `verificar_entidad_certificadora(cert, incrustados: list[x509.Certificate], ca_dir: Path, descargar: Callable[[str], bytes] | None = None) -> tuple[Verificacion, list[x509.Certificate] | None]`.
  - `descripcion_certificado(cert) -> tuple[str, str, str]`: CN del titular, CN del emisor y serie en hexadecimal.
  - `limpiar_caches() -> None`: vacía la caché de certificados AIA descargados.
- **Regla de confianza:**
  - Cada certificado de `ca_dir` es un **ancla**: la entidad autorizada por INDOTEL. Para Viafirma, el ancla es el intermedio `VIAFIRMA QUALIFIED CERTIFICATES / VIAFIRMA DOMINICANA`, no la raíz española, que también emite para otros países.
  - La cadena se arma desde la hoja subiendo por el emisor, con `issuer == subject` más `child.verify_directly_issued_by(parent)`, usando los incrustados, `ca_dir` y, si falta un eslabón y hay `descargar`, la URL CA Issuers del AIA.
  - Es `OK` si algún eslabón **coincide byte a byte (huella SHA-256)** con un certificado de `ca_dir` y su firma verificó. No basta con que coincida el nombre. El detalle con `OK` es `"<O>, <OU>"` del ancla, por ejemplo `"VIAFIRMA, VIAFIRMA DOMINICANA"`.
  - Devuelve la cadena `[hoja, emisor, ...]` hasta el ancla. La Tarea 6 usa `cadena[1]`.

- [ ] **Paso 1:** descargar `https://cps.viafirma.do/viafirmaqtspsubca008.crt` y guardarlo como `confianza/viafirma-dominicana.pem`. Consultar la lista de entidades de certificación autorizadas por INDOTEL y agregar el certificado emisor de cada una. Anotar las URL y fechas en `FUENTE.md`.
- [ ] **Paso 2: escribir las pruebas que fallan**

```python
CONFIANZA_DIR = Path(certificado.__file__).parents[1] / 'confianza'
def hoja_muestra(): return cargar_certificado(leer_ecf(MUESTRA_XML).certificados_der[0])

def test_muestra_vigente(): 
    v = verificar_vigencia(hoja_muestra(), leer_ecf(MUESTRA_XML).fecha_firma)
    assert v.resultado == OK and v.detalle == 'Vigente 2026-01-12 a 2027-01-12'
def test_muestra_entidad_autorizada():
    v, cadena = verificar_entidad_certificadora(hoja_muestra(), [], CONFIANZA_DIR)
    assert v.resultado == OK and 'VIAFIRMA DOMINICANA' in v.detalle and len(cadena) == 2
def test_fuera_de_vigencia():
    _, c = crear_hoja(*crear_ca('CA'), datetime(2025,1,1,tzinfo=ZONA_RD), datetime(2025,6,1,tzinfo=ZONA_RD))
    assert verificar_vigencia(c, datetime(2025,7,1,tzinfo=ZONA_RD)).resultado == FALLO
def test_sin_certificado(): assert verificar_vigencia(None, T0).resultado == FALLO
def test_carpeta_vacia(tmp_path):
    v, cadena = verificar_entidad_certificadora(hoja_muestra(), [], tmp_path); assert v.resultado == FALLO and cadena is None
def test_ca_falsa_con_el_mismo_nombre(tmp_path):
    # una CA de prueba con subject idéntico al ancla real no debe pasar
    ancla = cargar_certificado((CONFIANZA_DIR / 'viafirma-dominicana.pem').read_bytes())
    k, falsa = crear_ca_con_subject(ancla.subject)          # definir en tests/pki.py
    _, hoja = crear_hoja(k, falsa, AYER, MANANA)
    assert verificar_entidad_certificadora(hoja, [falsa], CONFIANZA_DIR)[0].resultado == FALLO
def test_intermedio_descargado_por_aia(tmp_path):
    ca_k, ca = crear_ca('Raiz'); int_k, inter = crear_intermedio(ca_k, ca, 'Emisora')
    (tmp_path / 'emisora.pem').write_bytes(inter.public_bytes(Encoding.PEM))
    _, hoja = crear_hoja(int_k, inter, AYER, MANANA, ca_issuers_url='http://aia.prueba/emisora.crt')
    descargas = []
    def descargar(u): descargas.append(u); return inter.public_bytes(Encoding.DER)
    v, cadena = verificar_entidad_certificadora(hoja, [], tmp_path, descargar)
    assert v.resultado == OK and cadena[1] == inter
```

Agregar a `tests/pki.py`: `crear_ca_con_subject(subject: x509.Name) -> tuple[key, cert]`.

- [ ] **Paso 3:** `.venv/Scripts/python -m pytest tests/ecf/test_certificado.py -v`. Esperado: FALLA.
- [ ] **Paso 4:** implementar. La vigencia compara `fecha_firma` con `not_valid_before_utc` y `not_valid_after_utc`.
- [ ] **Paso 5:** `.venv/Scripts/python -m pytest tests/ecf/test_certificado.py -v`. Esperado: PASA.
- [ ] **Paso 6:** commit — `feat(ecf): vigencia del certificado y entidad certificadora autorizada`.

---

### Tarea 6: Verificación `revocacion` (OCSP con respaldo en CRL)

**Archivos:**
- Crear: `src/common/ecf/verificaciones/revocacion.py`, `tests/ecf/test_revocacion.py`

**Interfaces:**
- Consume: la cadena de la Tarea 5 (`hoja = cadena[0]`, `emisor = cadena[1]`).
- Produce:
  - `verificar_revocacion(hoja, emisor, fecha_firma: datetime, ocsp_post: Callable[[str, bytes], bytes], descargar: Callable[[str], bytes], ahora: datetime) -> Verificacion`;
  - `limpiar_caches() -> None`.

  Los callables lanzan una excepción ante un fallo de red o un HTTP distinto de 200.

- **Reglas:**
  1. **Sin URL de OCSP ni de CRL** en la hoja → `NO_VERIFICABLE` con `"Sin URL de revocación"`.
  2. **OCSP:**
     - petición `OCSPRequestBuilder().add_certificate(hoja, emisor, SHA1())`;
     - la respuesta solo se acepta si `response_status == SUCCESSFUL`, si `serial_number == hoja.serial_number` y si la firma verifica con la clave pública del `emisor`, o con la del certificado delegado incluido en la respuesta (`resp.certificates`) cuando ese certificado está emitido por `emisor` y tiene EKU `OCSPSigning`;
     - `GOOD` → `OK` con `"OCSP: good"`;
     - `REVOKED` → `FALLO` si `revocation_time_utc <= fecha_firma`; si no, `OK` con `"Revocado el AAAA-MM-DD, después de la firma"`;
     - `UNKNOWN`, una respuesta no aceptada o una excepción → se pasa a CRL.
  3. **CRL:**
     - se descarga cada URL de distribución (DER o PEM) y solo se acepta si `crl.is_signature_valid(emisor.public_key())`;
     - se busca con `get_revoked_certificate_by_serial_number`, con la misma regla de fechas;
     - si no figura → `OK` con `"CRL: no revocado"`.
  4. **Sin respuesta aceptada** en ninguna de las dos → `NO_VERIFICABLE` con `"OCSP y CRL sin respuesta válida"`.
- **Caché de CRL:** a nivel de módulo, con clave por URL y vigencia hasta `next_update_utc`. Si es `None`, se guarda 1 hora contada desde `ahora`.

- [ ] **Paso 1: escribir las pruebas que fallan.** Primero, agregar a `tests/pki.py`:
  - `responder_ocsp(firmante_key, firmante_cert, hoja, estado: str, revocado_en: datetime | None = None, serie: int | None = None, emisor=None) -> bytes`:
    - construye con `ocsp.OCSPResponseBuilder` una respuesta `SUCCESSFUL` para la `hoja` (`estado` es `'GOOD'`, `'REVOKED'` o `'UNKNOWN'`; `emisor` por defecto = `firmante_cert`);
    - la firma con `firmante_key` (SHA-256) y la devuelve en DER;
    - si se pasa `serie`, la respuesta usa una hoja clonada con esa serie.
  - `firmar_crl(firmante_key, firmante_cert, revocados: dict[int, datetime], next_update: datetime | None) -> bytes`: arma la CRL en DER con `x509.CertificateRevocationListBuilder`.

  Luego, en el archivo de pruebas:

```python
FIRMA = T0
ca_k, ca = crear_ca('CA Rev')
hoja_k, hoja = crear_hoja(ca_k, ca, AYER - timedelta(days=30), MANANA, ocsp_url='http://ocsp.prueba', crl_url='http://crl.prueba/a.crl')
_, hoja_sin_urls = crear_hoja(ca_k, ca, AYER, MANANA)
def resp_ocsp(estado, revocado_en=None, firmante=None, serie=None):
    fk, fc = firmante or (ca_k, ca)
    return responder_ocsp(fk, fc, hoja, estado, revocado_en, serie, emisor=ca)
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
```

- [ ] **Paso 2:** `.venv/Scripts/python -m pytest tests/ecf/test_revocacion.py -v`. Esperado: FALLA.
- [ ] **Paso 3:** implementar.
- [ ] **Paso 4:** `.venv/Scripts/python -m pytest tests/ecf/test_revocacion.py -v`. Esperado: PASA. Ejecutar también la suite `tests/ecf` completa en el orden por defecto y con `-p no:randomly`; la limpieza de cachés de `conftest.py` evita que el orden afecte los resultados.
- [ ] **Paso 5:** commit — `feat(ecf): verificación de revocación OCSP/CRL a la fecha de firma`.

---

### Tarea 7: `cruce`, `comprador` y el orquestador `validar_xml`

**Archivos:**
- Crear: `src/common/ecf/verificaciones/cruce.py`, `src/common/ecf/validacion.py`, `tests/ecf/test_cruce.py`, `tests/ecf/test_validacion.py`
- Modificar: `tests/ayudantes.py`

**Interfaces:**
- Produce:
  - `verificar_cruce(d: DatosECF, qr_params: dict | None) -> Verificacion`:
    - con `None` o `{}` → `NO_VERIFICABLE` con `"Sin PDF"`;
    - con `FALLO`, el detalle es `"Discrepan: <campos separados por coma>"`, con los nombres del QR (`MontoTotal`, ...).
  - `verificar_comprador(d: DatosECF, rnc_terpel: str | None) -> Verificacion`.
  - `@dataclass ConfigValidacion(xsd_dir: Path, ca_dir: Path, rnc_terpel: str | None, ocsp_post: Callable, descargar: Callable)`.
  - `ConfigValidacion.por_defecto() -> ConfigValidacion`: `XSD_DIR`, `confianza/` del paquete, `rnc_terpel=None` y los callables HTTP reales.
  - `config_validacion_desde_parametros(parametros: ParametrosManager) -> ConfigValidacion`.
  - Callables HTTP reales, en `validacion.py`:
    - `http_descargar(url) -> bytes`: `requests.get(url, timeout=5)`;
    - `http_ocsp_post(url, cuerpo) -> bytes`: `requests.post(url, data=cuerpo, headers={'Content-Type': 'application/ocsp-request'}, timeout=5)`;
    - ambos con `raise_for_status()`.
  - `validar_xml(xml_bytes: bytes, qr_params: dict | None = None, config: ConfigValidacion | None = None, ahora: datetime | None = None) -> ResultadoValidacionXML`:
    - `config=None` usa `ConfigValidacion.por_defecto()` y `ahora=None` usa `datetime.now(ZONA_RD)`;
    - **nunca lanza excepción**;
    - si `leer_ecf` falla: `estructura`, `integridad`, `vigencia` y `entidad_certificadora` dan `FALLO` con el mensaje; `revocacion`, `cruce` y `comprador` dan `NO_VERIFICABLE`;
    - sin cadena de confianza: `revocacion` da `NO_VERIFICABLE` con `"Sin cadena de confianza"`.
- Agrega a `ayudantes.py`:
  - `QR_MUESTRA` = el diccionario de "Hechos verificados";
  - `CONFIG_SIN_RED` = `ConfigValidacion(XSD_DIR, <confianza del paquete>, None, ocsp_post=_lanza, descargar=_lanza)`, una **constante** y no una fixture; `_lanza` lanza `ConnectionError`;
  - `config_con(**cambios) -> ConfigValidacion`, que aplica `dataclasses.replace` sobre `CONFIG_SIN_RED`.

- **Normalización del cruce:**
  - claves sin distinguir mayúsculas;
  - RNC y e-NCF con `strip().upper()`;
  - `MontoTotal` como `Decimal`, quitando `,`;
  - fechas: se aplica `unquote_plus` solo si el texto contiene `%`, y se comparan como `datetime`/`date`;
  - `CodigoSeguridad`: `valor.replace(' ', '+')`, porque `parse_qs` convierte el `+` en espacio, y luego comparación exacta con `d.codigo_seguridad`;
  - un campo ausente en el QR no es discrepancia.

- [ ] **Paso 1: escribir las pruebas que fallan**

```python
D = leer_ecf(MUESTRA_XML)
def test_cruce_muestra_ok(): assert verificar_cruce(D, QR_MUESTRA).resultado == OK
def test_cruce_monto_distinto():
    v = verificar_cruce(D, {**QR_MUESTRA, 'MontoTotal': '9999'}); assert v.resultado == FALLO and v.detalle == 'Discrepan: MontoTotal'
def test_cruce_formatos_equivalentes():  # Foco 2
    q = {k.lower(): val for k, val in QR_MUESTRA.items()}
    q.update(montototal='1,250.00', fechafirma='10-02-2026%2009%3A22%3A21')
    assert verificar_cruce(D, q).resultado == OK
def test_cruce_mas_convertido_en_espacio():  # Foco 2
    d = dataclasses.replace(D, codigo_seguridad='Bu+kvC')
    assert verificar_cruce(d, {**QR_MUESTRA, 'CodigoSeguridad': 'Bu kvC'}).resultado == OK
def test_cruce_sin_pdf(): assert verificar_cruce(D, None).detalle == 'Sin PDF'
@pytest.mark.skipif(not zbar_disponible(), reason='zbar no instalado')   # zbar_disponible() en ayudantes: intenta importar pyzbar.pyzbar
def test_cruce_contra_pdf_real():
    assert verificar_cruce(D, PDFProcessor(str(MUESTRA_PDF)).extract_qr_params()).resultado == OK
def test_comprador():
    assert verificar_comprador(D, '101107146').resultado == OK
    assert verificar_comprador(D, '130000000').resultado == FALLO
    assert verificar_comprador(D, None).resultado == NO_VERIFICABLE and verificar_comprador(D, '').resultado == NO_VERIFICABLE

def test_validar_xml_muestra():
    r = validar_xml(MUESTRA_XML, QR_MUESTRA, config_con(rnc_terpel='101107146'), ahora=T0)
    assert {k: v['resultado'] for k, v in r.a_dict().items()} == {
        'estructura': OK, 'integridad': OK, 'vigencia': OK, 'entidad_certificadora': OK,
        'revocacion': NO_VERIFICABLE, 'cruce': OK, 'comprador': OK}
    assert r.certificado_titular == 'AURELIO ALCANTARA FAMILIA'
def test_validar_xml_basura():
    r = validar_xml(b'no es xml', None, CONFIG_SIN_RED, ahora=T0)
    assert r.integridad.resultado == FALLO and r.cruce.resultado == NO_VERIFICABLE
def test_validar_xml_revocacion_con_red_simulada(tmp_path):
    (tmp_path / 'ca.pem').write_bytes(CA_PRUEBA.public_bytes(Encoding.PEM))
    cfg = config_con(ca_dir=tmp_path, ocsp_post=lambda u, b: responder_ocsp(CA_PRUEBA_KEY, CA_PRUEBA, HOJA_PRUEBA, 'GOOD'))
    r = validar_xml(ecf_de_prueba('E310000000001'), None, cfg, ahora=T0)
    assert r.entidad_certificadora.resultado == OK and r.revocacion.resultado == OK
```
- [ ] **Paso 2:** `.venv/Scripts/python -m pytest tests/ecf/test_cruce.py tests/ecf/test_validacion.py -v`. Esperado: FALLA.
- [ ] **Paso 3:** implementar.
- [ ] **Paso 4:** `.venv/Scripts/python -m pytest tests/ecf -v`. Esperado: PASA.
- [ ] **Paso 5:** commit — `feat(ecf): cruce XML-QR, comprador y orquestador validar_xml`.

---

### Tarea 8: Consulta a la DGII (URL, analizador y mapeo de estados)

**Archivos:**
- Crear: `src/common/ecf/dgii.py`, `tests/ecf/fixtures/dgii/` (HTML reales y `LEEME.md`), `tests/ecf/test_dgii.py`
- Modificar: `tests/ayudantes.py`

**Interfaces:**
- Produce:
  - `construir_url_consulta(d: DatosECF) -> str`:
    - **tipo `'32'` con `monto_total < Decimal('250000')`:** `https://ecf.dgii.gov.do/eCF/ConsultaTimbreFC?` con `RncEmisor`, `ENCF`, `MontoTotal` y `CodigoSeguridad`;
    - **otro caso:** `https://ecf.dgii.gov.do/eCF/ConsultaTimbre?` con `RncEmisor`, `RncComprador`, `ENCF`, `FechaEmision`, `MontoTotal`, `FechaFirma` y `CodigoSeguridad`;
    - formato de valores: `MontoTotal` con `f'{monto:.2f}'`; `FechaEmision` y `FechaFirma` tal como vienen en el XML (`fecha_emision_texto` y `fecha_firma_texto`); se codifica con `urlencode(..., quote_via=quote)`, igual que el QR de la DGII (`%20` para el espacio);
    - los parámetros con valor `None` se omiten.
  - `@dataclass RespuestaDGII(tipo: str, estado_texto: str | None = None, razon_social: str | None = None, detalle: str = '')`, con `tipo` en `'DATOS'`, `'NO_ENCONTRADO'` o `'ERROR'`.
  - `analizar_respuesta(status: int, html: str) -> RespuestaDGII`:
    - status distinto de 200 → `ERROR`;
    - fila `th` con texto `Estado` → `DATOS`;
    - texto `No fue encontrada la factura` → `NO_ENCONTRADO`;
    - cualquier otra cosa → `ERROR` con `"HTML inesperado"`.
  - `consultar_dgii(url: str, http_get=requests.get, timeout: int = 15) -> RespuestaDGII`. **Nunca lanza excepción.**
  - `mapear_estado(texto: str | None) -> str`:
    - compara sin mayúsculas, sin acentos y sin espacios extremos;
    - `'NO_ENCONTRADO'` → `PENDIENTE`;
    - un texto no mapeado → `DESCONOCIDO` con `logging.warning`.
- Agrega a `ayudantes.py`:
  - `DATOS_ACEPTADO = RespuestaDGII('DATOS', 'Aceptado', 'EMPRESAS ASAVIM S R L')`;
  - `NO_ENCONTRADO_R = RespuestaDGII('NO_ENCONTRADO')`;
  - `ERROR_R = RespuestaDGII('ERROR', detalle='HTTP 500')`;
  - `fijo(r) -> Callable[[str], RespuestaDGII]`, que devuelve siempre `r`;
  - `fixture_dgii(nombre) -> str`.

- [ ] **Paso 1:** capturar con `requests` y guardar en `fixtures/dgii/`:
  - `aceptado.html`: la URL del QR de la muestra;
  - `no_encontrado.html`: la misma URL con `ENCF=E319999999999` y `CodigoSeguridad=AAAAAA`;
  - si se encuentra un e-NCF tipo 32 menor a 250 mil, también la variante FC.

  En `LEEME.md` anotar la fecha, las URL y los textos de estado de la DGII (ver "Hechos verificados"; buscar en su documentación los textos "Aceptado Condicional", "Rechazado" y "En Proceso").
- [ ] **Paso 2: escribir las pruebas que fallan**

```python
def test_url_desde_xml_igual_al_qr():
    u = construir_url_consulta(leer_ecf(MUESTRA_XML))
    assert u == 'https://ecf.dgii.gov.do/eCF/ConsultaTimbre?RncEmisor=101616202&RncComprador=101107146&ENCF=E310000002882&FechaEmision=10-02-2026&MontoTotal=1250.00&FechaFirma=10-02-2026%2009%3A22%3A21&CodigoSeguridad=BuLkvC'
def tipo32(monto): return dataclasses.replace(leer_ecf(MUESTRA_XML), tipo_ecf='32', monto_total=Decimal(monto))
def test_url_fc(): assert construir_url_consulta(tipo32('1000')).startswith('https://ecf.dgii.gov.do/eCF/ConsultaTimbreFC?RncEmisor=101616202&ENCF=')
def test_url_tipo32_grande(): assert '/ConsultaTimbre?' in construir_url_consulta(tipo32('300000'))
def test_analiza_datos():
    r = analizar_respuesta(200, fixture_dgii('aceptado.html'))
    assert (r.tipo, r.estado_texto, r.razon_social) == ('DATOS', 'Aceptado', 'EMPRESAS ASAVIM S R L')
def test_analiza_no_encontrado(): assert analizar_respuesta(200, fixture_dgii('no_encontrado.html')).tipo == 'NO_ENCONTRADO'
def test_html_inesperado(): assert analizar_respuesta(200, '<html>mantenimiento</html>').tipo == 'ERROR'
def test_http_500(): assert analizar_respuesta(500, '').tipo == 'ERROR'
def test_timeout():
    def lanza(*a, **k): raise requests.Timeout()
    assert consultar_dgii('http://x', http_get=lanza).tipo == 'ERROR'
@pytest.mark.parametrize('texto,esperado', [('Aceptado', ACEPTADO), (' ACEPTADO ', ACEPTADO), ('Aceptado Condicional', ACEPTADO_CONDICIONAL),
    ('Rechazado', RECHAZADO), ('En Proceso', PENDIENTE), ('NO_ENCONTRADO', PENDIENTE), ('Algo raro', DESCONOCIDO), (None, DESCONOCIDO)])
def test_mapeo(texto, esperado): assert mapear_estado(texto) == esperado
```

  Nota: si la DGII acepta la URL con `:` sin codificar (como en su propio QR) y no con `%3A`, ajustar `quote_via` y la prueba, y anotarlo en `LEEME.md`. Se comprueba en el Paso 1 consultando la URL construida.
- [ ] **Paso 3:** `.venv/Scripts/python -m pytest tests/ecf/test_dgii.py -v`. Esperado: FALLA.
- [ ] **Paso 4:** implementar con BeautifulSoup.
- [ ] **Paso 5:** `.venv/Scripts/python -m pytest tests/ecf/test_dgii.py -v`. Esperado: PASA.
- [ ] **Paso 6:** commit — `feat(ecf): consulta a la DGII con distinción entre no encontrado y error`.

---

### Tarea 9: Tablas `comprobantes` y `comprobante_historial`

**Archivos:**
- Modificar: `src/db/base_db_wrapper.py` (stubs `NotImplementedError` de los métodos nuevos), `src/db/postgres_db_wrapper.py`, `tests/ayudantes.py`
- Crear: `tests/bd/test_comprobantes.py`

**Interfaces:**
- **Tabla `comprobantes`** (`create_comprobantes_tables()`, llamado desde `__init__`):
  - `id SERIAL PK`;
  - identificación: `rnc_emisor TEXT NOT NULL`, `encf TEXT NOT NULL`, `rnc_comprador`, `tipo_ecf`, `fecha_emision TEXT`, `monto_total NUMERIC(18,2)`, `fecha_firma TIMESTAMPTZ`, `codigo_seguridad`, `razon_social_emisor`, `url_consulta`;
  - documento: `xml_contenido BYTEA NOT NULL`, `xml_hash_sha256 TEXT NOT NULL`, `qr_params JSONB`, `origen TEXT NOT NULL`, `referencia_origen`;
  - validación: `validacion_detalle JSONB NOT NULL`, `integridad`, `vigencia`, `entidad_certificadora`, `revocacion` (TEXT);
  - certificado: `certificado_titular`, `certificado_emisor`, `certificado_serie`;
  - estado: `estado TEXT NOT NULL`, `estado_dgii_texto`, `ultima_consulta_dgii TIMESTAMPTZ`;
  - seguimiento: `seguimiento_activo BOOLEAN NOT NULL`, `seguimiento_hasta TIMESTAMPTZ NOT NULL`, `proxima_consulta TIMESTAMPTZ NOT NULL`, `intervalo_actual_min INTEGER NOT NULL`, `intentos INTEGER NOT NULL DEFAULT 0`;
  - `creado_en` y `actualizado_en TIMESTAMPTZ DEFAULT now()`;
  - `UNIQUE(rnc_emisor, encf)` e índice `(seguimiento_activo, proxima_consulta)`.
- **Tabla `comprobante_historial`:**
  - `id SERIAL PK`, `comprobante_id INTEGER REFERENCES comprobantes(id)`, `fecha TIMESTAMPTZ NOT NULL`, `tipo TEXT NOT NULL`, `estado_anterior`, `estado_nuevo`, `estado_dgii_texto`, `detalle`;
  - índice en `comprobante_id`.
- **Métodos:**
  - `get_comprobante(rnc_emisor, encf) -> dict | None`: normaliza ambos con `strip().upper()`;
  - `insert_comprobante(campos: dict) -> int | None`: `INSERT ... ON CONFLICT (rnc_emisor, encf) DO NOTHING RETURNING id`, que devuelve `None` si ya existía;
  - `update_comprobante(id: int, campos: dict) -> None`: siempre actualiza `actualizado_en = now()`;
  - `insert_historial(id, tipo, estado_anterior=None, estado_nuevo=None, estado_dgii_texto=None, detalle=None, fecha: datetime | None = None)`: con `fecha=None` usa `now()`;
  - `get_historial(id) -> list[dict]`, ordenado por `fecha, id`;
  - `get_comprobantes_por_consultar(ahora, limite=100) -> list[dict]`;
  - `transaccion()`: context manager que devuelve `self.conn.transaction()`.

  Las claves de `campos` se validan contra una lista blanca de columnas: una clave desconocida lanza `ValueError`. Los `dict` se envuelven en `Jsonb` y las lecturas usan `dict_row`.
- Agrega a `ayudantes.py`: `campos_minimos(encf='E310000002882', **cambios) -> dict`, con todas las columnas `NOT NULL` y valores válidos: `xml_contenido=MUESTRA_XML`, `validacion_detalle={}`, `estado='PENDIENTE'`, `seguimiento_activo=True`, `seguimiento_hasta=T0+72h`, `proxima_consulta=T0+60min`, `intervalo_actual_min=120` y `origen='api'`.

- [ ] **Paso 1: escribir las pruebas que fallan**

```python
def test_insert_get_y_conflicto(db_pg):
    cid = db_pg.insert_comprobante(campos_minimos())
    assert db_pg.get_comprobante(' 101616202 ', 'e310000002882')['id'] == cid
    assert db_pg.insert_comprobante(campos_minimos()) is None
def test_bytes_y_json_ida_y_vuelta(db_pg):
    db_pg.insert_comprobante(campos_minimos(validacion_detalle={'integridad': {'resultado': 'OK', 'detalle': ''}}))
    c = db_pg.get_comprobante('101616202', 'E310000002882')
    assert bytes(c['xml_contenido']) == MUESTRA_XML and c['validacion_detalle']['integridad']['resultado'] == 'OK'
def test_columna_desconocida(db_pg):
    with pytest.raises(ValueError): db_pg.insert_comprobante({**campos_minimos(), 'hack; DROP': 1})
def test_por_consultar(db_pg):
    db_pg.insert_comprobante(campos_minimos('E31A', proxima_consulta=T0))
    db_pg.insert_comprobante(campos_minimos('E31B', proxima_consulta=T0 + timedelta(hours=1)))
    db_pg.insert_comprobante(campos_minimos('E31C', proxima_consulta=T0, seguimiento_activo=False))
    assert [c['encf'] for c in db_pg.get_comprobantes_por_consultar(T0)] == ['E31A']
def test_historial_ordenado(db_pg):
    cid = db_pg.insert_comprobante(campos_minimos())
    db_pg.insert_historial(cid, 'CONSULTA', fecha=T0 + timedelta(hours=1)); db_pg.insert_historial(cid, 'REGISTRO', fecha=T0)
    assert [h['tipo'] for h in db_pg.get_historial(cid)] == ['REGISTRO', 'CONSULTA']
def test_transaccion_revierte(db_pg):
    cid = db_pg.insert_comprobante(campos_minimos())
    with pytest.raises(RuntimeError):
        with db_pg.transaccion():
            db_pg.update_comprobante(cid, {'estado': 'ACEPTADO'}); raise RuntimeError()
    assert db_pg.get_comprobante('101616202', 'E310000002882')['estado'] == 'PENDIENTE'
```

- [ ] **Paso 2:** `.venv/Scripts/python -m pytest tests/bd -v`. Esperado: FALLA.
- [ ] **Paso 3:** implementar.
- [ ] **Paso 4:** `.venv/Scripts/python -m pytest tests/bd -v`. Esperado: PASA.
- [ ] **Paso 5:** commit — `feat(db): tablas comprobantes e historial en PostgreSQL`.

---

### Tarea 10: Calendario y reglas de transición (funciones puras)

**Archivos:**
- Crear: `src/common/ecf/seguimiento.py`, `tests/ecf/test_seguimiento.py`

**Interfaces:**
- Produce:
  - `@dataclass ConfigSeguimiento(intervalo_inicial_min: int = 60, factor: float = 2.0, intervalo_max_min: int = 1440, duracion_max_horas: int = 72, ciclo_seg: int = 300)`.
  - `config_seguimiento_desde_parametros(parametros: ParametrosManager) -> ConfigSeguimiento`.
  - `calendario_inicial(ahora: datetime, cfg) -> dict` → `{seguimiento_activo: True, seguimiento_hasta: ahora + duración, proxima_consulta: ahora + inicial, intervalo_actual_min: int(round(min(inicial*factor, max))), intentos: 0}`.
  - `@dataclass Evento(tipo: str, estado_anterior=None, estado_nuevo=None, estado_dgii_texto=None, detalle=None)`.
  - `@dataclass Decision(campos: dict, eventos: list[Evento])`. Las claves de `campos` son **nombres de columna** de la Tarea 9.
  - `decidir(c: dict, r: RespuestaDGII, ahora: datetime, cfg) -> Decision`. `c` trae `estado`, `seguimiento_hasta`, `intervalo_actual_min` e `intentos`.

  Reglas (spec §6.5):

```
campos['intentos'] = c['intentos'] + 1
si r.tipo == 'ERROR':
    eventos: ERROR_CONSULTA(detalle=r.detalle)          # estado, intervalo y proxima_consulta sin cambio
    si ahora >= seguimiento_hasta + 60 min:
        campos['seguimiento_activo'] = False
        eventos += ERROR_CONSULTA(detalle='seguimiento cerrado sin consulta válida')
si no:
    nuevo = mapear_estado(r.estado_texto) si r.tipo == 'DATOS' si no PENDIENTE
    campos: estado_dgii_texto = r.estado_texto (None si NO_ENCONTRADO), ultima_consulta_dgii = ahora,
            razon_social_emisor = r.razon_social si no es None
    eventos: CONSULTA(estado_dgii_texto=...)
    si ahora >= seguimiento_hasta:
        campos['seguimiento_activo'] = False
        si r.tipo == 'NO_ENCONTRADO': nuevo = NO_ENCONTRADO   # solo por respuesta "no encontrado"; un "En Proceso" al cierre queda PENDIENTE
    si no:
        campos['proxima_consulta'] = min(ahora + intervalo_actual_min, seguimiento_hasta)
        campos['intervalo_actual_min'] = int(round(min(intervalo_actual_min * factor, intervalo_max_min)))
    campos['estado'] = nuevo
    si nuevo != c['estado']: eventos += CAMBIO_ESTADO(c['estado'], nuevo)   # también si retrocede
```

- [ ] **Paso 1: escribir las pruebas que fallan**

```python
CFG = ConfigSeguimiento()
def base(estado=PENDIENTE): return {'estado': estado, **calendario_inicial(T0, CFG)}
def recorrer(cfg, respuesta=DATOS_ACEPTADO):
    c = {'estado': PENDIENTE, **calendario_inicial(T0, cfg)}; ahora = c['proxima_consulta']; gaps = []
    while c['seguimiento_activo']:
        c.update(decidir(c, respuesta, ahora, cfg).campos)
        if c['seguimiento_activo']: gaps.append((c['proxima_consulta'] - ahora).total_seconds() / 60); ahora = c['proxima_consulta']
    return c, ahora, gaps

def test_intervalos_crecientes():
    c, fin, gaps = recorrer(CFG)
    assert gaps == [120, 240, 480, 960, 1440, 1020] and fin == T0 + timedelta(hours=72) and c['estado'] == ACEPTADO
def test_factor_1(): assert set(recorrer(ConfigSeguimiento(factor=1))[2]) == {60}
def test_error_no_cambia_estado_ni_avanza():
    d = decidir(base(ACEPTADO), ERROR_R, T0 + timedelta(hours=1), CFG)
    assert d.campos == {'intentos': 1} and [e.tipo for e in d.eventos] == [ERROR_CONSULTA]
def test_no_encontrado_al_cierre():
    d = decidir(base(), NO_ENCONTRADO_R, T0 + timedelta(hours=72), CFG)
    assert d.campos['estado'] == NO_ENCONTRADO and d.campos['seguimiento_activo'] is False
def test_en_proceso_al_cierre_queda_pendiente():
    d = decidir(base(), RespuestaDGII('DATOS', 'En Proceso'), T0 + timedelta(hours=72), CFG)
    assert d.campos['estado'] == PENDIENTE and d.campos['seguimiento_activo'] is False
def test_error_al_cierre():
    hasta = T0 + timedelta(hours=72)
    assert 'seguimiento_activo' not in decidir(base(), ERROR_R, hasta + timedelta(minutes=30), CFG).campos
    d = decidir(base(ACEPTADO), ERROR_R, hasta + timedelta(minutes=61), CFG)
    assert d.campos['seguimiento_activo'] is False and 'estado' not in d.campos
    assert d.eventos[-1].detalle == 'seguimiento cerrado sin consulta válida'
def test_retroceso():
    d = decidir(base(ACEPTADO), NO_ENCONTRADO_R, T0 + timedelta(hours=5), CFG)
    assert d.campos['estado'] == PENDIENTE and [e.tipo for e in d.eventos] == [CONSULTA, CAMBIO_ESTADO]
def test_parametros(db_pg):
    db_pg.set_param('SEGUIMIENTO_FACTOR', 'abc'); db_pg.set_param('SEGUIMIENTO_DURACION_MAX_HORAS', '24')
    cfg = config_seguimiento_desde_parametros(ParametrosManager(db_pg))
    assert cfg.factor == 2.0 and cfg.duracion_max_horas == 24
```

- [ ] **Paso 2:** `.venv/Scripts/python -m pytest tests/ecf/test_seguimiento.py -v`. Esperado: FALLA.
- [ ] **Paso 3:** implementar `decidir` según el bloque de reglas.
- [ ] **Paso 4:** `.venv/Scripts/python -m pytest tests/ecf/test_seguimiento.py -v`. Esperado: PASA.
- [ ] **Paso 5:** commit — `feat(ecf): calendario de seguimiento y reglas de transición`.

---

### Tarea 11: `registrar_comprobante`

**Archivos:**
- Crear: `src/common/ecf/registro.py`, `tests/ecf/test_registro.py`

**Interfaces:**
- Produce:
  - `extraer_qr_params(pdf_bytes: bytes) -> dict | None`: escribe un temporal, llama a `PDFProcessor(path).extract_qr_params()` y borra el archivo en `finally`. Cualquier excepción o un resultado vacío → `None`.
  - `campos_de_validacion(d: DatosECF | None, r: ResultadoValidacionXML) -> dict`: `validacion_detalle=r.a_dict()`, las 4 columnas de firma y las 3 del certificado. La Tarea 12 la reutiliza.
  - `registrar_comprobante(db, xml_bytes: bytes, pdf_bytes: bytes | None = None, origen: str = 'api', referencia_origen: str | None = None, *, config_validacion: ConfigValidacion | None = None, config_seguimiento: ConfigSeguimiento | None = None, consultar: Callable[[str], RespuestaDGII] = consultar_dgii, ahora: datetime | None = None) -> dict`:
    - devuelve la fila final de `comprobantes`;
    - `config_*=None` se toma de `ParametrosManager(db)`; `ahora=None` es `datetime.now(ZONA_RD)`;
    - lanza `ErrorLecturaECF` si no hay RNC o e-NCF.

- **Flujo:**
  1. `d = leer_ecf(xml_bytes)`; `qr = extraer_qr_params(pdf_bytes) if pdf_bytes else None`; `r = validar_xml(xml_bytes, qr, config_validacion, ahora)`.
  2. Armar `campos`:
     - identificación de `d`;
     - `url_consulta = construir_url_consulta(d)`, **siempre desde el XML**;
     - `xml_contenido = xml_bytes` (los bytes originales) y su hash;
     - `qr_params = qr`, `origen`, `referencia_origen`;
     - `campos_de_validacion(d, r)`.
  3. `nuevo_id = db.insert_comprobante({**campos, 'estado': PENDIENTE, **calendario_inicial(ahora, cfg)})`.
  4. **Si `nuevo_id` no es `None` (nuevo)**, dentro de `db.transaccion()`:
     - historial `REGISTRO` con `fecha=ahora`;
     - `resp = consultar(url_consulta)`;
     - `dec = decidir(fila, resp, ahora, cfg)`;
     - aplicar de `dec.campos` **solo** `estado`, `estado_dgii_texto`, `ultima_consulta_dgii`, `razon_social_emisor` e `intentos`, sin tocar el calendario;
     - insertar los eventos con `fecha=ahora`.
  5. **Si es `None` (ya existía, también en una carrera)**, dentro de `db.transaccion()`:
     - si el hash es igual → actualizar solo las columnas de validación (y `qr_params` si llegó uno). Sin eventos;
     - si el hash es distinto → actualizar `campos` completos (identificación, `url_consulta`, XML, hash, `qr_params`, validación y certificado) más el evento `DOCUMENTO_REEMPLAZADO`, con `detalle` = `"hash anterior <8 primeros> → nuevo <8 primeros>; integridad=<resultado>"`.

     En ningún caso se consulta la DGII ni se toca el calendario.

- [ ] **Paso 1: escribir las pruebas que fallan**

```python
def reg(db, xml=MUESTRA_XML, **kw):
    kw.setdefault('consultar', fijo(DATOS_ACEPTADO)); kw.setdefault('ahora', T0)
    kw.setdefault('config_validacion', CONFIG_SIN_RED); kw.setdefault('config_seguimiento', ConfigSeguimiento())
    return registrar_comprobante(db, xml, **kw)
def tipos(db, cid): return [h['tipo'] for h in db.get_historial(cid)]

def test_nuevo_aceptado(db_pg):
    c = reg(db_pg)
    assert (c['estado'], c['seguimiento_activo'], c['proxima_consulta'], c['intentos']) == (ACEPTADO, True, T0 + timedelta(minutes=60), 1)
    assert c['integridad'] == OK and bytes(c['xml_contenido']) == MUESTRA_XML
    assert tipos(db_pg, c['id']) == [REGISTRO, CONSULTA, CAMBIO_ESTADO]
def test_url_viene_del_xml_no_del_qr(db_pg, monkeypatch):
    monkeypatch.setattr(registro, 'extraer_qr_params', lambda b: {**QR_MUESTRA, 'MontoTotal': '9999'})
    urls = []
    c = reg(db_pg, pdf_bytes=b'%PDF', consultar=lambda u: urls.append(u) or DATOS_ACEPTADO)
    assert urls == [construir_url_consulta(leer_ecf(MUESTRA_XML))] and c['validacion_detalle']['cruce']['resultado'] == FALLO
def test_pdf_corrupto_no_aborta(db_pg): assert reg(db_pg, pdf_bytes=b'no es pdf')['validacion_detalle']['cruce']['resultado'] == NO_VERIFICABLE
def test_dgii_caida(db_pg):
    c = reg(db_pg, consultar=fijo(ERROR_R)); assert c['estado'] == PENDIENTE and tipos(db_pg, c['id']) == [REGISTRO, ERROR_CONSULTA]
def test_reenvio_identico(db_pg):  # Foco 5
    a = reg(db_pg); b = reg(db_pg, ahora=T0 + timedelta(hours=5), consultar=fijo(ERROR_R))
    assert a['id'] == b['id'] and b['proxima_consulta'] == a['proxima_consulta'] and b['estado'] == ACEPTADO
    assert DOCUMENTO_REEMPLAZADO not in tipos(db_pg, a['id'])
def test_reenvio_distinto(db_pg):
    a = reg(db_pg); alterado = MUESTRA_XML.replace(b'<MontoTotal>1250</MontoTotal>', b'<MontoTotal>9250</MontoTotal>')
    b = reg(db_pg, alterado, ahora=T0 + timedelta(hours=1))
    assert b['id'] == a['id'] and b['integridad'] == FALLO and b['proxima_consulta'] == a['proxima_consulta']
    assert b['monto_total'] == Decimal('9250') and 'MontoTotal=9250.00' in b['url_consulta']
    assert tipos(db_pg, a['id'])[-1] == DOCUMENTO_REEMPLAZADO
def test_normaliza_identificacion(db_pg):  # Foco 3
    xml = MUESTRA_XML.replace(b'<eNCF>E310000002882</eNCF>', b'<eNCF> e310000002882 </eNCF>')
    assert reg(db_pg, xml)['encf'] == 'E310000002882'
def test_xml_ilegible(db_pg):
    with pytest.raises(ErrorLecturaECF): reg(db_pg, b'basura')
```

- [ ] **Paso 2:** `.venv/Scripts/python -m pytest tests/ecf/test_registro.py -v`. Esperado: FALLA.
- [ ] **Paso 3:** implementar.
- [ ] **Paso 4:** `.venv/Scripts/python -m pytest tests/ecf/test_registro.py -v`. Esperado: PASA.
- [ ] **Paso 5:** commit — `feat(ecf): registro de comprobantes (punto de entrada común)`.

---

### Tarea 12: Worker de seguimiento

**Archivos:**
- Crear: `src/seguimiento/__init__.py`, `src/seguimiento/ciclo.py`, `src/seguimiento/worker_main.py`, `tests/worker/test_ciclo.py`
- Modificar: `src/api/Dockerfile` (`COPY seguimiento /app/seguimiento`), `docker-compose.yml`

**Interfaces:**
- Produce: `procesar_ciclo(db, ahora: datetime, cfg: ConfigSeguimiento, config_validacion: ConfigValidacion, consultar=consultar_dgii, dormir=time.sleep) -> int` (cantidad procesada).

  Para cada fila de `get_comprobantes_por_consultar(ahora)`:
  1. `resp = consultar(fila['url_consulta'])`. Si lanza una excepción: `resp = RespuestaDGII('ERROR', detalle=repr(exc))`.
  2. `dec = decidir(fila, resp, ahora, cfg)`.
  3. Si `fila['revocacion'] == NO_VERIFICABLE`, ejecutar `r = validar_xml(bytes(fila['xml_contenido']), fila['qr_params'], config_validacion, ahora)` y sumar `campos_de_validacion(...)` a `dec.campos`. Así se actualizan a la vez la columna `revocacion` y `validacion_detalle`, y el cruce se conserva porque se pasan los `qr_params` guardados. Si esto lanza una excepción, se agrega un evento `ERROR_CONSULTA` con `repr(exc)` y la Decision sigue sin esos campos.
  4. Dentro de `db.transaccion()`: `update_comprobante` + `insert_historial` de cada evento, con `fecha=ahora`.
  5. Si el paso 4 lanza una excepción: `logging.exception` y se sigue con el siguiente comprobante.
  6. `dormir(1)` entre comprobantes, también después de uno que falló, pero no después del último.

  `worker_main.main()`:
  - `logging.basicConfig(level=INFO)`;
  - bucle infinito: (re)conecta con `get_db_wrapper(*leer_config_db())` si no hay conexión; lee los parámetros; ejecuta `procesar_ciclo(..., datetime.now(ZONA_RD))`; registra `"Ciclo: N comprobantes"`; duerme `cfg.ciclo_seg`;
  - toda excepción del ciclo → `logging.exception`, descartar la conexión (se reconecta en la siguiente vuelta) y dormir `cfg.ciclo_seg`;
  - `if __name__ == '__main__': main()`.
- **Compose:** servicio `seguimiento` con el mismo `build` que `backend`, `command: python -m seguimiento.worker_main`, las mismas variables de base, `depends_on: postgres: condition: service_healthy` y `restart: unless-stopped`.

- [ ] **Paso 1: escribir las pruebas que fallan**

```python
CFG = ConfigSeguimiento(); SIN_PAUSA = lambda s: None
def reg(db, xml, ahora=T0): return registrar_comprobante(db, xml, consultar=fijo(DATOS_ACEPTADO), ahora=ahora, config_validacion=CONFIG_SIN_RED, config_seguimiento=CFG)
def fila(db, encf): return db.get_comprobante('101616202', encf)
def tipos(db, encf): return [h['tipo'] for h in db.get_historial(fila(db, encf)['id'])]

def test_solo_vencidos(db_pg):
    reg(db_pg, ecf_de_prueba('E31A')); reg(db_pg, ecf_de_prueba('E31B'), ahora=T0 + timedelta(minutes=50))
    assert procesar_ciclo(db_pg, T0 + timedelta(minutes=60), CFG, CONFIG_SIN_RED, fijo(DATOS_ACEPTADO), SIN_PAUSA) == 1
    assert fila(db_pg, 'E31A')['proxima_consulta'] == T0 + timedelta(minutes=180) and fila(db_pg, 'E31B')['intentos'] == 1
def test_excepcion_no_detiene_y_aplica_cierre(db_pg):  # Foco 4
    reg(db_pg, ecf_de_prueba('E31A')); reg(db_pg, ecf_de_prueba('E31B'))
    def consultar(u):
        if 'E31A' in u: raise RuntimeError('boom')
        return RespuestaDGII('DATOS', 'Rechazado')
    assert procesar_ciclo(db_pg, T0 + timedelta(minutes=60), CFG, CONFIG_SIN_RED, consultar, SIN_PAUSA) == 2
    assert fila(db_pg, 'E31B')['estado'] == RECHAZADO and tipos(db_pg, 'E31A')[-1] == ERROR_CONSULTA
    assert fila(db_pg, 'E31A')['intentos'] == 2   # 1 del registro + 1 del ciclo: la excepción pasó por decidir
    fin = T0 + timedelta(hours=73, minutes=1)
    procesar_ciclo(db_pg, fin, CFG, CONFIG_SIN_RED, consultar, SIN_PAUSA)
    assert fila(db_pg, 'E31A')['seguimiento_activo'] is False
def test_reintenta_revocacion_y_conserva_cruce(db_pg, monkeypatch):
    monkeypatch.setattr(registro, 'extraer_qr_params', lambda b: QR_MUESTRA)
    registrar_comprobante(db_pg, MUESTRA_XML, pdf_bytes=b'%PDF', consultar=fijo(DATOS_ACEPTADO), ahora=T0,
                          config_validacion=CONFIG_SIN_RED, config_seguimiento=CFG)
    assert fila(db_pg, 'E310000002882')['revocacion'] == NO_VERIFICABLE
    procesar_ciclo(db_pg, T0 + timedelta(minutes=60), CFG, CONFIG_SIN_RED, fijo(DATOS_ACEPTADO), SIN_PAUSA)
    f = fila(db_pg, 'E310000002882')
    assert f['validacion_detalle']['cruce']['resultado'] == OK          # el cruce no se pierde al revalidar
    assert f['revocacion'] == f['validacion_detalle']['revocacion']['resultado']
def test_revocacion_actualiza_columna_y_json(db_pg, monkeypatch):
    reg(db_pg, ecf_de_prueba('E31A'))
    ok = ResultadoValidacionXML(*(Verificacion(OK) for _ in range(7)), None, None, None)
    monkeypatch.setattr(ciclo, 'validar_xml', lambda *a, **k: ok)
    procesar_ciclo(db_pg, T0 + timedelta(minutes=60), CFG, CONFIG_SIN_RED, fijo(DATOS_ACEPTADO), SIN_PAUSA)
    f = fila(db_pg, 'E31A'); assert f['revocacion'] == OK and f['validacion_detalle']['revocacion']['resultado'] == OK
def test_pausas(db_pg):
    for e in ('E31A', 'E31B', 'E31C'): reg(db_pg, ecf_de_prueba(e))
    pausas = []; procesar_ciclo(db_pg, T0 + timedelta(minutes=60), CFG, CONFIG_SIN_RED, fijo(DATOS_ACEPTADO), pausas.append)
    assert pausas == [1, 1]
```

- [ ] **Paso 2:** `.venv/Scripts/python -m pytest tests/worker -v`. Esperado: FALLA.
- [ ] **Paso 3:** implementar `procesar_ciclo`, `worker_main`, el Dockerfile y el compose.
- [ ] **Paso 4:** `.venv/Scripts/python -m pytest tests/worker -v`. Esperado: PASA. Luego `docker compose build && docker compose up -d && sleep 20 && docker compose logs seguimiento`. Esperado: `Ciclo: 0 comprobantes`, sin trazas.
- [ ] **Paso 5:** commit — `feat(seguimiento): worker periódico de consulta a la DGII`.

---

### Tarea 13: Endpoint `GET /comprobantes/{rnc_emisor}/{encf}`

**Archivos:**
- Modificar: `src/api/backend.py`, `src/api/schemas.py`, `README.md`
- Crear: `tests/endpoint/test_consulta_comprobante.py`

**Interfaces:**
- Produce:
  - `VerificacionOut(resultado: str, detalle: str)`.
  - `ComprobanteEstadoOut`: los campos exactos del JSON de la spec §6.6; `validacion: dict[str, VerificacionOut]`.
  - La ruta:
    - llama a `get_db()` **dentro del cuerpo** (igual que las rutas existentes, no con `Depends`) y cierra la conexión en `finally` si el wrapper tiene `close`;
    - si el motor no es `postgres` → 503 con `{"detail": "Requiere DB_ENGINE=postgres"}`;
    - sin registro → 404 con el cuerpo exacto `{"registrado": false}`, vía `JSONResponse`;
    - con registro → 200, con las fechas convertidas con `.astimezone(ZONA_RD)` antes de construir el modelo.

- [ ] **Paso 1: escribir las pruebas que fallan**

```python
from api import backend
KEY = {'x-api-key': 'clave-prueba'}
@pytest.fixture
def cliente(db_pg, monkeypatch):
    monkeypatch.setattr(backend, 'API_KEYS', ['clave-prueba'])
    monkeypatch.setattr(backend, 'get_db', lambda: db_pg)
    monkeypatch.setattr(db_pg, 'close', lambda: None)          # la fixture db_pg cierra al final
    monkeypatch.setenv('DB_ENGINE', 'postgres')
    return TestClient(backend.app)
def registrar_muestra(db): return registrar_comprobante(db, MUESTRA_XML, consultar=fijo(DATOS_ACEPTADO), ahora=T0, config_validacion=CONFIG_SIN_RED, config_seguimiento=ConfigSeguimiento())

def test_200(cliente, db_pg):
    registrar_muestra(db_pg)
    r = cliente.get('/comprobantes/101616202/E310000002882', headers=KEY); j = r.json()
    assert r.status_code == 200 and j['registrado'] is True and j['estado'] == 'ACEPTADO' and j['estado_dgii_texto'] == 'Aceptado'
    assert set(j['validacion']) == {'estructura','integridad','vigencia','entidad_certificadora','revocacion','cruce','comprador'}
    assert j['seguimiento_hasta'] == '2026-11-13T10:00:00-04:00' and j['seguimiento_activo'] is True
def test_404(cliente, db_pg):
    r = cliente.get('/comprobantes/101616202/E319999999999', headers=KEY); assert r.status_code == 404 and r.json() == {'registrado': False}
def test_normaliza_ruta(cliente, db_pg):  # Foco 3
    registrar_muestra(db_pg); assert cliente.get('/comprobantes/ 101616202 /e310000002882', headers=KEY).status_code == 200
def test_sin_api_key(cliente): assert cliente.get('/comprobantes/1/E31').status_code in (401, 422)
def test_motor_no_postgres(cliente, monkeypatch):
    monkeypatch.setenv('DB_ENGINE', 'sqlite'); assert cliente.get('/comprobantes/1/E31', headers=KEY).status_code == 503
def test_endpoints_existentes_siguen():
    assert {'/validar-factura-pdf-base64', '/validar-factura-pdf-multipart', '/validar-factura-params'} <= {r.path for r in backend.app.routes}
```

- [ ] **Paso 2:** `.venv/Scripts/python -m pytest tests/endpoint -v`. Esperado: FALLA.
- [ ] **Paso 3:** implementar. El motor se lee con `leer_config_db()[0]`.
- [ ] **Paso 4:** `.venv/Scripts/python -m pytest -v`, que corre los `testpaths` de `pytest.ini`. Esperado: todo PASA. Las pruebas antiguas (`tests/test_*.py`) ya fallaban antes y quedan fuera de `testpaths`.
- [ ] **Paso 5:** en `README.md` documentar:
  - el endpoint, con el JSON de ejemplo y el 404;
  - `DB_ENGINE` y `DB_CONNECTION_STRING`;
  - los parámetros nuevos;
  - cómo agregar una entidad certificadora a `confianza/`;
  - que con Postgres la bitácora `facturas` de los endpoints existentes pasa a vivir en Postgres.
- [ ] **Paso 6:** commit — `feat(api): consulta del último estado de un comprobante`.
