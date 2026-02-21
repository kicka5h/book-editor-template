"""Flet UI for the Book Editor desktop app."""

import re
import threading
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


def main(page: ft.Page) -> None:
    page.title = "Book Editor"
    page.window.min_width = 900
    page.window.min_height = 600
    page.theme_mode = ft.ThemeMode.LIGHT

    config = load_config()
    token_holder = {"value": (config.get("github_token") or "").strip()}
    current_md_path = {"value": None}
    editor_dirty = {"value": False}

    # --- Sign-in view (GitHub Device Flow) ---
    signin_user_code = ft.Text(
        "", size=32, weight=ft.FontWeight.BOLD, selectable=True
    )
    signin_instruction = ft.Text("")
    signin_error = ft.Text("", color=ft.Colors.ERROR)
    signin_progress = ft.ProgressRing(visible=False)
    signin_button = ft.ElevatedButton("Sign in with GitHub", disabled=False)

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

        # Open the browser for the user
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
            ft.Text("Sign in to GitHub", size=24, weight=ft.FontWeight.BOLD),
            ft.Text("Connect your GitHub account to store your book in a repository."),
            ft.Container(height=20),
            signin_button,
            ft.Container(height=16),
            signin_user_code,
            ft.Container(height=4),
            signin_instruction,
            ft.Container(height=8),
            ft.Row([signin_progress, signin_error]),
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    # --- Repo selection view ---
    repos_dropdown = ft.Dropdown(
        label="Choose a repository",
        width=420,
        options=[],
    )
    repo_progress = ft.ProgressRing(visible=False)
    repo_error = ft.Text("", color=ft.Colors.ERROR)
    create_repo_name_field = ft.TextField(label="New repository name", width=320)
    create_private_check = ft.Checkbox(label="Private repository", value=True)

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
            repos = load_repos()
            repo_progress.visible = False
            repos_dropdown.options = [
                ft.dropdown.Option(f"{owner}/{name}", key=f"{owner}|{name}|{url}")
                for owner, name, url in repos
            ]
            if not repos_dropdown.options:
                repo_error.value = "No repositories found."
            page.update()

        threading.Thread(target=_load, daemon=True).start()

    def on_select_repo(e):
        key = repos_dropdown.value
        if not key:
            repo_error.value = "Select a repository."
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
                page.snack_bar = ft.SnackBar(ft.Text("Enter a repository name."), open=True)
                page.update()
                return
            if not re.match(r"^[a-zA-Z0-9_.-]+$", name):
                page.snack_bar = ft.SnackBar(ft.Text("Use only letters, numbers, - and _."), open=True)
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
                page.snack_bar = ft.SnackBar(ft.Text(str(ex)), open=True)
                page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("Create new repository"),
            content=ft.Column(
                [
                    create_repo_name_field,
                    create_private_check,
                ],
                tight=True,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e2: page.close(dlg)),
                ft.ElevatedButton("Create and open", on_click=do_create),
            ],
        )
        page.open(dlg)
        page.update()

    repo_content = ft.Column(
        [
            ft.Text("Select repository", size=24, weight=ft.FontWeight.BOLD),
            ft.Text("Choose where to store your book, or create a new repository."),
            ft.Container(height=20),
            ft.Row([repos_dropdown, repo_progress], alignment=ft.MainAxisAlignment.START),
            ft.Container(height=8),
            ft.Row(
                [
                    ft.ElevatedButton("Use selected repository", on_click=on_select_repo),
                    ft.OutlinedButton("Create new repository", on_click=open_create_repo_dialog),
                ],
            ),
            ft.Container(height=8),
            repo_error,
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    # --- Editor view ---
    repo_path_holder = {"value": get_repo_path(config)}
    chapter_list = ft.Column([], scroll=ft.ScrollMode.AUTO, expand=True)
    editor = ft.TextField(
        multiline=True,
        min_lines=20,
        expand=True,
        text_style=ft.TextStyle(font_family="monospace"),
        on_change=lambda e: _set_dirty(True),
    )

    def _set_dirty(dirty: bool):
        editor_dirty["value"] = dirty
        save_btn_label.value = "Save (unsaved)" if dirty else "Save"
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
            chapter_list.controls.append(
                ft.ListTile(
                    title=ft.Text(f"Chapter {num}"),
                    subtitle=ft.Text(ver),
                    data=md_path,
                    on_click=lambda e, p=md_path: load_chapter_file(p),
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
        page.update()

    def save_current(e):
        path = current_md_path["value"]
        if not path:
            page.snack_bar = ft.SnackBar(ft.Text("No chapter open."), open=True)
            page.update()
            return
        try:
            Path(path).write_text(editor.value or "", encoding="utf-8")
            _set_dirty(False)
            token = token_holder["value"] or load_config().get("github_token")
            if token:
                try:
                    git_push(repo_path_holder["value"], token)
                    page.snack_bar = ft.SnackBar(ft.Text("Saved and pushed to GitHub."), open=True)
                except GitCommandError as err:
                    page.snack_bar = ft.SnackBar(ft.Text(f"Push failed: {err}"), open=True)
            else:
                page.snack_bar = ft.SnackBar(ft.Text("Saved locally. Sign in to push."), open=True)
        except Exception as ex:
            page.snack_bar = ft.SnackBar(ft.Text(f"Save failed: {ex}"), open=True)
        page.update()

    def tool_new_chapter(e):
        path = repo_path_holder["value"]
        if not path:
            page.snack_bar = ft.SnackBar(ft.Text("No project loaded."), open=True)
            page.update()
            return
        try:
            create_new_chapter(chapters_dir(path))
            refresh_chapter_list()
            page.snack_bar = ft.SnackBar(ft.Text("New chapter created."), open=True)
        except Exception as ex:
            page.snack_bar = ft.SnackBar(ft.Text(str(ex)), open=True)
        page.update()

    def tool_bump(e, bump_type: str):
        path = repo_path_holder["value"]
        cur = current_md_path["value"]
        if not path or not cur:
            page.snack_bar = ft.SnackBar(ft.Text("Open a chapter first."), open=True)
            page.update()
            return
        m = re.search(r"[Cc]hapter\s+(\d+)", str(cur))
        if not m:
            page.snack_bar = ft.SnackBar(ft.Text("Could not detect chapter number."), open=True)
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
            page.snack_bar = ft.SnackBar(ft.Text(f"Bumped {bump_type} for chapter {num}."), open=True)
        except Exception as ex:
            page.snack_bar = ft.SnackBar(ft.Text(str(ex)), open=True)
        page.update()

    def tool_increment(e):
        path = repo_path_holder["value"]
        if not path:
            page.snack_bar = ft.SnackBar(ft.Text("No project loaded."), open=True)
            page.update()
            return
        after = ft.TextField(label="Increment chapters after number", keyboard_type=ft.KeyboardType.NUMBER)

        def do_increment(e2):
            try:
                n = int(after.value)
                success = increment_chapters(str(chapters_dir(path)), n, confirm=False)
                if success:
                    refresh_chapter_list()
                    page.snack_bar = ft.SnackBar(ft.Text("Chapters renumbered."), open=True)
                page.close(dlg)
            except Exception as ex:
                page.snack_bar = ft.SnackBar(ft.Text(str(ex)), open=True)
            page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("Increment chapter numbers"),
            content=after,
            actions=[
                ft.TextButton("Cancel", on_click=lambda e2: page.close(dlg)),
                ft.ElevatedButton("OK", on_click=do_increment),
            ],
        )
        page.open(dlg)
        page.update()

    def tool_word_count(e):
        path = repo_path_holder["value"]
        if not path:
            page.snack_bar = ft.SnackBar(ft.Text("No project loaded."), open=True)
            page.update()
            return
        try:
            latest = find_latest_versions(chapters_dir(path))
            count_words_in_chapters(latest)
            total = sum(cv.word_count for cv in latest.values())
            page.snack_bar = ft.SnackBar(ft.Text(f"Total words (latest versions): {total:,}"), open=True)
        except Exception as ex:
            page.snack_bar = ft.SnackBar(ft.Text(str(ex)), open=True)
        page.update()

    def tool_format(e):
        path = current_md_path["value"]
        if not path:
            page.snack_bar = ft.SnackBar(ft.Text("Open a chapter first."), open=True)
            page.update()
            return
        try:
            changed = process_file(Path(path), in_place=True)
            if changed:
                editor.value = Path(path).read_text(encoding="utf-8")
                page.snack_bar = ft.SnackBar(ft.Text("Formatted."), open=True)
            else:
                page.snack_bar = ft.SnackBar(ft.Text("No formatting changes needed."), open=True)
        except Exception as ex:
            page.snack_bar = ft.SnackBar(ft.Text(str(ex)), open=True)
        page.update()

    def tool_generate_pdf(e):
        path = repo_path_holder["value"]
        if not path:
            page.snack_bar = ft.SnackBar(ft.Text("No project loaded."), open=True)
            page.update()
            return
        if not check_pandoc_available():
            page.snack_bar = ft.SnackBar(
                ft.Text("Pandoc is not installed. Install pandoc and a LaTeX engine (e.g. pdflatex) to generate PDFs."),
                open=True,
            )
            page.update()
            return
        title_field = ft.TextField(label="Book title", value="Book", width=320)
        author_field = ft.TextField(label="Author", value="", width=320)

        def do_pdf(e2):
            try:
                out = build_pdf(
                    path,
                    title=title_field.value or "Book",
                    author=author_field.value or "",
                )
                page.close(dlg)
                page.snack_bar = ft.SnackBar(ft.Text(f"PDF saved to {out}"), open=True)
            except Exception as ex:
                page.snack_bar = ft.SnackBar(ft.Text(f"PDF failed: {ex}"), open=True)
            page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("Generate PDF"),
            content=ft.Column([title_field, author_field], tight=True),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e2: page.close(dlg)),
                ft.ElevatedButton("Generate", on_click=do_pdf),
            ],
        )
        page.open(dlg)
        page.update()

    save_btn_label = ft.Text("Save")

    def go_setup(e):
        token_holder["value"] = load_config().get("github_token", "")
        page.go("/repo")
        page.update()

    toolbar = ft.Row(
        [
            ft.ElevatedButton("New chapter", on_click=tool_new_chapter),
            ft.PopupMenuButton(
                content=ft.Text("Bump version"),
                items=[
                    ft.PopupMenuItem(content=ft.Text("Minor"), on_click=lambda e: tool_bump(e, "minor")),
                    ft.PopupMenuItem(content=ft.Text("Patch"), on_click=lambda e: tool_bump(e, "patch")),
                    ft.PopupMenuItem(content=ft.Text("Major"), on_click=lambda e: tool_bump(e, "major")),
                ],
            ),
            ft.ElevatedButton("Increment chapters", on_click=tool_increment),
            ft.ElevatedButton("Word count", on_click=tool_word_count),
            ft.ElevatedButton("Format", on_click=tool_format),
            ft.ElevatedButton("Generate PDF", on_click=tool_generate_pdf),
            ft.Container(expand=True),
            ft.IconButton(ft.Icons.SETTINGS, tooltip="Settings", on_click=go_setup),
            ft.ElevatedButton(content=save_btn_label, on_click=save_current),
        ],
    )

    editor_content = ft.Column(
        [
            toolbar,
            ft.Container(height=8),
            ft.Row(
                [
                    ft.Container(
                        ft.Column(
                            [
                                ft.Text("Chapters", weight=ft.FontWeight.BOLD),
                                chapter_list,
                            ],
                            expand=True,
                        ),
                        width=220,
                        border=ft.border.all(1, ft.Colors.OUTLINE),
                        border_radius=8,
                        padding=8,
                    ),
                    ft.Container(editor, expand=True, margin=ft.margin.only(left=8)),
                ],
                expand=True,
            ),
        ],
        expand=True,
    )

    def route_change(e):
        page.views.clear()
        cfg = load_config()
        token_holder["value"] = (cfg.get("github_token") or "").strip()
        repo_path_holder["value"] = get_repo_path(cfg)

        if page.route == "/signin":
            page.views.append(ft.View("/signin", [signin_content], padding=24))
        elif page.route == "/repo":
            page.views.append(ft.View("/repo", [repo_content], padding=24))
            on_repo_view_visible()
        elif page.route == "/editor":
            if repo_path_holder["value"]:
                refresh_chapter_list()
            page.views.append(ft.View("/editor", [editor_content], padding=16))
        else:
            page.views.append(ft.View("/signin", [signin_content], padding=24))
        page.update()

    page.on_route_change = route_change

    # Initial route: sign in → select repo → editor (or editor if path missing, go to repo)
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
