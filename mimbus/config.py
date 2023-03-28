import os


class Config:
    DB_URL = os.getenv('DB_URL')
    DEBUG = os.getenv('DEBUG', False)
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    AUTH_TOKEN_TTL = int(os.getenv('AUTH_TOKEN_TTL', 60 * 60))

    USE_PRIVATE_PROXY = os.getenv('USE_PRIVATE_PROXY', True)

    ADMIN_ONLY = os.getenv('ADMIN_ONLY', False)

    ESCALATION_CHAT_ID = os.getenv('ESCALATION_CHAT_ID', None)
