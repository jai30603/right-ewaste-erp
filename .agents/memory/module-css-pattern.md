---
name: Module CSS pattern
description: How per-module CSS is structured and loaded in this ERP to avoid conflicts with shared.css
---

Each module gets its own CSS file in `backend/static/css/` with a unique class prefix:
- `sales.css` → prefix `sv3-`
- `masters.css` → prefix `mst-`

**Why:** `shared.css` aggressively uses `!important` on `.card`, `.card-header`, etc. Any module-specific overrides must also use `!important` or use custom class names that shared.css doesn't target.

**How to apply:** When creating a new module CSS file:
1. Pick a short unique prefix (3–4 chars)
2. Load it via `<link href="/static/css/<module>.css?v=N" rel="stylesheet">` inside `{% block content %}` of each template that needs it
3. Bump the `?v=N` query param whenever the CSS file changes to bust the browser cache
4. For gradient cards / coloured backgrounds, define dedicated classes (not `.card`) with `!important` on `background`
