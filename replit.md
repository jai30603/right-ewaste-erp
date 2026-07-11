# Right Ewaste ERP

Internal ERP system for **Right Ewaste Recycle Pvt. Ltd.**

## Stack

- **Backend:** Python Flask (Blueprints + Services + Repositories)
- **Database:** SQLite (`database/erp.db`)
- **Frontend:** HTML + Bootstrap 5 + custom CSS
- **Icons:** Bootstrap Icons

## How to run

```
cd backend && python -m flask --app app run --host=0.0.0.0 --port=5000
```

The workflow **Start application** is already configured and runs this automatically.

## Project structure

```
backend/
  app.py              # Flask app + blueprint registration
  database.py         # SQLite connection helper
  routes/             # Flask Blueprints (one per module)
  services/           # Business logic
  repositories/       # All database queries (SQLite)
  templates/          # Jinja2 HTML templates
    base.html         # Shared layout (sidebar, topbar, flash messages)
    party_form.html   # Unified add/edit party form
  static/
    css/style.css     # Custom ERP design system
    js/state.js       # State → state-code auto-fill
  data/
    states.py         # Indian states with GST codes
database/
  erp.db              # SQLite database
  schema/             # SQL schema files
```

## Modules

| Module           | Status        | Routes                          |
|------------------|---------------|---------------------------------|
| Dashboard        | ✅ Live        | `/`                             |
| Party            | ✅ Production  | `/party`, `/party/add`, `/party/<id>/edit`, `/party/<id>/delete` |
| Material         | 🚧 In progress | `/material`                     |
| Sales Invoice    | 🚧 In progress | `/sales`                        |
| Purchase Invoice | 🚧 In progress | `/purchase`                     |

## Party module features

- List all active parties with search (party code, name, contact, phone, GSTIN)
- Add party — auto-generates `PTY-NNNNN` code
- Edit party — pre-fills all fields
- Soft delete — sets `is_active = 0`, never removes rows
- Flash messages on all actions
- Full validation (required fields, phone digits-only, email format, GSTIN max 15)

## User preferences

- Keep existing Flask Blueprint structure
- Business logic stays in services/repositories, not in routes or templates
- Do not duplicate HTML — reuse `base.html` and shared form templates
- Soft delete only — never permanently remove records
