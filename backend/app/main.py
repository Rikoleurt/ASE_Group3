import os
from contextlib import asynccontextmanager
from threading import Thread

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from mysql.connector import Error as DatabaseError
from backend.app import tablet_demo
from backend.app.routes.reading_routes import router as reading_router
from backend.app.routes.tablet_demo_routes import router as tablet_demo_router
from backend.app.routes.user_routes import router as user_router
from backend.app.routes.analysis_routes import router as analysis_router
from backend.app.routes.glyph_routes import router as glyph_router



@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Loading the models takes ~20-60 s on CPU; do it in the background at startup
    # so the first upload doesn't wait. PRELOAD_MODELS=0 turns it off (tests do).
    if os.getenv("PRELOAD_MODELS", "1") != "0":
        Thread(target=tablet_demo.warm_up, name="warm-up", daemon=True).start()
    yield


app = FastAPI(title="ASE Backend", lifespan=lifespan)

app.include_router(user_router)
app.include_router(tablet_demo_router)
app.include_router(reading_router)
app.include_router(analysis_router)
app.include_router(glyph_router)

@app.exception_handler(DatabaseError)
async def database_unavailable(_request, _error):
    return JSONResponse(status_code=503, content={"detail": "Account storage is unavailable."},
                        headers={"Cache-Control": "no-store"})


@app.middleware("http")
async def private_responses(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith(("/users", "/analysis")):
        response.headers["Cache-Control"] = "no-store"
    return response


# Quick debug to test backend connectivity to the frontend.
@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
