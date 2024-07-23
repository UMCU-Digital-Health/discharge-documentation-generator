import uvicorn

from discharge_docs.api.app import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8124)
