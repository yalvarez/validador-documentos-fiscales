-- Script SQL para poblar la tabla parametros con los valores actuales del archivo .env
-- Sobrescribe los valores existentes (INSERT OR REPLACE)

INSERT OR REPLACE INTO parametros (clave, valor, descripcion, ultima_actualizacion) VALUES
('O365_CLIENT_ID', 'TU_CLIENT_ID', 'Parametro migrado desde .env', CURRENT_TIMESTAMP),
('O365_CLIENT_SECRET', 'TU_CLIENT_SECRET', 'Parametro migrado desde .env', CURRENT_TIMESTAMP),
('EMAIL_PROVIDER', 'gmail', 'Parametro migrado desde .env', CURRENT_TIMESTAMP),
('EMAIL_USER', 'isaiasalvarez@gmail.com', 'Parametro migrado desde .env', CURRENT_TIMESTAMP),
('EMAIL_PASS', 'rljk jpwc wnab ncss', 'Parametro migrado desde .env', CURRENT_TIMESTAMP),
('ATTACHMENTS_DIR', 'attachments', 'Parametro migrado desde .env', CURRENT_TIMESTAMP),
('LOG_FILE', 'validador.log', 'Parametro migrado desde .env', CURRENT_TIMESTAMP),
('API_URL', 'https://api.ejemplo.com/validar', 'Parametro migrado desde .env', CURRENT_TIMESTAMP),
('API_KEY', 'TU_API_KEY', 'Parametro migrado desde .env', CURRENT_TIMESTAMP),
('CHECK_INTERVAL', '60', 'Parametro migrado desde .env', CURRENT_TIMESTAMP),
('MAILBOX_FOLDER', 'Inbox', 'Parametro migrado desde .env', CURRENT_TIMESTAMP),
('DB_ENGINE', 'sqlite', 'Parametro migrado desde .env', CURRENT_TIMESTAMP),
('DB_CONNECTION_STRING', './db.sqlite3', 'Parametro migrado desde .env', CURRENT_TIMESTAMP),
('AZURE_TENANT_ID', '', 'Parametro migrado desde .env', CURRENT_TIMESTAMP),
('AZURE_CLIENT_ID', '', 'Parametro migrado desde .env', CURRENT_TIMESTAMP),
('AZURE_ALLOWED_GROUP_ID', '', 'Parametro migrado desde .env', CURRENT_TIMESTAMP);