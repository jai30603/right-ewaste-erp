---
name: Dashboard hero card gradient fix
description: Why inline gradient styles on Bootstrap .card elements render as white in this ERP
---

`backend/static/css/shared.css` contains:
```css
.card {
  background: var(--card-bg) !important;
  color: var(--text-primary) !important;
}
```

**Why this matters:** The `!important` rule overrides both inline `style="background: linear-gradient(...)"` and Bootstrap's own `.card` background, so any element using the `.card` class will render with the plain card background colour — gradients are silently lost.

**How to apply:** Never use Bootstrap's `.card` class for gradient/coloured hero cards. Instead, define a dedicated CSS class in the module's scoped CSS file (e.g. `.sd-hero-green`, `.mst-profile-hero`) and set `background: linear-gradient(...) !important` there. This wins the specificity battle.
