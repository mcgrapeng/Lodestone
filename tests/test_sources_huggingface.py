"""Tests for the HuggingFace source plugin. Run: python3 -m tests.test_sources_huggingface"""
import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from lodestone.plugins.huggingface import HuggingFaceSource


def test_hf_metadata():
    src = HuggingFaceSource()
    assert src.name == "huggingface"
    assert "spaces_endpoint" in src.config_schema["properties"]


def test_hf_crawl_spaces_and_models():
    # Both spaces and models endpoints return the same fake (2 items each).
    fake = [{"id": "owner/space1", "likes": 50}, {"id": "owner/space2", "likes": 30}]

    async def fake_fetch(url, **kw):
        return json.dumps(fake)

    async def run():
        src = HuggingFaceSource()
        with patch.object(src, "_hf_api", side_effect=fake_fetch):
            out = []
            async for r in src.crawl():
                out.append(r)
            # 2 spaces + 2 models = 4 (same fake served by both endpoint calls)
            assert len(out) == 4
            spaces = [r for r in out if r.name.startswith("spaces/")]
            models = [r for r in out if r.name.startswith("models/")]
            assert len(spaces) == 2 and len(models) == 2
            assert out[0].stars == 50  # spaces use 'likes' as stars

    asyncio.run(run())


if __name__ == "__main__":
    for name, fn in sorted(
        {k: v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)}.items()
    ):
        fn()
        print(f"✓ {name}")
    print("\nAll tests passed.")
