import logging
import os

def setup_logger(log_file='validador.log'):
    os.makedirs(os.path.dirname(log_file) or '.', exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
        handlers=[logging.FileHandler(log_file), logging.StreamHandler()]
    )
    return logging.getLogger('validador')
