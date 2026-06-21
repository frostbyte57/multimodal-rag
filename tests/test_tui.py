import asyncio

from mmrag.config import CONFIG
from mmrag.tui import MMRagTUI, SettingsScreen


def test_tui_loads_corpus_and_answers():
    async def scenario():
        app = MMRagTUI()
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.workers.wait_for_complete()  # initial corpus ingest
            assert app.session.chunk_count > 0

            # Submit a question through the input.
            inp = app.query_one("#q")
            inp.value = "What is the VCCAUX voltage for Artix-7?"
            await pilot.press("enter")
            await app.workers.wait_for_complete()

            # A query worker ran without error and the session still has chunks.
            assert app.session.chunk_count > 0

            # A slash command updates filters.
            inp.value = "/filter doc_type=errata"
            await pilot.press("enter")
            await pilot.pause()
            assert app.filters.get("doc_type") == "errata"

    asyncio.run(scenario())


def test_settings_screen_opens_and_applies(tmp_path, monkeypatch):
    # Don't write the real .mmrag.json during the test.
    monkeypatch.setattr("mmrag.config.CONFIG_PATH", tmp_path / ".mmrag.json")

    async def scenario():
        app = MMRagTUI()
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.workers.wait_for_complete()

            app.action_settings()  # opens the modal
            await pilot.pause()
            assert isinstance(app.screen, SettingsScreen)

            # Change a value and save (widgets live on the modal screen).
            app.screen.query_one("#cfg-max_chunk_tokens").value = "321"
            app.screen.query_one("#save").press()
            await pilot.pause()
            await app.workers.wait_for_complete()

            assert CONFIG.max_chunk_tokens == 321
            assert (tmp_path / ".mmrag.json").exists()
            # Session was rebuilt and still has the corpus.
            assert app.session.chunk_count > 0

    asyncio.run(scenario())
