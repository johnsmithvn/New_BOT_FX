"""
dashboard/dashboard.py

FastAPI application entry point for the analytics dashboard.

Usage:
    python -m dashboard.dashboard

Environment variables:
    DASHBOARD_DB_PATH   Path to bot SQLite database (default: data/bot.db)
    DASHBOARD_API_KEY   Optional API key for /api/* endpoints
    DASHBOARD_PORT      Port to run on (default: 8000)
    DASHBOARD_HOST      Host to bind (default: 0.0.0.0)
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from dashboard.api.routes import router as api_router, set_db
from dashboard.db.queries import DashboardDB

# ── Configuration ────────────────────────────────────────────────

DB_PATH = os.getenv("DASHBOARD_DB_PATH", "data/bot.db")
API_KEY = os.getenv("DASHBOARD_API_KEY", "")
PORT = int(os.getenv("DASHBOARD_PORT", "8000"))
HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")

# ── App Setup ────────────────────────────────────────────────────

app = FastAPI(
    title="Forex Bot Dashboard",
    version="0.12.0",
    docs_url="/docs" if not API_KEY else None,
)

# CORS — allow Vercel frontend to call VPS API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_methods=["GET"],
    allow_headers=["X-API-Key"],
)

# ── API Key Middleware ───────────────────────────────────────────


@app.middleware("http")
async def check_api_key(request: Request, call_next):
    """Validate API key for /api/* calls if DASHBOARD_API_KEY is set."""
    if API_KEY and request.url.path.startswith("/api/"):
        key = request.headers.get("X-API-Key", "")
        if key != API_KEY:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )
    return await call_next(request)


# ── Database ─────────────────────────────────────────────────────


@app.on_event("startup")
def startup_db() -> None:
    """Initialize read-only database connection."""
    db_path = Path(DB_PATH)
    if not db_path.exists():
        print(f"⚠️  Database not found at {db_path.resolve()}")
        print("   Dashboard will start but API calls will fail.")
        print(f"   Set DASHBOARD_DB_PATH to the correct path.")
        return
    db = DashboardDB(db_path)
    set_db(db)
    print(f"✅ Database connected: {db_path.resolve()}")


# ── Routes ───────────────────────────────────────────────────────

# API routes
app.include_router(api_router)

# Static files (CSS, JS)
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Templates
TEMPLATE_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


# ── Page Routes ──────────────────────────────────────────────────


@app.get("/")
async def page_overview(request: Request):
    """Main dashboard overview page."""
    return templates.TemplateResponse("overview.html", {"request": request})


@app.get("/channels")
async def page_channels(request: Request):
    """Channel performance page."""
    return templates.TemplateResponse("channels.html", {"request": request})


@app.get("/trades")
async def page_trades(request: Request):
    """Trade history page."""
    return templates.TemplateResponse("trades.html", {"request": request})


# ── Entry Point ──────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print(f"🚀 Starting Forex Bot Dashboard on {HOST}:{PORT}")
    uvicorn.run(
        "dashboard.dashboard:app",
        host=HOST,
        port=PORT,
        reload=False,
    )
