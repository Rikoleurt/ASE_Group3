import os
from contextlib import contextmanager
from typing import Iterator

import mysql.connector
from mysql.connector.connection import MySQLConnection


class DataController:
    """
    Base class responsible for opening/closing MySQL connections.
    """

    def __init__(self) -> None:
        self.config = {
            "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
            "port": int(os.getenv("MYSQL_PORT", "3306")),
            "user": os.getenv("MYSQL_USER", "ase"),
            "password": os.getenv("MYSQL_PASSWORD", "ase"),
            "database": os.getenv("MYSQL_DATABASE", "ase3"),
            "connection_timeout": 5,
        }

    @contextmanager
    def connection(self) -> Iterator[MySQLConnection]:
        connection = mysql.connector.connect(**self.config)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
