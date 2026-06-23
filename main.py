import subprocess
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routes import router
from config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    try:
        result = subprocess.run(
            [settings.PDFLATEX_PATH, "--version"],
            capture_output=True,
            timeout=5,
        )
        if result.returncode == 0:
            print(f"pdflatex found at {settings.PDFLATEX_PATH}")
        else:
            print(f"WARNING: pdflatex returned non-zero exit at {settings.PDFLATEX_PATH}")
    except FileNotFoundError:
        print(f"WARNING: pdflatex not found at {settings.PDFLATEX_PATH}. PDF compilation will be unavailable.")
    except Exception as e:
        print(f"WARNING: Could not verify pdflatex: {e}")

    yield


app = FastAPI(
    title="img2latex",
    description="Convert any image to a LaTeX PDF using Claude vision.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Latex-Source", "Content-Disposition"],
)

app.include_router(router)
app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
