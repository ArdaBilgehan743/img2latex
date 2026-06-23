import asyncio
import base64
import subprocess
from datetime import datetime
from pathlib import Path

import anthropic
from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
import io

from api.schemas import HealthResponse
from config import get_settings
from services import claude_service, latex_service
from services.latex_service import LatexCompilationError

router = APIRouter(prefix="/api")

ALLOWED_MEDIA_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "image/bmp", "image/tiff", "image/x-tiff",
}


def _check_pdflatex() -> bool:
    settings = get_settings()
    try:
        result = subprocess.run(
            [settings.PDFLATEX_PATH, "--version"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


@router.get("/health", response_model=HealthResponse)
async def health():
    settings = get_settings()
    return HealthResponse(
        status="ok" if _check_pdflatex() else "degraded",
        pdflatex_available=_check_pdflatex(),
        model=settings.MODEL,
    )


@router.post("/convert")
async def convert(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    want_latex: bool = Form(False),
):
    settings = get_settings()

    # Validate file size
    image_bytes = await file.read()
    max_bytes = settings.MAX_IMAGE_SIZE_MB * 1024 * 1024
    if len(image_bytes) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {settings.MAX_IMAGE_SIZE_MB} MB.",
        )

    # Validate it's a real image via Pillow
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.verify()
    except (UnidentifiedImageError, Exception):
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Please upload a valid image (JPEG, PNG, GIF, WEBP, BMP, TIFF).",
        )

    media_type = file.content_type or "image/png"
    if media_type not in ALLOWED_MEDIA_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported media type: {media_type}.",
        )

    if not _check_pdflatex():
        raise HTTPException(
            status_code=503,
            detail=(
                "pdflatex is not available on this server. "
                "Install TeX Live: brew install --cask mactex (macOS) or apt install texlive-full (Linux)."
            ),
        )

    # Call Claude to generate LaTeX
    try:
        latex_source = await claude_service.image_to_latex(image_bytes, media_type)
    except anthropic.AuthenticationError:
        raise HTTPException(status_code=500, detail="Invalid Anthropic API key.")
    except anthropic.RateLimitError:
        raise HTTPException(status_code=429, detail="Anthropic API rate limit exceeded. Please try again later.")
    except anthropic.BadRequestError as e:
        raise HTTPException(status_code=400, detail=f"Claude rejected the image: {e}")
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Claude API error: {e}")

    # Convert image to PNG for pdflatex \includegraphics compatibility
    try:
        png_buf = io.BytesIO()
        Image.open(io.BytesIO(image_bytes)).convert("RGB").save(png_buf, format="PNG")
        png_bytes = png_buf.getvalue()
    except Exception:
        png_bytes = None

    # Compile LaTeX to PDF
    try:
        pdf_path, workdir = await latex_service.compile(latex_source, image_bytes=png_bytes)
    except LatexCompilationError as e:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "LaTeX compiled successfully by Claude but pdflatex failed to produce a PDF.",
                "latex_source": latex_source,
                "pdflatex_stderr": e.stderr,
                "pdflatex_stdout": e.stdout,
            },
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"img2latex_{timestamp}.pdf"

    background_tasks.add_task(latex_service.cleanup, workdir)

    headers = {}
    if want_latex:
        headers["X-Latex-Source"] = base64.b64encode(latex_source.encode()).decode()
        headers["Access-Control-Expose-Headers"] = "X-Latex-Source, Content-Disposition"

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=filename,
        headers=headers,
    )
