# Right Ewaste ERP

An internal ERP system built for Right Ewaste Recycle Pvt. Ltd.

## Features

- Company Management
- Party Management
- Material Management
- Sales Invoice
- Purchase Invoice
- Inventory
- Reports

## Technology Stack

- Python
- Flask
- SQLite
- Bootstrap 5

## Project Status

🚧 Under Development

## Run the app

From the project root:

```bash
python app.py
```

Or from the backend folder:

```bash
cd backend
python app.py
```

The app will be available at http://127.0.0.1:5000

## Production configuration

Copy `.env.example` into your deployment environment and set the listed values.
When `APP_ENV=production`, the application requires a `SESSION_SECRET` and an
administrator account. Authentication is enabled automatically; administrators
can perform all actions, while operators cannot delete records.
Viewers can access reports and operational screens but cannot change data.
