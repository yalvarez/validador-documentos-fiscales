from db.config import leer_config_db


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
