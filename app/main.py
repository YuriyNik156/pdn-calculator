from fastapi import FastAPI

app = FastAPI(title="PDN Calculator API", version="0.1.0")

@app.get("/")
def root():
    return {"message": "PDN Calculator API is running!"}
