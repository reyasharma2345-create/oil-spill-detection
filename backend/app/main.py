import sys
from pathlib import Path

# Ensure root workspace and backend directories are in sys.path
_ROOT = Path(__file__).resolve().parent.parent.parent
_BACKEND = Path(__file__).resolve().parent.parent
for _p in [str(_ROOT), str(_BACKEND)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.cases import router as cases_router
from app.api.predict import router as predict_router
from app.api.copernicus import router as copernicus_router
from app.api.ais import router as ais_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Full-stack AI-based maritime oil slick attribution, reverse-physics hindcasting, counterfactual candidate release simulation, and GIS vulnerability system."
)

# Enable CORS for local dev and WebGIS frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount core routers
app.include_router(cases_router, prefix=settings.API_PREFIX)
app.include_router(predict_router, prefix=settings.API_PREFIX)
app.include_router(predict_router)  # Root /predict support
app.include_router(copernicus_router, prefix=settings.API_PREFIX)
app.include_router(ais_router, prefix=settings.API_PREFIX)

# Mount static directory for prediction overlays and masks
from fastapi.staticfiles import StaticFiles
preds_dir = Path(__file__).resolve().parent.parent.parent / "outputs" / "predictions"
preds_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static/predictions", StaticFiles(directory=str(preds_dir)), name="predictions")


@app.get("/")
def root():
    return {
        "system": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs_url": "/docs",
        "api_prefix": settings.API_PREFIX
    }

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "oil-spill-attribution-backend"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
