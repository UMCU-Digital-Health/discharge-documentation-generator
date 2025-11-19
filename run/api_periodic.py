import logging
import os
from typing import Literal, cast

import uvicorn
from dotenv import load_dotenv
from umcu_ai_utils.database_connection import get_engine

from discharge_docs.api.app_periodic import app
from discharge_docs.config import setup_root_logger
from discharge_docs.database.models import Base, Request

load_dotenv()

logger = logging.getLogger(__name__)
setup_root_logger()


def init_engine():
    db_schema_name = Request.__table__.schema
    db_env = cast(Literal["PROD", "ACC", "DEBUG"], os.getenv("DB_ENVIRONMENT"))
    engine = get_engine(db_env=db_env, schema_name=db_schema_name)
    table_list = [
        table
        for table in Base.metadata.tables.values()
        if table.schema == db_schema_name
    ]
    Base.metadata.create_all(engine, tables=table_list)
    app.state.engine = engine


try:
    init_engine()
except Exception as e:
    logger.warning(f"Failed to initialize database engine: {e}")
    raise


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8126)
