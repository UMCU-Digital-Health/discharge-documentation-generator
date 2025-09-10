import uvicorn
from umcu_ai_utils.database_connection import get_engine

from discharge_docs.api.app_periodic import app
from discharge_docs.database.models import Base, Request

if __name__ == "__main__":
    engine = get_engine(schema_name=Request.__table__.schema)
    Base.metadata.create_all(engine)
    app.state.engine = engine
    uvicorn.run(app, host="0.0.0.0", port=8127)
