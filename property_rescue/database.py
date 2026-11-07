"""Application database configuration; separate from Switch provider storage."""

import os
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import ArgumentError

from property_rescue.config import ConfigurationError


def database_url() -> str:
    value = os.environ.get("APP_DATABASE_URL", "")
    try:
        url = make_url(value)
        if url.drivername != "postgresql+psycopg" or not url.host or not url.database:
            raise ValueError
    except (ValueError, ArgumentError):
        # SQLAlchemy's ArgumentError can include the input. Never echo it.
        raise ConfigurationError("Set a valid APP_DATABASE_URL using postgresql+psycopg") from None
    return value


def build_engine(url: str | None = None) -> Engine:
    return create_engine(url or database_url(), pool_pre_ping=True, hide_parameters=True,
                         connect_args={"connect_timeout": 5})
