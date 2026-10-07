from fastapi import FastAPI
from backend.app.routes.reading_routes import router as reading_router
from backend.app.routes.tablet_demo_routes import router as tablet_demo_router
from backend.app.routes.user_routes import router as user_router

app = FastAPI(title="ASE Backend")

app.include_router(user_router)
app.include_router(tablet_demo_router)
app.include_router(reading_router)

# Quick debug to test backend connectivity to the frontend.
@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
