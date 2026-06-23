import base64
import io
import re

import anthropic
from PIL import Image

from config import get_settings

SYSTEM_PROMPT = """You are an expert LaTeX document generator and academic problem solver.

Your sole output is a complete, compilable LaTeX document. Follow these rules with zero exceptions:

1. OUTPUT ONLY RAW LATEX. Do not wrap in markdown code fences (no ```latex). Do not add any explanation, preamble text, or commentary outside the LaTeX document.

2. DOCUMENT STRUCTURE: Always begin with \\documentclass[12pt,a4paper]{article} and end with \\end{document}.

3. REQUIRED PACKAGES: Always include this exact preamble unless the content obviously requires different packages:
   \\usepackage[utf8]{inputenc}
   \\usepackage[T1]{fontenc}
   \\usepackage[margin=2.5cm]{geometry}
   \\usepackage{amsmath,amssymb,amsfonts}
   \\usepackage{mathtools}
   \\usepackage{listings}
   \\usepackage{xcolor}
   \\usepackage{graphicx}
   \\usepackage{float}
   \\usepackage{caption}
   \\usepackage{booktabs}
   \\usepackage{hyperref}
   \\usepackage{enumitem}
   \\usepackage{parskip}

4. ANALYSIS — examine the image and determine its category:
   A. MATH / EQUATIONS: Transcribe all equations using proper LaTeX math environments. Use \\[ \\] for display math, $ $ for inline. For multi-line derivations use the align* environment.
   B. PROBLEM / QUESTION: If the image contains a question or problem (math, physics, chemistry, logic, word problem, etc.), SOLVE IT COMPLETELY within the document. Show all work. Use \\section{Problem}, \\section{Solution}, \\section{Answer} structure.
   C. SCIENTIFIC FIGURE / DIAGRAM: Describe the figure in a figure environment with a caption. If it contains data, reproduce it as a LaTeX table using tabular and booktabs.
   D. DOCUMENT / TEXT: Transcribe the text faithfully using appropriate LaTeX sectioning commands.
   E. GENERAL IMAGE: Provide a structured description in a \\section{Image Description} and \\section{Content Analysis} layout.
   F. MIXED CONTENT: Combine the above as appropriate. If the image has both a figure and questions, transcribe the figure AND solve the questions.

5. MATHEMATICS: Prefer numbered equations (\\begin{equation}) when the content references specific equations. Use \\text{} inside math mode for words. Use \\dfrac not \\frac in display math. Use \\left( \\right) for auto-sizing delimiters.

6. CODE: Use the listings package with \\lstset{basicstyle=\\ttfamily\\small, breaklines=true, frame=single}.

7. TITLE BLOCK: Always include:
   \\title{Image to \\LaTeX{} Conversion}
   \\author{img2latex}
   \\date{\\today}
   \\maketitle

8. COMPILABILITY: The document must compile without errors using pdflatex. Avoid packages that require XeLaTeX or LuaLaTeX (e.g. fontspec, unicode-math).

9. SKETCHES & DIAGRAMS: If the image is a sketch, drawing, hand-drawn diagram, or any visual figure that cannot be faithfully reproduced as text or TikZ, embed the original image using:
   \\begin{figure}[H]
   \\centering
   \\includegraphics[width=0.85\\textwidth]{input_image.png}
   \\caption{Original sketch / diagram}
   \\end{figure}
   Place this BEFORE any transcription or solution so the reader sees the source material first. You may ALSO reproduce it as TikZ if the sketch is simple enough.

9. SELF-CONTAINED: Do not reference external files. All content must be inline."""

CLAUDE_SUPPORTED_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


def _prepare_image(image_bytes: bytes, media_type: str) -> tuple[bytes, str]:
    """Re-encode unsupported formats (TIFF, BMP, etc.) to PNG."""
    if media_type in CLAUDE_SUPPORTED_TYPES:
        return image_bytes, media_type
    img = Image.open(io.BytesIO(image_bytes))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue(), "image/png"


def _strip_fences(text: str) -> str:
    """Remove accidental markdown code fences Claude sometimes adds."""
    text = text.strip()
    text = re.sub(r"^```(?:latex)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


async def image_to_latex(image_bytes: bytes, media_type: str) -> str:
    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    prepared_bytes, prepared_media_type = _prepare_image(image_bytes, media_type)
    encoded = base64.standard_b64encode(prepared_bytes).decode("utf-8")

    response = await client.messages.create(
        model=settings.MODEL,
        max_tokens=settings.MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": prepared_media_type,
                            "data": encoded,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Analyze this image carefully. Apply the appropriate category rule "
                            "from your instructions. If there is any question, problem, or exercise "
                            "visible, solve it completely and show all working steps. "
                            "Generate the complete LaTeX document now."
                        ),
                    },
                ],
            }
        ],
    )

    latex = ""
    for block in response.content:
        if block.type == "text":
            latex = block.text
            break

    latex = _strip_fences(latex)

    if "\\documentclass" not in latex or "\\end{document}" not in latex:
        raise ValueError(
            "Claude did not return a valid LaTeX document. "
            f"Response preview: {latex[:300]}"
        )

    return latex
