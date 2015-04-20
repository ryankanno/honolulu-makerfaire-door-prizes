import logging
from logging.handlers import RotatingFileHandler
from makerfaire.app import app


if __name__ == '__main__':
    handler = RotatingFileHandler('/var/log/flask-hnlmakerfaire.log',
                                  maxBytes=1024*1024*5, backupCount=30)
    handler.setLevel(logging.DEBUG)
    app.logger.addHandler(handler)
    app.run()
