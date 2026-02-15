import sqlite3
from tabulate import tabulate

class Reportes:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)

    def resumen_validaciones(self):
        cur = self.conn.execute('''
            SELECT resultado, COUNT(*) as cantidad
            FROM validaciones
            GROUP BY resultado
        ''')
        rows = cur.fetchall()
        print(tabulate(rows, headers=['Resultado', 'Cantidad'], tablefmt='psql'))

    def listado_validaciones(self, limit=20):
        cur = self.conn.execute('''
            SELECT fecha, subject, sender, resultado, qr_url
            FROM validaciones
            ORDER BY fecha DESC
            LIMIT ?
        ''', (limit,))
        rows = cur.fetchall()
        print(tabulate(rows, headers=['Fecha', 'Asunto', 'Remitente', 'Resultado', 'URL QR'], tablefmt='psql'))

    def buscar_por_folio(self, folio):
        cur = self.conn.execute('''
            SELECT fecha, subject, sender, resultado, qr_url
            FROM validaciones
            WHERE subject LIKE ? OR qr_url LIKE ?
            ORDER BY fecha DESC
        ''', (f'%{folio}%', f'%{folio}%'))
        rows = cur.fetchall()
        print(tabulate(rows, headers=['Fecha', 'Asunto', 'Remitente', 'Resultado', 'URL QR'], tablefmt='psql'))
