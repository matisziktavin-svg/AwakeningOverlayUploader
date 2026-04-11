import tkinter as tk
import queue


class StatusWindow:
    def __init__(self, root, status_queue, overlay_url):
        self._root = root
        self._queue = status_queue
        self._url = overlay_url
        self._status_var = tk.StringVar(value="Starting...")
        self._build_widgets()
        self._root.after(100, self._poll_queue)

    def _build_widgets(self):
        root = self._root
        root.title("Awakening Overlay Uploader")
        root.resizable(False, False)

        tk.Label(root, text="Status:").grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
        tk.Label(root, textvariable=self._status_var, width=38, anchor="w").grid(
            row=0, column=1, padx=(0, 12), pady=(12, 4)
        )

        tk.Label(root, text="OBS URL:").grid(row=1, column=0, sticky="w", padx=12, pady=4)
        tk.Label(root, text=self._url, fg="blue").grid(
            row=1, column=1, sticky="w", padx=(0, 12), pady=4
        )

        tk.Button(root, text="Copy URL", command=self._copy_url).grid(
            row=2, column=1, sticky="w", padx=(0, 12), pady=(4, 12)
        )

    def _copy_url(self):
        self._root.clipboard_clear()
        self._root.clipboard_append(self._url)

    def _poll_queue(self):
        try:
            while True:
                msg = self._queue.get_nowait()
                self._status_var.set(msg)
        except queue.Empty:
            pass
        try:
            self._root.after(100, self._poll_queue)
        except tk.TclError:
            pass  # window is being destroyed

    def run(self):
        self._root.mainloop()
