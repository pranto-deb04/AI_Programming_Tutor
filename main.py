from fastapi import FastAPI
import models
from database import engine

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Programming Tutor API")


@app.get("/")
def read_root():
    return {"message": "Welcome to AI Programming Tutor Backend!"}
