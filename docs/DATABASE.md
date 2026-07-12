# Database

The production schema is SQLite and lives in `database/schema`, ordered by numeric prefix. Initialise a fresh database with:

```powershell
python database\init_db.py --database path\to\erp.db
```

`company`, `party`, and `material` are master data. `sales_invoice` is the header and `sales_invoice_item` contains its line items. Application connections enable SQLite foreign-key enforcement.

Do not treat `database/erp.db` as a source-controlled production database. Back up the deployed database before upgrades and use a separate migration for every schema change.
