# Writing a Lodestone 2.0 Plugin

Three plugin kinds: **source** (yields repos), **scorer** (rates repos 0-1), **notifier** (fires events).

## 1. Source plugin
```python
from lodestone.source import Source, SourceResult
from typing import AsyncIterator

class RedditSource(Source):
    name = "reddit"
    version = "1.0.0"
    config_schema = {"type": "object", "properties": {"subreddit": {"type": "string"}}}

    async def crawl(self) -> AsyncIterator[SourceResult]:
        # ... fetch from Reddit, yield SourceResult per post
        ...
```

## 2. Scorer plugin
```python
from lodestone.scorer import Scorer, Score

class MyScorer(Scorer):
    name = "my_scorer"
    version = "1.0.0"
    config_schema = {"type": "object"}

    async def score(self, repo: dict, context: dict) -> Score:
        return Score(value=0.5, reasoning="placeholder")
```

## 3. Notifier plugin
```python
from lodestone.notifier import Notifier, Notification

class MyNotifier(Notifier):
    name = "my_notifier"
    version = "1.0.0"
    config_schema = {"type": "object"}

    async def notify(self, notification: Notification) -> None:
        print(notification.title)
```

## Registration
Add to your `pyproject.toml`:
```toml
[project.entry-points."lodestone.sources"]
reddit = "mypackage.reddit:RedditSource"

[project.entry-points."lodestone.scorers"]
my_scorer = "mypackage.my_scorer:MyScorer"

[project.entry-points."lodestone.notifiers"]
my_notifier = "mypackage.my_notifier:MyNotifier"
```

Install: `pip install -e .`. Plugin auto-discovered on next `lodestone serve`.
