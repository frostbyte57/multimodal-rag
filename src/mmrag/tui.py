"""Terminal UI for the multimodal RAG assistant.

Ask questions in natural language, or use slash commands to manage the corpus:

    /attach <path>     ingest a file or folder (recursively)
    /reload            re-scan the default corpus dir for new files
    /filter k=v ...    set metadata filters for subsequent queries
    /filter            clear all filters
    /docs              list indexed documents
    /help              show commands
    /quit              exit

You can also drop files into ``data/corpus/`` and run ``/reload``.

Run with:  mmrag-tui   (or  python scripts/tui.py)
"""

from __future__ import annotations

import asyncio

from rich.console import Group
from rich.panel import Panel
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, Label, RichLog, Static

from .config import CONFIG
from .generate.answer import AnswerResult
from .session import RagSession

# (config key, label, is_password) for the settings screen.
SETTINGS_FIELDS = [
    ("anthropic_api_key", "Anthropic API key (blank = offline generation)", True),
    ("voyage_api_key", "Voyage API key (blank = offline embeddings)", True),
    ("generation_model", "Generation model", False),
    ("embedding_model", "Embedding model", False),
    ("rerank_model", "Rerank model", False),
    ("embedding_dim", "Embedding dimension", False),
    ("database_url", "Postgres URL (used when store = postgres)", False),
    ("pg_table", "Postgres table", False),
    ("neo4j_uri", "Neo4j URI", False),
    ("neo4j_user", "Neo4j User", False),
    ("neo4j_password", "Neo4j Password", True),
    ("max_chunk_tokens", "Max chunk tokens", False),
    ("ollama_base_url", "Ollama Base URL (e.g. http://localhost:11434)", False),
    ("ollama_model", "Ollama Model", False),
]

WELCOME = (
    "[b]Multimodal RAG[/b] — ask a question, or attach documents.\n"
    "Commands: [cyan]/attach <path>[/], [cyan]/reload[/], [cyan]/filter k=v[/], "
    "[cyan]/config[/] (or F2), [cyan]/help[/], [cyan]/quit[/].  "
    "Drop files into [cyan]data/corpus/[/] then [cyan]/reload[/]. "
    "Set API keys & vector store in [cyan]/config[/] — no env vars needed."
)

HELP = """[b]Commands[/b]
  [cyan]/attach <path>[/]   Ingest a file or folder (recurses into subfolders).
                    e.g. /attach ~/papers   or   /attach data/corpus/foo.md
  [cyan]/reload[/]          Re-scan the default corpus dir for new files.
  [cyan]/filter k=v ...[/]  Filter retrieval by metadata (repeatable keys).
                    e.g. /filter doc_type=errata stepping=ES1
  [cyan]/filter[/]          Clear all filters.
  [cyan]/pin <version>[/]   Pin a document revision (e.g. /pin v1.5). /pin clears.
  [cyan]/docs[/]            List indexed documents.
  [cyan]/config[/]          Open settings (API keys, models, store). Also F2.
  [cyan]/help[/]            This message.
  [cyan]/quit[/]            Exit (also Ctrl+C).
Anything else is treated as a question."""


class SettingsScreen(ModalScreen[dict | None]):
    """Modal form for all configuration — persisted to .mmrag.json on save."""

    CSS = """
    SettingsScreen { align: center middle; }
    #box {
        width: 84; max-height: 90%; padding: 1 2;
        border: round $primary; background: $surface;
    }
    #box Label { margin-top: 1; color: $text-muted; }
    #box Input { width: 100%; }
    #buttons { height: auto; align-horizontal: right; margin-top: 1; }
    #buttons Button { margin-left: 2; }
    .title { text-style: bold; margin-bottom: 1; }
    """

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="box"):
            yield Static("Settings — saved to .mmrag.json", classes="title")
            for key, label, pw in SETTINGS_FIELDS:
                yield Label(label)
                val = getattr(CONFIG, key)
                yield Input(value="" if val is None else str(val), password=pw, id=f"cfg-{key}")
            with Horizontal(id="buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Save", variant="success", id="save")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        result: dict = {}
        for key, _, _ in SETTINGS_FIELDS:
            result[key] = self.query_one(f"#cfg-{key}", Input).value
        self.dismiss(result)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)


class MMRagTUI(App):
    CSS = """
    Screen { layout: vertical; }
    #status {
        dock: top; height: 1; padding: 0 1;
        background: $panel; color: $text-muted;
    }
    #log { height: 1fr; padding: 0 1; background: $surface; }
    #prompt { dock: bottom; height: 3; }
    Input { border: round $primary; }
    """

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+l", "clear_log", "Clear"),
        ("f2", "settings", "Settings"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.session = RagSession()
        self.filters: dict[str, object] = {}
        self.pin_version: str | None = None
        # Roots the user has attached, re-ingested when settings change.
        self.attached_roots: list[str] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("", id="status")
        yield RichLog(id="log", wrap=True, markup=True, highlight=False)
        with Vertical(id="prompt"):
            yield Input(
                placeholder="Ask a question, or /attach <path>, /config, /help …",
                id="q",
            )
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Multimodal RAG"
        self._log(WELCOME)
        self._refresh_status()
        self.query_one("#q", Input).focus()
        # Load the default corpus in the background so the UI is responsive.
        self._ingest(str(CONFIG.corpus_dir), announce=False)

    # -- helpers ------------------------------------------------------------
    def _log(self, renderable) -> None:
        self.query_one("#log", RichLog).write(renderable)

    def _refresh_status(self) -> None:
        s = self.session
        filt = " ".join(f"{k}={v}" for k, v in self.filters.items()) or "none"
        pin = self.pin_version or "latest"
        self.query_one("#status", Static).update(
            f"docs:{s.doc_count}  chunks:{s.chunk_count}  images:{s.image_count}  "
            f"│ filters:{filt}  rev:{pin}  │ {s.backend_label}"
        )

    def action_clear_log(self) -> None:
        self.query_one("#log", RichLog).clear()
        self._log(WELCOME)

    # -- input handling -----------------------------------------------------
    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""
        if not text:
            return
        if text.startswith("/"):
            self._handle_command(text)
        else:
            self._log(Text(f"❯ {text}", style="bold cyan"))
            self._run_query(text)

    def _handle_command(self, text: str) -> None:
        parts = text.split()
        cmd, args = parts[0].lower(), parts[1:]
        if cmd in ("/quit", "/exit", "/q"):
            self.exit()
        elif cmd == "/help":
            self._log(Panel(HELP, border_style="blue", title="help"))
        elif cmd == "/attach":
            if not args:
                self._log(Text("usage: /attach <path>", style="yellow"))
            else:
                self._ingest(" ".join(args), announce=True)
        elif cmd == "/reload":
            self._ingest(str(CONFIG.corpus_dir), announce=True)
        elif cmd == "/filter":
            self._set_filters(args)
        elif cmd == "/pin":
            self.pin_version = args[0] if args else None
            self._log(Text(f"revision pin: {self.pin_version or 'latest'}", style="green"))
            self._refresh_status()
        elif cmd == "/docs":
            self._list_docs()
        elif cmd == "/config":
            self.action_settings()
        else:
            self._log(Text(f"unknown command: {cmd} (try /help)", style="yellow"))

    # -- settings -----------------------------------------------------------
    def action_settings(self) -> None:
        self.push_screen(SettingsScreen(), self._on_settings_saved)

    def _on_settings_saved(self, result: dict | None) -> None:
        if not result:
            return
        CONFIG.update(**result)
        path = CONFIG.save()
        self._log(Text(f"✓ settings saved → {path.name}; re-indexing…", style="green"))
        self._rebuild_session()

    @work(exclusive=True)
    async def _rebuild_session(self) -> None:
        roots = list(dict.fromkeys([str(CONFIG.corpus_dir), *self.attached_roots]))

        def build() -> RagSession:
            s = RagSession()
            for root in roots:
                s.ingest_path(root)
            return s

        try:
            new_session = await asyncio.to_thread(build)
        except Exception as exc:  # noqa: BLE001 - keep the old session, report
            self._log(Text(f"✗ settings not applied: {exc}", style="red"))
            self._log(Text("  (kept previous configuration)", style="dim"))
            return
        self.session = new_session
        self._log(Text("✓ configuration applied", style="green"))
        self._refresh_status()

    def _set_filters(self, args: list[str]) -> None:
        if not args:
            self.filters = {}
            self._log(Text("filters cleared", style="green"))
        else:
            for item in args:
                if "=" in item:
                    k, _, v = item.partition("=")
                    vals = [p.strip() for p in v.split(",") if p.strip()]
                    self.filters[k.strip()] = vals if len(vals) > 1 else vals[0]
            self._log(Text(f"filters: {self.filters}", style="green"))
        self._refresh_status()

    def _list_docs(self) -> None:
        seen: dict[str, str] = {}
        for c in self.session.chunks:
            seen.setdefault(c.doc_id, f"{c.doc_id}  {c.version}  [{c.doc_type}]  {c.title}")
        if not seen:
            self._log(Text("no documents indexed", style="yellow"))
            return
        body = "\n".join(f"• {v}" for v in seen.values())
        self._log(Panel(body, title=f"{len(seen)} documents", border_style="blue"))

    # -- workers (off the UI thread) ---------------------------------------
    @work(exclusive=False)
    async def _ingest(self, path: str, announce: bool) -> None:
        if announce:
            self._log(Text(f"… ingesting {path}", style="dim"))
        # Remember attached roots so a config change can re-index them.
        if path not in self.attached_roots and path != str(CONFIG.corpus_dir):
            self.attached_roots.append(path)
        files, chunks, errors = await asyncio.to_thread(self.session.ingest_path, path)
        for e in errors:
            self._log(Text(f"  ✗ {e}", style="red"))
        if files or announce:
            msg = (
                f"indexed {files} file(s), {chunks} chunk(s) from {path}"
                if files
                else f"nothing new to index in {path}"
            )
            self._log(Text(f"✓ {msg}", style="green"))
        self._refresh_status()

    @work(exclusive=True)
    async def _run_query(self, question: str) -> None:
        result = await asyncio.to_thread(
            self.session.query, question, self.filters or None, self.pin_version
        )
        self._log(_render_answer(result))


def _render_answer(result: AnswerResult) -> Group:
    parts: list = []
    style = "yellow" if result.unsupported else "white"
    parts.append(Panel(Text(result.answer, style=style), border_style="grey50"))
    for w in result.warnings:
        parts.append(Text(f"⚠ {w}", style="yellow"))
    if result.citations:
        lines = Text()
        for c in result.citations:
            sup = f"  (superseded by {c.superseded_by})" if c.superseded_by else ""
            lines.append(f"• {c.label}{sup}\n", style="cyan")
            if c.cited_text:
                snip = c.cited_text.strip().replace("\n", " ")
                lines.append(f"    “{snip[:160]}”\n", style="dim")
        parts.append(Panel(lines, title=f"sources ({len(result.citations)})", border_style="blue"))
    else:
        parts.append(Text("no citations — answer not grounded", style="dim red"))
    return Group(*parts)


def main() -> None:
    # All configuration comes from .mmrag.json (edited in the settings screen).
    # Fresh installs default to the offline in-memory store, so this just works.
    MMRagTUI().run()


if __name__ == "__main__":
    main()
