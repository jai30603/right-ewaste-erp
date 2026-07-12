# Right Ewaste ERP

Internal ERP for Right Ewaste Recycle Pvt. Ltd., built with Flask, SQLite, and Bootstrap.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python database\init_db.py
$env:FLASK_DEBUG = "1"
python backend\app.py
```

Open `http://127.0.0.1:5000`. Set `SECRET_KEY` in the environment before using a persistent deployment. Set `RIGHT_EWASTE_DATABASE` to use a database outside the repository.

## Current modules

- Dashboard and Party management are usable.
- Company, Material, Sales, and Purchase screens are placeholders pending their full workflows.

See [database documentation](docs/DATABASE.md) and [workflow notes](docs/WORKFLOW.md).
