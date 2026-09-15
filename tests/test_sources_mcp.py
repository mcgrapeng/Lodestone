"""Tests for the MCP Registry source plugin. Run: python3 -m tests.test_sources_mcp"""
import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from lodestone.plugins.mcp_registry import MCPRegistrySource


def test_mcp_metadata():
    src = MCPRegistrySource()
    assert src.name == "mcp_registry"
    assert "endpoint" in src.config_schema["properties"]


def test_mcp_crawl_yields_servers():
    fake_response = {"servers": [
        {"name": "server1", "description": "test mcp",
         "repoUrl": "https://github.com/o/server1",
         "stars": 200, "language": "Python", "tags": ["ai"]}
    ]}

    async def fake(url: str, **kw) -> str:
        return json.dumps(fake_response)

    async def run():
        src = MCPRegistrySource()
        with patch.object(src, "_fetch", side_effect=fake):
            out = []
            async for r in src.crawl():
                out.append(r)
            assert len(out) == 1
            assert out[0].name == "o/server1"
            assert out[0].stars == 200

    asyncio.run(run())


if __name__ == "__main__":
    for name, fn in sorted(
        {k: v for k, v in globals().items() if k.startswith("test_") and callable(v)}.items()
    ):
        fn()
        print(f"✓ {name}")
    print("\nAll tests passed.")
