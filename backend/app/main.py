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
from backend.app.routes.benchmark_routes import router as benchmark_router
from backend.app.routes.glyph_routes import router as glyph_router
from backend.app.routes.correction_routes import router as correction_router
from backend.app.routes.admin_routes import router as admin_router
from backend.app.routes.box_set_routes import router as box_set_router
from backend.app.routes.corpus_routes import router as corpus_router
from backend.app.routes.version_routes import router as version_router
from backend.app.routes.edition_routes import router as edition_router
from backend.app.routes.activity_routes import router as activity_router
from backend.app.routes.bookmark_routes import router as bookmark_router
from backend.app.routes.notification_routes import router as notification_router
from backend.app.routes.link_routes import router as link_router
from backend.app.routes.search_routes import router as search_router
from backend.app.routes.share_routes import router as share_router
from backend.app.routes.comment_routes import router as comment_router
from backend.app.routes.community_routes import router as community_router



@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Loading the models takes ~20-60 s on CPU; do it in the background at startup
    # so the first upload doesn't wait. PRELOAD_MODELS=0 turns it off (tests do).
    if os.getenv("PRELOAD_MODELS", "1") != "0":
        Thread(target=tablet_demo.warm_up, name="warm-up", daemon=True).start()
    yield


app = FastAPI(title="ASE Backend", lifespan=lifespan)

app.include_router(share_router)  # before user_router: /users/search is not /users/{user_id}
app.include_router(user_router)
app.include_router(tablet_demo_router)
app.include_router(reading_router)
app.include_router(analysis_router)
app.include_router(benchmark_router)
app.include_router(glyph_router)
app.include_router(correction_router)
app.include_router(admin_router)
app.include_router(box_set_router)
app.include_router(corpus_router)
app.include_router(version_router)
app.include_router(edition_router)
app.include_router(activity_router)
app.include_router(bookmark_router)
app.include_router(notification_router)
app.include_router(link_router)
app.include_router(search_router)
app.include_router(comment_router)
app.include_router(community_router)

@app.exception_handler(DatabaseError)
async def database_unavailable(_request, _error):
    return JSONResponse(status_code=503, content={"detail": "Storage is unavailable. Please try again."},
                        headers={"Cache-Control": "no-store"})


@app.middleware("http")
async def private_responses(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith(("/users", "/analysis", "/corrections", "/community")):
        response.headers["Cache-Control"] = "no-store"
    return response


# Upload size limits, checked before the body is read: FastAPI parses a multipart body before
# any route dependency runs, so a check inside the route would come after the whole upload (#98).
BODY_LIMITS = {"/analysis": 10 * 1024 * 1024 + 64 * 1024}


@app.middleware("http")
async def limit_upload_size(request, call_next):
    limit = BODY_LIMITS.get(request.url.path) if request.method == "POST" else None
    if limit is not None:
        declared = request.headers.get("content-length", "")
        if not declared.isdigit():
            return JSONResponse({"detail": "Uploads must declare their size."}, status_code=411)
        if int(declared) > limit:
            return JSONResponse({"detail": "The image is larger than 10 MB."}, status_code=413)
    return await call_next(request)


# Quick debug to test backend connectivity to the frontend.
@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
