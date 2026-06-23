# img2latex

A small FastAPI service that turns an image into a compiled LaTeX PDF. Upload a
photo or screenshot (handwritten notes, a textbook page, a formula), and the
service transcribes it to LaTeX with a vision model and compiles the result to
PDF with `pdflatex`.

## How it works

1. The browser UI (`static/index.html`) posts an image to `POST /convert`.
2. `services/claude_service.py` sends the image to Anthropic's vision API and
   gets back LaTeX source.
3. `services/latex_service.py` runs `pdflatex` on that source and returns the
   compiled PDF.

## Requirements

- Python 3.11+
- A working `pdflatex` (e.g. MacTeX / TeX Live)
- An Anthropic API key

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # then fill in the values
```

`.env` keys (see `.env.example`):

| Key | Description |
|-----|-------------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `PDFLATEX_PATH` | Path to the `pdflatex` binary (e.g. `/Library/TeX/texbin/pdflatex`) |
| `MAX_IMAGE_SIZE_MB` | Max accepted upload size (default `20`) |

## Run

```bash
uvicorn main:app --reload
```

Then open <http://127.0.0.1:8000/> for the web UI. On startup the server checks
that `pdflatex` is reachable and warns if it isn't.

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/health`  | Health check |
| `POST` | `/convert` | Multipart image upload → LaTeX + compiled PDF |

## Layout

```
main.py                  # app setup, pdflatex preflight, router + static mount
config.py                # settings loaded from .env (pydantic-settings)
api/routes.py            # /health and /convert endpoints
api/schemas.py           # request/response models
services/claude_service.py   # image → LaTeX (Anthropic vision API)
services/latex_service.py    # LaTeX → PDF (pdflatex)
static/index.html        # browser UI
tests/                   # tests
```

> Note: `.env` is gitignored — your API key is never committed.
