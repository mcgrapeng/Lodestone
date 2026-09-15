#!/usr/bin/env python3
"""Render 3 docs to a single HTML preview site (uses mistune for reliable markdown).

Output: docs/preview/index.html
"""
from __future__ import annotations
import re
from pathlib import Path

import mistune

DOCS = Path(__file__).resolve().parent.parent  # /Users/.../lodestone
PREVIEW_DIR = DOCS / "docs" / "preview"
PREVIEW_DIR.mkdir(exist_ok=True)

# Set up mistune with GitHub-flavored features
md = mistune.create_markdown(
    renderer="html",
    plugins=["table", "url", "strikethrough"],
)


def fixup(md_html: str, doc_id: str) -> str:
    """Tweak generated HTML — add anchors to headings, etc."""
    # Add id to top heading
    md_html = re.sub(
        r"<h1>(.*?)</h1>",
        rf'<h1 id="{doc_id}">\1</h1>',
        md_html,
        count=1,
    )
    # Add anchors to ALL headings (so nav links work)
    def _anch(m):
        level, txt = m.group(1), m.group(2)
        # make id from text
        anchor_txt = re.sub(r"<[^>]+>", "", txt).lower()
        anchor = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", anchor_txt).strip("-")
        return f"<h{level} id=\"{anchor}\">{txt}</h{level}>"
    md_html = re.sub(r"<h([1-6])>(.*?)</h\1>", _anch, md_html)
    # Rewrite local file links to anchors within same doc
    md_html = re.sub(r'href="README\.md#', f'href="#readme/', md_html)
    md_html = re.sub(r'href="安装说明\.md#', f'href="#install/', md_html)
    md_html = re.sub(r'href="使用手册\.md#', f'href="#manual/', md_html)
    md_html = re.sub(r'href="SKILL\.md"', f'href="#skill"', md_html)
    # Resolve relative image paths to docs/
    md_html = re.sub(r'<img src="(?!http|/|docs/)([^"]+)"', r'<img src="../\1"', md_html)
    return md_html


# Note: README.md references `logo.svg` and `screenshots/*.png` which need to resolve
# relative to the repo root. Since the preview is at docs/preview/index.html,
# we rewrite `src="logo.svg"` → `src="../logo.svg"`. Same for screenshots.

LOGO_REWRITER = re.compile(r'(<img[^>]+src=")(?!http|/|#|docs/)([^"]+)"')


def rewrite_logo(html: str) -> str:
    """Move image paths up one level (docs/preview → docs/)."""
    return LOGO_REWRITER.sub(r'\1../\2"', html)


README_MD = (DOCS / "README.md").read_text()
INSTALL_MD = (DOCS / "安装说明.md").read_text()
MANUAL_MD = (DOCS / "使用手册.md").read_text()

README_HTML = fixup(md(README_MD), "readme-top")
INSTALL_HTML = fixup(md(INSTALL_MD), "install-top")
MANUAL_HTML = fixup(md(MANUAL_MD), "manual-top")

README_HTML = rewrite_logo(README_HTML)
INSTALL_HTML = rewrite_logo(INSTALL_HTML)
MANUAL_HTML = rewrite_logo(MANUAL_HTML)


NAV = """
<nav class="site-nav">
  <a href="#readme-top" class="nav-item">📖 README</a>
  <a href="#install-top" class="nav-item">📦 安装说明</a>
  <a href="#manual-top" class="nav-item">🛠 使用手册</a>
  <a href="https://github.com/lodestone/lodestone" class="nav-item nav-external" target="_blank" rel="noopener">⭐ GitHub →</a>
</nav>
"""


CSS = """
:root {
  --bg: #0b0d12;
  --bg-2: #131722;
  --panel: #1a1f2e;
  --panel-2: #232a3d;
  --border: #2d3548;
  --text: #e6e9ef;
  --text-dim: #9ba4b5;
  --accent: #8b5cf6;
  --accent-2: #ec4899;
  --accent-3: #6366f1;
  --good: #10b981;
  --warn: #f59e0b;
  --bad: #ef4444;
  --code-bg: #0a0c12;
  --link: #a78bfa;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", system-ui, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.7;
  font-size: 16px;
}
.container { max-width: 920px; margin: 0 auto; padding: 32px 24px 80px; }
header.site-header {
  text-align: center;
  padding: 48px 0 32px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 32px;
}
header.site-header img { max-width: 540px; height: auto; }
header.site-header h1 {
  font-size: 36px;
  background: linear-gradient(135deg, var(--accent-3), var(--accent), var(--accent-2));
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  margin: 24px 0 8px;
}
header.site-header p {
  color: var(--text-dim);
  font-size: 17px;
  max-width: 600px;
  margin: 0 auto;
  line-height: 1.5;
}
nav.site-nav {
  display: flex;
  gap: 8px;
  justify-content: center;
  flex-wrap: wrap;
  padding: 14px 16px;
  position: sticky;
  top: 0;
  background: rgba(11, 13, 18, 0.94);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  z-index: 100;
  border-bottom: 1px solid var(--border);
  margin-bottom: 48px;
}
nav.site-nav a {
  color: var(--text-dim);
  text-decoration: none;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s ease;
}
nav.site-nav a:hover {
  background: var(--panel);
  color: var(--text);
}
nav.site-nav a.nav-external {
  background: linear-gradient(135deg, var(--accent-3), var(--accent));
  color: white;
}
nav.site-nav a.nav-external:hover { opacity: 0.9; }
section.doc {
  padding-top: 48px;
  margin-top: 48px;
  border-top: 1px solid var(--border);
}
section.doc:first-of-type {
  border-top: none;
  margin-top: 0;
  padding-top: 0;
}
h1, h2, h3, h4, h5, h6 {
  color: var(--text);
  font-weight: 700;
  line-height: 1.3;
  margin: 1.8em 0 0.6em;
  scroll-margin-top: 80px;
}
h1 { font-size: 36px; margin-top: 0; }
h2 {
  font-size: 26px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}
h3 { font-size: 20px; color: var(--accent); }
h4 { font-size: 17px; }
p { margin: 0.8em 0; color: var(--text); }
ul, ol { margin: 0.6em 0 0.6em 1.5em; }
li { margin: 0.3em 0; }
li > p { margin: 0.4em 0; }
strong { color: var(--accent); font-weight: 600; }
em { color: var(--text); font-style: italic; }
code {
  font-family: "SF Mono", "Monaco", "Cascadia Code", "Fira Code", "Consolas", monospace;
  font-size: 0.9em;
  background: var(--code-bg);
  border: 1px solid var(--border);
  padding: 2px 6px;
  border-radius: 4px;
  color: #fbbf24;
}
pre {
  background: var(--code-bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
  margin: 1em 0;
  overflow-x: auto;
}
pre code {
  background: none;
  border: none;
  padding: 0;
  color: var(--text);
  font-size: 13px;
  line-height: 1.5;
}
blockquote {
  border-left: 3px solid var(--accent);
  background: var(--panel);
  margin: 1em 0;
  padding: 12px 16px;
  border-radius: 0 8px 8px 0;
  color: var(--text-dim);
  font-style: italic;
}
blockquote p { margin: 0; }
table {
  border-collapse: collapse;
  width: 100%;
  margin: 1em 0;
  font-size: 14px;
}
th, td {
  text-align: left;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
}
th {
  background: var(--panel);
  font-weight: 600;
  color: var(--accent);
}
tbody tr:hover { background: var(--panel); }
img {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
  margin: 1em 0;
  border: 1px solid var(--border);
}
hr {
  border: none;
  border-top: 1px solid var(--border);
  margin: 2em 0;
}
a { color: var(--link); text-decoration: none; }
a:hover { text-decoration: underline; }
footer.site-footer {
  margin-top: 80px;
  padding: 24px 0;
  border-top: 1px solid var(--border);
  text-align: center;
  color: var(--text-dim);
  font-size: 14px;
}
code.language-bash { color: #a5d6a7; }
"""


def build_html() -> str:
    import datetime as _dt
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Lodestone · 文档预览</title>
<style>{CSS}</style>
</head>
<body>

<div class="container">

<header class="site-header">
  <img src="../logo.svg" alt="Lodestone · 磁石 · 你的 AI 工程师罗盘">
  <h1>Lodestone · 文档预览</h1>
  <p>完整文档嵌入到 GitHub 仓库根（README.md / 安装说明.md / 使用手册.md）。本预览页用 mistune 渲染，挂本地 server 即可访问。</p>
</header>

{NAV}

<section class="doc">
{README_HTML}
</section>

<section class="doc">
{INSTALL_HTML}
</section>

<section class="doc">
{MANUAL_HTML}
</section>

<footer class="site-footer">
  <p>Lodestone · Apache-2.0 · 渲染时间 {_dt.datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
  <p>Regenerate: <code>python3 scripts/render_preview.py</code> · Logo: <code>docs/logo.svg</code></p>
</footer>

</div>

</body>
</html>
"""


def main():
    out = PREVIEW_DIR / "index.html"
    out.write_text(build_html(), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
