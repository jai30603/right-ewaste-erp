# Right Ewaste ERP

An internal ERP system for Right Ewaste Recycle Pvt. Ltd.

## How to run

```bash
python app.py
```

This starts the Flask development server on port 5000. The app runs in **development mode** by default — no login is required and a random session key is generated on each start.

## Stack

- **Backend**: Python / Flask
- **Database**: SQLite (`database/erp.db`, created automatically on first run)
- **Frontend**: Jinja2 templates + Bootstrap 5

## Modules

Sales Invoice, Purchase Invoice, Inventory, Materials, Material Processing, Employees, Certificates, Reports, Enterprise Document Management (EDMS), Communication, Settings, Audit, Traceability

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `SESSION_SECRET` | Production only | Flask session secret key |
| `APP_ENV` | No (default: `development`) | Set to `production` to enable authentication |
| `ERP_ADMIN_USERNAME` / `ERP_ADMIN_PASSWORD_HASH` | Production only | Admin account credentials |
| `ERP_OPERATOR_USERNAME` / `ERP_OPERATOR_PASSWORD_HASH` | Optional | Operator account (can create/edit, not delete) |
| `ERP_VIEWER_USERNAME` / `ERP_VIEWER_PASSWORD_HASH` | Optional | Read-only account |

Password hashes must be Werkzeug hashes — generate with:
```bash
python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('your-password'))"
```

## Project structure

```
app.py              # Entry point (imports backend/app.py)
backend/
  app.py            # Flask app factory, route registration
  database.py       # SQLite initialisation & schema migrations
  routes/           # Blueprint route handlers
  modules/          # Business logic modules
  repositories/     # Data access layer
  document_engine/  # PDF/report generation
  erp_platform/     # KPIs, audit, notifications, search
  config/           # Business configuration
  static/           # CSS, JS, images
  templates/        # Jinja2 HTML templates
database/
  schema/           # SQL schema files (auto-applied on startup)
  erp.db            # SQLite database (auto-created)
```

## User preferences
