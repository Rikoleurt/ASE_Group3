from fastapi import FastAPI

from backend.app.routes.user_routes import router as user_router


app = FastAPI(title="ASE Backend")

app.include_router(user_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
