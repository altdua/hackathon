"""Tk desktop dashboard. All agent work runs outside the UI process."""

import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .core import (ROOT, RUNS, SETTINGS, STAGES, default_settings, is_available,
                   list_runs, load_settings, prepare_run, stage_info, write_json)

NAVY = "#142938"
TEAL = "#087f78"
BG = "#f2f5f7"
INK = "#18313f"
MUTED = "#596f7a"


class Dashboard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AI Risk Analysis | Agent Workspace")
        self.geometry("1240x850")
        self.minsize(980, 700)
        self.configure(bg=BG)
        self.stage = STAGES[0]["id"]
        self.process = None
        self.active_directory = None
        self.active_stage = None
        self.log_handle = None
        self.cancel_requested = False
        self.pipeline_queue = []
        self.viewed_run = None
        self.records = []
        self.artifact_paths = {}
        self.history_items = {}
        self.log_offset = 0
        self.poll_ticks = 0
        self.settings_warning = None
        try:
            self.settings = load_settings()
        except (OSError, ValueError) as exc:
            self.settings = default_settings()
            self.settings_warning = f"Saved settings could not be loaded: {exc}. Defaults are shown."
        self._style()
        self._layout()
        self.select_stage(self.stage, save=False)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(250, self.poll)
        if self.settings_warning:
            self.after(300, lambda: messagebox.showwarning("Settings", self.settings_warning))

    def _style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=INK, font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 24, "bold"))
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 8))
        style.configure("Primary.TButton", background=TEAL, foreground="white", borderwidth=0)
        style.map("Primary.TButton", background=[("active", "#09665f"), ("disabled", "#c1cecf")])
        style.configure("TEntry", padding=7)
        style.configure("TCombobox", padding=6)
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(16, 10), font=("Segoe UI", 10))
        style.map("TNotebook.Tab", background=[("selected", "white")], foreground=[("selected", TEAL)])
        style.configure("Treeview", rowheight=30, font=("Segoe UI", 10), background="white", fieldbackground="white", borderwidth=0)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), padding=8)
        style.map("Treeview", background=[("selected", "#d7efeb")], foreground=[("selected", INK)])
        style.configure("TLabelframe", background=BG)
        style.configure("TLabelframe.Label", font=("Segoe UI", 10, "bold"), background=BG, foreground=INK)

    def _layout(self):
        sidebar = tk.Frame(self, bg=NAVY, width=235)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        tk.Label(sidebar, text="QUANTEXA CHALLENGE", bg=NAVY, fg="#8cafb7", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=22, pady=(28, 8))
        tk.Label(sidebar, text="AI Risk\nAnalysis", justify="left", bg=NAVY, fg="white", font=("Segoe UI", 25, "bold")).pack(anchor="w", padx=20)
        tk.Label(sidebar, text="AGENT WORKSPACE", bg=NAVY, fg="#8cafb7", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=22, pady=(36, 14))
        self.stage_buttons = {}
        for stage in STAGES:
            button = tk.Button(sidebar, text="", anchor="w", justify="left", font=("Segoe UI", 11),
                               bg=NAVY, fg="white", activebackground="#244858", activeforeground="white",
                               relief="flat", bd=0, padx=15, pady=16, cursor="hand2",
                               command=lambda sid=stage["id"]: self.select_stage(sid))
            button.pack(fill="x", padx=10, pady=3)
            self.stage_buttons[stage["id"]] = button
        tk.Label(sidebar, text="Local workspace\nResults stay in this project.\nLLM mode sends notes to its API.",
                 bg=NAVY, fg="#a7bdc4", justify="left", font=("Segoe UI", 9), wraplength=194).pack(side="bottom", padx=20, pady=24, anchor="w")
        main = ttk.Frame(self, padding=(25, 23))
        main.pack(side="left", fill="both", expand=True)
        toolbar = ttk.Frame(main)
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="PIPELINE / ANALYSIS", style="Muted.TLabel").pack(side="left")
        self.pipeline_button = ttk.Button(toolbar, text="Run connected pipeline", command=self.run_pipeline)
        self.pipeline_button.pack(side="right")
        ttk.Button(toolbar, text="Refresh stages", command=self.refresh).pack(side="right", padx=8)
        self.heading = ttk.Label(main, style="Title.TLabel")
        self.heading.pack(anchor="w", pady=(22, 5))
        self.description = ttk.Label(main, style="Muted.TLabel", wraplength=730)
        self.description.pack(anchor="w")
        self.banner = tk.Label(main, text="", anchor="w", justify="left", bg="#e2efec", fg="#176b61", padx=14, pady=12, font=("Segoe UI", 10), wraplength=760)
        self.banner.pack(fill="x", pady=(18, 15))
        self.tabs = ttk.Notebook(main)
        self.tabs.pack(fill="both", expand=True)
        self.setup_tab = ttk.Frame(self.tabs, padding=18)
        self.result_tab = ttk.Frame(self.tabs, padding=14)
        self.log_tab = ttk.Frame(self.tabs, padding=14)
        self.history_tab = ttk.Frame(self.tabs, padding=14)
        for frame, title in ((self.setup_tab, "Setup"), (self.result_tab, "Results & evidence"), (self.log_tab, "Run log"), (self.history_tab, "Run history")):
            self.tabs.add(frame, text=title)
        self._setup_layout()
        self._results_layout()
        self.log_label = ttk.Label(self.log_tab, text="No run selected", style="Muted.TLabel")
        self.log_label.pack(anchor="w", pady=(0, 10))
        self.log_text = self.text_area(self.log_tab)
        self._history_layout()
        bottom = ttk.Frame(main)
        bottom.pack(fill="x", pady=(14, 0))
        self.progress = ttk.Progressbar(bottom, mode="indeterminate", length=140)
        self.progress.pack(side="left")
        self.status = ttk.Label(bottom, text="Ready", style="Muted.TLabel")
        self.status.pack(side="left", padx=12)
        self.cancel_button = ttk.Button(bottom, text="Stop run", command=self.cancel_run, state="disabled")
        self.cancel_button.pack(side="right")

    def _setup_layout(self):
        top = ttk.Frame(self.setup_tab)
        top.pack(fill="x")
        ttk.Label(top, text="Input data", font=("Segoe UI", 11, "bold")).pack(side="left")
        self.previous_button = ttk.Button(top, text="Use latest previous result", command=self.use_previous)
        self.previous_button.pack(side="right")
        input_row = ttk.Frame(self.setup_tab)
        input_row.pack(fill="x", pady=(8, 5))
        self.input_var = tk.StringVar()
        ttk.Entry(input_row, textvariable=self.input_var).pack(side="left", fill="x", expand=True)
        ttk.Button(input_row, text="Browse…", command=self.browse_input).pack(side="right", padx=(8, 0))
        self.input_hint = ttk.Label(self.setup_tab, style="Muted.TLabel", wraplength=750)
        self.input_hint.pack(anchor="w", pady=(0, 15))
        self.feature_frame = ttk.LabelFrame(self.setup_tab, text="Feature extraction settings", padding=14)
        self.date_var = tk.StringVar()
        self.extractor_var = tk.StringVar()
        self.model_var = tk.StringVar()
        for index, title in enumerate(("Cutoff date (YYYY-MM-DD)", "Text extractor", "Model ID (LLM mode only)")):
            ttk.Label(self.feature_frame, text=title).grid(row=index, column=0, sticky="w", padx=(0, 18), pady=7)
        ttk.Entry(self.feature_frame, textvariable=self.date_var).grid(row=0, column=1, sticky="ew")
        mode = ttk.Combobox(self.feature_frame, textvariable=self.extractor_var, values=("demo", "openai"), state="readonly")
        mode.grid(row=1, column=1, sticky="ew")
        mode.bind("<<ComboboxSelected>>", lambda _: self.update_mode())
        self.model_entry = ttk.Entry(self.feature_frame, textvariable=self.model_var)
        self.model_entry.grid(row=2, column=1, sticky="ew")
        self.feature_frame.columnconfigure(1, weight=1)
        self.mode_hint = ttk.Label(self.feature_frame, style="Muted.TLabel", wraplength=680)
        self.mode_hint.grid(row=3, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self.generic_frame = ttk.LabelFrame(self.setup_tab, text="Agent settings (JSON)", padding=12)
        self.config_text = tk.Text(self.generic_frame, height=7, font=("Consolas", 11), relief="flat", padx=10, pady=10)
        self.config_text.pack(fill="both", expand=True)
        self.connection_note = ttk.Label(self.setup_tab, wraplength=730, style="Muted.TLabel")
        self.connection_note.pack(anchor="w", pady=(14, 10), side="bottom")
        actions = ttk.Frame(self.setup_tab)
        actions.pack(fill="x", side="bottom", pady=(15, 0))
        self.run_button = ttk.Button(actions, text="Run this agent", style="Primary.TButton", command=self.run_selected)
        self.run_button.pack(side="left")
        ttk.Button(actions, text="Save settings", command=self.save_settings).pack(side="left", padx=8)
        self.example_button = ttk.Button(actions, text="Load synthetic example", command=self.load_example)
        self.example_button.pack(side="left")

    def _results_layout(self):
        self.result_summary = ttk.Label(self.result_tab, text="Run an agent to inspect its results.", wraplength=730)
        self.result_summary.pack(anchor="w", pady=(0, 10))
        row = ttk.Frame(self.result_tab)
        row.pack(fill="x")
        ttk.Label(row, text="Artifact").pack(side="left", padx=(0, 8))
        self.artifact_var = tk.StringVar()
        self.artifact_combo = ttk.Combobox(row, textvariable=self.artifact_var, state="readonly")
        self.artifact_combo.pack(side="left", fill="x", expand=True)
        self.artifact_combo.bind("<<ComboboxSelected>>", lambda _: self.show_artifact())
        ttk.Button(row, text="Export file…", command=self.export_artifact).pack(side="right", padx=(8, 0))
        search_row = ttk.Frame(self.result_tab)
        search_row.pack(fill="x", pady=9)
        ttk.Label(search_row, text="Find a record").pack(side="left", padx=(0, 8))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.render_records())
        ttk.Entry(search_row, textvariable=self.search_var).pack(side="left", fill="x", expand=True)
        self.count_label = ttk.Label(search_row, style="Muted.TLabel")
        self.count_label.pack(side="right", padx=(10, 0))
        panes = ttk.Panedwindow(self.result_tab, orient="vertical")
        panes.pack(fill="both", expand=True)
        table_frame = ttk.Frame(panes)
        self.table = ttk.Treeview(table_frame, show="headings", selectmode="browse", height=7)
        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        xscroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.table.xview)
        self.table.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.table.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.table.bind("<<TreeviewSelect>>", self.show_record)
        detail_frame = ttk.Frame(panes)
        ttk.Label(detail_frame, text="Selected record · full values and source evidence", style="Muted.TLabel").pack(anchor="w", pady=(8, 6))
        self.detail = self.text_area(detail_frame)
        panes.add(table_frame, weight=1)
        panes.add(detail_frame, weight=1)

    def _history_layout(self):
        ttk.Label(self.history_tab, text="Select a saved run to inspect its configuration, results and log.", style="Muted.TLabel").pack(anchor="w", pady=(0, 10))
        frame = ttk.Frame(self.history_tab)
        frame.pack(fill="both", expand=True)
        columns = ("created", "stage", "status")
        self.history = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
        for name, title, width in (("created", "Started (local time)", 180), ("stage", "Agent", 190), ("status", "Status", 100)):
            self.history.heading(name, text=title)
            self.history.column(name, width=width)
        self.history.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.history.yview)
        scroll.pack(side="right", fill="y")
        self.history.configure(yscrollcommand=scroll.set)
        self.history.bind("<<TreeviewSelect>>", self.inspect_history)
        self.history_detail = ttk.Label(self.history_tab, text="", wraplength=720, style="Muted.TLabel")
        self.history_detail.pack(anchor="w", pady=10)
        ttk.Button(self.history_tab, text="View selected run results", command=self.view_history_result).pack(anchor="w")

    @staticmethod
    def text_area(parent):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        text = tk.Text(frame, wrap="word", font=("Consolas", 10), relief="flat", bg="white", fg=INK, padx=12, pady=10, state="disabled", height=6)
        text.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        scroll.pack(side="right", fill="y")
        text.configure(yscrollcommand=scroll.set)
        return text

    @staticmethod
    def set_text(widget, value):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def capture_settings(self):
        if self.stage == "feature_engineering":
            config = {"as_of": self.date_var.get().strip(), "extractor": self.extractor_var.get(), "model": self.model_var.get().strip()}
        else:
            config = json.loads(self.config_text.get("1.0", "end"))
            if not isinstance(config, dict):
                raise ValueError("Agent settings must be a JSON object")
        self.settings[self.stage] = {"input": self.input_var.get().strip(), "config": config}

    def select_stage(self, stage_id, save=True):
        if save:
            try:
                self.capture_settings()
            except ValueError as exc:
                messagebox.showerror("Invalid settings", str(exc))
                return
        self.stage = stage_id
        stage = stage_info(stage_id)
        self.heading.configure(text=stage["title"])
        self.description.configure(text=stage["description"])
        entry = self.settings[stage_id]
        self.input_var.set(entry["input"])
        self.feature_frame.pack_forget()
        self.generic_frame.pack_forget()
        if stage_id == "feature_engineering":
            config = entry["config"]
            self.date_var.set(config.get("as_of", ""))
            self.extractor_var.set(config.get("extractor", "demo"))
            self.model_var.set(config.get("model", ""))
            self.feature_frame.pack(fill="x", after=self.input_hint)
            self.update_mode()
            self.input_hint.configure(text="JSON citizen records with housing, appointments and notes.")
        else:
            self.config_text.delete("1.0", "end")
            self.config_text.insert("1.0", json.dumps(entry["config"], indent=2))
            self.generic_frame.pack(fill="both", expand=True, after=self.input_hint)
            self.input_hint.configure(text="Choose a previous agent's output, or select a compatible input file.")
        self.example_button.configure(state="normal" if stage_id == "feature_engineering" else "disabled")
        self.previous_button.configure(state="disabled" if stage_id == "feature_engineering" else "normal")
        self.connection_note.configure(text="Each run saves its input snapshot, settings, logs and output in a separate run folder." if is_available(stage_id) else f"To connect this stage, implement run() in {stage_id}/agent.py, then refresh stages. The folder README explains the interface.")
        self.refresh()
        candidates = [r for r in list_runs() if r.get("stage") == stage_id]
        if candidates:
            self.load_run(candidates[0])
        else:
            self.viewed_run = None
            self.artifact_paths = {}
            self.artifact_combo.configure(values=[])
            self.artifact_var.set("")
            self.records = []
            self.render_records()
            self.result_summary.configure(text="No runs yet. Configure this agent and run it to see results.")
            self.set_text(self.detail, "No result selected.")
            self.set_text(self.log_text, "No run log yet.")
            self.log_label.configure(text="No run selected")

    def update_mode(self):
        online = self.extractor_var.get() == "openai"
        self.model_entry.configure(state="normal" if online else "disabled")
        available = bool(os.environ.get("OPENAI_API_KEY"))
        self.mode_hint.configure(text=("LLM mode sends eligible note text to OpenAI. API key: " + ("available in environment." if available else "not set; set OPENAI_API_KEY before launching.") + " Choose a model that supports structured outputs.") if online else "Offline demo recognises only the synthetic example markers. Use LLM mode for ordinary case notes.")

    def refresh(self):
        for stage in STAGES:
            sid = stage["id"]
            state = "Running" if self.process and sid == self.active_stage else "Connected" if is_available(sid) else "Pending"
            self.stage_buttons[sid].configure(text=f"{stage['number']}   {stage['title']}\n       {state}", bg="#24505c" if sid == self.stage else NAVY)
        busy = self.process is not None
        self.run_button.configure(state="normal" if is_available(self.stage) and not busy else "disabled")
        self.pipeline_button.configure(state="disabled" if busy else "normal")
        self.cancel_button.configure(state="normal" if busy else "disabled")
        if busy:
            self.banner.configure(text=f"Running {stage_info(self.active_stage)['title']}. You can inspect saved results while it works.")
        elif is_available(self.stage):
            self.banner.configure(text="Connected · Ready to run with the settings below.")
        else:
            self.banner.configure(text="Pending implementation · Settings can be prepared now. No simulated results are generated.")
        self.refresh_history()

    def save_settings(self):
        try:
            self.capture_settings()
            write_json(SETTINGS, self.settings)
            self.status.configure(text="Settings saved")
        except (OSError, ValueError) as exc:
            messagebox.showerror("Cannot save settings", str(exc))

    def browse_input(self):
        path = filedialog.askopenfilename(title="Choose agent input", filetypes=[("Data files", "*.json *.csv"), ("All files", "*.*")])
        if path:
            self.input_var.set(path)

    def load_example(self):
        self.input_var.set(str(ROOT / "feature_engineering/examples/citizens.json"))
        self.date_var.set("2026-09-10")
        self.extractor_var.set("demo")
        self.update_mode()

    def use_previous(self):
        index = [s["id"] for s in STAGES].index(self.stage)
        if index == 0:
            return
        previous = STAGES[index - 1]["id"]
        run = next((r for r in list_runs() if r.get("stage") == previous and r.get("status") == "completed" and Path(r.get("primary_artifact") or "").is_file()), None)
        if run:
            self.input_var.set(run["primary_artifact"])
            self.status.configure(text="Previous result selected")
        else:
            messagebox.showinfo("No previous result", f"Complete a {stage_info(previous)['title']} run first.")

    def validate_setup(self):
        self.capture_settings()
        config = self.settings["feature_engineering"]["config"]
        if self.stage == "feature_engineering" or self.pipeline_queue:
            from feature_engineering.pipeline import parse_date
            parse_date(config["as_of"])
            if config["extractor"] == "openai" and (not config.get("model") or not os.environ.get("OPENAI_API_KEY")):
                raise ValueError("LLM mode requires a model ID and OPENAI_API_KEY in the launch environment")
        write_json(SETTINGS, self.settings)

    def run_selected(self):
        if self.process:
            return
        try:
            self.validate_setup()
            self.start_run(self.stage, self.settings[self.stage]["input"])
        except (OSError, ValueError, KeyError) as exc:
            messagebox.showerror("Cannot start run", str(exc))

    def run_pipeline(self):
        if self.process:
            return
        self.pipeline_queue = []
        for stage in STAGES:
            if not is_available(stage["id"]):
                break
            self.pipeline_queue.append(stage["id"])
        try:
            if not self.pipeline_queue:
                raise ValueError("Connect Feature Engineering first")
            self.validate_setup()
            first = self.pipeline_queue.pop(0)
            self.start_run(first, self.settings[first]["input"])
        except (OSError, ValueError, KeyError) as exc:
            self.pipeline_queue = []
            messagebox.showerror("Cannot start pipeline", str(exc))

    def start_run(self, stage, input_path, parent=None):
        directory = prepare_run(stage, input_path, self.settings[stage]["config"], parent)
        self.active_directory = directory
        self.active_stage = stage
        self.cancel_requested = False
        self.log_handle = (directory / "run.log").open("w", encoding="utf-8")
        try:
            self.process = subprocess.Popen([sys.executable, "-u", "-m", "dashboard.worker", str(directory)],
                                            cwd=ROOT, stdout=self.log_handle, stderr=subprocess.STDOUT,
                                            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError:
            self.log_handle.close()
            self.log_handle = None
            state = json.loads((directory / "status.json").read_text())
            state.update(status="failed", error="Worker could not start")
            write_json(directory / "status.json", state)
            raise
        self.select_stage(stage)
        self.tabs.select(self.log_tab)
        self.progress.start(12)
        self.status.configure(text=f"Running {stage_info(stage)['title']}")
        self.refresh()

    def poll(self):
        try:
            if self.process:
                if self.viewed_run and Path(self.viewed_run["directory"]) == self.active_directory:
                    self.read_log(self.active_directory)
                code = self.process.poll()
                if code is not None:
                    self.finish_run(code)
        finally:
            self.after(250, self.poll)

    def finish_run(self, code):
        self.log_handle.close()
        self.log_handle = None
        state_path = self.active_directory / "status.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if self.cancel_requested and state.get("status") != "completed":
            state.update(status="cancelled", error="Stopped by user")
        elif state.get("status") in ("queued", "running"):
            state.update(status="failed", error=f"Worker exited unexpectedly (code {code})")
        state.setdefault("finished_at", datetime.now(timezone.utc).isoformat())
        write_json(state_path, state)
        state["directory"] = str(self.active_directory)
        self.process = None
        self.progress.stop()
        self.status.configure(text=f"{stage_info(state['stage'])['title']}: {state['status']}")
        if self.stage == state["stage"]:
            self.load_run(state)
            self.tabs.select(self.result_tab if state["status"] == "completed" else self.log_tab)
        self.refresh()
        if state["status"] == "completed" and self.pipeline_queue and not self.cancel_requested:
            next_stage = self.pipeline_queue.pop(0)
            try:
                self.start_run(next_stage, state["primary_artifact"], state["id"])
            except (OSError, ValueError) as exc:
                self.pipeline_queue = []
                messagebox.showerror("Pipeline stopped", str(exc))
        else:
            self.pipeline_queue = []

    def cancel_run(self):
        if self.process:
            self.pipeline_queue = []
            self.cancel_requested = True
            self.process.terminate()
            self.status.configure(text="Stopping run…")

    def refresh_history(self):
        selected = self.history.selection()
        self.history.delete(*self.history.get_children())
        self.history_items = {}
        for run in list_runs():
            run_id = run.get("id")
            if not run_id or run.get("stage") not in [s["id"] for s in STAGES]:
                continue
            started = datetime.fromisoformat(run["created_at"]).astimezone().strftime("%d %b %Y  %H:%M:%S")
            status = run.get("status", "unknown")
            if status in ("running", "queued") and (not self.process or Path(run["directory"]) != self.active_directory):
                status = "Interrupted / unknown"
            self.history.insert("", "end", iid=run_id, values=(started, stage_info(run["stage"])["title"], status))
            self.history_items[run_id] = run
        if selected and selected[0] in self.history_items:
            self.history.selection_set(selected[0])

    def inspect_history(self, _event=None):
        selected = self.history.selection()
        if selected:
            run = self.history_items[selected[0]]
            self.history_detail.configure(text=f"Run: {run['id']}\nInput: {run['input']}\nSettings: {json.dumps(run['config'])}")

    def view_history_result(self):
        selected = self.history.selection()
        if selected:
            run = self.history_items[selected[0]]
            self.select_stage(run["stage"])
            if self.stage == run["stage"]:
                self.load_run(run)
                self.tabs.select(self.result_tab)

    def load_run(self, run):
        self.viewed_run = run
        directory = Path(run["directory"])
        self.log_offset = 0
        self.set_text(self.log_text, "")
        self.log_label.configure(text=f"{stage_info(run['stage'])['title']} · {run['id']}")
        self.read_log(directory)
        self.artifact_paths = {}
        output = directory / "output"
        if output.exists() and run.get("status") == "completed":
            for path in sorted(output.rglob("*")):
                if path.is_file() and path.resolve().is_relative_to(output.resolve()):
                    self.artifact_paths[str(path.relative_to(output))] = path
        names = list(self.artifact_paths)
        primary = Path(run.get("primary_artifact") or "")
        chosen = next((name for name, path in self.artifact_paths.items() if path.resolve() == primary.resolve()), names[0] if names else "")
        self.artifact_combo.configure(values=names)
        self.artifact_var.set(chosen)
        self.search_var.set("")
        self.show_artifact()
        self.result_summary.configure(text=f"{run['status'].capitalize()} · Run {run['id']}" + (f" · {run['error']}" if run.get("error") else ""))

    def read_log(self, directory):
        path = directory / "run.log"
        if path.exists():
            with path.open("r", encoding="utf-8", errors="replace") as stream:
                stream.seek(self.log_offset)
                chunk = stream.read()
                self.log_offset = stream.tell()
            if chunk:
                self.log_text.configure(state="normal")
                self.log_text.insert("end", chunk)
                self.log_text.see("end")
                self.log_text.configure(state="disabled")

    def show_artifact(self):
        self.records = []
        path = self.artifact_paths.get(self.artifact_var.get())
        try:
            if not path:
                self.set_text(self.detail, "No completed output for this run. Check the run log for progress or errors.")
            elif path.stat().st_size > 20 * 1024 * 1024:
                self.set_text(self.detail, "This file exceeds the 20 MB preview limit. Use Export file to inspect it externally.")
            elif path.suffix.lower() == ".json":
                value = json.loads(path.read_text(encoding="utf-8-sig"))
                if isinstance(value, list):
                    self.records = [v if isinstance(v, dict) else {"value": v} for v in value]
                else:
                    self.records = [value if isinstance(value, dict) else {"value": value}]
                self.set_text(self.detail, "Select a record to view its full values and evidence.")
            elif path.suffix.lower() == ".csv":
                with path.open(encoding="utf-8-sig", newline="") as stream:
                    self.records = list(csv.DictReader(stream))
                self.set_text(self.detail, "Select a row to inspect all values.")
            elif path.suffix.lower() in (".txt", ".md", ".log"):
                self.set_text(self.detail, path.read_text(encoding="utf-8", errors="replace"))
            else:
                self.set_text(self.detail, "Preview is available for JSON, CSV and text files. Export this file to open it with another application.")
        except (OSError, ValueError, csv.Error) as exc:
            self.set_text(self.detail, f"Cannot preview file: {exc}")
        self.render_records()

    @staticmethod
    def flat_record(record):
        if isinstance(record.get("features"), dict):
            return {"citizen_id": record.get("citizen_id"), "as_of": record.get("as_of"), **record["features"]}
        return record

    def render_records(self):
        self.table.delete(*self.table.get_children())
        query = self.search_var.get().casefold()
        matching = [(i, r) for i, r in enumerate(self.records) if not query or query in json.dumps(r, ensure_ascii=False).casefold()]
        columns = []
        for _, record in matching[:500]:
            for key in self.flat_record(record):
                if key not in columns:
                    columns.append(key)
        self.table.configure(columns=columns)
        for key in columns:
            self.table.heading(key, text=key.replace("_", " ").capitalize())
            self.table.column(key, width=180, minwidth=120, stretch=False)
        for index, record in matching[:500]:
            flat = self.flat_record(record)
            values = []
            for key in columns:
                value = flat.get(key)
                display = "Unknown" if value is None else json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
                values.append(display[:160])
            self.table.insert("", "end", iid=str(index), values=values)
        self.count_label.configure(text=f"{min(len(matching), 500)} / {len(matching)} matching")
        if matching:
            self.table.selection_set(str(matching[0][0]))
            self.show_record()
        elif self.records:
            self.set_text(self.detail, "No records match this search.")

    def show_record(self, _event=None):
        selected = self.table.selection()
        if selected:
            self.set_text(self.detail, json.dumps(self.records[int(selected[0])], indent=2, ensure_ascii=False))

    def export_artifact(self):
        source = self.artifact_paths.get(self.artifact_var.get())
        if not source:
            messagebox.showinfo("No artifact", "Choose a completed run and an output file first.")
            return
        target = filedialog.asksaveasfilename(initialfile=source.name, defaultextension=source.suffix, title="Export output file")
        if target:
            import shutil
            try:
                if source.resolve() != Path(target).resolve():
                    shutil.copyfile(source, target)
                self.status.configure(text="File exported")
            except OSError as exc:
                messagebox.showerror("Export failed", str(exc))

    def close(self):
        if self.process:
            if not messagebox.askyesno("Run in progress", "Stop the current run and close the workspace?"):
                return
            self.cancel_run()
            self.process.wait(timeout=5)
            self.finish_run(self.process.returncode)
        self.destroy()


def main():
    Dashboard().mainloop()
