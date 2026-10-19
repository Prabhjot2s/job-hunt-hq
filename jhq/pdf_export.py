"""DOCX -> PDF on Windows, macOS and Linux.

Order tried:
  Windows: Microsoft Word (COM, via PowerShell), then LibreOffice.
  macOS:   LibreOffice, then Microsoft Word through docx2pdf (if that package is installed).
  Linux:   LibreOffice.
Word gives the closest match to what recruiters see in Word; LibreOffice is free and fine.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


class ExportError(RuntimeError):
    pass


def _soffice() -> str | None:
    for name in ("soffice", "libreoffice"):
        p = shutil.which(name)
        if p:
            return p
    candidates = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ]
    return next((c for c in candidates if os.path.exists(c)), None)


def _word_windows(docx: Path, pdf: Path):
    # Paths go in through environment variables, never into the script text: folder names come
    # from job titles, and PowerShell treats curly quotes (’) as quote marks too.
    ps = (
        "$ErrorActionPreference='Stop';"
        "$w=New-Object -ComObject Word.Application;$w.Visible=$false;$w.DisplayAlerts=0;"
        "try{$doc=$w.Documents.Open($env:JHQ_DOCX,$false,$true);"
        "$doc.ExportAsFixedFormat($env:JHQ_PDF,17);$doc.Close($false)}"
        "finally{$w.Quit();[void][Runtime.InteropServices.Marshal]::ReleaseComObject($w)}"
    )
    env = {**os.environ, "JHQ_DOCX": str(docx.resolve()), "JHQ_PDF": str(pdf.resolve())}
    res = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                         capture_output=True, text=True, timeout=180, env=env)
    if res.returncode != 0 or not pdf.exists():
        raise ExportError(res.stderr.strip()[-400:] or "Word export failed")


def _libreoffice(docx: Path, pdf: Path):
    exe = _soffice()
    if not exe:
        raise ExportError("LibreOffice not found")
    with tempfile.TemporaryDirectory() as out:
        # A private profile dir avoids clashing with a LibreOffice window the user has open.
        profile = Path(out) / "lo-profile"
        res = subprocess.run([exe, f"-env:UserInstallation={profile.as_uri()}", "--headless",
                              "--convert-to", "pdf", "--outdir", out, str(docx)],
                             capture_output=True, text=True, timeout=180)
        made = Path(out) / (docx.stem + ".pdf")
        if res.returncode != 0 or not made.exists():
            raise ExportError(res.stderr.strip()[-400:] or "LibreOffice export failed")
        shutil.move(str(made), str(pdf))


def _docx2pdf(docx: Path, pdf: Path):
    try:
        from docx2pdf import convert  # optional; drives Word for Mac
    except ImportError as e:
        raise ExportError("docx2pdf not installed") from e
    convert(str(docx), str(pdf))
    if not pdf.exists():
        raise ExportError("Word for Mac export failed")


def methods():
    if sys.platform == "win32":
        return [("Microsoft Word", _word_windows), ("LibreOffice", _libreoffice)]
    if sys.platform == "darwin":
        return [("LibreOffice", _libreoffice), ("Microsoft Word (docx2pdf)", _docx2pdf)]
    return [("LibreOffice", _libreoffice)]


def export_pdf(docx, pdf) -> str:
    """Write `pdf` from `docx`; returns the method used. Raises ExportError with every reason."""
    docx, pdf = Path(docx), Path(pdf)
    errors = []
    for name, fn in methods():
        try:
            if pdf.exists():
                pdf.unlink()  # PermissionError here = the PDF is open in a viewer
            fn(docx, pdf)
            return name
        except PermissionError as e:
            raise ExportError(f"{pdf.name} is open in another program; close it and retry") from e
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {e}")
    raise ExportError("Could not make a PDF. Install LibreOffice (free) or Microsoft Word.\n  "
                      + "\n  ".join(errors))


def available() -> list[str]:
    """What this computer can use, for `jhq doctor`."""
    out = []
    if sys.platform == "win32":
        try:
            import winreg
            winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Word.Application").Close()
            out.append("Microsoft Word")
        except OSError:
            pass
    if _soffice():
        out.append("LibreOffice")
    if sys.platform == "darwin":
        try:
            import docx2pdf  # noqa: F401
            out.append("Microsoft Word (docx2pdf)")
        except ImportError:
            pass
    return out
