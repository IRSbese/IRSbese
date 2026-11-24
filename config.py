# ЧАСТЬ 1. Настройки приложения и production-режима.
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY')
    DEBUG = os.getenv('FLASK_DEBUG', '0') == '1'
    ENVIRONMENT = os.getenv('APP_ENV', 'development').lower()
    DATABASE = os.getenv('DATABASE_PATH', str(BASE_DIR / 'instance' / 'irsbese.sqlite3'))
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', str(BASE_DIR / 'app' / 'static' / 'uploads'))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.getenv('COOKIE_SECURE', '0') == '1'
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 14
    DEMO_MODE = os.getenv('DEMO_MODE', '1') == '1'
    PAYMENTS_ENABLED = os.getenv('PAYMENTS_ENABLED', '0') == '1'
    YOOKASSA_SHOP_ID = os.getenv('YOOKASSA_SHOP_ID', '')
    YOOKASSA_SECRET_KEY = os.getenv('YOOKASSA_SECRET_KEY', '')
    YOOKASSA_API_URL = 'https://api.yookassa.ru/v3'
    SMTP_HOST = os.getenv('SMTP_HOST', '')
    SMTP_PORT = os.getenv('SMTP_PORT', '587')
    SMTP_USER = os.getenv('SMTP_USER', '')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
    SMTP_FROM = os.getenv('SMTP_FROM', 'noreply@irsbese.local')
