from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    pdflatex_available: bool
    model: str


class ConversionResponse(BaseModel):
    latex_source: str
    filename: str
    compilation_success: bool
    error_message: str | None = None
