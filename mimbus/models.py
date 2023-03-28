import sqlalchemy
from sqlalchemy.sql import func

from mimbus.utils import Base


class User(Base):
    __tablename__ = 'users'

    id = sqlalchemy.Column(sqlalchemy.BigInteger, primary_key=True)
    tg_name = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
    language = sqlalchemy.Column(sqlalchemy.Text)

    steam_name = sqlalchemy.Column(sqlalchemy.Text)
    refresh_token = sqlalchemy.Column(sqlalchemy.Text)

    uid = sqlalchemy.Column(sqlalchemy.BigInteger)
    public_uid = sqlalchemy.Column(sqlalchemy.Text)

    auto_assemble = sqlalchemy.Column(sqlalchemy.Boolean, server_default='false')

    last_assembled_at = sqlalchemy.Column(sqlalchemy.DateTime, server_default='1970-01-01 00:00:00')
    notification_sent = sqlalchemy.Column(sqlalchemy.Boolean, server_default='false')

    auth_token = sqlalchemy.Column(sqlalchemy.Text)
    auth_token_created_at = sqlalchemy.Column(sqlalchemy.DateTime)

    created_at = sqlalchemy.Column(sqlalchemy.DateTime, server_default=func.now())
