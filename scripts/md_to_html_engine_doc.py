    """Build 引擎运作.html from 引擎运作.md (run from repo root: python scripts/md_to_html_engine_doc.py)."""

from __future__ import annotations

import re
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
MD_PATH = ROOT / "引擎运作.md"
OUT_PATH = ROOT / "引擎运作.html"


def main() -> None:
    md_text = MD_PATH.read_text(encoding="utf-8")

    html_body = markdown.markdown(
        md_text,
        extensions=[
            "markdown.extensions.extra",
            "markdown.extensions.nl2br",
            "markdown.extensions.toc",
            "markdown.extensions.sane_lists",
        ],
    )

    def mermaid_repl(m: re.Match[str]) -> str:
        inner = m.group(1).strip()
        return f"<div class=\"mermaid\">\n{inner}\n</div>"

    html_body = re.sub(
        r'<pre><code class="language-mermaid">(.*?)</code></pre>',
        mermaid_repl,
        html_body,
        flags=re.DOTALL,
    )

    template = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>惨剧轮回 — 引擎运作说明</title>
<style>
  body { font-family: system-ui, "Segoe UI", "Microsoft YaHei", sans-serif; line-height: 1.6; max-width: 52rem; margin: 0 auto; padding: 1.5rem 1rem 3rem; color: #1a1a1a; }
  h1 { border-bottom: 1px solid #ddd; padding-bottom: 0.3em; }
  h2 { margin-top: 1.75em; border-bottom: 1px solid #eee; padding-bottom: 0.2em; }
  h3 { margin-top: 1.25em; }
  table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 0.95em; }
  th, td { border: 1px solid #ccc; padding: 0.45em 0.65em; text-align: left; }
  th { background: #f5f5f5; }
  code { background: #f4f4f4; padding: 0.1em 0.35em; border-radius: 4px; font-size: 0.92em; }
  pre { background: #f8f8f8; padding: 1rem; overflow-x: auto; border-radius: 6px; border: 1px solid #e8e8e8; }
  pre code { background: none; padding: 0; }
  hr { border: none; border-top: 1px solid #ddd; margin: 2em 0; }
  .mermaid { margin: 1.25em 0; text-align: center; }
  nav#toc { background: #fafafa; border: 1px solid #e0e0e0; border-radius: 8px; padding: 1rem 1.25rem; margin-bottom: 2rem; }
  nav#toc > p:first-child { margin-top: 0; font-weight: 600; }
</style>
</head>
<body>
__BODY__
<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs";
  mermaid.initialize({ startOnLoad: true, theme: "neutral", securityLevel: "loose", fontFamily: "system-ui, Microsoft YaHei, sans-serif" });
</script>
</body>
</html>"""

    out = template.replace("__BODY__", html_body)
    OUT_PATH.write_text(out, encoding="utf-8")
    print(f"Wrote {OUT_PATH} ({len(out)} bytes)")


if __name__ == "__main__":
    main()
