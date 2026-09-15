"""Tests for the GitHub source plugin. Run: python3 -m tests.test_sources_github"""
import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from lodestone.plugins.github import GitHubSource


def test_github_source_metadata():
    src = GitHubSource()
    assert src.name == "github"
    assert src.version == "2.0.0"
    assert "token" in src.config_schema["properties"]


def test_github_source_crawl_yields_results():
    fake_response = {
        "items": [
            {"full_name": "owner/repo1", "html_url": "https://github.com/owner/repo1",
             "description": "test repo 1", "stargazers_count": 100, "forks_count": 5,
             "language": "Python", "topics": ["ai-agent"]},
        ]
    }

    async def fake_hget(*args, **kwargs):
        return json.dumps(fake_response)

    async def run():
        src = GitHubSource()
        with patch.object(src, "_gh_api", side_effect=fake_hget):
            results = []
            async for r in src.crawl():
                results.append(r)
            assert len(results) == 1
            assert results[0].name == "owner/repo1"
            assert results[0].stars == 100

    asyncio.run(run())


if __name__ == "__main__":
    for name, fn in sorted(
        {k: v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)}.items()
    ):
        fn()
        print(f"✓ {name}")
    print("\nAll tests passed.")
