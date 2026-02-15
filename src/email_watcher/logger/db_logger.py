from datetime import datetime

from db.db_factory import get_db_wrapper
from db.base_db_wrapper import BaseDBWrapper

class DBLogger:
    def __init__(self, db_engine, db_config):
        self.db: BaseDBWrapper = get_db_wrapper(db_engine, db_config)
        self.conn = self.db.conn
        self._create_table()

    def _create_table(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS validaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT,
                subject TEXT,
                sender TEXT,
                pdf_path TEXT,
                xml_path TEXT,
                qr_url TEXT,
                resultado TEXT,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

    def create_facturas_table(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS facturas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()
        # Migración automática: agrega el campo si falta
        cur = self.conn.execute("PRAGMA table_info(facturas)")
        columns = [row[1] for row in cur.fetchall()]
        if 'razon_social_emisor' not in columns:
            try:
                self.conn.execute("ALTER TABLE facturas ADD COLUMN razon_social_emisor TEXT")
                self.conn.commit()
            except Exception as e:
                pass  # Ya existe o error de migración

    def create_mensajes_table(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS mensajes_recibidos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                remitente TEXT,
                asunto TEXT
            )
        ''')
        self.conn.commit()

    def insert_factura(self, factura_dict, estado):
        self.conn.execute('''
            INSERT INTO facturas (
                message_id, rncemisor, rnccomprador, ncfelectronico, fechaemision, montototal, fechafirma, codigoseguridad, estado, url_validacion, razon_social_emisor
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            factura_dict.get('message_id'),
            factura_dict.get('RncEmisor'),
            factura_dict.get('RncComprador'),
            factura_dict.get('ENCF'),
            factura_dict.get('FechaEmision'),
            factura_dict.get('MontoTotal'),
            factura_dict.get('FechaFirma'),
            factura_dict.get('CodigoSeguridad'),
            estado,
            factura_dict.get('url_validacion'),
            factura_dict.get('razon_social_emisor')
        ))
        self.conn.commit()

    def insert_mensaje(self, message_id, remitente, asunto):
        self.conn.execute('''
            INSERT INTO mensajes_recibidos (message_id, remitente, asunto)
            VALUES (?, ?, ?)
        ''', (message_id, remitente, asunto))
        self.conn.commit()

    def update_factura_estado(self, message_id, nuevo_estado):
        self.conn.execute('''
            UPDATE facturas SET estado = ?, fecha = CURRENT_TIMESTAMP WHERE message_id = ?
        ''', (nuevo_estado, message_id))
        self.conn.commit()

    def update_factura_envio(self, message_id, estado_envio, mensaje_error=None):
        self.conn.execute('''
            UPDATE facturas SET estado_envio = ?, mensaje_error = ?, fecha = CURRENT_TIMESTAMP WHERE message_id = ?
        ''', (estado_envio, mensaje_error, message_id))
        self.conn.commit()

    def log_validacion(self, message_id, subject, sender, pdf_path, xml_path, qr_url, resultado):
        self.conn.execute('''
            INSERT INTO validaciones (message_id, subject, sender, pdf_path, xml_path, qr_url, resultado)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (message_id, subject, sender, pdf_path, xml_path, qr_url, resultado))
        self.conn.commit()

    def is_message_processed(self, message_id):
        cur = self.conn.execute('SELECT 1 FROM validaciones WHERE message_id = ?', (message_id,))
        return cur.fetchone() is not None
import sqlite3
from datetime import datetime
