"""Save every built deck as a PDF through PowerPoint (Windows, PowerPoint installed).

    python materials/export_pdfs.py

Reads materials/out/decks/*.pptx and writes materials/out/pdf/*.pdf. PDFs can be
added to NotebookLM directly with "Upload source".
"""
import base64
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DECKS, PDFS = ROOT / 'out' / 'decks', ROOT / 'out' / 'pdf'

SCRIPT = r"""
$decks = '{decks}'
$pdfs = '{pdfs}'
New-Item -ItemType Directory -Force $pdfs | Out-Null
$ppt = New-Object -ComObject PowerPoint.Application
try {{
    foreach ($file in Get-ChildItem $decks -Filter *.pptx) {{
        $pres = $ppt.Presentations.Open($file.FullName, $true, $false, $false)
        $pres.SaveAs((Join-Path $pdfs ($file.BaseName + '.pdf')), 32)   # 32 = PDF
        $pres.Close()
        "saved $($file.BaseName).pdf"
    }}
}} finally {{
    if ($ppt.Presentations.Count -eq 0) {{ $ppt.Quit() }}
}}
"""


def main():
    script = SCRIPT.format(decks=str(DECKS).replace("'", "''"), pdfs=str(PDFS).replace("'", "''"))
    encoded = base64.b64encode(script.encode('utf-16-le')).decode('ascii')
    result = subprocess.run(['powershell', '-NoProfile', '-EncodedCommand', encoded], text=True, capture_output=True)
    print(result.stdout.strip() or result.stderr.strip())
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
