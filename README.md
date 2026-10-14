# Fake News Flask Yusra

FakeNews-Flask-Yusra is a machine-learning application for news text classification.

![Flask](https://img.shields.io/badge/Flask-2563EB?style=flat-square) ![MySQL](https://img.shields.io/badge/MySQL-0F172A?style=flat-square)

## Overview

The Flask implementation is organized around the entry points and modules below.

## Implemented workflows

The source defines these handlers:

- **Index** — `index`
- **Login** — `login`
- **Logout** — `logout`
- **Register** — `register`
- **User Login** — `user_login`
- **User Logout** — `user_logout`
- **Dashboard** — `dashboard`
- **Analyze News** — `analyze_news`
- **Analysis History** — `analysis_history`
- **View Profile** — `view_profile`
- **Update Profile** — `update_profile`
- **Export History Excel** — `export_history_excel`

## Getting started

### 1. Get the project

```bash
git clone https://github.com/nasirabbas827/FakeNews-Flask-Yusra.git
cd FakeNews-Flask-Yusra
```

### 2. Prepare Python

Create an isolated environment:

```bash
python -m venv .venv
```

Activate it with `.venv\Scripts\activate` on Windows Command Prompt, or `source .venv/bin/activate` on macOS/Linux.

No requirements file is included. The inspected Python imports indicate these dependencies as a starting point:

```bash
python -m pip install Flask Flask-MySQLdb Werkzeug pandas numpy joblib scikit-learn XlsxWriter
```

Dependency versions are not pinned in this repository.

### 3. Configure and run

Import [`Database/fakenews_db.sql`](Database/fakenews_db.sql) and set the local database connection in the application configuration before starting.

Run from the repository root so relative file paths resolve correctly:

```bash
python app.py
```

Open http://127.0.0.1:5000/, or use the address printed by the application.

### Model files

Included artifacts: [`trained_model.pkl`](trained_model.pkl), [`vectorizer.pkl`](vectorizer.pkl).

Keep models, preprocessing objects, and label mappings together in the locations expected by the source.

## Repository guide

| Path | Purpose |
| --- | --- |
| [`Database`](Database) | Database scripts |
| [`app.py`](app.py) | Application entry point |
| [`static`](static) | Static application assets |
| [`templates`](templates) | HTML page templates |

## Development notes

These setup instructions are based on the repository source. The application has not been executed as part of this documentation update; verify dependencies and configuration in your local environment.
