from fastapi import FastAPI

app = FastAPI(
    title="ASE Group 3 API",
    version="0.1.0",
)


@app.get("/")
def root():
    return {"message": "ASE Group 3 backend is running"}


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "message": "Backend is communicating with the frontend"
    }