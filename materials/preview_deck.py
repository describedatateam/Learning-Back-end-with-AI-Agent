"""Export every slide of a .pptx to PNG through PowerPoint (Windows, PowerPoint installed).

    python materials/preview_deck.py materials/out/decks/01-http-requests.pptx <output folder>

The PowerShell commands are passed inline (-EncodedCommand), so this works even
where running .ps1 script files is disabled.
"""
import base64
import subprocess
import sys
from pathlib import Path

SCRIPT = r"""
$deck = '{deck}'
$out = '{out}'
New-Item -ItemType Directory -Force $out | Out-Null
$ppt = New-Object -ComObject PowerPoint.Application
try {{
    $pres = $ppt.Presentations.Open($deck, $true, $false, $false)
    $i = 0
    foreach ($slide in $pres.Slides) {{
        $i++
        $slide.Export((Join-Path $out ('slide{{0:D2}}.png' -f $i)), 'PNG', 1280, 720)
    }}
    $pres.Close()
    "Exported $i slides to $out"
}} finally {{
    # PowerPoint is shared: only quit if nobody else has a presentation open.
    if ($ppt.Presentations.Count -eq 0) {{ $ppt.Quit() }}
}}
"""


def main(deck, out):
    deck, out = Path(deck).resolve(), Path(out).resolve()
    script = SCRIPT.format(deck=str(deck).replace("'", "''"), out=str(out).replace("'", "''"))
    encoded = base64.b64encode(script.encode('utf-16-le')).decode('ascii')
    result = subprocess.run(['powershell', '-NoProfile', '-EncodedCommand', encoded], text=True, capture_output=True)
    print(result.stdout.strip() or result.stderr.strip())
    return result.returncode


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:3]))
