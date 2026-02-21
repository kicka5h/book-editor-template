"""Flet UI for the Book Editor desktop app."""

import re
import sys
import threading
import traceback
from pathlib import Path

import flet as ft
from git.repo.base import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

from book_editor.config import (
    load_config,
    save_config_full,
    save_github_connection,
    save_repo_selection,
    is_github_connected,
    has_repo_selected,
    get_repo_path,
    config_dir,
)
from book_editor.services import (
    ChapterVersionManager,
    create_new_chapter,
    increment_chapters,
    find_latest_versions,
    count_words_in_chapters,
    process_file,
    git_push,
    list_chapters_with_versions,
    validate_token,
    list_user_repos,
    create_repo,
    clone_repo,
    ensure_chapters_structure,
    start_device_flow,
    poll_device_flow,
    build_pdf,
    check_pandoc_available,
)
from book_editor.utils import chapters_dir


# ── Anthropic brand palette ──────────────────────────────────────────────────
_BG = "#1A1A1A"          # near-black background
_SURFACE = "#242424"     # card / sidebar surface
_SURFACE2 = "#2C2C2C"   # slightly lighter surface (toolbar, inputs)
_ACCENT = "#DA7756"      # Anthropic coral
_ACCENT_HOVER = "#C4674A"
_TEXT = "#F5F0EB"        # warm off-white primary text
_TEXT_MUTED = "#A09890"  # muted / secondary text
_BORDER = "#383838"      # subtle border
_ERROR = "#E05C5C"       # error red
_SUCCESS = "#6BBF8E"     # success green (snackbar positive)


def _log(label: str, ex: BaseException) -> None:
    """Print a labelled exception + full traceback to stderr."""
    print(f"\n[Book Editor] {label}: {ex}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    print(file=sys.stderr)


# ── Reusable styled widget factories ────────────────────────────────────────

def _heading(text: str, size: int = 22) -> ft.Text:
    return ft.Text(text, size=size, weight=ft.FontWeight.BOLD, color=_TEXT)


def _body(text: str, color: str = _TEXT_MUTED) -> ft.Text:
    return ft.Text(text, size=13, color=color)


def _divider() -> ft.Divider:
    return ft.Divider(height=1, color=_BORDER)


def _primary_btn(label: str, on_click=None, disabled: bool = False) -> ft.ElevatedButton:
    return ft.ElevatedButton(
        label,
        on_click=on_click,
        disabled=disabled,
        style=ft.ButtonStyle(
            bgcolor={
                ft.ControlState.DEFAULT: _ACCENT,
                ft.ControlState.HOVERED: _ACCENT_HOVER,
                ft.ControlState.DISABLED: _SURFACE2,
            },
            color={
                ft.ControlState.DEFAULT: _TEXT,
                ft.ControlState.DISABLED: _TEXT_MUTED,
            },
            shape=ft.RoundedRectangleBorder(radius=6),
            elevation=0,
            padding=ft.padding.symmetric(horizontal=16, vertical=10),
        ),
    )


def _secondary_btn(label: str, on_click=None, icon=None) -> ft.OutlinedButton:
    return ft.OutlinedButton(
        label,
        on_click=on_click,
        icon=icon,
        style=ft.ButtonStyle(
            color={ft.ControlState.DEFAULT: _TEXT_MUTED, ft.ControlState.HOVERED: _TEXT},
            side={ft.ControlState.DEFAULT: ft.BorderSide(1, _BORDER), ft.ControlState.HOVERED: ft.BorderSide(1, _ACCENT)},
            shape=ft.RoundedRectangleBorder(radius=6),
            elevation=0,
            padding=ft.padding.symmetric(horizontal=16, vertical=10),
        ),
    )


def _ghost_btn(label: str, on_click=None, icon=None, color: str = _TEXT_MUTED) -> ft.TextButton:
    return ft.TextButton(
        label,
        on_click=on_click,
        icon=icon,
        style=ft.ButtonStyle(
            color={ft.ControlState.DEFAULT: color, ft.ControlState.HOVERED: _TEXT},
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
        ),
    )


def _toolbar_btn(label: str, on_click=None) -> ft.TextButton:
    """Compact toolbar button."""
    return ft.TextButton(
        label,
        on_click=on_click,
        style=ft.ButtonStyle(
            color={ft.ControlState.DEFAULT: _TEXT_MUTED, ft.ControlState.HOVERED: _TEXT},
            bgcolor={ft.ControlState.HOVERED: _SURFACE2},
            shape=ft.RoundedRectangleBorder(radius=4),
            padding=ft.padding.symmetric(horizontal=10, vertical=6),
        ),
    )


def _styled_field(label: str, width=None, multiline: bool = False,
                  min_lines: int = 1, expand: bool = False,
                  on_change=None, keyboard_type=None) -> ft.TextField:
    return ft.TextField(
        label=label,
        label_style=ft.TextStyle(color=_TEXT_MUTED, size=12),
        width=width,
        multiline=multiline,
        min_lines=min_lines,
        expand=expand,
        on_change=on_change,
        keyboard_type=keyboard_type,
        text_style=ft.TextStyle(color=_TEXT, size=13),
        border_color=_BORDER,
        focused_border_color=_ACCENT,
        cursor_color=_ACCENT,
        bgcolor=_SURFACE2,
        border_radius=6,
        content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
    )


def _code_field(label: str, multiline: bool = False, min_lines: int = 1,
                expand: bool = False, on_change=None) -> ft.TextField:
    """Monospace variant for the markdown editor."""
    return ft.TextField(
        label=label,
        label_style=ft.TextStyle(color=_TEXT_MUTED, size=12),
        multiline=multiline,
        min_lines=min_lines,
        expand=expand,
        on_change=on_change,
        text_style=ft.TextStyle(color=_TEXT, font_family="monospace", size=13),
        border_color=_BORDER,
        focused_border_color=_ACCENT,
        cursor_color=_ACCENT,
        bgcolor=_SURFACE,
        border_radius=6,
        content_padding=ft.padding.symmetric(horizontal=12, vertical=12),
    )


def _card(content: ft.Control, padding: int = 20) -> ft.Container:
    return ft.Container(
        content,
        bgcolor=_SURFACE,
        border_radius=10,
        padding=padding,
        border=ft.border.all(1, _BORDER),
    )


def _accent_badge(text: str) -> ft.Container:
    """Small pill badge with accent colour."""
    return ft.Container(
        ft.Text(text, size=11, color=_TEXT, weight=ft.FontWeight.W_600),
        bgcolor=_ACCENT,
        border_radius=100,
        padding=ft.padding.symmetric(horizontal=10, vertical=4),
    )


# ── App theme ────────────────────────────────────────────────────────────────

def _build_theme() -> ft.Theme:
    return ft.Theme(
        color_scheme_seed=_ACCENT,
        color_scheme=ft.ColorScheme(
            primary=_ACCENT,
            on_primary=_TEXT,
            background=_BG,
            surface=_SURFACE,
            on_surface=_TEXT,
            secondary=_ACCENT,
        ),
        visual_density=ft.VisualDensity.COMPACT,
    )


# ── Main app ─────────────────────────────────────────────────────────────────

def main(page: ft.Page) -> None:
    page.title = "Book Editor"
    page.window.min_width = 960
    page.window.min_height = 620
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = _BG
    page.theme = _build_theme()
    page.padding = 0

    config = load_config()
    token_holder = {"value": (config.get("github_token") or "").strip()}
    current_md_path = {"value": None}
    editor_dirty = {"value": False}

    # ── Sign-in view (GitHub Device Flow) ───────────────────────────────────
    signin_user_code = ft.Text(
        "", size=34, weight=ft.FontWeight.BOLD, selectable=True,
        color=_ACCENT, font_family="monospace",
    )
    signin_instruction = ft.Text("", size=13, color=_TEXT_MUTED)
    signin_error = ft.Text("", color=_ERROR, size=13)
    signin_progress = ft.ProgressRing(visible=False, color=_ACCENT, stroke_width=2, width=20, height=20)
    signin_button = _primary_btn("Sign in with GitHub", disabled=False)

    def _do_device_flow():
        """Runs entirely on a background thread."""
        signin_button.disabled = True
        signin_error.value = ""
        signin_instruction.value = "Contacting GitHub…"
        signin_user_code.value = ""
        signin_progress.visible = True
        page.update()
        try:
            flow = start_device_flow()
        except Exception as ex:
            _log("Device flow start failed", ex)
            signin_error.value = str(ex)
            signin_instruction.value = ""
            signin_progress.visible = False
            signin_button.disabled = False
            page.update()
            return

        code = flow["user_code"]
        uri = flow["verification_uri"]
        signin_user_code.value = code
        signin_instruction.value = (
            f"Go to  {uri}  and enter the code above.\n"
            "Waiting for you to authorise…"
        )
        page.update()

        import webbrowser
        webbrowser.open(uri)

        def _on_waiting():
            page.update()

        try:
            token = poll_device_flow(
                device_code=flow["device_code"],
                interval=flow.get("interval", 5),
                expires_in=flow.get("expires_in", 900),
                on_waiting=_on_waiting,
            )
        except Exception as ex:
            _log("Device flow poll failed", ex)
            signin_error.value = str(ex)
            signin_instruction.value = ""
            signin_user_code.value = ""
            signin_progress.visible = False
            signin_button.disabled = False
            page.update()
            return

        user = validate_token(token)
        if not user:
            signin_error.value = "Token received but could not verify with GitHub."
            signin_progress.visible = False
            signin_button.disabled = False
            page.update()
            return

        save_github_connection(token, user)
        token_holder["value"] = token
        signin_progress.visible = False
        signin_user_code.value = ""
        signin_instruction.value = ""
        page.update()
        page.go("/repo")

    def on_signin(e):
        threading.Thread(target=_do_device_flow, daemon=True).start()

    signin_button.on_click = on_signin

    signin_content = ft.Column(
        [
            ft.Container(height=40),
            ft.Row(
                [
                    ft.Container(
                        ft.Column(
                            [
                                # Logo-ish mark
                                ft.Container(
                                    ft.Text("✦", size=28, color=_ACCENT),
                                    margin=ft.margin.only(bottom=16),
                                ),
                                _heading("Book Editor", size=26),
                                ft.Container(height=6),
                                _body("Connect your GitHub account to store\nyour book in a private repository."),
                                ft.Container(height=32),
                                signin_button,
                                ft.Container(height=20),
                                # Code display card (hidden until flow starts)
                                ft.Container(
                                    ft.Column([
                                        _body("Your device code", _TEXT_MUTED),
                                        ft.Container(height=6),
                                        signin_user_code,
                                        ft.Container(height=4),
                                        signin_instruction,
                                    ]),
                                    visible=True,
                                ),
                                ft.Container(height=8),
                                ft.Row([signin_progress, signin_error], spacing=8),
                            ],
                            spacing=0,
                        ),
                        width=400,
                        padding=40,
                        bgcolor=_SURFACE,
                        border_radius=12,
                        border=ft.border.all(1, _BORDER),
                    )
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    # ── Repo selection view ──────────────────────────────────────────────────
    repos_dropdown = ft.Dropdown(
        label="Repository",
        width=420,
        options=[],
        border_color=_BORDER,
        focused_border_color=_ACCENT,
        bgcolor=_SURFACE2,
        border_radius=6,
        label_style=ft.TextStyle(color=_TEXT_MUTED, size=12),
        text_style=ft.TextStyle(color=_TEXT, size=13),
    )
    repo_progress = ft.ProgressRing(visible=False, color=_ACCENT, stroke_width=2, width=20, height=20)
    repo_error = ft.Text("", color=_ERROR, size=13)
    create_repo_name_field = _styled_field("Repository name", width=320)
    create_private_check = ft.Checkbox(
        label="Private repository",
        value=True,
        active_color=_ACCENT,
        label_style=ft.TextStyle(color=_TEXT_MUTED, size=13),
    )

    def load_repos():
        token = token_holder.get("value") or load_config().get("github_token") or ""
        if not token:
            return []
        return list_user_repos(token)

    def on_repo_view_visible():
        repo_progress.visible = True
        repo_error.value = ""
        repos_dropdown.options = []
        page.update()

        def _load():
            try:
                repos = load_repos()
                repo_progress.visible = False
                repos_dropdown.options = [
                    ft.dropdown.Option(key=f"{owner}|{name}|{url}", text=f"{owner}/{name}")
                    for owner, name, url in repos
                ]
                if not repos_dropdown.options:
                    repo_error.value = "No repositories found."
            except Exception as ex:
                _log("Failed to load repositories", ex)
                repo_progress.visible = False
                repo_error.value = f"Failed to load repositories: {ex}"
            page.update()

        threading.Thread(target=_load, daemon=True).start()

    def on_select_repo(e):
        key = repos_dropdown.value
        if not key:
            repo_error.value = "Select a repository first."
            page.update()
            return
        parts = key.split("|", 2)
        if len(parts) != 3:
            repo_error.value = "Invalid selection."
            page.update()
            return
        owner, name, url = parts
        token = token_holder.get("value") or load_config().get("github_token") or ""
        local_base = config_dir() / "repos"
        local_base.mkdir(parents=True, exist_ok=True)
        local_path = local_base / f"{owner}_{name}"
        repo_error.value = "Cloning…"
        page.update()
        try:
            if local_path.exists():
                repo_error.value = "Repository folder already exists. Using it."
                page.update()
            else:
                clone_repo(url, local_path, token)
            ensure_chapters_structure(local_path)
            save_repo_selection(owner, name, url, str(local_path))
            page.go("/editor")
        except Exception as ex:
            repo_error.value = str(ex)
        page.update()

    def open_create_repo_dialog(e):
        create_repo_name_field.value = ""
        create_private_check.value = True

        def do_create(e2):
            name = (create_repo_name_field.value or "").strip()
            if not name:
                page.open(ft.SnackBar(ft.Text("Enter a repository name.")))
                page.update()
                return
            if not re.match(r"^[a-zA-Z0-9_.-]+$", name):
                page.open(ft.SnackBar(ft.Text("Use only letters, numbers, - and _.")))
                page.update()
                return
            token = token_holder.get("value") or load_config().get("github_token") or ""
            try:
                owner, repo_name, url = create_repo(
                    token, name, private=create_private_check.value, description="Book content"
                )
                local_base = config_dir() / "repos"
                local_base.mkdir(parents=True, exist_ok=True)
                local_path = local_base / f"{owner}_{repo_name}"
                clone_repo(url, local_path, token)
                ensure_chapters_structure(local_path)
                save_repo_selection(owner, repo_name, url, str(local_path))
                page.close(dlg)
                page.update()
                page.go("/editor")
            except Exception as ex:
                page.open(ft.SnackBar(ft.Text(str(ex))))
                page.update()

        dlg = ft.AlertDialog(
            bgcolor=_SURFACE,
            title=_heading("Create new repository", size=18),
            content=ft.Container(
                ft.Column(
                    [create_repo_name_field, ft.Container(height=8), create_private_check],
                    tight=True,
                ),
                width=340,
            ),
            actions=[
                _ghost_btn("Cancel", on_click=lambda e2: page.close(dlg)),
                _primary_btn("Create and open", on_click=do_create),
            ],
            shape=ft.RoundedRectangleBorder(radius=10),
        )
        page.open(dlg)
        page.update()

    def sign_out(e):
        save_config_full({})
        token_holder["value"] = ""
        page.go("/signin")

    repo_content = ft.Column(
        [
            ft.Container(height=32),
            ft.Row(
                [
                    ft.Container(
                        ft.Column(
                            [
                                ft.Row([
                                    ft.Text("✦", size=20, color=_ACCENT),
                                    ft.Container(width=8),
                                    _heading("Select repository", size=20),
                                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                                ft.Container(height=6),
                                _body("Choose where to store your book, or create a new repository."),
                                ft.Container(height=24),
                                ft.Row([repos_dropdown, repo_progress], spacing=12,
                                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
                                ft.Container(height=16),
                                ft.Row(
                                    [
                                        _primary_btn("Open repository", on_click=on_select_repo),
                                        ft.Container(width=8),
                                        _secondary_btn("Create new", on_click=open_create_repo_dialog),
                                    ],
                                ),
                                ft.Container(height=12),
                                repo_error,
                                ft.Container(height=32),
                                _divider(),
                                ft.Container(height=12),
                                _ghost_btn("Sign out", on_click=sign_out,
                                           icon=ft.Icons.LOGOUT, color=_ERROR),
                            ],
                            spacing=0,
                        ),
                        width=520,
                        padding=36,
                        bgcolor=_SURFACE,
                        border_radius=12,
                        border=ft.border.all(1, _BORDER),
                    )
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    # ── Editor view ──────────────────────────────────────────────────────────
    repo_path_holder = {"value": get_repo_path(config)}
    chapter_list = ft.Column([], scroll=ft.ScrollMode.AUTO, expand=True, spacing=2)

    editor = _code_field(
        label="",
        multiline=True,
        min_lines=20,
        expand=True,
        on_change=lambda e: _set_dirty(True),
    )

    def _set_dirty(dirty: bool):
        editor_dirty["value"] = dirty
        save_btn_label.value = "Save •" if dirty else "Save"
        save_btn_label.color = _ACCENT if dirty else _TEXT
        page.update()

    def refresh_chapter_list():
        path = repo_path_holder["value"]
        if not path:
            return
        if not chapters_dir(path).exists():
            chapter_list.controls.clear()
            page.update()
            return
        items = list_chapters_with_versions(path)
        chapter_list.controls.clear()
        for num, ver, md_path in items:
            is_active = (current_md_path["value"] == md_path)
            chapter_list.controls.append(
                ft.Container(
                    ft.Column([
                        ft.Text(f"Chapter {num}", size=13, color=_TEXT if is_active else _TEXT_MUTED,
                                weight=ft.FontWeight.W_500 if is_active else ft.FontWeight.NORMAL),
                        ft.Text(ver, size=11, color=_ACCENT if is_active else _TEXT_MUTED),
                    ], spacing=2, tight=True),
                    data=md_path,
                    on_click=lambda e, p=md_path: load_chapter_file(p),
                    padding=ft.padding.symmetric(horizontal=10, vertical=8),
                    border_radius=6,
                    bgcolor=_SURFACE2 if is_active else None,
                    ink=True,
                )
            )
        page.update()

    def load_chapter_file(md_path: Path):
        current_md_path["value"] = md_path
        try:
            editor.value = md_path.read_text(encoding="utf-8")
        except Exception:
            editor.value = ""
        _set_dirty(False)
        refresh_chapter_list()  # re-render to highlight active chapter
        page.update()

    def save_current(e):
        path = current_md_path["value"]
        if not path:
            page.open(ft.SnackBar(ft.Text("No chapter open.")))
            page.update()
            return

        try:
            Path(path).write_text(editor.value or "", encoding="utf-8")
        except Exception as ex:
            page.open(ft.SnackBar(ft.Text(f"Save failed: {ex}")))
            page.update()
            return

        _set_dirty(False)

        save_btn.disabled = True
        save_btn_label.value = "Saving…"
        save_btn_label.color = _TEXT_MUTED
        page.update()

        def _push():
            token = token_holder["value"] or load_config().get("github_token")
            try:
                if token:
                    git_push(repo_path_holder["value"], token)
                    page.open(ft.SnackBar(ft.Text("Saved and synced to GitHub.")))
                else:
                    page.open(ft.SnackBar(ft.Text("Saved locally. Sign in to sync.")))
            except GitCommandError as err:
                _log("git push failed", err)
                page.open(ft.SnackBar(ft.Text(f"Sync failed: {err}")))
            except Exception as ex:
                _log("Sync failed", ex)
                page.open(ft.SnackBar(ft.Text(f"Sync failed: {ex}")))
            finally:
                save_btn.disabled = False
                save_btn_label.value = "Save"
                save_btn_label.color = _TEXT
                page.update()

        threading.Thread(target=_push, daemon=True).start()

    def tool_new_chapter(e):
        path = repo_path_holder["value"]
        if not path:
            page.open(ft.SnackBar(ft.Text("No project loaded.")))
            page.update()
            return
        try:
            create_new_chapter(chapters_dir(path))
            refresh_chapter_list()
            page.open(ft.SnackBar(ft.Text("New chapter created.")))
        except Exception as ex:
            page.open(ft.SnackBar(ft.Text(str(ex))))
        page.update()

    def tool_bump(e, bump_type: str):
        path = repo_path_holder["value"]
        cur = current_md_path["value"]
        if not path or not cur:
            page.open(ft.SnackBar(ft.Text("Open a chapter first.")))
            page.update()
            return
        m = re.search(r"[Cc]hapter\s+(\d+)", str(cur))
        if not m:
            page.open(ft.SnackBar(ft.Text("Could not detect chapter number.")))
            page.update()
            return
        num = int(m.group(1))
        manager = ChapterVersionManager(str(chapters_dir(path)))
        try:
            manager.bump_chapter(num, bump_type)
            refresh_chapter_list()
            for n, v, p in list_chapters_with_versions(path):
                if n == num:
                    load_chapter_file(p)
                    break
            page.open(ft.SnackBar(ft.Text(f"Bumped {bump_type} for chapter {num}.")))
        except Exception as ex:
            page.open(ft.SnackBar(ft.Text(str(ex))))
        page.update()

    def tool_increment(e):
        path = repo_path_holder["value"]
        if not path:
            page.open(ft.SnackBar(ft.Text("No project loaded.")))
            page.update()
            return
        after = _styled_field("Increment chapters after number",
                               keyboard_type=ft.KeyboardType.NUMBER)

        def do_increment(e2):
            try:
                n = int(after.value)
                success = increment_chapters(str(chapters_dir(path)), n, confirm=False)
                if success:
                    refresh_chapter_list()
                    page.open(ft.SnackBar(ft.Text("Chapters renumbered.")))
                page.close(dlg)
            except Exception as ex:
                page.open(ft.SnackBar(ft.Text(str(ex))))
            page.update()

        dlg = ft.AlertDialog(
            bgcolor=_SURFACE,
            title=_heading("Increment chapter numbers", size=18),
            content=ft.Container(after, width=320),
            actions=[
                _ghost_btn("Cancel", on_click=lambda e2: page.close(dlg)),
                _primary_btn("OK", on_click=do_increment),
            ],
            shape=ft.RoundedRectangleBorder(radius=10),
        )
        page.open(dlg)
        page.update()

    def tool_word_count(e):
        path = repo_path_holder["value"]
        if not path:
            page.open(ft.SnackBar(ft.Text("No project loaded.")))
            page.update()
            return
        try:
            latest = find_latest_versions(chapters_dir(path))
            count_words_in_chapters(latest)
            total = sum(cv.word_count for cv in latest.values())
            page.open(ft.SnackBar(ft.Text(f"Total words (latest versions): {total:,}")))
        except Exception as ex:
            page.open(ft.SnackBar(ft.Text(str(ex))))
        page.update()

    def tool_format(e):
        path = current_md_path["value"]
        if not path:
            page.open(ft.SnackBar(ft.Text("Open a chapter first.")))
            page.update()
            return
        try:
            changed = process_file(Path(path), in_place=True)
            if changed:
                editor.value = Path(path).read_text(encoding="utf-8")
                page.open(ft.SnackBar(ft.Text("Formatted.")))
            else:
                page.open(ft.SnackBar(ft.Text("No formatting changes needed.")))
        except Exception as ex:
            page.open(ft.SnackBar(ft.Text(str(ex))))
        page.update()

    def tool_generate_pdf(e):
        path = repo_path_holder["value"]
        if not path:
            page.open(ft.SnackBar(ft.Text("No project loaded.")))
            page.update()
            return
        if not check_pandoc_available():
            page.open(ft.SnackBar(
                ft.Text("Pandoc is not installed. Install pandoc and a LaTeX engine to generate PDFs."),
            ))
            page.update()
            return
        title_field = _styled_field("Book title", width=320)
        title_field.value = "Book"
        author_field = _styled_field("Author", width=320)

        def do_pdf(e2):
            try:
                out = build_pdf(
                    path,
                    title=title_field.value or "Book",
                    author=author_field.value or "",
                )
                page.close(dlg)
                page.open(ft.SnackBar(ft.Text(f"PDF saved to {out}")))
            except Exception as ex:
                page.open(ft.SnackBar(ft.Text(f"PDF failed: {ex}")))
            page.update()

        dlg = ft.AlertDialog(
            bgcolor=_SURFACE,
            title=_heading("Generate PDF", size=18),
            content=ft.Container(
                ft.Column([title_field, ft.Container(height=8), author_field], tight=True),
                width=340,
            ),
            actions=[
                _ghost_btn("Cancel", on_click=lambda e2: page.close(dlg)),
                _primary_btn("Generate", on_click=do_pdf),
            ],
            shape=ft.RoundedRectangleBorder(radius=10),
        )
        page.open(dlg)
        page.update()

    # Save button (uses a Text child so we can mutate label)
    save_btn_label = ft.Text("Save", color=_TEXT, size=13, weight=ft.FontWeight.W_500)
    save_btn = ft.ElevatedButton(
        content=save_btn_label,
        on_click=lambda e: save_current(e),
        style=ft.ButtonStyle(
            bgcolor={
                ft.ControlState.DEFAULT: _ACCENT,
                ft.ControlState.HOVERED: _ACCENT_HOVER,
                ft.ControlState.DISABLED: _SURFACE2,
            },
            shape=ft.RoundedRectangleBorder(radius=6),
            elevation=0,
            padding=ft.padding.symmetric(horizontal=16, vertical=8),
        ),
    )

    def go_setup(e):
        token_holder["value"] = load_config().get("github_token", "")
        page.go("/repo")
        page.update()

    # Toolbar
    toolbar = ft.Container(
        ft.Row(
            [
                # Logo mark
                ft.Container(
                    ft.Text("✦", size=16, color=_ACCENT),
                    margin=ft.margin.only(right=4),
                ),
                ft.Text("Book Editor", size=13, color=_TEXT_MUTED, weight=ft.FontWeight.W_500),
                ft.Container(
                    ft.VerticalDivider(width=1, color=_BORDER),
                    height=20,
                    margin=ft.margin.symmetric(horizontal=8),
                ),
                _toolbar_btn("New chapter", on_click=tool_new_chapter),
                ft.PopupMenuButton(
                    content=ft.Container(
                        ft.Row([
                            ft.Text("Bump version", size=13, color=_TEXT_MUTED),
                            ft.Icon(ft.Icons.ARROW_DROP_DOWN, color=_TEXT_MUTED, size=16),
                        ], spacing=2),
                        padding=ft.padding.symmetric(horizontal=10, vertical=6),
                        border_radius=4,
                        ink=True,
                    ),
                    items=[
                        ft.PopupMenuItem(content=ft.Text("Minor", color=_TEXT, size=13),
                                         on_click=lambda e: tool_bump(e, "minor")),
                        ft.PopupMenuItem(content=ft.Text("Patch", color=_TEXT, size=13),
                                         on_click=lambda e: tool_bump(e, "patch")),
                        ft.PopupMenuItem(content=ft.Text("Major", color=_TEXT, size=13),
                                         on_click=lambda e: tool_bump(e, "major")),
                    ],
                ),
                _toolbar_btn("Increment", on_click=tool_increment),
                _toolbar_btn("Word count", on_click=tool_word_count),
                _toolbar_btn("Format", on_click=tool_format),
                _toolbar_btn("PDF", on_click=tool_generate_pdf),
                ft.Container(expand=True),
                ft.IconButton(
                    ft.Icons.SETTINGS_OUTLINED,
                    tooltip="Repository settings",
                    on_click=go_setup,
                    icon_color=_TEXT_MUTED,
                    hover_color=_SURFACE2,
                    icon_size=18,
                ),
                ft.Container(width=4),
                save_btn,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=_SURFACE,
        border=ft.border.only(bottom=ft.BorderSide(1, _BORDER)),
        padding=ft.padding.symmetric(horizontal=16, vertical=8),
    )

    # Sidebar
    sidebar = ft.Container(
        ft.Column(
            [
                ft.Container(
                    ft.Row([
                        ft.Text("CHAPTERS", size=10, color=_TEXT_MUTED,
                                weight=ft.FontWeight.W_600, letter_spacing=1.2),
                    ]),
                    padding=ft.padding.symmetric(horizontal=10, vertical=8),
                ),
                _divider(),
                ft.Container(height=4),
                chapter_list,
            ],
            spacing=0,
            expand=True,
        ),
        width=200,
        bgcolor=_SURFACE,
        border=ft.border.only(right=ft.BorderSide(1, _BORDER)),
    )

    editor_content = ft.Column(
        [
            toolbar,
            ft.Row(
                [
                    sidebar,
                    ft.Container(
                        editor,
                        expand=True,
                        bgcolor=_BG,
                        padding=ft.padding.all(0),
                    ),
                ],
                expand=True,
                spacing=0,
            ),
        ],
        expand=True,
        spacing=0,
    )

    # ── Routing ──────────────────────────────────────────────────────────────
    def route_change(e):
        page.views.clear()
        cfg = load_config()
        repo_path_holder["value"] = get_repo_path(cfg)

        if page.route == "/signin":
            page.views.append(
                ft.View("/signin", [signin_content], bgcolor=_BG, padding=24)
            )
        elif page.route == "/repo":
            page.views.append(
                ft.View("/repo", [repo_content], bgcolor=_BG, padding=24)
            )
            on_repo_view_visible()
        elif page.route == "/editor":
            if repo_path_holder["value"]:
                refresh_chapter_list()
            page.views.append(
                ft.View("/editor", [editor_content], bgcolor=_BG, padding=0)
            )
        else:
            page.views.append(
                ft.View("/signin", [signin_content], bgcolor=_BG, padding=24)
            )
        page.update()

    page.on_route_change = route_change

    # Initial route
    if not is_github_connected(config):
        page.route = "/signin"
    elif not has_repo_selected(config):
        page.route = "/repo"
    else:
        repo_path = get_repo_path(config)
        if not Path(repo_path).exists():
            cfg = load_config()
            cfg["local_repo_path"] = ""
            cfg["repo_path"] = ""
            save_config_full(cfg)
            page.route = "/repo"
        else:
            page.route = "/editor"
    route_change(None)
