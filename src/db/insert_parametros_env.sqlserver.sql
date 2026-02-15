-- Script SQL para poblar la tabla parametros en SQL Server
-- Sobrescribe los valores existentes (MERGE)
MERGE INTO parametros AS target
USING (VALUES
('O365_CLIENT_ID', 'TU_CLIENT_ID', 'Parametro migrado desde .env'),
('O365_CLIENT_SECRET', 'TU_CLIENT_SECRET', 'Parametro migrado desde .env'),
('EMAIL_PROVIDER', 'gmail', 'Parametro migrado desde .env'),
('EMAIL_USER', 'isaiasalvarez@gmail.com', 'Parametro migrado desde .env'),
('EMAIL_PASS', 'rljk jpwc wnab ncss', 'Parametro migrado desde .env'),
('ATTACHMENTS_DIR', 'attachments', 'Parametro migrado desde .env'),
('LOG_FILE', 'validador.log', 'Parametro migrado desde .env'),
('API_URL', 'https://api.ejemplo.com/validar', 'Parametro migrado desde .env'),
('API_KEY', 'TU_API_KEY', 'Parametro migrado desde .env'),
('CHECK_INTERVAL', '60', 'Parametro migrado desde .env'),
('MAILBOX_FOLDER', 'Inbox', 'Parametro migrado desde .env'),
('DB_ENGINE', 'sqlserver', 'Parametro migrado desde .env'),
('DB_CONNECTION_STRING', 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=host;DATABASE=dbname;UID=user;PWD=password', 'Parametro migrado desde .env')
) AS vals (clave, valor, descripcion)
ON target.clave = vals.clave
WHEN MATCHED THEN
    UPDATE SET valor = vals.valor, descripcion = vals.descripcion, ultima_actualizacion = SYSDATETIME()
WHEN NOT MATCHED THEN
    INSERT (clave, valor, descripcion, ultima_actualizacion)
    VALUES (vals.clave, vals.valor, vals.descripcion, SYSDATETIME());
