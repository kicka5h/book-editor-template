"""Flet UI for the Book Editor desktop app."""

import re
import sys
import threading
import traceback
from pathlib import Path

import flet as ft
from git.exc import GitCommandError

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


# ── Palette ──────────────────────────────────────────────────────────────────
_BG      = "#1A1A1A"
_SURFACE = "#242424"
_SURFACE2= "#2C2C2C"
_ACCENT  = "#DA7756"
_ACCENT_HOVER = "#C4674A"
_TEXT    = "#F5F0EB"
_TEXT_MUTED = "#A09890"
_BORDER  = "#383838"
_ERROR   = "#E05C5C"


def _log(label: str, ex: BaseException) -> None:
    print(f"\n[Book Editor] {label}: {ex}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    print(file=sys.stderr)


# ── Widget helpers ───────────────────────────────────────────────────────────

def _heading(text: str, size: int = 22) -> ft.Text:
    return ft.Text(text, size=size, weight=ft.FontWeight.BOLD, color=_TEXT)

def _body(text: str, color: str = _TEXT_MUTED) -> ft.Text:
    return ft.Text(text, size=13, color=color)

def _divider() -> ft.Divider:
    return ft.Divider(height=1, color=_BORDER)

def _primary_btn(label: str, on_click=None, disabled: bool = False) -> ft.ElevatedButton:
    return ft.ElevatedButton(
        label, on_click=on_click, disabled=disabled,
        style=ft.ButtonStyle(
            bgcolor={ft.ControlState.DEFAULT: _ACCENT, ft.ControlState.HOVERED: _ACCENT_HOVER,
                     ft.ControlState.DISABLED: _SURFACE2},
            color={ft.ControlState.DEFAULT: _TEXT, ft.ControlState.DISABLED: _TEXT_MUTED},
            shape=ft.RoundedRectangleBorder(radius=6),
            elevation=0,
            padding=ft.padding.symmetric(horizontal=16, vertical=10),
        ),
    )

def _secondary_btn(label: str, on_click=None, icon=None) -> ft.OutlinedButton:
    return ft.OutlinedButton(
        label, on_click=on_click, icon=icon,
        style=ft.ButtonStyle(
            color={ft.ControlState.DEFAULT: _TEXT_MUTED, ft.ControlState.HOVERED: _TEXT},
            side={ft.ControlState.DEFAULT: ft.BorderSide(1, _BORDER),
                  ft.ControlState.HOVERED: ft.BorderSide(1, _ACCENT)},
            shape=ft.RoundedRectangleBorder(radius=6),
            elevation=0,
            padding=ft.padding.symmetric(horizontal=16, vertical=10),
        ),
    )

def _ghost_btn(label: str, on_click=None, icon=None, color: str = _TEXT_MUTED) -> ft.TextButton:
    return ft.TextButton(
        label, on_click=on_click, icon=icon,
        style=ft.ButtonStyle(
            color={ft.ControlState.DEFAULT: color, ft.ControlState.HOVERED: _TEXT},
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
        ),
    )

def _styled_field(label: str, width=None, multiline: bool = False,
                  min_lines: int = 1, expand: bool = False,
                  on_change=None, keyboard_type=None) -> ft.TextField:
    return ft.TextField(
        label=label,
        label_style=ft.TextStyle(color=_TEXT_MUTED, size=12),
        width=width, multiline=multiline, min_lines=min_lines,
        expand=expand, on_change=on_change, keyboard_type=keyboard_type,
        text_style=ft.TextStyle(color=_TEXT, size=13),
        border_color=_BORDER, focused_border_color=_ACCENT,
        cursor_color=_ACCENT, bgcolor=_SURFACE2, border_radius=6,
        content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
    )

def _build_theme() -> ft.Theme:
    return ft.Theme(
        color_scheme_seed=_ACCENT,
        color_scheme=ft.ColorScheme(
            primary=_ACCENT, on_primary=_TEXT,
            background=_BG, surface=_SURFACE,
            on_surface=_TEXT, secondary=_ACCENT,
        ),
        visual_density=ft.VisualDensity.COMPACT,
    )


# ── App ───────────────────────────────────────────────────────────────────────

def main(page: ft.Page) -> None:
    page.title = "Book Editor"
    page.window.min_width = 800
    page.window.min_height = 560
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = _BG
    page.theme = _build_theme()
    page.padding = 0

    config = load_config()
    token_holder = {"value": (config.get("github_token") or "").strip()}
    current_md_path = {"value": None}
    editor_dirty = {"value": False}

    # ── Sign-in ──────────────────────────────────────────────────────────────
    signin_user_code = ft.Text(
        "", size=32, weight=ft.FontWeight.BOLD, selectable=True,
        color=_ACCENT, font_family="monospace",
    )
    signin_instruction = ft.Text("", size=13, color=_TEXT_MUTED)
    signin_error = ft.Text("", color=_ERROR, size=13)
    signin_progress = ft.ProgressRing(
        visible=False, color=_ACCENT, stroke_width=2, width=18, height=18
    )
    signin_button = _primary_btn("Sign in with GitHub")

    def _do_device_flow():
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
            ft.Container(height=60),
            ft.Row(
                [
                    ft.Container(
                        ft.Column(
                            [
                                ft.Text("✦", size=24, color=_ACCENT),
                                ft.Container(height=16),
                                _heading("Book Editor", size=24),
                                ft.Container(height=6),
                                _body("Connect your GitHub account to store\nyour book in a repository."),
                                ft.Container(height=32),
                                signin_button,
                                ft.Container(height=20),
                                signin_user_code,
                                ft.Container(height=4),
                                signin_instruction,
                                ft.Container(height=8),
                                ft.Row([signin_progress, signin_error], spacing=8),
                            ],
                            spacing=0,
                        ),
                        width=380,
                        padding=36,
                        bgcolor=_SURFACE,
                        border_radius=10,
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

    # ── Repo selection ────────────────────────────────────────────────────────
    repos_dropdown = ft.Dropdown(
        label="Repository",
        width=380,
        options=[],
        border_color=_BORDER,
        focused_border_color=_ACCENT,
        bgcolor=_SURFACE2,
        border_radius=6,
        label_style=ft.TextStyle(color=_TEXT_MUTED, size=12),
        text_style=ft.TextStyle(color=_TEXT, size=13),
    )
    repo_progress = ft.ProgressRing(
        visible=False, color=_ACCENT, stroke_width=2, width=18, height=18
    )
    repo_error = ft.Text("", color=_ERROR, size=13)
    create_repo_name_field = _styled_field("Repository name", width=300)
    create_private_check = ft.Checkbox(
        label="Private repository", value=True, active_color=_ACCENT,
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
                    token, name, private=create_private_check.value,
                    description="Book content"
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
                width=320,
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
            ft.Container(height=60),
            ft.Row(
                [
                    ft.Container(
                        ft.Column(
                            [
                                ft.Text("✦", size=20, color=_ACCENT),
                                ft.Container(height=16),
                                _heading("Select repository", size=20),
                                ft.Container(height=6),
                                _body("Choose where to store your book."),
                                ft.Container(height=24),
                                ft.Row(
                                    [repos_dropdown, repo_progress], spacing=12,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                ft.Container(height=16),
                                ft.Row([
                                    _primary_btn("Open", on_click=on_select_repo),
                                    ft.Container(width=8),
                                    _secondary_btn("Create new", on_click=open_create_repo_dialog),
                                ]),
                                ft.Container(height=10),
                                repo_error,
                                ft.Container(height=28),
                                _divider(),
                                ft.Container(height=10),
                                _ghost_btn("Sign out", on_click=sign_out,
                                           icon=ft.Icons.LOGOUT, color=_ERROR),
                            ],
                            spacing=0,
                        ),
                        width=480,
                        padding=36,
                        bgcolor=_SURFACE,
                        border_radius=10,
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

    # ── Editor ────────────────────────────────────────────────────────────────
    repo_path_holder = {"value": get_repo_path(config)}
    chapter_list = ft.Column([], scroll=ft.ScrollMode.AUTO, expand=True, spacing=0)

    # Dual-mode state: "preview" shows ft.Markdown, "edit" shows ft.TextField
    editor_mode = {"value": "preview"}  # "preview" | "edit"
    # Raw markdown content is the source of truth
    md_content = {"value": ""}

    # ── Markdown style sheet — Anthropic palette ─────────────────────────────
    _md_body_style  = ft.TextStyle(color=_TEXT,       size=15, font_family="Georgia")
    _md_code_style  = ft.TextStyle(color="#C9D1D9",   size=13, font_family="monospace")
    _md_muted_style = ft.TextStyle(color=_TEXT_MUTED, size=15)

    _md_stylesheet = ft.MarkdownStyleSheet(
        p_text_style        = _md_body_style,
        p_padding           = ft.padding.symmetric(vertical=4),
        h1_text_style       = ft.TextStyle(color=_TEXT, size=26, weight=ft.FontWeight.BOLD),
        h1_padding          = ft.padding.symmetric(vertical=8),
        h2_text_style       = ft.TextStyle(color=_TEXT, size=21, weight=ft.FontWeight.BOLD),
        h2_padding          = ft.padding.symmetric(vertical=6),
        h3_text_style       = ft.TextStyle(color=_TEXT, size=17, weight=ft.FontWeight.W_600),
        h3_padding          = ft.padding.symmetric(vertical=5),
        em_text_style       = ft.TextStyle(color=_TEXT, size=15, italic=True),
        strong_text_style   = ft.TextStyle(color=_TEXT, size=15, weight=ft.FontWeight.BOLD),
        del_text_style      = ft.TextStyle(color=_TEXT_MUTED, size=15,
                                           decoration=ft.TextDecoration.LINE_THROUGH),
        blockquote_text_style = ft.TextStyle(color=_TEXT_MUTED, size=15, italic=True),
        blockquote_padding  = ft.padding.only(left=16, top=8, bottom=8, right=8),
        blockquote_decoration = ft.BoxDecoration(
            border=ft.border.only(left=ft.BorderSide(3, _ACCENT)),
            color=_SURFACE,
        ),
        code_text_style     = _md_code_style,
        codeblock_padding   = ft.padding.all(12),
        codeblock_decoration = ft.BoxDecoration(
            color=_SURFACE2,
            border_radius=ft.border_radius.all(6),
        ),
        list_bullet_text_style = ft.TextStyle(color=_ACCENT, size=15),
        block_spacing       = 8,
    )

    # ── Preview widget (ft.Markdown) ─────────────────────────────────────────
    md_preview = ft.Markdown(
        value="",
        extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED,
        selectable=True,
        fit_content=True,
        md_style_sheet=_md_stylesheet,
        code_theme=ft.MarkdownCodeTheme.TOMORROW_NIGHT,
    )

    # Invisible click catcher layered over the preview; tap → switch to edit
    def _enter_edit_mode(e=None):
        if editor_mode["value"] == "edit":
            return
        editor_mode["value"] = "edit"
        raw_editor.value = md_content["value"]
        preview_layer.visible = False
        edit_layer.visible = True
        page.update()
        raw_editor.focus()

    def _exit_edit_mode(e=None):
        if editor_mode["value"] != "edit":
            return
        # Flush current text → source of truth
        new_text = raw_editor.value or ""
        md_content["value"] = new_text
        md_preview.value = new_text
        editor_mode["value"] = "preview"
        preview_layer.visible = True
        edit_layer.visible = False
        # Mark dirty and update word count (batch into single page.update)
        _mark_dirty(True)
        _update_word_count_internal()
        page.update()

    # Preview layer: scrollable Markdown + transparent tap target on top
    preview_layer = ft.Container(
        content=ft.Column(
            [
                ft.GestureDetector(
                    content=ft.Container(
                        content=ft.Column(
                            [
                                ft.Container(
                                    md_preview,
                                    padding=ft.padding.symmetric(horizontal=48, vertical=32),
                                    expand=True,
                                ),
                                # Clickable empty space below text to enter edit mode
                                ft.GestureDetector(
                                    content=ft.Container(height=200, expand=False),
                                    on_tap=_enter_edit_mode,
                                ),
                            ],
                            expand=True,
                            spacing=0,
                        ),
                        bgcolor=_BG,
                        expand=True,
                    ),
                    on_tap=_enter_edit_mode,
                )
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=0,
        ),
        expand=True,
        bgcolor=_BG,
        visible=True,
    )

    # ── Raw editor widget (ft.TextField) ─────────────────────────────────────
    def _on_raw_editor_change(e):
        md_content["value"] = raw_editor.value or ""
        _mark_dirty(True)
        _update_word_count_internal()
        page.update()

    def _on_raw_editor_blur(e):
        _exit_edit_mode()

    raw_editor = ft.TextField(
        multiline=True,
        min_lines=30,
        expand=True,
        text_style=ft.TextStyle(color=_TEXT, font_family="monospace", size=14),
        cursor_color=_ACCENT,
        bgcolor=_BG,
        border_color="transparent",
        focused_border_color="transparent",
        content_padding=ft.padding.symmetric(horizontal=48, vertical=32),
        on_change=_on_raw_editor_change,
        on_blur=_on_raw_editor_blur,
    )

    # Edit layer: raw TextField in scrollable container
    edit_layer = ft.Container(
        content=ft.Column(
            [raw_editor],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=0,
        ),
        expand=True,
        bgcolor=_BG,
        visible=False,
    )

    # Editor area: stack preview + edit layers
    editor_area = ft.Stack(
        [preview_layer, edit_layer],
        expand=True,
    )

    # Status bar state
    status_chapter = ft.Text("", size=12, color=_TEXT_MUTED)
    status_words = ft.Text("", size=12, color=_TEXT_MUTED)
    save_indicator = ft.Text("", size=12, color=_TEXT_MUTED)

    def _mark_dirty(dirty: bool):
        """Update dirty state and save indicator without calling page.update()."""
        editor_dirty["value"] = dirty
        save_indicator.value = "●  unsaved" if dirty else ""
        save_indicator.color = _ACCENT if dirty else _TEXT_MUTED

    def _set_dirty(dirty: bool):
        _mark_dirty(dirty)
        page.update()

    def _update_word_count_internal():
        text = md_content["value"] or ""
        words = len(text.split()) if text.strip() else 0
        status_words.value = f"{words:,} words"

    def _update_word_count():
        _update_word_count_internal()
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
                        ft.Text(
                            f"Chapter {num}", size=12,
                            color=_TEXT if is_active else _TEXT_MUTED,
                            weight=ft.FontWeight.W_500 if is_active else ft.FontWeight.NORMAL,
                        ),
                        ft.Text(ver, size=10, color=_ACCENT if is_active else _BORDER),
                    ], spacing=1, tight=True),
                    data=md_path,
                    on_click=lambda e, p=md_path: load_chapter_file(p),
                    padding=ft.padding.symmetric(horizontal=12, vertical=7),
                    bgcolor=_SURFACE2 if is_active else None,
                    ink=True,
                )
            )
        page.update()

    def load_chapter_file(md_path: Path):
        current_md_path["value"] = md_path
        try:
            text = md_path.read_text(encoding="utf-8")
        except Exception:
            text = ""
        md_content["value"] = text
        md_preview.value = text
        raw_editor.value = text
        # Always start in preview mode when opening a chapter
        editor_mode["value"] = "preview"
        preview_layer.visible = True
        edit_layer.visible = False
        # Extract chapter number for status bar
        m = re.search(r"[Cc]hapter\s+(\d+)", str(md_path))
        status_chapter.value = f"Chapter {m.group(1)}" if m else md_path.stem
        _mark_dirty(False)
        _update_word_count_internal()
        # refresh_chapter_list will call page.update() at the end
        refresh_chapter_list()

    def save_current(e=None):
        path = current_md_path["value"]
        if not path:
            page.open(ft.SnackBar(ft.Text("No chapter open.")))
            page.update()
            return
        # If currently editing, flush the raw editor text first
        if editor_mode["value"] == "edit":
            md_content["value"] = raw_editor.value or ""
        try:
            Path(path).write_text(md_content["value"], encoding="utf-8")
        except Exception as ex:
            page.open(ft.SnackBar(ft.Text(f"Save failed: {ex}")))
            page.update()
            return

        _set_dirty(False)
        save_indicator.value = "Syncing…"
        save_indicator.color = _TEXT_MUTED
        page.update()

        def _push():
            token = token_holder["value"] or load_config().get("github_token")
            try:
                if token:
                    git_push(repo_path_holder["value"], token)
                    save_indicator.value = "Saved"
                else:
                    save_indicator.value = "Saved locally"
            except GitCommandError as err:
                _log("git push failed", err)
                page.open(ft.SnackBar(ft.Text(f"Sync failed: {err}")))
                save_indicator.value = "Sync failed"
            except Exception as ex:
                _log("Sync failed", ex)
                page.open(ft.SnackBar(ft.Text(f"Sync failed: {ex}")))
                save_indicator.value = "Sync failed"
            finally:
                save_indicator.color = _TEXT_MUTED
                page.update()

        threading.Thread(target=_push, daemon=True).start()

    # ── Tool handlers ─────────────────────────────────────────────────────────

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
            content=ft.Container(after, width=300),
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
            page.open(ft.SnackBar(ft.Text(f"Total words across all chapters: {total:,}")))
        except Exception as ex:
            page.open(ft.SnackBar(ft.Text(str(ex))))
        page.update()

    def tool_format(e):
        path = current_md_path["value"]
        if not path:
            page.open(ft.SnackBar(ft.Text("Open a chapter first.")))
            page.update()
            return
        # Flush any in-progress edit before formatting
        if editor_mode["value"] == "edit":
            md_content["value"] = raw_editor.value or ""
            Path(path).write_text(md_content["value"], encoding="utf-8")
        try:
            changed = process_file(Path(path), in_place=True)
            if changed:
                text = Path(path).read_text(encoding="utf-8")
                md_content["value"] = text
                md_preview.value = text
                raw_editor.value = text
                # Switch back to preview after format
                editor_mode["value"] = "preview"
                preview_layer.visible = True
                edit_layer.visible = False
                page.open(ft.SnackBar(ft.Text("Formatted.")))
            else:
                page.open(ft.SnackBar(ft.Text("Already formatted.")))
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
        title_field = _styled_field("Book title", width=300)
        title_field.value = "Book"
        author_field = _styled_field("Author", width=300)

        def do_pdf(e2):
            try:
                out = build_pdf(path, title=title_field.value or "Book",
                                author=author_field.value or "")
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
                width=320,
            ),
            actions=[
                _ghost_btn("Cancel", on_click=lambda e2: page.close(dlg)),
                _primary_btn("Generate", on_click=do_pdf),
            ],
            shape=ft.RoundedRectangleBorder(radius=10),
        )
        page.open(dlg)
        page.update()

    def go_setup(e):
        token_holder["value"] = load_config().get("github_token", "")
        page.go("/repo")
        page.update()

    # ── Editor layout ─────────────────────────────────────────────────────────

    # Narrow chapter sidebar — no header chrome, just the list
    sidebar = ft.Container(
        ft.Column(
            [
                ft.Container(
                    ft.Text("Chapters", size=11, color=_TEXT_MUTED,
                            weight=ft.FontWeight.W_500),
                    padding=ft.padding.only(left=12, top=14, bottom=8),
                ),
                chapter_list,
                ft.Container(
                    ft.TextButton(
                        "+ New chapter",
                        on_click=tool_new_chapter,
                        style=ft.ButtonStyle(
                            color={ft.ControlState.DEFAULT: _TEXT_MUTED,
                                   ft.ControlState.HOVERED: _ACCENT},
                            padding=ft.padding.symmetric(horizontal=12, vertical=6),
                        ),
                    ),
                    padding=ft.padding.only(bottom=8),
                ),
            ],
            spacing=0,
            expand=True,
        ),
        width=160,
        bgcolor=_SURFACE,
        border=ft.border.only(right=ft.BorderSide(1, _BORDER)),
    )

    # Overflow menu — all the less-frequent tools
    tools_menu = ft.PopupMenuButton(
        content=ft.Container(
            ft.Icon(ft.Icons.MORE_HORIZ, color=_TEXT_MUTED, size=16),
            padding=ft.padding.symmetric(horizontal=8, vertical=4),
            border_radius=4,
            ink=True,
        ),
        items=[
            ft.PopupMenuItem(
                content=ft.Text("Bump version — minor", color=_TEXT, size=13),
                on_click=lambda e: tool_bump(e, "minor"),
            ),
            ft.PopupMenuItem(
                content=ft.Text("Bump version — patch", color=_TEXT, size=13),
                on_click=lambda e: tool_bump(e, "patch"),
            ),
            ft.PopupMenuItem(
                content=ft.Text("Bump version — major", color=_TEXT, size=13),
                on_click=lambda e: tool_bump(e, "major"),
            ),
            ft.PopupMenuItem(),  # divider
            ft.PopupMenuItem(
                content=ft.Text("Increment chapter numbers", color=_TEXT, size=13),
                on_click=tool_increment,
            ),
            ft.PopupMenuItem(
                content=ft.Text("Word count — all chapters", color=_TEXT, size=13),
                on_click=tool_word_count,
            ),
            ft.PopupMenuItem(
                content=ft.Text("Format markdown", color=_TEXT, size=13),
                on_click=tool_format,
            ),
            ft.PopupMenuItem(
                content=ft.Text("Generate PDF", color=_TEXT, size=13),
                on_click=tool_generate_pdf,
            ),
            ft.PopupMenuItem(),  # divider
            ft.PopupMenuItem(
                content=ft.Text("Repository settings", color=_TEXT, size=13),
                on_click=go_setup,
            ),
        ],
    )

    # Minimal status bar at the bottom
    status_bar = ft.Container(
        ft.Row(
            [
                status_chapter,
                ft.Container(width=16),
                status_words,
                ft.Container(expand=True),
                save_indicator,
                ft.Container(width=12),
                ft.TextButton(
                    "Save",
                    on_click=lambda e: save_current(),
                    style=ft.ButtonStyle(
                        color={ft.ControlState.DEFAULT: _TEXT_MUTED,
                               ft.ControlState.HOVERED: _TEXT},
                        padding=ft.padding.symmetric(horizontal=10, vertical=4),
                    ),
                ),
                ft.Container(width=4),
                tools_menu,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=_SURFACE,
        border=ft.border.only(top=ft.BorderSide(1, _BORDER)),
        padding=ft.padding.symmetric(horizontal=16, vertical=6),
        height=36,
    )

    editor_content = ft.Column(
        [
            ft.Row(
                [
                    sidebar,
                    editor_area,
                ],
                expand=True,
                spacing=0,
            ),
            status_bar,
        ],
        expand=True,
        spacing=0,
    )

    # ── Routing ───────────────────────────────────────────────────────────────
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
