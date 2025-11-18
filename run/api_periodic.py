import os
from typing import Literal, cast

import uvicorn
from dotenv import load_dotenv
from umcu_ai_utils.database_connection import get_engine

from discharge_docs.api.app_periodic import app
from discharge_docs.database.models import Base, Request

load_dotenv()

if __name__ == "__main__":
    db_schema_name = Request.__table__.schema
    db_env = cast(Literal["PROD", "ACC", "DEBUG"], os.getenv("DB_ENVIRONMENT"))
    engine = get_engine(db_env=db_env, schema_name=db_schema_name)

    # Prevent creating tables from dev dashboard
    table_list = [
        table
        for table in Base.metadata.tables.values()
        if table.schema == db_schema_name
    ]
    Base.metadata.create_all(engine, tables=table_list)
    app.state.engine = engine
    uvicorn.run(app, host="0.0.0.0", port=8127)
