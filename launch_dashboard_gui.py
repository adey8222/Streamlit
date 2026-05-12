#!/usr/bin/env python3
"""Tiny GUI: starts Streamlit or Dash in the background and opens your browser (no Terminal)."""

from __future__ import annotations

import queue
import subprocess
import threading
import time
from pathlib import Path

import tkinter as tk
from tkinter import messagebox

BASE = Path(__file__).resolve().parent
VENV_PY = BASE / ".venv" / "bin" / "python"
LOG_DIR = BASE / "logs"


def curl_ok(url: str) -> bool:
    try:
        import urllib.request

        urllib.request.urlopen(url, timeout=1)
        return True
    except Exception:
        return False


def wait_browser(url: str, out_q: queue.Queue[str]) -> None:
    for _ in range(40):
        if curl_ok(url):
            subprocess.run(["open", url], check=False)
            out_q.put("")
            return
        time.sleep(0.5)
    subprocess.run(["open", url], check=False)
    out_q.put("The page opened; if it fails, logs are in ~/Library/Logs/ or dashboard/logs/")


def start_streamlit() -> None:
    if not VENV_PY.exists():
        messagebox.showerror(
            "Missing environment",
            f"Could not find a virtualenv Python at:\n{VENV_PY}\n\n"
            "One‑time setup in Terminal:\n"
            "  cd ~/Desktop/beverage_factory_dashboard\n"
            "  python3 -m venv .venv\n"
            "  .venv/bin/pip install -r requirements.txt",
        )
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logfile = LOG_DIR / "streamlit.log"
    f = logfile.open("a", encoding="utf-8")
    subprocess.Popen(
        [
            str(VENV_PY),
            "-m",
            "streamlit",
            "run",
            str(BASE / "app.py"),
            "--server.headless",
            "true",
            "--server.address",
            "127.0.0.1",
            "--server.port",
            "8501",
        ],
        cwd=str(BASE),
        stdin=subprocess.DEVNULL,
        stdout=f,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    url = "http://127.0.0.1:8501"
    if curl_ok(url):
        subprocess.run(["open", url], check=False)
        return
    q: queue.Queue[str] = queue.Queue()
    threading.Thread(target=wait_browser, args=(url, q), daemon=True).start()

    def poll() -> None:
        try:
            msg = q.get_nowait()
            if msg:
                messagebox.showinfo("Dashboard", msg)
        except queue.Empty:
            root.after(200, poll)

    root.after(300, poll)


def start_dash() -> None:
    if not VENV_PY.exists():
        messagebox.showerror("Missing environment", f"Missing venv at {VENV_PY}")
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logfile = LOG_DIR / "dash.log"
    f = logfile.open("a", encoding="utf-8")
    subprocess.Popen(
        [str(VENV_PY), str(BASE / "dash_app.py")],
        cwd=str(BASE),
        stdin=subprocess.DEVNULL,
        stdout=f,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    url = "http://127.0.0.1:8050"
    if curl_ok(url):
        subprocess.run(["open", url], check=False)
        return
    q: queue.Queue[str] = queue.Queue()
    threading.Thread(target=wait_browser, args=(url, q), daemon=True).start()

    def poll() -> None:
        try:
            msg = q.get_nowait()
            if msg:
                messagebox.showinfo("Dashboard", msg)
        except queue.Empty:
            root.after(200, poll)

    root.after(300, poll)


def main() -> None:
    global root
    root = tk.Tk()
    root.title("Employee dashboard")
    root.geometry("440x220")
    root.resizable(False, False)
    frm = tk.Frame(root, padx=20, pady=20)
    frm.pack(fill="both", expand=True)
    tk.Label(
        frm,
        text="Start the dashboard (no Terminal). Default browser opens\nwhen the server is ready.",
        justify="left",
    ).pack(anchor="w", pady=(0, 12))
    tk.Button(frm, text="Open Streamlit dashboard", width=28, command=start_streamlit).pack(
        pady=4
    )
    tk.Button(frm, text="Open Dash dashboard", width=28, command=start_dash).pack(pady=4)
    tk.Label(frm, text=f"Project: {BASE}", font=("System", 10), fg="#666").pack(
        anchor="w", pady=(12, 0)
    )
    root.mainloop()


if __name__ == "__main__":
    main()
