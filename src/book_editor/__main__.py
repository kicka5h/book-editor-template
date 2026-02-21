"""Entry point for the Book Editor desktop app (python -m book_editor or book-editor)."""

import flet as ft

from book_editor.app import main as app_main


def run_gui() -> None:
    """Run the Flet desktop application."""
    ft.app(target=app_main)


if __name__ == "__main__":
    run_gui()
