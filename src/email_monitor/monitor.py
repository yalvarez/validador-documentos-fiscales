import os
from typing import List, Optional
from attachment_handler.handler import EmailClient
import email
from email.utils import parsedate_to_datetime
from datetime import datetime

class EmailMonitor:
    def __init__(self, provider: str, username: str, password: str, app_password: Optional[str] = None):
        self.provider = provider
        self.username = username
        self.password = password
        self.app_password = app_password or password
        self.client = EmailClient(provider, username, password, app_password)

    def get_unread_inbox_messages(self) -> List[dict]:
        # Solo usa IMAP genérico, no importa O365
        mail = self.client.connect_imap()
        print('Conectado al servidor IMAP.')
        mail.select('inbox')
        from datetime import datetime, timedelta
        messages = []
        today = datetime.now().date()
        # Formato de fecha para IMAP: 11-Feb-2026
        since_str = today.strftime('%d-%b-%Y')
        before_str = (today + timedelta(days=1)).strftime('%d-%b-%Y')
        # Buscar solo correos no leídos del día
        search_criteria = f'(UNSEEN SINCE {since_str} BEFORE {before_str})'
        typ, data = mail.search(None, search_criteria)
        print(f'Búsqueda realizada con criterio: {search_criteria}. Resultados: {data}')
        for num in data[0].split():
            typ, msg_data = mail.fetch(num, '(RFC822)')
            msg = email.message_from_bytes(msg_data[0][1])
            messages.append({
                'subject': msg.get('Subject'),
                'from': msg.get('From'),
                'to': msg.get('To'),
                'date': msg.get('Date'),
                'raw': msg,
                'id': num
            })
        mail.close()
        mail.logout()
        return messages

    def mark_as_read(self, message_id):
        mail = self.client.connect_imap()
        mail.select('inbox')
        mail.store(message_id, '+FLAGS', '\Seen')
        mail.close()
        mail.logout()
