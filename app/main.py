"""Application entry point."""

from app.core import app
from app import features  # register restaurant routes
from app import fiscal  # register fiscal adapters
from app import reporting
from app import completion
from app import hardening
from app import province_adapters
from app import worker
from app import menu_images

# Serve the local workspace from the same origin as its authenticated API.
from pathlib import Path
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles


@app.get("/", include_in_schema=False)
def root_redirect():
    return RedirectResponse(url="/ui/")


app.mount(
    "/ui",
    StaticFiles(directory=Path(__file__).resolve().parents[1] / "frontend", html=True),
    name="frontend",
)
