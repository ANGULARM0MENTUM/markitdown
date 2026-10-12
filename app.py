"""Desktop window for converting documents to Markdown with MarkItDown."""

from __future__ import annotations

import ctypes
import os
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

# A windowed PyInstaller build leaves the standard streams unset. Libraries
# such as Magika print warnings during startup, and print() would then raise.
def _ensure_stdio() -> None:
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8", errors="replace")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8", errors="replace")


_ensure_stdio()

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from markitdown import MarkItDown
    from markitdown import __version__ as MARKITDOWN_VERSION
except ImportError:  # pragma: no cover - shown in the GUI when unpackaged
    MarkItDown = None  # type: ignore[misc, assignment]
    MARKITDOWN_VERSION = ""


DOCUMENT_FILTER = (
    "*.pdf *.docx *.xlsx *.xls *.pptx *.html *.htm *.csv *.txt *.md *.json "
    "*.jsonl *.ipynb *.epub *.zip *.jpg *.jpeg *.png *.wav *.mp3 *.m4a *.mp4 "
    "*.msg *.xml *.rss *.atom"
)

FILE_DIALOG_TYPES = [
    ("Supported documents", DOCUMENT_FILTER),
    ("PDF", "*.pdf"),
    ("Word", "*.docx"),
    ("Excel", "*.xlsx *.xls"),
    ("PowerPoint", "*.pptx"),
    ("Web and text", "*.html *.htm *.csv *.txt *.md *.json *.xml *.rss *.atom"),
    ("Images", "*.jpg *.jpeg *.png"),
    ("Audio and video", "*.wav *.mp3 *.m4a *.mp4"),
    ("All files", "*.*"),
]

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".mp4"}

_CONVERTER = None
_CONVERTER_LOCK = threading.Lock()


def _split_drop_paths(widget: tk.Misc, data: str) -> list[str]:
    """Turn a tkdnd path list into filesystem paths."""
    try:
        parts = widget.tk.splitlist(data)
    except tk.TclError:
        parts = [data]
    return [part.strip("{}") for part in parts if part]


def get_converter():
    """Create one MarkItDown instance and reuse it for later files."""
    if MarkItDown is None:
        raise RuntimeError(
            "The markitdown package is not installed. From the repository root, run:\n"
            "pip install \"packages/markitdown[all]\""
        )
    global _CONVERTER
    with _CONVERTER_LOCK:
        if _CONVERTER is None:
            _CONVERTER = MarkItDown()
        return _CONVERTER


def default_output_path(source: Path) -> Path:
    """Markdown path beside the source. Avoids replacing the source itself."""
    candidate = source.with_suffix(".md")
    try:
        same_file = candidate.resolve() == source.resolve()
    except OSError:
        same_file = candidate == source
    if same_file:
        return source.with_name(f"{source.stem}.converted.md")
    return candidate


def convert_file(source: Path, destination: Path) -> tuple[str, Path]:
    """Convert one local document and write UTF-8 Markdown.

    Returns the Markdown text and the path that was written.
    """
    if not source.is_file():
        raise FileNotFoundError(f"File not found: {source}")
    result = get_converter().convert(str(source))
    text = result.markdown or ""
    try:
        overwrites_source = destination.resolve() == source.resolve()
    except OSError:
        overwrites_source = False
    if overwrites_source:
        destination = source.with_name(f"{source.stem}.converted.md")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
    return text, destination


def _enable_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            return


class App(tk.Tk):
    """Browse or drop documents, then write a Markdown file for each one."""

    def __init__(self) -> None:
        super().__init__()
        version = f" {MARKITDOWN_VERSION}" if MARKITDOWN_VERSION else ""
        self.title(f"MarkItDown{version}")
        self.geometry("760x700")
        self.minsize(640, 560)
        self._files: list[Path] = []
        self._last_dir = str(Path.home())
        self._last_output: Path | None = None
        self._converting = False
        self.auto_output = tk.BooleanVar(value=True)
        self.custom_output = tk.StringVar()
        self.status = tk.StringVar(value="Ready")

        self._build()
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.after(50, self._setup_drag_and_drop)
        self.report_callback_exception = self._report_callback_exception  # type: ignore[method-assign]

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(6, weight=1)

        header = ttk.Frame(self, padding=(16, 14, 16, 4))
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="MarkItDown", font=("Segoe UI", 18, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            header,
            text="Convert documents to Markdown. Drop files below, or browse for them.",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        drop = tk.Frame(self, bg="#e7eef6", highlightbackground="#8aa4c0", highlightthickness=1)
        drop.grid(row=1, column=0, sticky="ew", padx=16, pady=(8, 4))
        self.drop_zone = drop
        tk.Label(
            drop,
            text="Drop documents here",
            bg="#e7eef6",
            fg="#1b3a4b",
            font=("Segoe UI", 12, "bold"),
        ).pack(pady=(16, 0))
        tk.Label(
            drop,
            text="PDF, Word, Excel, PowerPoint, HTML, CSV, images, notebooks, and more",
            bg="#e7eef6",
            fg="#3d5566",
            font=("Segoe UI", 9),
        ).pack(pady=(2, 8))
        ttk.Button(drop, text="Browse files", command=self._browse_files).pack(pady=(0, 14))

        files_bar = ttk.Frame(self, padding=(16, 8, 16, 0))
        files_bar.grid(row=2, column=0, sticky="ew")
        ttk.Label(files_bar, text="Selected files").pack(side="left")
        ttk.Button(files_bar, text="Clear", command=self._clear_files).pack(side="right")
        ttk.Button(files_bar, text="Remove", command=self._remove_selected).pack(
            side="right", padx=(0, 6)
        )

        list_frame = ttk.Frame(self, padding=(16, 4, 16, 0))
        list_frame.grid(row=3, column=0, sticky="ew")
        list_frame.columnconfigure(0, weight=1)
        self.file_list = tk.Listbox(
            list_frame,
            height=5,
            activestyle="dotbox",
            exportselection=False,
        )
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.file_list.yview)
        self.file_list.configure(yscrollcommand=scroll.set)
        self.file_list.grid(row=0, column=0, sticky="ew")
        scroll.grid(row=0, column=1, sticky="ns")
        self.file_list.bind("<Delete>", lambda _event: self._remove_selected())

        output = ttk.LabelFrame(self, text="Output", padding=(12, 8))
        output.grid(row=4, column=0, sticky="ew", padx=16, pady=(10, 4))
        output.columnconfigure(0, weight=1)
        ttk.Checkbutton(
            output,
            text="Save next to each source file",
            variable=self.auto_output,
            command=self._refresh_output_hint,
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        self.output_hint = ttk.Label(output, wraplength=680)
        self.output_hint.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 6))
        self.output_entry = ttk.Entry(output, textvariable=self.custom_output)
        self.output_entry.grid(row=2, column=0, sticky="ew")
        self.output_browse = ttk.Button(output, text="Choose location", command=self._browse_output)
        self.output_browse.grid(row=2, column=1, padx=(8, 0))

        actions = ttk.Frame(self, padding=(16, 8, 16, 0))
        actions.grid(row=5, column=0, sticky="ew")
        self.convert_button = ttk.Button(actions, text="Convert", command=self._start_convert)
        self.convert_button.pack(side="left")
        self.open_button = ttk.Button(
            actions, text="Show output folder", command=self._open_output_folder, state="disabled"
        )
        self.open_button.pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Clear log", command=self._clear_log).pack(side="right")

        log_frame = ttk.Frame(self, padding=(16, 8, 16, 4))
        log_frame.grid(row=6, column=0, sticky="nsew")
        log_frame.rowconfigure(1, weight=1)
        log_frame.columnconfigure(0, weight=1)
        ttk.Label(log_frame, text="Status").grid(row=0, column=0, sticky="w")
        self.log = tk.Text(log_frame, height=10, wrap="word", state="disabled", font=("Consolas", 9))
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=log_scroll.set)
        self.log.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        log_scroll.grid(row=1, column=1, sticky="ns", pady=(4, 0))

        status_bar = ttk.Label(self, textvariable=self.status, padding=(16, 6), relief="sunken")
        status_bar.grid(row=7, column=0, sticky="ew")
        self._refresh_output_hint()
        self._log("Choose one or more documents, then click Convert.")

    def _setup_drag_and_drop(self) -> None:
        try:
            from tkinterdnd2 import DND_FILES, TkinterDnD
        except ImportError:
            self._log("Drag-and-drop is unavailable. Use Browse files.")
            return
        try:
            TkinterDnD.require(self)
        except (tk.TclError, RuntimeError, OSError) as exc:
            self._log(f"Drag-and-drop is unavailable ({exc}). Use Browse files.")
            return

        targets = [self, self.drop_zone, *self.drop_zone.winfo_children()]
        for widget in targets:
            self._register_drop_target(widget, DND_FILES)
        self._log("Drop files onto the window, or use Browse files.")

    def _register_drop_target(self, widget: tk.Misc, dnd_files: str) -> None:
        def on_drop(event) -> str:
            self.add_paths(_split_drop_paths(self, getattr(event, "data", "")))
            return "copy"

        register = getattr(widget, "drop_target_register", None)
        bind = getattr(widget, "dnd_bind", None)
        if register is not None and bind is not None:
            register(dnd_files)
            bind("<<Drop>>", on_drop)
            bind("<<DropEnter>>", lambda _event: "copy")
            bind("<<DropPosition>>", lambda _event: "copy")
            return

        self.tk.call("tkdnd::drop_target", "register", widget._w, dnd_files)

        def _substitute(*args):
            event = tk.Event()
            event.widget = widget
            event.data = args[0] if args else ""
            on_drop(event)
            return "copy"

        widget.tk.call("bind", widget._w, "<<Drop>>", widget._register(_substitute))

    def _report_callback_exception(self, exc_type, exc, tb) -> None:
        details = "".join(traceback.format_exception(exc_type, exc, tb))
        self._log("Something went wrong in the window:\n" + details)

    def _log(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")

        def write() -> None:
            self.log.configure(state="normal")
            self.log.insert("end", f"{stamp}  {message.rstrip()}\n")
            self.log.see("end")
            self.log.configure(state="disabled")

        if threading.current_thread() is threading.main_thread():
            write()
        else:
            self.after(0, write)

    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _set_status(self, text: str) -> None:
        self.after(0, lambda: self.status.set(text))

    def _browse_files(self) -> None:
        selected = filedialog.askopenfilenames(
            title="Select documents to convert",
            filetypes=FILE_DIALOG_TYPES,
            initialdir=self._last_dir,
        )
        if selected:
            self.add_paths(list(selected))

    def add_paths(self, paths: list[str]) -> None:
        added = 0
        for raw in paths:
            path = Path(raw)
            if path.is_dir():
                self._log(f"Skipped folder {path}. Select files inside it.")
                continue
            if not path.is_file():
                self._log(f"Skipped missing file {path}.")
                continue
            resolved = path.resolve()
            if resolved in self._files:
                continue
            self._files.append(resolved)
            self.file_list.insert("end", str(resolved))
            self._last_dir = str(resolved.parent)
            added += 1
        if added:
            self._refresh_output_hint()
            self._set_status(f"{len(self._files)} file(s) selected")
            self.drop_zone.configure(bg="#dff3e6", highlightbackground="#2e7d4f")
            for child in self.drop_zone.winfo_children():
                if isinstance(child, tk.Label):
                    child.configure(bg="#dff3e6")
            self.after(400, self._reset_drop_zone)

    def _reset_drop_zone(self) -> None:
        self.drop_zone.configure(bg="#e7eef6", highlightbackground="#8aa4c0")
        for child in self.drop_zone.winfo_children():
            if isinstance(child, tk.Label):
                child.configure(bg="#e7eef6")

    def _remove_selected(self) -> None:
        selected = list(self.file_list.curselection())
        if not selected:
            return
        for index in reversed(selected):
            del self._files[index]
            self.file_list.delete(index)
        self._refresh_output_hint()
        self._set_status(f"{len(self._files)} file(s) selected")

    def _clear_files(self) -> None:
        self._files.clear()
        self.file_list.delete(0, "end")
        self._refresh_output_hint()
        self._set_status("Ready")

    def _refresh_output_hint(self) -> None:
        custom = not self.auto_output.get()
        state = "normal" if custom else "disabled"
        self.output_entry.configure(state=state)
        self.output_browse.configure(state=state)
        if not custom:
            if len(self._files) == 1:
                hint = f"Will write {default_output_path(self._files[0])}"
            elif len(self._files) > 1:
                hint = f"Will write a .md file beside each of the {len(self._files)} documents."
            else:
                hint = "Each Markdown file is written beside its source document."
        elif len(self._files) > 1:
            hint = "Choose a folder. Each document is saved there as a .md file."
        else:
            hint = "Choose the .md file to write."
        self.output_hint.configure(text=hint)

    def _browse_output(self) -> None:
        if len(self._files) > 1:
            folder = filedialog.askdirectory(
                title="Select the folder for Markdown files",
                initialdir=self._last_dir,
            )
            if folder:
                self.custom_output.set(folder)
                self.auto_output.set(False)
        else:
            initial_name = "document.md"
            initial_dir = self._last_dir
            if len(self._files) == 1:
                suggested = default_output_path(self._files[0])
                initial_name = suggested.name
                initial_dir = str(suggested.parent)
            chosen = filedialog.asksaveasfilename(
                title="Save Markdown as",
                defaultextension=".md",
                filetypes=[("Markdown", "*.md"), ("All files", "*.*")],
                initialdir=initial_dir,
                initialfile=initial_name,
            )
            if chosen:
                self.custom_output.set(chosen)
                self.auto_output.set(False)
        self._refresh_output_hint()

    def _destination_for(self, source: Path) -> Path:
        if self.auto_output.get():
            return default_output_path(source)
        raw = self.custom_output.get().strip()
        if not raw:
            raise ValueError("Choose an output file or folder, or keep automatic naming.")
        chosen = Path(raw)
        if len(self._files) <= 1:
            if chosen.exists() and chosen.is_dir():
                return chosen / default_output_path(source).name
            if chosen.suffix.lower() != ".md":
                chosen = chosen.with_name(chosen.name + ".md")
            return chosen
        if chosen.suffix.lower() == ".md":
            chosen = chosen.parent
        return chosen / default_output_path(source).name

    def _planned_jobs(self) -> list[tuple[Path, Path]]:
        jobs: list[tuple[Path, Path]] = []
        used: set[Path] = set()
        for source in self._files:
            destination = self._destination_for(source)
            try:
                key = destination.resolve()
            except OSError:
                key = destination
            suffix_n = 2
            while key in used:
                destination = destination.with_name(f"{destination.stem}-{suffix_n}{destination.suffix}")
                try:
                    key = destination.resolve()
                except OSError:
                    key = destination
                suffix_n += 1
            used.add(key)
            jobs.append((source, destination))
        return jobs

    def _start_convert(self) -> None:
        if self._converting:
            return
        if MarkItDown is None:
            messagebox.showerror(
                "MarkItDown is not installed",
                "Install the local package with its format extras, then start the app again:\n\n"
                'pip install "packages/markitdown[all]"',
            )
            return
        if not self._files:
            messagebox.showinfo("No documents selected", "Drop or browse for at least one file.")
            return
        try:
            jobs = self._planned_jobs()
        except ValueError as exc:
            messagebox.showerror("Output location", str(exc))
            return
        existing = [dest for _src, dest in jobs if dest.exists()]
        if existing:
            preview = "\n".join(str(path) for path in existing[:8])
            extra = "" if len(existing) <= 8 else f"\n…and {len(existing) - 8} more"
            replace = messagebox.askyesno(
                "Replace existing files?",
                "These Markdown files already exist and will be replaced:\n\n" + preview + extra,
            )
            if not replace:
                self._log("Conversion cancelled. Existing files were left unchanged.")
                return
        self._converting = True
        self.convert_button.configure(state="disabled", text="Converting...")
        self._set_status("Converting...")
        worker = threading.Thread(target=self._convert_jobs, args=(jobs,), daemon=True)
        worker.start()

    def _convert_jobs(self, jobs: list[tuple[Path, Path]]) -> None:
        ok = 0
        failed = 0
        try:
            self._log("Loading converters...")
            get_converter()
            for source, destination in jobs:
                self._set_status(f"Converting {source.name}")
                self._log(f"Converting {source.name}")
                try:
                    text, written = convert_file(source, destination)
                except Exception as exc:
                    failed += 1
                    self._log(f"Failed {source.name}: {exc}")
                    protected_excel = source.suffix.lower() in {".xlsx", ".xls"} and "not a zip file" in str(exc).lower()
                    if protected_excel:
                        self._log(
                            "This PC returned Excel bytes that are not a ZIP package. "
                            "Document-protection software can do that for unrecognized programs. "
                            "Allow MarkItDown.exe in that software, then convert again."
                        )
                    continue
                ok += 1
                self._last_output = written
                self._log(f"Wrote {written} ({len(text)} characters)")
                self._note_empty_result(source, text)
        finally:
            summary = f"Finished. {ok} succeeded, {failed} failed."
            self._log(summary)
            self._set_status(summary)
            self.after(0, self._finish_convert, ok)

    def _note_empty_result(self, source: Path, text: str) -> None:
        if text.strip():
            return
        suffix = source.suffix.lower()
        if suffix in IMAGE_EXTENSIONS:
            self._log(
                "Image Markdown is empty unless ExifTool is on PATH "
                "(metadata) or an LLM client is configured in code (a caption)."
            )
        elif suffix in AUDIO_EXTENSIONS:
            self._log(
                "Audio Markdown needs SpeechRecognition, and formats other than "
                "wav/aiff/flac also need ffmpeg on PATH."
            )
        else:
            self._log("The converter returned empty Markdown for this file.")

    def _finish_convert(self, ok: int) -> None:
        self._converting = False
        self.convert_button.configure(state="normal", text="Convert")
        if ok and self._last_output is not None:
            self.open_button.configure(state="normal")

    def _open_output_folder(self) -> None:
        if self._last_output is None:
            return
        folder = self._last_output.parent
        if sys.platform == "win32":
            os.startfile(folder)  # noqa: S606
        else:
            self._log(f"Output folder: {folder}")


def cli_convert(source: Path, destination: Path) -> int:
    """Convert one file without opening the window. Used to check a built executable."""
    try:
        convert_file(source, destination)
    except Exception:
        error_path = destination.with_name(destination.name + ".error.txt")
        error_path.parent.mkdir(parents=True, exist_ok=True)
        error_path.write_text(traceback.format_exc(), encoding="utf-8")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["--convert"]:
        if len(args) != 3:
            return 2
        return cli_convert(Path(args[1]), Path(args[2]))
    _enable_dpi_awareness()
    app = App()
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
