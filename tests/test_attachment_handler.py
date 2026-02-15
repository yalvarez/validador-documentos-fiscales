import os
from unittest.mock import MagicMock
from common.attachment_handler.handler import AttachmentHandler

class DummyAttachment:
    def __init__(self, name):
        self.name = name
    def save_as(self, path):
        with open(path, 'w') as f:
            f.write('dummy')

class DummyMessage:
    def __init__(self):
        self.attachments = [DummyAttachment('test.pdf'), DummyAttachment('test.xml')]


def test_download_attachments():
    handler = AttachmentHandler(download_dir='test_attachments')
    msg = DummyMessage()
    pdf, xml = handler.download_attachments(msg)
    print('PDF:', pdf, 'XML:', xml)
    assert os.path.exists(pdf)
    assert os.path.exists(xml)
    # Limpieza
    os.remove(pdf)
    os.remove(xml)
    os.rmdir('test_attachments')
