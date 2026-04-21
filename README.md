# BenchCAD project page

Static landing page for the BenchCAD benchmark — served via GitHub Pages
from the root of this repository on the `main` branch.

## Preview locally

```bash
python3 -m http.server 8000
# open http://localhost:8000
```

## Structure

```
index.html                    # single-page content
static/
  css/index.css               # custom styles
  images/
    favicon.svg
    family_distribution.svg   # 8-category wheel, 106 families
  cases/<family>.webp         # rotating 3D renders
  vendor/
    css/{bulma,fontawesome}.min.css
    webfonts/                 # fa-solid, fa-brands
```

Fully self-contained — no CDN dependencies.
