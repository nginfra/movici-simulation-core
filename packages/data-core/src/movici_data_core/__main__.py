import uvicorn

from movici_data_core.api import make_default_app

app = make_default_app()


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000)
