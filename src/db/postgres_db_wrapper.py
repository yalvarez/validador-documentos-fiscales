from datetime import datetime

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from .base_db_wrapper import BaseDBWrapper


COLUMNAS_COMPROBANTE = frozenset({
    'rnc_emisor', 'encf', 'rnc_comprador', 'tipo_ecf', 'fecha_emision', 'monto_total', 'fecha_firma',
    'codigo_seguridad', 'razon_social_emisor', 'url_consulta',
    'xml_contenido', 'xml_hash_sha256', 'qr_params', 'origen', 'referencia_origen',
    'validacion_detalle', 'integridad', 'vigencia', 'entidad_certificadora', 'revocacion',
    'certificado_titular', 'certificado_emisor', 'certificado_serie',
    'estado', 'estado_dgii_texto', 'ultima_consulta_dgii',
    'seguimiento_activo', 'seguimiento_hasta', 'proxima_consulta', 'intervalo_actual_min', 'intentos',
})


def _validar_columnas(campos):
    desconocidas = set(campos) - COLUMNAS_COMPROBANTE
    if desconocidas:
        raise ValueError(f'Columnas desconocidas: {sorted(desconocidas)}')


def _preparar(campos):
    """Valida columnas y zonas horarias; devuelve una copia con RNC/e-NCF normalizados."""
    _validar_columnas(campos)
    copia = dict(campos)
    for c in ('rnc_emisor', 'encf'):
        if isinstance(copia.get(c), str):
            copia[c] = copia[c].strip().upper()
    for c, v in copia.items():
        _exigir_aware(c, v)
    return copia


def _exigir_aware(nombre, v):
    if isinstance(v, datetime) and v.tzinfo is None:
        raise ValueError(f'Fecha sin zona horaria: {nombre}')


def _valor(v):
    return Jsonb(v) if isinstance(v, (dict, list)) else v


class PostgresDBWrapper(BaseDBWrapper):
    def __init__(self, conn_str):
        self.conn = psycopg.connect(conn_str, autocommit=True)
        # La API y el worker pueden arrancar a la vez: CREATE TABLE IF NOT EXISTS
        # concurrente puede lanzar UniqueViolation; se reintenta.
        for intento in range(3):
            try:
                self.create_facturas_table()
                self.create_mensajes_table()
                self.create_parametros_table()
                self.create_comprobantes_tables()
                break
            except psycopg.errors.UniqueViolation:
                if intento == 2:
                    raise

    def close(self):
        self.conn.close()

    def execute(self, query, params=None):
        cur = self.conn.cursor()
        cur.execute(query, params or None)
        return cur

    def fetchall(self, query, params=None):
        cur = self.conn.cursor()
        cur.execute(query, params or None)
        return cur.fetchall()

    def is_message_processed(self, message_id):
        cur = self.conn.execute('SELECT 1 FROM mensajes_recibidos WHERE message_id = %s', (message_id,))
        return cur.fetchone() is not None

    def insert_factura(self, factura_dict):
        self.conn.execute('''
            INSERT INTO facturas (
                rncemisor, rnccomprador, ncfelectronico, fechaemision, montototal, fechafirma, codigoseguridad, estado, url_validacion, razon_social_emisor
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            factura_dict.get('rncemisor'),
            factura_dict.get('rnccomprador'),
            factura_dict.get('ncfelectronico'),
            factura_dict.get('fechaemision'),
            factura_dict.get('montototal'),
            factura_dict.get('fechafirma'),
            factura_dict.get('codigoseguridad'),
            factura_dict.get('estado'),
            factura_dict.get('url_validacion'),
            factura_dict.get('razon_social_emisor'),
        ))

    def insert_mensaje(self, message_id, remitente, asunto):
        self.conn.execute('''
            INSERT INTO mensajes_recibidos (message_id, remitente, asunto)
            VALUES (%s, %s, %s)
        ''', (message_id, remitente, asunto))

    def update_factura_estado(self, message_id, nuevo_estado):
        self.conn.execute('''
            UPDATE facturas SET estado = %s, fecha = CURRENT_TIMESTAMP WHERE message_id = %s
        ''', (nuevo_estado, message_id))

    def update_factura_envio(self, message_id, estado_envio, mensaje_error=None):
        self.conn.execute('''
            UPDATE facturas SET estado_envio = %s, mensaje_error = %s, fecha = CURRENT_TIMESTAMP WHERE message_id = %s
        ''', (estado_envio, mensaje_error, message_id))

    def create_facturas_table(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS facturas (
                id BIGSERIAL PRIMARY KEY,
                message_id TEXT,
                rncemisor TEXT,
                rnccomprador TEXT,
                ncfelectronico TEXT,
                fechaemision TEXT,
                montototal TEXT,
                fechafirma TEXT,
                codigoseguridad TEXT,
                estado TEXT,
                url_validacion TEXT,
                razon_social_emisor TEXT,
                estado_envio TEXT DEFAULT 'NO ENVIADO',
                mensaje_error TEXT,
                fecha TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    def create_mensajes_table(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS mensajes_recibidos (
                id BIGSERIAL PRIMARY KEY,
                message_id TEXT,
                fecha TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                remitente TEXT,
                asunto TEXT
            )
        ''')

    def create_parametros_table(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS parametros (
                id BIGSERIAL PRIMARY KEY,
                clave TEXT UNIQUE NOT NULL,
                valor TEXT NOT NULL,
                descripcion TEXT,
                ultima_actualizacion TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    def get_param(self, clave):
        cur = self.conn.execute('SELECT valor FROM parametros WHERE clave = %s', (clave,))
        row = cur.fetchone()
        return row[0] if row else None

    def set_param(self, clave, valor, descripcion=None):
        self.conn.execute('''
            INSERT INTO parametros (clave, valor, descripcion, ultima_actualizacion)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor, descripcion = EXCLUDED.descripcion, ultima_actualizacion = CURRENT_TIMESTAMP
        ''', (clave, valor, descripcion))

    def get_all_params(self):
        cur = self.conn.execute('SELECT clave, valor, descripcion, ultima_actualizacion FROM parametros')
        return cur.fetchall()

    def create_comprobantes_tables(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS comprobantes (
                id SERIAL PRIMARY KEY,
                rnc_emisor TEXT NOT NULL,
                encf TEXT NOT NULL,
                rnc_comprador TEXT,
                tipo_ecf TEXT,
                fecha_emision TEXT,
                monto_total NUMERIC(18,2),
                fecha_firma TIMESTAMPTZ,
                codigo_seguridad TEXT,
                razon_social_emisor TEXT,
                url_consulta TEXT,
                xml_contenido BYTEA NOT NULL,
                xml_hash_sha256 TEXT NOT NULL,
                qr_params JSONB,
                origen TEXT NOT NULL,
                referencia_origen TEXT,
                validacion_detalle JSONB NOT NULL,
                integridad TEXT,
                vigencia TEXT,
                entidad_certificadora TEXT,
                revocacion TEXT,
                certificado_titular TEXT,
                certificado_emisor TEXT,
                certificado_serie TEXT,
                estado TEXT NOT NULL,
                estado_dgii_texto TEXT,
                ultima_consulta_dgii TIMESTAMPTZ,
                seguimiento_activo BOOLEAN NOT NULL,
                seguimiento_hasta TIMESTAMPTZ NOT NULL,
                proxima_consulta TIMESTAMPTZ NOT NULL,
                intervalo_actual_min INTEGER NOT NULL,
                intentos INTEGER NOT NULL DEFAULT 0,
                creado_en TIMESTAMPTZ DEFAULT now(),
                actualizado_en TIMESTAMPTZ DEFAULT now(),
                UNIQUE (rnc_emisor, encf)
            )
        ''')
        self.conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_comprobantes_seguimiento
            ON comprobantes (seguimiento_activo, proxima_consulta)
        ''')
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS comprobante_historial (
                id SERIAL PRIMARY KEY,
                comprobante_id INTEGER REFERENCES comprobantes(id),
                fecha TIMESTAMPTZ NOT NULL,
                tipo TEXT NOT NULL,
                estado_anterior TEXT,
                estado_nuevo TEXT,
                estado_dgii_texto TEXT,
                detalle TEXT
            )
        ''')
        self.conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_historial_comprobante
            ON comprobante_historial (comprobante_id)
        ''')

    def _filas(self, query, params=None):
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, params)
            return cur.fetchall()

    def get_comprobante(self, rnc_emisor, encf):
        filas = self._filas(
            'SELECT * FROM comprobantes WHERE rnc_emisor = %s AND encf = %s',
            (rnc_emisor.strip().upper(), encf.strip().upper()))
        return filas[0] if filas else None

    def insert_comprobante(self, campos):
        campos = _preparar(campos)
        columnas = list(campos)
        consulta = sql.SQL(
            'INSERT INTO comprobantes ({}) VALUES ({}) ON CONFLICT (rnc_emisor, encf) DO NOTHING RETURNING id'
        ).format(
            sql.SQL(', ').join(sql.Identifier(c) for c in columnas),
            sql.SQL(', ').join(sql.Placeholder() for _ in columnas))
        cur = self.conn.execute(consulta, [_valor(campos[c]) for c in columnas])
        fila = cur.fetchone()
        return fila[0] if fila else None

    def update_comprobante(self, id, campos):
        campos = _preparar(campos)
        asignaciones = [sql.SQL('{} = %s').format(sql.Identifier(c)) for c in campos]
        asignaciones.append(sql.SQL('actualizado_en = now()'))
        consulta = sql.SQL('UPDATE comprobantes SET {} WHERE id = %s').format(sql.SQL(', ').join(asignaciones))
        self.conn.execute(consulta, [_valor(v) for v in campos.values()] + [id])

    def insert_historial(self, id, tipo, estado_anterior=None, estado_nuevo=None,
                         estado_dgii_texto=None, detalle=None, fecha=None):
        _exigir_aware('fecha', fecha)
        self.conn.execute(
            'INSERT INTO comprobante_historial '
            '(comprobante_id, fecha, tipo, estado_anterior, estado_nuevo, estado_dgii_texto, detalle) '
            'VALUES (%s, COALESCE(%s, now()), %s, %s, %s, %s, %s)',
            (id, fecha, tipo, estado_anterior, estado_nuevo, estado_dgii_texto, detalle))

    def get_historial(self, id):
        return self._filas(
            'SELECT * FROM comprobante_historial WHERE comprobante_id = %s ORDER BY fecha, id', (id,))

    def get_comprobantes_por_consultar(self, ahora, limite=100):
        _exigir_aware('ahora', ahora)
        return self._filas(
            'SELECT * FROM comprobantes WHERE seguimiento_activo AND proxima_consulta <= %s '
            'ORDER BY proxima_consulta, id LIMIT %s', (ahora, limite))

    def transaccion(self):
        return self.conn.transaction()
