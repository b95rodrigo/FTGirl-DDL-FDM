"""Offline checks for the FDM bridge; no browser or network access required."""
from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import AsyncMock, patch
import zlib

MODULE_FILE = Path(__file__).resolve().parents[1] / "plugin" / "python" / "fdm_bridge.py"
SPEC = importlib.util.spec_from_file_location("fdm_bridge", MODULE_FILE)
bridge = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(bridge)

FF = "https://fuckingfast.co/abc123#game.part01.rar"
FF2 = "https://fuckingfast.co/f/xyz_9#game.part02.rar"
PASTE = "https://paste.fitgirl-repacks.site/?abcdef#key"


class UrlTests(TestCase):
    def test_upstream_version(self):
        self.assertEqual(bridge.UPSTREAM_VERSION, "0.4.12")
        self.assertEqual(bridge.ZENDRIVER_VERSION, "0.17.1")

    def test_filename(self):
        self.assertEqual(bridge.filename_from_url(FF), "game.part01.rar")
        self.assertEqual(bridge.filename_from_url("https://fuckingfast.co/a#hello%20world.rar"), "hello world.rar")

    def test_id_legacy_and_f_path(self):
        self.assertEqual(bridge.extract_file_id(FF), "abc123")
        self.assertEqual(bridge.extract_file_id(FF2), "xyz_9")

    def test_reject_bad_hosts_and_paths(self):
        for url in [
            "http://fuckingfast.co/abc", "https://example.com/abc",
            "https://fuckingfast.co.evil.test/abc",
            "https://fuckingfast.co:443/abc", "https://fuckingfast.co/dl/abc",
            "https://fuckingfast.co/f/abc/go",
        ]:
            with self.subTest(url=url):
                self.assertFalse(bridge.is_ff_page(url))
                with self.assertRaises(ValueError):
                    bridge.extract_file_id(url)


class PrivateBinTests(TestCase):
    def test_raw_deflate(self):
        raw = json.dumps({"paste": "hello"}).encode()
        compressor = zlib.compressobj(wbits=-zlib.MAX_WBITS)
        packed = compressor.compress(raw) + compressor.flush()
        self.assertEqual(bridge._decode_privatebin_payload(packed, "zlib"), {"paste": "hello"})

    def test_zlib_wrapper(self):
        self.assertEqual(
            bridge._decode_privatebin_payload(zlib.compress(b'{"paste":"ok"}'), "zlib"),
            {"paste": "ok"},
        )

    def test_uncompressed(self):
        self.assertEqual(bridge._decode_privatebin_payload(b'{"paste":"hi"}', "none"), {"paste": "hi"})


class BridgeTests(TestCase):
    def test_playlist_returns_page_links_without_resolving(self):
        with patch.object(bridge, "scrape_paste_http", return_value=[FF, FF, FF2, "https://evil.test/a"]):
            with patch.object(bridge, "resolve_direct_http", side_effect=AssertionError("too early")):
                data = asyncio.run(bridge.resolve_source(PASTE))
        self.assertTrue(data["ok"])
        self.assertEqual([item["source_url"] for item in data["items"]], [FF, FF2])
        self.assertTrue(all("direct_url" not in item for item in data["items"]))

    def test_http_resolve_one(self):
        with patch.object(bridge, "resolve_direct_http", return_value="https://cdn.example.net/file"):
            data = asyncio.run(bridge.resolve_one(FF))
        self.assertEqual(data["items"][0]["direct_url"], "https://cdn.example.net/file")

    def test_browser_fallback_for_paste(self):
        fake_tab = object()
        fake_browser = SimpleNamespace(get=AsyncMock(return_value=fake_tab), stop=AsyncMock())
        with patch.object(bridge, "scrape_paste_http", side_effect=OSError("blocked")):
            with patch.object(bridge, "start_browser", new=AsyncMock(return_value=fake_browser)):
                with patch.object(bridge, "scrape_paste_browser", new=AsyncMock(return_value=[FF])):
                    data = asyncio.run(bridge.resolve_source(PASTE))
        self.assertEqual(data["items"][0]["source_url"], FF)
        fake_browser.stop.assert_awaited_once()

    def test_five_browser_attempts_with_recovery(self):
        class FakeTab:
            def __init__(self):
                self.calls = 0
                self.visited = []
            async def evaluate(self, *args, **kwargs):
                self.calls += 1
                if self.calls < 5:
                    return {"status": 503, "headers": {}}
                return {"status": 200, "headers": {"hx-redirect": "https://cdn.example.net/file"}}
            async def get(self, url):
                self.visited.append(url)
            async def wait_for_ready_state(self, *args, **kwargs):
                pass

        tab = FakeTab()
        with patch.object(bridge.asyncio, "sleep", new=AsyncMock()):
            url = asyncio.run(bridge.extract_direct_browser(tab, FF))
        self.assertEqual(url, "https://cdn.example.net/file")
        self.assertEqual(tab.calls, 5)
        self.assertIn("https://fuckingfast.co", tab.visited)

    def test_spoiler_selector_from_upstream(self):
        class Tag:
            def __init__(self, href, text=""):
                self.attrs = {"href": href}
                self.text_all = text
        class FakeTab:
            selectors = []
            async def get(self, url):
                pass
            async def wait_for(self, *args, **kwargs):
                pass
            async def query_selector_all(self, selector):
                self.selectors.append(selector)
                if selector.endswith("> a") and "li:nth-child(2)" in selector:
                    return [Tag(PASTE, "Filehoster: FuckingFast")]
                if selector == "div.su-spoiler > div.su-spoiler-content > a":
                    return [Tag(FF2), Tag(FF), Tag("https://example.org/ignore")]
                return []
        tab = FakeTab()
        data = asyncio.run(bridge.scrape_fitgirl_post(tab, "https://fitgirl-repacks.site/any-game/"))
        self.assertEqual(set(data), {FF, FF2})
        self.assertIn("div.su-spoiler > div.su-spoiler-content > a", tab.selectors)


if __name__ == "__main__":
    import unittest
    unittest.main()
