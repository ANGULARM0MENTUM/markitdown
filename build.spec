# -*- mode: python ; coding: utf-8 -*-
"""Windowed one-folder build of the MarkItDown desktop app.

Run with the virtualenv that has this repo's markitdown[all] extra installed:

    venv\\Scripts\\python.exe -m PyInstaller --noconfirm build.spec
"""

import os

from PyInstaller.utils.hooks import collect_all, collect_data_files, copy_metadata

datas = []
binaries = []
hiddenimports = [
    "markitdown",
    "markitdown.converters",
    "magika",
    "onnxruntime",
    "pdfminer",
    "pdfminer.high_level",
    "pdfminer.layout",
    "pdfminer.cmapdb",
    "pdfplumber",
    "pypdfium2",
    "pypdfium2_raw",
    "PIL",
    "mammoth",
    "pptx",
    "openpyxl",
    "xlrd",
    "pandas",
    "lxml",
    "lxml.etree",
    "bs4",
    "markdownify",
    "charset_normalizer",
    "defusedxml",
    "olefile",
    "pydub",
    "speech_recognition",
    "youtube_transcript_api",
    "requests",
    "certifi",
    "azure.ai.documentintelligence",
    "azure.ai.contentunderstanding",
    "azure.identity",
    "azure.core",
]

# Core library plus the [all] extra (pdf, docx, pptx, xlsx, xls, audio, outlook, youtube, azure).
PACKAGES = [
    "markitdown",
    "magika",
    "onnxruntime",
    "pdfminer",
    "pdfplumber",
    "pypdfium2",
    "pypdfium2_raw",
    "PIL",
    "mammoth",
    "cobble",
    "pptx",
    "openpyxl",
    "xlrd",
    "et_xmlfile",
    "pandas",
    "numpy",
    "lxml",
    "bs4",
    "soupsieve",
    "markdownify",
    "charset_normalizer",
    "defusedxml",
    "olefile",
    "pydub",
    "speech_recognition",
    "youtube_transcript_api",
    "requests",
    "urllib3",
    "certifi",
    "idna",
    "azure",
]


def _keep(name: str) -> bool:
    return ".tests" not in name and ".testing" not in name


def _merge(bucket, items):
    seen = {(os.path.normcase(src), os.path.normcase(dest)) for src, dest in bucket}
    for src, dest in items:
        key = (os.path.normcase(str(src)), os.path.normcase(str(dest)))
        if key in seen:
            continue
        seen.add(key)
        bucket.append((src, dest))


for package in PACKAGES:
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    except Exception as exc:
        print(f"warning: could not collect {package}: {exc}")
        continue
    _merge(datas, pkg_datas)
    _merge(binaries, pkg_binaries)
    hiddenimports.extend(name for name in pkg_hidden if _keep(name))

hiddenimports = [name for name in dict.fromkeys(hiddenimports) if _keep(name)]

# tkdnd ships platform binaries next to its Tcl package. Keep that layout
# (collect_data_files) so Tcl can load the matching Windows DLL.
try:
    _merge(datas, collect_data_files("tkinterdnd2"))
    hiddenimports.append("tkinterdnd2")
except Exception as exc:
    print(f"warning: could not collect tkinterdnd2: {exc}")

for dist_name in (
    "magika",
    "markitdown",
    "onnxruntime",
    "pdfminer.six",
    "pdfplumber",
    "charset-normalizer",
    "pypdfium2",
):
    try:
        datas.extend(copy_metadata(dist_name))
    except Exception as exc:
        print(f"warning: could not copy metadata for {dist_name}: {exc}")


def _keep_data(src, dest) -> bool:
    path = os.path.normcase(str(src))
    if f"{os.sep}tkdnd{os.sep}" not in path:
        return True
    # The Windows Tcl package for this build. win-x64 also matches win-x64-tcl9.
    return f"{os.sep}win-x64" in path


datas = [(src, dest) for src, dest in datas if _keep_data(src, dest)]

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter.test", "pytest", "IPython", "matplotlib"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MarkItDown",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="MarkItDown",
)
