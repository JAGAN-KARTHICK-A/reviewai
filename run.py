from app.webhooks import router
from fastapi import FastAPI
import uvicorn

app = FastAPI()
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run("run:app", host = "localhost", port = 3000, reload=True)
