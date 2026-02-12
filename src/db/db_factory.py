def get_db_wrapper(db_type, config):
    if db_type == 'sqlite':
        from .sqlite_db_wrapper import SQLiteDBWrapper
        return SQLiteDBWrapper(config['db_path'])
    elif db_type == 'mysql':
        from .mysql_db_wrapper import MySQLDBWrapper
        return MySQLDBWrapper(config)
    elif db_type == 'sqlserver':
        from .sqlserver_db_wrapper import SQLServerDBWrapper
        return SQLServerDBWrapper(config)
    else:
        raise ValueError('Tipo de base de datos no soportado')
