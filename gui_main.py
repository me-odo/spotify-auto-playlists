import threading
import sys
import tkinter as tk
from tkinter import messagebox, scrolledtext

from main import run_pipeline, PromptFn


def prompt_yes_no_gui(message: str, default_yes: bool = True) -> bool:
    """
    GUI implementation of yes/no prompt using Tkinter messagebox.
    The default_yes is only reflected in the wording; askyesno always
    returns True/False based on user click.
    """
    return messagebox.askyesno("Confirmation", message)


class TextRedirector:
    """
    Simple object to redirect sys.stdout / sys.stderr into a Tkinter Text widget.
    """

    def __init__(self, text_widget: tk.Text, tag: str = "stdout") -> None:
        self.text_widget = text_widget
        self.tag = tag

    def write(self, s: str) -> None:
        self.text_widget.insert(tk.END, s, (self.tag,))
        self.text_widget.see(tk.END)

    def flush(self) -> None:
        pass  # required for file-like interface, but nothing to do


def main() -> None:
    root = tk.Tk()
    root.title("Spotify Auto-Playlists")

    # Text area for logs
    text = scrolledtext.ScrolledText(root, wrap=tk.WORD, height=30, width=100)
    text.pack(fill=tk.BOTH, expand=True)

    # Redirect stdout / stderr to the text widget
    sys.stdout = TextRedirector(text, "stdout")
    sys.stderr = TextRedirector(text, "stderr")

    # Flag to let cli_utils know we're in GUI mode
    setattr(sys.stdout, "is_gui", True)

    def run_pipeline_in_thread():
        def _target():
            try:
                # In GUI, we prefer the automatic browser auth (no --cli-auth)
                run_pipeline(prompt_yes_no=prompt_yes_no_gui, use_cli_auth=False)
            except Exception as e:
                print(f"❌ Error: {e}")

        threading.Thread(target=_target, daemon=True).start()

    # Run button
    run_button = tk.Button(root, text="Run sync", command=run_pipeline_in_thread)
    run_button.pack(pady=5)

    root.mainloop()


if __name__ == "__main__":
    main()
