#!/usr/bin/env python3
"""Inline engine.js into the dashboard so the page is one self-contained file.
Writes bess_dashboard.html (offline copy) and docs/index.html (what GitHub Pages and Vercel serve)."""
import os
here = os.path.dirname(os.path.abspath(__file__))
root = os.path.join(here, "..")
src = open(os.path.join(here, "dashboard_src.html")).read()
eng = open(os.path.join(here, "engine.js")).read()
assert "/*ENGINE*/" in src
page = src.replace("/*ENGINE*/", eng)
os.makedirs(os.path.join(root, "docs"), exist_ok=True)
for p in ("bess_dashboard.html", os.path.join("docs", "index.html")):
    open(os.path.join(root, p), "w").write(page)
print("wrote bess_dashboard.html and docs/index.html")
