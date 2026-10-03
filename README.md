# ASE authentication backend — MySQL

FastAPI + MySQL implementation for user registration and login.

## Structure

```text
backend/
├── database/
│   └── init.sql
├── data_controller/
│   ├── data_controller.py
│   └── user_data_controller.py
├── model/
│   └── user.py
├── routes/
│   └── user_routes.py
└── main.py
```

## Install

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Start MySQL

The easiest option is Docker:

```bash
docker compose up -d
```

The included Compose file starts MySQL on port `3306` and executes
`backend/database/init.sql` on first initialization.

Default development configuration:

```text
database: ase
user:     ase
password: ase
host:     127.0.0.1
port:     3306
```

If you already have MySQL locally, initialize the schema with:

```bash
mysql -u root -p < backend/database/init.sql
```

## Environment variables

The application reads:

```text
MYSQL_HOST
MYSQL_PORT
MYSQL_USER
MYSQL_PASSWORD
MYSQL_DATABASE
```

Defaults match the included Docker Compose setup.

## Start FastAPI

```bash
uvicorn backend.main:app --reload
```

Swagger/OpenAPI is available at `http://127.0.0.1:8000/docs`.

## Development user

```text
email:    dev@ase3.com
password: dev
```

The database stores a PBKDF2 hash of `dev`, never the plaintext password.

## Endpoints

- `POST /users/register`
- `POST /users/login`

The login endpoint validates credentials but does not yet issue a JWT/session token.
