# Odoo Lite Backend

FastAPI backend for a lightweight inventory and sales management system. It includes authentication, product management, sales confirmation/history, admin audit logs, and financial endpoints.

## Tech Stack

- FastAPI
- SQLModel
- Pydantic Settings
- JWT authentication with `python-jose`
- Pytest
- Docker

## Project Structure

```text
app/
  api/v1/endpoints/   API route modules
  core/               App configuration and security helpers
  db/                 Database engine/session setup
  models/             SQLModel models
  main.py             FastAPI app entrypoint
tests/                Pytest test suite
.github/workflows/   GitHub Actions CI workflows
```

## Requirements

- Python 3.12
- pip

## Environment Variables

Create a `.env` file in the project root.

```env
DATABASE_URL=sqlite:///./test.db
SECRET_KEY=change-this-secret
```

For PostgreSQL, use a URL like:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
```

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Run the API

```bash
uvicorn app.main:app --reload
```

The API will be available at:

- `http://127.0.0.1:8000`
- `http://127.0.0.1:8000/docs`

## API Routes

Main route groups:

- `/api/v1/auth`
- `/api/v1/products`
- `/api/v1/sales`
- `/api/v1/admin`

## Run Tests

```bash
pytest
```

## Docker

Build the image:

```bash
docker build -t odoo-lite-backend .
```

Run the container:

```bash
docker run --env-file .env -p 8000:8000 odoo-lite-backend
```

## Continuous Integration

GitHub Actions runs the test suite on pushes and pull requests using Python 3.12. The workflow is defined in:

```text
.github/workflows/tests.yml
```
