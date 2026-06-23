import asyncio
import shutil
import tempfile
from pathlib import Path

from config import get_settings


class LatexCompilationError(Exception):
    def __init__(self, stderr: str, stdout: str):
        self.stderr = stderr
        self.stdout = stdout
        super().__init__(f"pdflatex compilation failed.\nSTDERR: {stderr[:500]}")


async def compile(
    latex_source: str,
    image_bytes: bytes | None = None,
) -> tuple[Path, Path]:
    """Compile LaTeX source to PDF. Returns (pdf_path, workdir_path).

    If image_bytes is provided, it is saved as input_image.png in the workdir
    so Claude-generated \\includegraphics{input_image.png} commands resolve correctly.
    The caller is responsible for cleaning up workdir after the response is sent.
    """
    settings = get_settings()
    workdir = Path(tempfile.mkdtemp(prefix="img2latex_"))
    tex_file = workdir / "document.tex"
    tex_file.write_text(latex_source, encoding="utf-8")

    if image_bytes is not None:
        (workdir / "input_image.png").write_bytes(image_bytes)

    cmd = [
        settings.PDFLATEX_PATH,
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-output-directory", str(workdir),
        str(tex_file),
    ]

    for pass_num in (1, 2):
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(workdir),
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=60.0)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise LatexCompilationError(
                stderr="pdflatex timed out after 60 seconds.",
                stdout="",
            )

        if proc.returncode != 0 and pass_num == 2:
            raise LatexCompilationError(
                stderr=stderr_b.decode(errors="replace"),
                stdout=stdout_b.decode(errors="replace"),
            )

    pdf_path = workdir / "document.pdf"
    if not pdf_path.exists():
        raise LatexCompilationError(stderr="PDF file was not produced.", stdout="")

    return pdf_path, workdir


def cleanup(workdir: Path) -> None:
    shutil.rmtree(str(workdir), ignore_errors=True)
