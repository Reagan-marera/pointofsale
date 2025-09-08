import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'reaganx12x#'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///pos.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_PASSWORD = os.environ.get('SECRET_PASSWORD') or 'reaganx12x#'
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_USERNAME = 'transactionsfinance355@gmail.com'
    MAIL_PASSWORD = 'rvzxngpossphfgzm'