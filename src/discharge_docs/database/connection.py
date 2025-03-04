import os

from sqlalchemy import Engine, create_engine


def get_connection_string(
    db_user: str | None = None,
    db_passwd: str | None = None,
    db_host: str | None = None,
    db_port: str | None = None,
    db_database: str | None = None,
) -> str:
    """Get the connection string from the environment variables

    Optionally use the parameters to override the environment variables

    Parameters
    ----------
    db_user : str, optional
        Username of the service account, by default None
    db_passwd : str, optional
        Password of the service account, by default None
    db_host : str, optional
        Host of the database, by default None
    db_port : str, optional
        Database port, by default None
    db_database : str, optional
        Database name, by default None

    Returns
    -------
    str
        The connection string to the database
    """
    db_user = db_user or os.getenv("DB_USER")
    db_passwd = db_passwd or os.getenv("DB_PASSWD")
    db_host = db_host or os.getenv("DB_HOST")
    db_port = db_port or os.getenv("DB_PORT")
    db_database = db_database or os.getenv("DB_DATABASE")

    return f"mssql+pymssql://{db_user}:{db_passwd}@{db_host}:{db_port}/{db_database}"


def get_engine(
    connection_str: str | None = None, execute_options: dict | None = None
) -> Engine:
    """Get the SQLAlchemy engine

    Optionally use the parameter to override the connection string

    Parameters
    ----------
    connection_str : str, optional
        The connection string to the database, by default None

    Returns
    -------
    create_engine
        The SQLAlchemy engine used for queries
    """
    connection_str = connection_str or get_connection_string()
    return create_engine(
        connection_str, pool_pre_ping=True, execution_options=execute_options
    )
