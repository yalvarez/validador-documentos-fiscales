import importlib
import importlib.util
import os
from urllib.parse import urlparse

import psycopg
import pytest
from psycopg import sql

from db.postgres_db_wrapper import PostgresDBWrapper

TEST_DATABASE_URL = os.getenv(
    'TEST_DATABASE_URL',
    'postgresql://validador:validador@localhost:5433/validador_test',
)

MODULOS_CON_CACHES = (
    'common.ecf.verificaciones.certificado',
    'common.ecf.verificaciones.revocacion',
)


@pytest.fixture
def db_pg():
    nombre = urlparse(TEST_DATABASE_URL).path.lstrip('/')
    if not nombre.endswith('_test'):
        pytest.fail(f"TEST_DATABASE_URL debe apuntar a una base cuyo nombre termine en '_test' (recibido: '{nombre}')")
    db = PostgresDBWrapper(TEST_DATABASE_URL)
    try:
        tablas = [f[0] for f in db.fetchall("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")]
        if tablas:
            lista = sql.SQL(', ').join(sql.Identifier('public', t) for t in tablas)
            db.conn.execute(sql.SQL('TRUNCATE {} RESTART IDENTITY CASCADE').format(lista))
        yield db
    finally:
        db.close()


def _existe(nombre):
    try:
        return importlib.util.find_spec(nombre) is not None
    except (ImportError, ValueError):
        return False


@pytest.fixture(autouse=True)
def limpiar_caches_ecf():
    for nombre in MODULOS_CON_CACHES:
        if _existe(nombre):
            importlib.import_module(nombre).limpiar_caches()
    yield
