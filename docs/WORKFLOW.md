# Development workflow

1. Create a virtual environment and install `requirements.txt`.
2. Create a separate local database with `database/init_db.py`.
3. Run `python -m compileall -q backend` before committing.
4. Add automated tests for each bug fix and business rule.
5. Make schema changes in a new numbered SQL migration; never edit an already deployed migration.

Before production, configure `SECRET_KEY`, disable debug mode, run behind a production WSGI server, and establish database backups plus user authentication/authorization.
