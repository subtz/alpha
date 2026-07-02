import dotenv
dotenv.load_dotenv()
import dj_database_url
import os
from decouple import config
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY')

DEBUG_RAW = config('DEBUG', default='True')
if isinstance(DEBUG_RAW, str):
    DEBUG = DEBUG_RAW.lower() in ('true', '1', 'yes', 'on')
else:
    DEBUG = bool(DEBUG_RAW)

ALLOWED_HOSTS = ['alpha-0xjx.onrender.com', '127.0.0.1', 'localhost']
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
CSRF_TRUSTED_ORIGINS = ["https://alpha-0xjx.onrender.com"]

GROQ_API_KEY = config('GROQ_API_KEY', default='')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_extensions',
    'calc',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'alpha.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
    'django.template.context_processors.debug',
    'django.template.context_processors.request',
    'django.contrib.auth.context_processors.auth',
    'django.contrib.messages.context_processors.messages',
    'calc.context_processors.student_profile',
    'calc.context_processors.vapid_keys',
            ],
        },
    },
]

WSGI_APPLICATION = 'alpha.wsgi.application'

DATABASE_URL = config('DATABASE_URL', default='', cast=str)
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            ssl_require=DATABASE_URL.startswith('postgres'),
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# ==================================================
# EMAIL
# ==================================================
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False

# Load credentials from environment (.env or Render dashboard)
EMAIL_HOST_USER = config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')

# Always send from your Gmail address
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# Verification/reset token expiry — 24 hours
PASSWORD_RESET_TIMEOUT = 86400

# ==================================================
# CACHE (used for rate limiting resend emails)
# ==================================================
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# ==================================================
# AUTH
# ==================================================
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'home'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


VAPID_PUBLIC_KEY = config(
    'VAPID_PUBLIC_KEY',
    default=''
)

VAPID_PRIVATE_KEY = config(
    'VAPID_PRIVATE_KEY',
    default=''
)
# ==================================================
# AUTO-CREATE SUPERUSER (for Render free tier)
# --------------------------------------------------
# This block imports alpha/create_superuser.py at startup.
# The script checks if a superuser exists in the database.
# If not, it creates one using the DJANGO_SUPERUSER_* environment
# variables you set in Render’s Environment tab.
# This is required because free Render does not allow Shell access.
# ==================================================
try:
    import create_superuser
except Exception:
    # Fail silently if the helper script is missing or errors out
    pass
