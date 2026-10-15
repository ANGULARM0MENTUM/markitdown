# MarkItDown for Windows

`dist\MarkItDown\MarkItDown.exe` converts documents to Markdown. It bundles the local `markitdown` package and the `[all]` format extras (PDF, Word, Excel, PowerPoint, HTML, CSV, images, audio, Outlook, and the rest of that extra). Python does not need to be installed on the machine that runs the `.exe`.

Copy the whole `dist\MarkItDown` folder. The executable loads libraries from that folder, so moving `MarkItDown.exe` by itself will not start.

## Use the app

1. Open `dist\MarkItDown\MarkItDown.exe`.
2. Drop documents onto the window, or click **Browse files**.
3. Leave **Save next to each source file** checked, or clear it and choose a `.md` file (one document) or a folder (several documents).
4. Click **Convert**. Progress and errors appear in the status log.

Supported picks include `.pdf`, `.docx`, `.xlsx`, `.xls`, `.pptx`, `.html`, `.htm`, `.csv`, `.txt`, `.json`, `.ipynb`, `.epub`, `.zip`, `.jpg`, `.jpeg`, `.png`, `.wav`, `.mp3`, `.msg`, and `.xml`. Other files can still be tried; MarkItDown reports an error in the log when it cannot read one.

Image files are read with Windows OCR, which writes the recognized text. Metadata is added when [ExifTool](https://exiftool.org/) is on `PATH`. A picture caption still needs an LLM client configured in code. Audio files other than WAV need [ffmpeg](https://ffmpeg.org/) on `PATH` for transcription. ExifTool and ffmpeg are separate programs and are not inside the `.exe`.

If an Excel file fails in the `.exe` with “File is not a zip file” and the same file converts from the `venv` Python, document-protection software is handing `MarkItDown.exe` a transformed copy of the workbook. Word, PowerPoint, PDF, and HTML are unaffected. Allow `MarkItDown.exe` in that product and convert again.

A single file can also be converted from a terminal without opening the window:

```bat
dist\MarkItDown\MarkItDown.exe --convert "C:\docs\report.pdf" "C:\docs\report.md"
```

If that conversion fails, the error text is written beside the requested output as `report.md.error.txt`.

## Rebuild after code changes

From the repository root, in **Command Prompt**:

```bat
build.bat
```

The script creates `venv` if needed, installs this checkout with the `[all]` extra plus PyInstaller, and writes a new `dist\MarkItDown\MarkItDown.exe`.

To rebuild by hand after `venv` already exists:

```bat
venv\Scripts\python.exe -m pip install pyinstaller tkinterdnd2 "packages/markitdown[all]"
venv\Scripts\python.exe -m PyInstaller --noconfirm --clean build.spec
```

Reinstall `packages/markitdown[all]` when the library itself changes. Re-running PyInstaller is enough when only `app.py` changes. The build is one-folder and windowed (`console=False` in `build.spec`), which keeps startup from unpacking a single file on every launch and hides the terminal.

Check the window against the Python sources before packaging:

```bat
venv\Scripts\python.exe app.py
```
