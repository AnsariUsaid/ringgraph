"""Build docs/ringgraph_readout.pdf from the Markdown readout.

Needs the `markdown` package in .venv (uv pip install --python .venv/Scripts/python.exe markdown)
and Microsoft Edge or Chrome for the headless print. Run: .venv/Scripts/python.exe docs/build_pdf.py
"""

import subprocess
import tempfile
from pathlib import Path

import markdown

DOCS = Path(__file__).parent
BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
]
CSS = """
@page { size: A4; margin: 18mm 16mm; }
body { font: 10.5pt/1.55 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; color: #1c1b19; }
h1 { font-size: 24pt; margin: 0 0 6pt; letter-spacing: -0.02em; }
h2 { font-size: 15pt; margin: 22pt 0 6pt; padding-top: 8pt; border-top: 1px solid #d9d4c8; page-break-after: avoid; }
h3 { font-size: 11.5pt; margin: 14pt 0 4pt; page-break-after: avoid; }
p { margin: 5pt 0; }
ul, ol { margin: 4pt 0 6pt; padding-left: 18pt; }
li { margin: 2pt 0; }
hr { display: none; }
code { font: 9pt Consolas, monospace; background: #f1eee6; padding: 0 3px; border-radius: 3px; }
table { border-collapse: collapse; width: 100%; margin: 8pt 0; font-size: 9.2pt; page-break-inside: avoid; }
th, td { border: 1px solid #d9d4c8; padding: 4pt 6pt; text-align: left; vertical-align: top; }
th { background: #f1eee6; }
"""

html = markdown.markdown((DOCS / "ringgraph_readout.md").read_text(encoding="utf-8"), extensions=["tables", "sane_lists"])
page = DOCS / "ringgraph_readout.html"
page.write_text(f'<!doctype html><meta charset="utf-8"><title>RingGraph readout</title><style>{CSS}</style>{html}', encoding="utf-8")
browser = next(b for b in BROWSERS if Path(b).exists())
with tempfile.TemporaryDirectory() as profile:
    subprocess.run(
        [browser, "--headless=new", "--disable-gpu", f"--user-data-dir={profile}", "--no-pdf-header-footer",
         f"--print-to-pdf={DOCS / 'ringgraph_readout.pdf'}", page.as_uri()],
        check=True, timeout=120,
    )
page.unlink()
print("wrote", DOCS / "ringgraph_readout.pdf")
