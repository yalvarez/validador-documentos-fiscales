
import os
from typing import Tuple, Optional

import imaplib
import smtplib

class EmailClient:
    def __init__(self, provider: str, username: str, password: str, app_password: Optional[str] = None):
        self.provider = provider.lower()
        self.username = username
        self.password = password
        self.app_password = app_password or password
        self.imap_server, self.smtp_server, self.imap_port, self.smtp_port = self._get_config()

    def _get_config(self):
        if self.provider == "gmail":
            return (
                "imap.gmail.com",
                "smtp.gmail.com",
                993,
                587
            )
        elif self.provider in ["office365", "outlook"]:
            return (
                "outlook.office365.com",
                "smtp.office365.com",
                993,
                587
            )
        else:
            raise ValueError(f"Proveedor de correo no soportado: {self.provider}")

    def connect_imap(self):
        mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
        mail.login(self.username, self.app_password)
        return mail

    def connect_smtp(self):
        server = smtplib.SMTP(self.smtp_server, self.smtp_port)
        server.starttls()
        server.login(self.username, self.app_password)
        return server

# Ejemplo de uso:
# client = EmailClient("gmail", "tu_email@gmail.com", "tu_contraseña_o_app_password")
# imap_conn = client.connect_imap()
# smtp_conn = client.connect_smtp()

class AttachmentHandler:
    def __init__(self, download_dir: str = 'attachments'):
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)

    def download_attachments(self, attachments) -> Tuple[Optional[str], Optional[str]]:
        """
        Descarga adjuntos (PDF y XML) desde una lista de adjuntos (O365 o email.message.Message)
        y retorna las rutas locales.
        """
        import tempfile
        pdf_path, xml_path = None, None
        for att in attachments:
            filename = att.name.lower() if hasattr(att, 'name') else att.get_filename().lower()
            suffix = os.path.splitext(filename)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=self.download_dir) as tmp:
                if hasattr(att, 'content'):
                    tmp.write(att.content)
                else:
                    tmp.write(att.get_payload(decode=True))
                tmp.flush()
                if filename.endswith('.pdf'):
                    pdf_path = tmp.name
                elif filename.endswith('.xml'):
                    xml_path = tmp.name
        return pdf_path, xml_path
