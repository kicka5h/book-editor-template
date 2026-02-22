"""Flet UI for the Beckit desktop app."""

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
    delete_chapter,
    reorder_chapters,
    validate_token,
    list_user_repos,
    create_repo,
    clone_repo,
    ensure_chapters_structure,
    start_device_flow,
    poll_device_flow,
    build_pdf,
    check_pandoc_available,
    ensure_planning_structure,
    list_planning_files,
    create_planning_file,
    create_planning_folder,
    delete_planning_entry,
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
    print(f"\n[Beckit] {label}: {ex}", file=sys.stderr)
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
    page.title = "Beckit"
    page.window.width = 1280
    page.window.height = 800
    page.window.min_width = 900
    page.window.min_height = 600
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
                                _heading("Beckit", size=24),
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

    # Dual-mode state: "preview" shows ft.Markdown, "edit" shows ft.TextField
    editor_mode = {"value": "preview"}  # "preview" | "edit"
    # Raw markdown content is the source of truth
    md_content = {"value": ""}
    # Tracks whether the scratch-pad save dialog has already been triggered
    # for the current unsaved session (prevents re-triggering on every keystroke)
    _save_dialog_pending = {"value": False}
    # Set to True by the window-close guard when the user chooses "Save first…"
    # so that each save handler knows to destroy the window after saving.
    _pending_close = {"value": False}

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
            bgcolor=_SURFACE,
        ),
        code_text_style     = _md_code_style,
        codeblock_padding   = ft.padding.all(12),
        codeblock_decoration = ft.BoxDecoration(
            bgcolor=_SURFACE2,
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

    # Placeholder shown in preview mode when no chapter is open and no content yet
    _scratch_placeholder = ft.Container(
        ft.Text(
            "Start writing — you'll be asked where to save it.",
            size=15,
            color=_TEXT_MUTED,
            italic=True,
        ),
        padding=ft.padding.symmetric(horizontal=48, vertical=32),
        visible=True,  # shown by default; hidden once content exists or chapter is open
    )

    # Invisible click catcher layered over the preview; tap → switch to edit
    def _enter_edit_mode(e=None):
        if editor_mode["value"] == "edit":
            return
        editor_mode["value"] = "edit"
        raw_editor.value = md_content["value"]
        _scratch_placeholder.visible = False
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
        # Show placeholder only when no content and no chapter open
        _scratch_placeholder.visible = (
            not new_text.strip() and current_md_path["value"] is None
        )
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
                                # Placeholder shown when editor is empty and no chapter loaded
                                _scratch_placeholder,
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
    def _show_save_to_chapter_dialog():
        """Show dialog prompting user to save scratch-pad content to a chapter or planning file."""
        _save_dialog_pending["value"] = True
        path = repo_path_holder["value"]
        if not path:
            return

        # ── Chapter options ───────────────────────────────────────────────────
        existing = list_chapters_with_versions(path)
        chapter_options = [
            ft.dropdown.Option(key=str(md_p), text=f"Chapter {n}  ({ver})")
            for n, ver, md_p in existing
        ]
        chapter_dropdown = ft.Dropdown(
            label="Existing chapter",
            options=chapter_options,
            border_color=_BORDER,
            focused_border_color=_ACCENT,
            bgcolor=_SURFACE2,
            border_radius=6,
            label_style=ft.TextStyle(color=_TEXT_MUTED, size=12),
            text_style=ft.TextStyle(color=_TEXT, size=13),
            disabled=not chapter_options,
            hint_text="(none available)" if not chapter_options else None,
        )

        # ── Planning options ──────────────────────────────────────────────────
        ensure_planning_structure(path)
        planning_entries = list_planning_files(path)
        # Only .md files (not dirs) for the "existing" dropdown
        planning_file_options = [
            ft.dropdown.Option(key=str(fpath), text=label)
            for label, fpath, is_dir in planning_entries
            if not is_dir
        ]
        planning_dropdown = ft.Dropdown(
            label="Existing planning file",
            options=planning_file_options,
            border_color=_BORDER,
            focused_border_color=_ACCENT,
            bgcolor=_SURFACE2,
            border_radius=6,
            label_style=ft.TextStyle(color=_TEXT_MUTED, size=12),
            text_style=ft.TextStyle(color=_TEXT, size=13),
            disabled=not planning_file_options,
            hint_text="(none available)" if not planning_file_options else None,
        )
        planning_name_field = _styled_field(
            "New planning file name (e.g. Notes.md)", width=290
        )

        # ── Handlers ─────────────────────────────────────────────────────────
        def _save_to_new_chapter(e2):
            try:
                create_new_chapter(chapters_dir(path))
                new_chapters = list_chapters_with_versions(path)
                if new_chapters:
                    _, _, new_md_path = new_chapters[-1]
                    Path(new_md_path).write_text(md_content["value"], encoding="utf-8")
                    page.close(dlg)
                    if _pending_close["value"]:
                        _pending_close["value"] = False
                        page.window.destroy()
                        return
                    load_chapter_file(new_md_path)
                    page.open(ft.SnackBar(
                        ft.Text(f"Saved to new Chapter {new_chapters[-1][0]}.")
                    ))
            except Exception as ex:
                page.open(ft.SnackBar(ft.Text(str(ex))))
            page.update()

        def _save_to_existing_chapter(e2):
            sel = chapter_dropdown.value
            if not sel:
                page.open(ft.SnackBar(ft.Text("Select a chapter first.")))
                page.update()
                return
            try:
                sel_path = Path(sel)
                sel_path.write_text(md_content["value"], encoding="utf-8")
                page.close(dlg)
                if _pending_close["value"]:
                    _pending_close["value"] = False
                    page.window.destroy()
                    return
                load_chapter_file(sel_path)
                page.open(ft.SnackBar(ft.Text("Content saved to chapter.")))
            except Exception as ex:
                page.open(ft.SnackBar(ft.Text(str(ex))))
            page.update()

        def _save_to_new_planning(e2):
            name = (planning_name_field.value or "").strip()
            if not name:
                page.open(ft.SnackBar(ft.Text("Enter a file name.")))
                page.update()
                return
            try:
                new_path = create_planning_file(path, name)
                new_path.write_text(md_content["value"], encoding="utf-8")
                page.close(dlg)
                # Open the planning pane and load the new file
                if not planning_open["value"]:
                    toggle_planning_pane()
                else:
                    refresh_planning_list()
                load_planning_file(new_path)
                # Clear the chapter editor scratch state
                current_md_path["value"] = None
                _save_dialog_pending["value"] = False
                md_content["value"] = ""
                md_preview.value = ""
                raw_editor.value = ""
                status_chapter.value = ""
                _scratch_placeholder.visible = True
                _mark_dirty(False)
                _update_word_count_internal()
                if _pending_close["value"]:
                    _pending_close["value"] = False
                    page.window.destroy()
                    return
                page.open(ft.SnackBar(ft.Text(f"Saved to planning/{new_path.name}.")))
            except Exception as ex:
                page.open(ft.SnackBar(ft.Text(str(ex))))
            page.update()

        def _save_to_existing_planning(e2):
            sel = planning_dropdown.value
            if not sel:
                page.open(ft.SnackBar(ft.Text("Select a planning file first.")))
                page.update()
                return
            try:
                sel_path = Path(sel)
                sel_path.write_text(md_content["value"], encoding="utf-8")
                page.close(dlg)
                if not planning_open["value"]:
                    toggle_planning_pane()
                else:
                    refresh_planning_list()
                load_planning_file(sel_path)
                # Clear the chapter editor scratch state
                current_md_path["value"] = None
                _save_dialog_pending["value"] = False
                md_content["value"] = ""
                md_preview.value = ""
                raw_editor.value = ""
                status_chapter.value = ""
                _scratch_placeholder.visible = True
                _mark_dirty(False)
                _update_word_count_internal()
                if _pending_close["value"]:
                    _pending_close["value"] = False
                    page.window.destroy()
                    return
                page.open(ft.SnackBar(ft.Text(f"Saved to {sel_path.name}.")))
            except Exception as ex:
                page.open(ft.SnackBar(ft.Text(str(ex))))
            page.update()

        def _on_dismiss(e2=None):
            _save_dialog_pending["value"] = False
            _pending_close["value"] = False  # cancel any pending close-after-save

        dlg = ft.AlertDialog(
            bgcolor=_SURFACE,
            modal=False,
            title=_heading("Save to…", size=18),
            content=ft.Container(
                ft.Column(
                    [
                        ft.Text(
                            "Where would you like to save this content?",
                            color=_TEXT_MUTED,
                            size=13,
                        ),
                        ft.Container(height=16),

                        # ── Chapter section ───────────────────────────────
                        ft.Text("Chapter", color=_TEXT, size=13,
                                weight=ft.FontWeight.W_600),
                        ft.Container(height=8),
                        _primary_btn("Create new chapter", on_click=_save_to_new_chapter),
                        ft.Container(height=10),
                        chapter_dropdown,
                        ft.Container(height=4),
                        _secondary_btn(
                            "Save to selected chapter",
                            on_click=_save_to_existing_chapter,
                        ),
                        ft.Container(height=16),

                        # ── Planning section ──────────────────────────────
                        _divider(),
                        ft.Container(height=16),
                        ft.Text("Planning", color=_TEXT, size=13,
                                weight=ft.FontWeight.W_600),
                        ft.Container(height=8),
                        planning_name_field,
                        ft.Container(height=4),
                        _secondary_btn(
                            "Save as new planning file",
                            on_click=_save_to_new_planning,
                        ),
                        ft.Container(height=10),
                        planning_dropdown,
                        ft.Container(height=4),
                        _secondary_btn(
                            "Save to selected planning file",
                            on_click=_save_to_existing_planning,
                        ),
                    ],
                    tight=True,
                    spacing=0,
                    scroll=ft.ScrollMode.AUTO,
                ),
                width=340,
                padding=ft.padding.only(top=4),
            ),
            actions=[
                _ghost_btn(
                    "Keep editing (save later)",
                    on_click=lambda e2: (page.close(dlg), _on_dismiss()),
                ),
            ],
            on_dismiss=_on_dismiss,
            shape=ft.RoundedRectangleBorder(radius=10),
        )
        page.open(dlg)
        page.update()

    def _on_raw_editor_change(e):
        new_text = raw_editor.value or ""
        md_content["value"] = new_text
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
        hint_text="Start writing…",
        hint_style=ft.TextStyle(color=_TEXT_MUTED, size=15, italic=True),
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

    def _do_load_chapter_file(md_path: Path):
        """Internal: unconditionally load a chapter file into the editor."""
        current_md_path["value"] = md_path
        _save_dialog_pending["value"] = False
        try:
            text = md_path.read_text(encoding="utf-8")
        except Exception:
            text = ""
        md_content["value"] = text
        md_preview.value = text
        raw_editor.value = text
        editor_mode["value"] = "preview"
        preview_layer.visible = True
        edit_layer.visible = False
        _scratch_placeholder.visible = False
        m = re.search(r"[Cc]hapter\s+(\d+)", str(md_path))
        chap_label = f"Chapter {m.group(1)}" if m else md_path.stem
        status_chapter.value = chap_label
        chapter_panel_title.value = chap_label
        _mark_dirty(False)
        _update_word_count_internal()
        refresh_chapter_list()

    def load_chapter_file(md_path: Path):
        """Load a chapter, prompting to save/discard scratch content first if needed."""
        scratch_dirty = (
            current_md_path["value"] is None
            and md_content["value"].strip()
        )
        if not scratch_dirty:
            _do_load_chapter_file(md_path)
            return

        # Scratch pad has unsaved content — ask what to do before discarding it
        def _discard_and_open(e2):
            page.close(guard_dlg)
            _do_load_chapter_file(md_path)
            page.update()

        def _save_then_open(e2):
            page.close(guard_dlg)
            # Re-use the save dialog; after saving it will not auto-open the chapter,
            # so we chain: after the save dialog is dismissed (saved or kept), load the chapter.
            # We do this by temporarily monkey-patching _on_dismiss in the save dialog to
            # also trigger the load.  Simpler: just show the save dialog and let the user
            # choose — they can come back to open the chapter afterwards.
            _save_dialog_pending["value"] = False
            _show_save_to_chapter_dialog()
            page.update()

        guard_dlg = ft.AlertDialog(
            bgcolor=_SURFACE,
            modal=True,
            title=_heading("Unsaved scratch content", size=18),
            content=ft.Container(
                ft.Text(
                    "You have unsaved content in the scratch pad.\n"
                    "Save it before opening this chapter, or discard it?",
                    color=_TEXT_MUTED,
                    size=13,
                ),
                width=320,
            ),
            actions=[
                _ghost_btn("Cancel", on_click=lambda e2: page.close(guard_dlg)),
                _ghost_btn("Save first…", on_click=_save_then_open),
                ft.TextButton(
                    "Discard & open",
                    on_click=_discard_and_open,
                    style=ft.ButtonStyle(
                        color={ft.ControlState.DEFAULT: _ERROR,
                               ft.ControlState.HOVERED: "#FF7070"},
                        padding=ft.padding.symmetric(horizontal=12, vertical=8),
                    ),
                ),
            ],
            shape=ft.RoundedRectangleBorder(radius=10),
        )
        page.open(guard_dlg)
        page.update()

    def save_current(e=None):
        path = current_md_path["value"]
        if not path:
            # If there's scratch content, offer to save it; otherwise inform user
            if md_content["value"].strip():
                _save_dialog_pending["value"] = False  # allow re-trigger
                _show_save_to_chapter_dialog()
            else:
                page.open(ft.SnackBar(ft.Text("Nothing to save yet — start writing first.")))
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

    # ── Chapter sidebar (drag-to-reorder + delete) ────────────────────────────

    # chapter_order tracks the current sequence of chapter numbers so we can
    # map drag indices back to chapter numbers during reorder.
    chapter_order = {"value": []}  # list of int chapter numbers in display order

    def _confirm_delete_chapter(num: int):
        def do_delete(e):
            page.close(dlg)
            path = repo_path_holder["value"]
            try:
                # If the chapter being deleted is currently open, clear the editor
                cur = current_md_path["value"]
                if cur and re.search(rf"Chapter\s+{num}[/\\]", str(cur)):
                    current_md_path["value"] = None
                    _save_dialog_pending["value"] = False
                    md_content["value"] = ""
                    md_preview.value = ""
                    raw_editor.value = ""
                    status_chapter.value = ""
                    _scratch_placeholder.visible = True
                    _mark_dirty(False)
                    _update_word_count_internal()
                delete_chapter(path, num)
                refresh_chapter_list()
                page.open(ft.SnackBar(ft.Text(f"Chapter {num} deleted.")))
            except Exception as ex:
                page.open(ft.SnackBar(ft.Text(str(ex))))
            page.update()

        dlg = ft.AlertDialog(
            bgcolor=_SURFACE,
            title=_heading("Delete chapter?", size=18),
            content=ft.Container(
                ft.Text(
                    f"Delete Chapter {num} and all its versions?\n"
                    "This cannot be undone.",
                    color=_TEXT_MUTED, size=13,
                ),
                width=300,
            ),
            actions=[
                _ghost_btn("Cancel", on_click=lambda e: page.close(dlg)),
                ft.TextButton(
                    "Delete",
                    on_click=do_delete,
                    style=ft.ButtonStyle(
                        color={ft.ControlState.DEFAULT: _ERROR,
                               ft.ControlState.HOVERED: "#FF7070"},
                        padding=ft.padding.symmetric(horizontal=12, vertical=8),
                    ),
                ),
            ],
            shape=ft.RoundedRectangleBorder(radius=10),
        )
        page.open(dlg)
        page.update()

    def _on_chapter_reorder(e: ft.OnReorderEvent):
        """Called when the user drags a chapter row to a new position."""
        path = repo_path_holder["value"]
        if not path:
            return
        old_order = list(chapter_order["value"])
        if e.old_index == e.new_index or not old_order:
            return
        # Reorder the local list
        item = old_order.pop(e.old_index)
        old_order.insert(e.new_index, item)
        chapter_order["value"] = old_order
        try:
            reorder_chapters(path, old_order)
            # If the open file's chapter number changed, update current_md_path
            cur = current_md_path["value"]
            if cur:
                refresh_chapter_list()
                # Try to reopen the same chapter content at its new number
                # (refresh_chapter_list re-scans disk, so the path will have moved)
                # We load whichever chapter is now at the position that was opened.
                new_chapters = list_chapters_with_versions(path)
                if new_chapters:
                    # Find the chapter whose new number matches the drag destination
                    target_num = e.new_index + 1
                    for n, v, p in new_chapters:
                        if n == target_num:
                            load_chapter_file(p)
                            break
            else:
                refresh_chapter_list()
        except Exception as ex:
            page.open(ft.SnackBar(ft.Text(f"Reorder failed: {ex}")))
            chapter_order["value"] = list(chapter_order["value"])  # keep consistent
            refresh_chapter_list()
        page.update()

    # The reorderable list view for chapters
    chapter_reorder_list = ft.ReorderableListView(
        controls=[],
        on_reorder=_on_chapter_reorder,
        padding=ft.padding.only(bottom=4),
        show_default_drag_handles=False,  # we supply our own drag handle icon
    )

    def refresh_chapter_list():
        path = repo_path_holder["value"]
        if not path:
            return
        if not chapters_dir(path).exists():
            chapter_reorder_list.controls.clear()
            chapter_order["value"] = []
            page.update()
            return
        items = list_chapters_with_versions(path)
        chapter_order["value"] = [num for num, _ver, _p in items]
        chapter_reorder_list.controls.clear()
        for num, ver, md_path in items:
            is_active = (current_md_path["value"] == md_path)

            chapter_reorder_list.controls.append(
                ft.Container(
                    key=str(num),
                    content=ft.Row(
                        [
                            # Drag handle
                            ft.ReorderableDraggable(
                                index=chapter_order["value"].index(num),
                                content=ft.Container(
                                    ft.Icon(
                                        ft.Icons.DRAG_INDICATOR,
                                        color=_BORDER,
                                        size=14,
                                    ),
                                    padding=ft.padding.only(left=4, right=2),
                                ),
                            ),
                            # Chapter label (clickable)
                            ft.Container(
                                ft.Column(
                                    [
                                        ft.Text(
                                            f"Ch. {num}",
                                            size=12,
                                            color=_TEXT if is_active else _TEXT_MUTED,
                                            weight=ft.FontWeight.W_500 if is_active
                                                   else ft.FontWeight.NORMAL,
                                        ),
                                        ft.Text(
                                            ver, size=10,
                                            color=_ACCENT if is_active else _BORDER,
                                        ),
                                    ],
                                    spacing=1, tight=True,
                                ),
                                expand=True,
                                on_click=lambda e, p=md_path: load_chapter_file(p),
                                padding=ft.padding.symmetric(vertical=7),
                                ink=True,
                                bgcolor=_SURFACE2 if is_active else None,
                                border_radius=4,
                            ),
                            # Delete button
                            ft.IconButton(
                                icon=ft.Icons.CLOSE,
                                icon_size=12,
                                icon_color=_BORDER,
                                tooltip=f"Delete Chapter {num}",
                                on_click=lambda e, n=num: _confirm_delete_chapter(n),
                                style=ft.ButtonStyle(
                                    padding=ft.padding.all(4),
                                    overlay_color={
                                        ft.ControlState.HOVERED: "#33E05C5C",
                                    },
                                ),
                            ),
                        ],
                        spacing=0,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.padding.symmetric(horizontal=4),
                )
            )
        page.update()

    sidebar = ft.Container(
        ft.Column(
            [
                ft.Container(
                    ft.Row(
                        [
                            ft.Text("Chapters", size=11, color=_TEXT_MUTED,
                                    weight=ft.FontWeight.W_500),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    padding=ft.padding.only(left=12, right=8, top=14, bottom=8),
                ),
                ft.Container(chapter_reorder_list, expand=True),
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
        width=172,
        bgcolor=_SURFACE,
        border=ft.border.only(right=ft.BorderSide(1, _BORDER)),
    )

    # ── Chapter panel header (filename + close button) ────────────────────────

    chapter_panel_title = ft.Text(
        "New document", size=12, color=_TEXT_MUTED,
        overflow=ft.TextOverflow.ELLIPSIS, expand=True,
    )

    def _close_chapter_panel(e=None):
        """Close the current chapter / scratch-pad and return to blank scratch."""
        # Guard: if scratch has unsaved content in an actual chapter, prompt first
        if current_md_path["value"] is not None and editor_dirty["value"]:
            def _discard(e2):
                page.close(dlg)
                _clear_chapter_editor()
                page.update()
            def _save_then_close(e2):
                page.close(dlg)
                save_current()
                _clear_chapter_editor()
            dlg = ft.AlertDialog(
                bgcolor=_SURFACE, modal=True,
                title=_heading("Unsaved changes", size=18),
                content=ft.Container(
                    ft.Text("Save changes before closing?", color=_TEXT_MUTED, size=13),
                    width=280,
                ),
                actions=[
                    _ghost_btn("Cancel", on_click=lambda e2: page.close(dlg)),
                    _ghost_btn("Save & close", on_click=_save_then_close),
                    ft.TextButton("Discard", on_click=_discard,
                        style=ft.ButtonStyle(
                            color={ft.ControlState.DEFAULT: _ERROR,
                                   ft.ControlState.HOVERED: "#FF7070"},
                            padding=ft.padding.symmetric(horizontal=12, vertical=8),
                        )),
                ],
                shape=ft.RoundedRectangleBorder(radius=10),
            )
            page.open(dlg)
            page.update()
            return
        _clear_chapter_editor()
        page.update()

    def _clear_chapter_editor():
        """Reset editor to blank scratch state."""
        current_md_path["value"] = None
        _save_dialog_pending["value"] = False
        md_content["value"] = ""
        md_preview.value = ""
        raw_editor.value = ""
        status_chapter.value = ""
        chapter_panel_title.value = "New document"
        _scratch_placeholder.visible = True
        editor_mode["value"] = "preview"
        preview_layer.visible = True
        edit_layer.visible = False
        _mark_dirty(False)
        _update_word_count_internal()
        refresh_chapter_list()

    chapter_panel_header = ft.Container(
        ft.Row(
            [
                ft.Icon(ft.Icons.ARTICLE_OUTLINED, size=12, color=_TEXT_MUTED),
                ft.Container(width=6),
                chapter_panel_title,
                ft.IconButton(
                    icon=ft.Icons.CLOSE,
                    icon_size=12,
                    icon_color=_TEXT_MUTED,
                    tooltip="Close file",
                    on_click=_close_chapter_panel,
                    style=ft.ButtonStyle(padding=ft.padding.all(4)),
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
        ),
        padding=ft.padding.only(left=12, right=4, top=6, bottom=6),
        bgcolor=_SURFACE,
        border=ft.border.only(bottom=ft.BorderSide(1, _BORDER)),
    )

    # ── Planning pane ──────────────────────────────────────────────────────────

    planning_open = {"value": False}
    planning_editor_open = {"value": False}  # True when a planning file is loaded
    planning_file_list = ft.Column([], scroll=ft.ScrollMode.AUTO, expand=True, spacing=0)
    current_planning_path = {"value": None}

    # Planning uses the same dual-mode editor widgets as the chapter editor,
    # but with its own content buffer so switching panes doesn't clobber work.
    planning_md_content = {"value": ""}

    planning_preview = ft.Markdown(
        value="",
        extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED,
        selectable=True,
        fit_content=True,
        md_style_sheet=_md_stylesheet,
        code_theme=ft.MarkdownCodeTheme.TOMORROW_NIGHT,
    )

    planning_editor_mode = {"value": "preview"}

    def _planning_enter_edit(e=None):
        if planning_editor_mode["value"] == "edit":
            return
        planning_editor_mode["value"] = "edit"
        planning_raw.value = planning_md_content["value"]
        planning_preview_layer.visible = False
        planning_edit_layer.visible = True
        page.update()
        planning_raw.focus()

    def _planning_exit_edit(e=None):
        if planning_editor_mode["value"] != "edit":
            return
        new_text = planning_raw.value or ""
        planning_md_content["value"] = new_text
        planning_preview.value = new_text
        planning_editor_mode["value"] = "preview"
        planning_preview_layer.visible = True
        planning_edit_layer.visible = False
        # Auto-save planning file on blur
        p = current_planning_path["value"]
        if p:
            try:
                Path(p).write_text(new_text, encoding="utf-8")
            except Exception:
                pass
        page.update()

    def _on_planning_raw_change(e):
        planning_md_content["value"] = planning_raw.value or ""
        page.update()

    planning_raw = ft.TextField(
        multiline=True,
        min_lines=30,
        expand=True,
        text_style=ft.TextStyle(color=_TEXT, font_family="monospace", size=14),
        cursor_color=_ACCENT,
        bgcolor=_BG,
        border_color="transparent",
        focused_border_color="transparent",
        content_padding=ft.padding.symmetric(horizontal=32, vertical=24),
        on_change=_on_planning_raw_change,
        on_blur=_planning_exit_edit,
    )

    planning_preview_layer = ft.Container(
        content=ft.Column(
            [
                ft.GestureDetector(
                    content=ft.Container(
                        content=ft.Column(
                            [
                                ft.Container(
                                    planning_preview,
                                    padding=ft.padding.symmetric(horizontal=32, vertical=24),
                                    expand=True,
                                ),
                                ft.GestureDetector(
                                    content=ft.Container(height=200),
                                    on_tap=_planning_enter_edit,
                                ),
                            ],
                            expand=True, spacing=0,
                        ),
                        bgcolor=_BG, expand=True,
                    ),
                    on_tap=_planning_enter_edit,
                )
            ],
            scroll=ft.ScrollMode.AUTO, expand=True, spacing=0,
        ),
        expand=True, bgcolor=_BG, visible=True,
    )

    planning_edit_layer = ft.Container(
        content=ft.Column(
            [planning_raw],
            scroll=ft.ScrollMode.AUTO, expand=True, spacing=0,
        ),
        expand=True, bgcolor=_BG, visible=False,
    )

    planning_editor_area = ft.Stack(
        [planning_preview_layer, planning_edit_layer],
        expand=True,
    )

    # ── Planning editor panel header (filename + close button) ─────────────────
    planning_panel_title = ft.Text(
        "", size=12, color=_TEXT_MUTED,
        overflow=ft.TextOverflow.ELLIPSIS, expand=True,
    )

    def _close_planning_editor(e=None):
        """Close the planning editor panel (auto-saved on blur already)."""
        current_planning_path["value"] = None
        planning_md_content["value"] = ""
        planning_preview.value = ""
        planning_raw.value = ""
        planning_panel_title.value = ""
        planning_editor_mode["value"] = "preview"
        planning_preview_layer.visible = True
        planning_edit_layer.visible = False
        planning_editor_panel.visible = False
        planning_editor_open["value"] = False
        _adjust_window_for_planning(editor_open=False)
        refresh_planning_list()

    planning_panel_header = ft.Container(
        ft.Row(
            [
                ft.Icon(ft.Icons.ARTICLE_OUTLINED, size=12, color=_TEXT_MUTED),
                ft.Container(width=6),
                planning_panel_title,
                ft.IconButton(
                    icon=ft.Icons.CLOSE,
                    icon_size=12,
                    icon_color=_TEXT_MUTED,
                    tooltip="Close planning file",
                    on_click=_close_planning_editor,
                    style=ft.ButtonStyle(padding=ft.padding.all(4)),
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
        ),
        padding=ft.padding.only(left=12, right=4, top=6, bottom=6),
        bgcolor=_SURFACE,
        border=ft.border.only(
            left=ft.BorderSide(1, _BORDER),
            bottom=ft.BorderSide(1, _BORDER),
        ),
    )

    planning_editor_panel = ft.Container(
        ft.Column(
            [planning_panel_header, planning_editor_area],
            spacing=0, expand=True,
        ),
        expand=True,
        visible=False,
    )

    _PLANNING_EDITOR_WIDTH = 440  # px added to window when planning editor opens

    def _adjust_window_for_planning(editor_open: bool):
        """Grow / shrink the window width when the planning editor panel appears."""
        try:
            if editor_open:
                page.window.width = (page.window.width or 1280) + _PLANNING_EDITOR_WIDTH
            else:
                page.window.width = max(
                    900,
                    (page.window.width or 1280) - _PLANNING_EDITOR_WIDTH,
                )
        except Exception:
            pass

    def load_planning_file(path: Path):
        was_open = planning_editor_open["value"]
        current_planning_path["value"] = path
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            text = ""
        planning_md_content["value"] = text
        planning_preview.value = text
        planning_raw.value = text
        planning_panel_title.value = path.name
        planning_editor_mode["value"] = "preview"
        planning_preview_layer.visible = True
        planning_edit_layer.visible = False
        if not was_open:
            planning_editor_open["value"] = True
            planning_editor_panel.visible = True
            _adjust_window_for_planning(editor_open=True)
        refresh_planning_list()

    def refresh_planning_list():
        path = repo_path_holder["value"]
        if not path:
            return
        ensure_planning_structure(path)
        entries = list_planning_files(path)
        planning_file_list.controls.clear()
        for label, fpath, is_dir in entries:
            depth = label.count("/")
            indent = depth * 12
            is_active = (
                not is_dir and current_planning_path["value"] == fpath
            )
            icon = ft.Icons.FOLDER_OUTLINED if is_dir else ft.Icons.ARTICLE_OUTLINED
            icon_color = _TEXT_MUTED if is_dir else (_ACCENT if is_active else _TEXT_MUTED)
            name = fpath.name if not is_dir else fpath.name
            planning_file_list.controls.append(
                ft.Container(
                    ft.Row(
                        [
                            ft.Container(width=indent),
                            ft.Icon(icon, size=12, color=icon_color),
                            ft.Container(width=4),
                            ft.Text(
                                name,
                                size=12,
                                color=_TEXT if is_active else _TEXT_MUTED,
                                weight=ft.FontWeight.W_500 if is_active
                                       else ft.FontWeight.NORMAL,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                expand=True,
                            ),
                        ],
                        spacing=0,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.padding.symmetric(horizontal=8, vertical=5),
                    bgcolor=_SURFACE2 if is_active else None,
                    border_radius=4,
                    ink=not is_dir,
                    on_click=(lambda e, p=fpath: load_planning_file(p)) if not is_dir else None,
                )
            )
        page.update()

    def tool_new_planning_file(e):
        path = repo_path_holder["value"]
        if not path:
            return
        name_field = _styled_field("File name (e.g. Notes.md)", width=280)

        def do_create(e2):
            name = (name_field.value or "").strip()
            if not name:
                return
            try:
                new_path = create_planning_file(path, name)
                page.close(dlg)
                refresh_planning_list()
                load_planning_file(new_path)
            except Exception as ex:
                page.open(ft.SnackBar(ft.Text(str(ex))))
            page.update()

        dlg = ft.AlertDialog(
            bgcolor=_SURFACE,
            title=_heading("New planning file", size=18),
            content=ft.Container(name_field, width=300),
            actions=[
                _ghost_btn("Cancel", on_click=lambda e2: page.close(dlg)),
                _primary_btn("Create", on_click=do_create),
            ],
            shape=ft.RoundedRectangleBorder(radius=10),
        )
        page.open(dlg)
        page.update()

    def _close_planning_list(e=None):
        """Close the planning file-list sidebar (and editor if open)."""
        planning_open["value"] = False
        planning_list_panel.visible = False
        if planning_editor_open["value"]:
            _close_planning_editor()
        page.update()

    def toggle_planning_pane(e=None):
        if planning_open["value"]:
            _close_planning_list()
        else:
            planning_open["value"] = True
            planning_list_panel.visible = True
            refresh_planning_list()
            page.update()

    planning_list_panel = ft.Container(
        ft.Column(
            [
                # Header row
                ft.Container(
                    ft.Row(
                        [
                            ft.Text("Planning", size=11, color=_TEXT_MUTED,
                                    weight=ft.FontWeight.W_500),
                            ft.Container(expand=True),
                            ft.IconButton(
                                icon=ft.Icons.ADD,
                                icon_size=14,
                                icon_color=_TEXT_MUTED,
                                tooltip="New planning file",
                                on_click=tool_new_planning_file,
                                style=ft.ButtonStyle(padding=ft.padding.all(4)),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.CLOSE,
                                icon_size=12,
                                icon_color=_TEXT_MUTED,
                                tooltip="Close planning",
                                on_click=_close_planning_list,
                                style=ft.ButtonStyle(padding=ft.padding.all(4)),
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.padding.only(left=12, right=4, top=8, bottom=8),
                ),
                # File list
                ft.Container(planning_file_list, expand=True),
            ],
            spacing=0,
            expand=True,
        ),
        width=180,
        bgcolor=_SURFACE,
        border=ft.border.only(left=ft.BorderSide(1, _BORDER)),
        visible=False,
    )

    # Keep old name as alias for code that still references planning_pane
    planning_pane = planning_list_panel

    # ── Overflow menu — all less-frequent tools ────────────────────────────────
    tools_menu = ft.PopupMenuButton(
        content=ft.Container(
            ft.Icon(ft.Icons.MORE_HORIZ, color=_TEXT_MUTED, size=16),
            padding=ft.padding.symmetric(horizontal=8, vertical=4),
            border_radius=4,
            ink=True,
        ),
        items=[
            ft.PopupMenuItem(
                content=ft.Text("Planning", color=_TEXT, size=13),
                on_click=toggle_planning_pane,
            ),
            ft.PopupMenuItem(),  # divider
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

    # ── Status bar ─────────────────────────────────────────────────────────────
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

    # ── Chapter editor panel (header + editor area) ────────────────────────────
    chapter_panel = ft.Container(
        ft.Column(
            [chapter_panel_header, editor_area],
            spacing=0, expand=True,
        ),
        expand=True,
    )

    # ── Main editor layout ─────────────────────────────────────────────────────
    editor_content = ft.Column(
        [
            ft.Row(
                [
                    sidebar,
                    chapter_panel,
                    planning_editor_panel,
                    planning_list_panel,
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
            # Start with a blank scratch pad if no chapter is loaded
            if current_md_path["value"] is None:
                md_content["value"] = ""
                md_preview.value = ""
                raw_editor.value = ""
                _save_dialog_pending["value"] = False
                _scratch_placeholder.visible = True
                editor_mode["value"] = "preview"
                preview_layer.visible = True
                edit_layer.visible = False
                status_chapter.value = ""
                _mark_dirty(False)
                _update_word_count_internal()
            page.views.append(
                ft.View("/editor", [editor_content], bgcolor=_BG, padding=0)
            )
        else:
            page.views.append(
                ft.View("/signin", [signin_content], bgcolor=_BG, padding=24)
            )
        page.update()

    page.on_route_change = route_change

    # ── Window-close guard ────────────────────────────────────────────────────
    # Intercept the OS close button when the scratch pad has unsaved content.
    page.window.prevent_close = True

    def _on_window_event(e):
        if e.data != "close":
            return
        scratch_dirty = (
            current_md_path["value"] is None
            and md_content["value"].strip()
        )
        if not scratch_dirty:
            page.window.destroy()
            return

        def _save_and_close(e2):
            page.close(close_dlg)
            _pending_close["value"] = True
            _save_dialog_pending["value"] = False
            _show_save_to_chapter_dialog()
            page.update()

        def _discard_and_close(e2):
            page.close(close_dlg)
            page.window.destroy()

        close_dlg = ft.AlertDialog(
            bgcolor=_SURFACE,
            modal=True,
            title=_heading("Unsaved scratch content", size=18),
            content=ft.Container(
                ft.Text(
                    "You have unsaved content in the scratch pad.\n"
                    "Save it before closing, or discard it?",
                    color=_TEXT_MUTED,
                    size=13,
                ),
                width=320,
            ),
            actions=[
                _ghost_btn("Cancel", on_click=lambda e2: page.close(close_dlg)),
                _ghost_btn("Save first…", on_click=_save_and_close),
                ft.TextButton(
                    "Discard & close",
                    on_click=_discard_and_close,
                    style=ft.ButtonStyle(
                        color={ft.ControlState.DEFAULT: _ERROR,
                               ft.ControlState.HOVERED: "#FF7070"},
                        padding=ft.padding.symmetric(horizontal=12, vertical=8),
                    ),
                ),
            ],
            shape=ft.RoundedRectangleBorder(radius=10),
        )
        page.open(close_dlg)
        page.update()

    page.window.on_event = _on_window_event

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
