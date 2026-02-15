-- Script SQL para poblar la tabla parametros en MySQL
-- Sobrescribe los valores existentes (ON DUPLICATE KEY UPDATE)
INSERT INTO parametros (clave, valor, descripcion, ultima_actualizacion) VALUES
('O365_CLIENT_ID', 'TU_CLIENT_ID', 'Parametro migrado desde .env', NOW()),
('O365_CLIENT_SECRET', 'TU_CLIENT_SECRET', 'Parametro migrado desde .env', NOW()),
('EMAIL_PROVIDER', 'gmail', 'Parametro migrado desde .env', NOW()),
('EMAIL_USER', 'isaiasalvarez@gmail.com', 'Parametro migrado desde .env', NOW()),
('EMAIL_PASS', 'rljk jpwc wnab ncss', 'Parametro migrado desde .env', NOW()),
('ATTACHMENTS_DIR', 'attachments', 'Parametro migrado desde .env', NOW()),
('LOG_FILE', 'validador.log', 'Parametro migrado desde .env', NOW()),
('API_URL', 'https://api.ejemplo.com/validar', 'Parametro migrado desde .env', NOW()),
('API_KEY', 'TU_API_KEY', 'Parametro migrado desde .env', NOW()),
('CHECK_INTERVAL', '60', 'Parametro migrado desde .env', NOW()),
('MAILBOX_FOLDER', 'Inbox', 'Parametro migrado desde .env', NOW()),
('DB_ENGINE', 'mysql', 'Parametro migrado desde .env', NOW()),
('DB_CONNECTION_STRING', 'user:password@host:port/dbname', 'Parametro migrado desde .env', NOW())
ON DUPLICATE KEY UPDATE valor=VALUES(valor), descripcion=VALUES(descripcion), ultima_actualizacion=VALUES(ultima_actualizacion);
