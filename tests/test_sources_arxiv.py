"""Tests for the arXiv source plugin. Run: python3 -m tests.test_sources_arxiv"""
import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from lodestone.plugins.arxiv import ArxivSource


def test_arxiv_metadata():
    src = ArxivSource()
    assert src.name == "arxiv"
    assert "categories" in src.config_schema["properties"]


def test_arxiv_crawl_parses_atom():
    fake_atom = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.1</id>
    <title>Test Paper</title>
    <summary>abstract</summary>
  </entry>
</feed>"""

    async def fake(url: str, **kw) -> str:
        return fake_atom

    async def run():
        src = ArxivSource()
        with patch.object(src, "_fetch", side_effect=fake):
            out = []
            async for r in src.crawl():
                out.append(r)
            assert len(out) == 1
            assert "2401.1" in out[0].name
            assert out[0].description == "abstract"

    asyncio.run(run())


if __name__ == "__main__":
    for name, fn in sorted(
        {k: v for k, v in globals().items() if k.startswith("test_") and callable(v)}.items()
    ):
        fn()
        print(f"✓ {name}")
    print("\nAll tests passed.")
