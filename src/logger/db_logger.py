import sqlite3
from datetime import datetime

class DBLogger:
    def __init__(self, db_path='validador.db'):
        self.conn = sqlite3.connect(db_path)
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

    def log_validacion(self, message_id, subject, sender, pdf_path, xml_path, qr_url, resultado):
        self.conn.execute('''
            INSERT INTO validaciones (message_id, subject, sender, pdf_path, xml_path, qr_url, resultado)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (message_id, subject, sender, pdf_path, xml_path, qr_url, resultado))
        self.conn.commit()

    def is_message_processed(self, message_id):
        cur = self.conn.execute('SELECT 1 FROM validaciones WHERE message_id = ?', (message_id,))
        return cur.fetchone() is not None
