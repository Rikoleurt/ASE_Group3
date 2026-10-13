# ASE Group 3 — Exploring Linear A

This project explores the analysis of Linear A tablets. The web application combines
a **Vue** frontend, a **FastAPI** backend, and a **MySQL** database for user
accounts. It provides registration, login, a user profile, and an initial image
analysis demonstration using the HT13 tablet.

## 1. Installation and configuration

Requirements: **Node.js `^22.18.0` or `>=24.12.0`**, **Python 3.12+**, **uv**, and
**Docker with Docker Compose** to run MySQL. You can also use a local MySQL server.

Run the commands from the repository root:

```bash
npm install
npm --prefix frontend install
uv sync --project backend
```

Settings live in a `.env` file at the repository root. `npm run dev` creates it from
[.env.example](.env.example) the first time, or you can copy it yourself:

```bash
cp .env.example .env
```

These credentials are intended for local development. The `.env` file is ignored
by Git and loaded automatically when the application starts.
Keep `MYSQL_DATABASE=ase3`: the initialization script uses this name.

### MySQL with Docker

Start Docker, then start the database:

```bash
docker compose up -d --wait mysql
```

On the first run, Docker creates the database and MySQL user, then executes
[init.sql](backend/app/database/init.sql) to create the users table and the demo
account: **`dev@ase3.com` / `dev`**.
Data is persisted in a volume; initialization does not run again on an existing
volume. If port 3306 is already in use, set `MYSQL_PORT=3307` in `.env` before
starting Docker Compose.

### Alternative: MySQL without Docker

On a local MySQL server, run the script with an administrator account:

```bash
mysql -u root -p < backend/app/database/init.sql
```

Then create a dedicated user and grant access to the database from a MySQL
administrator session:

```sql
CREATE USER IF NOT EXISTS 'ase'@'localhost' IDENTIFIED BY 'ase';
GRANT ALL PRIVILEGES ON ase3.* TO 'ase'@'localhost';
```

Update `.env` to match this server's credentials and port.
`MYSQL_ROOT_PASSWORD` is only used for initialization with Docker.

## 2. Run the application

Once MySQL is running:

```bash
npm run dev
```

This command starts the frontend and backend together:

- Application: http://localhost:5173
- Interactive API documentation: http://127.0.0.1:8000/docs
- HT13 demo: http://localhost:5173/tablet-demo

The demo requires the `yolo26n.pt` file at the repository root. It uses a generic
YOLO model that has not yet been trained to recognize Linear A signs.

Stop the application with `Ctrl+C`. To stop MySQL when running it with Docker:

```bash
docker compose stop mysql
```

## 3. The role of `fraction-solver`

The [fraction-solver](fraction-solver/README.md) directory contains an independent
Python research tool. Using tablet transcriptions, it turns quantities and totals
into equations to investigate the values of fraction signs, with exact rational
arithmetic.

It complements visual analysis by exploring the numerical consistency of
transcriptions and the limits of what can be inferred. The
[study findings](fraction-solver/FINDINGS.md) indicate that the available
arithmetic evidence is insufficient to determine all unknown values.

This tool is not required for `npm run dev`. Its setup and commands are documented
in its [README](fraction-solver/README.md); run those commands from the
`fraction-solver/` directory. It also builds the training data for a Linear A sign
detector, described next.

## 4. Training data for a sign detector

No hand labelling is needed. lineara.eu publishes, for each tablet, a tracing of the
whole tablet and a crop of each sign cut from the same drawing. `fraction-solver`
finds each crop on its tracing (estimating the scale where the tracing was shrunk),
which gives the sign boxes, and writes them as a YOLO dataset
([la/signboxes.py](fraction-solver/la/signboxes.py)). On the current corpus this
gives 4,704 boxes on 730 tablets. HT 13 is held out because the demo shows it.

```bash
cd fraction-solver
python -m la.cli fetch      # once: cache the lineara.eu documents (~15 min)
python -m la.cli images     # tracings and sign crops (~40 min, resumable)
python -m la.cli dataset    # writes out/yolo_signs/ and prints a summary
cd ..
uv run --project backend yolo detect train data=fraction-solver/out/yolo_signs/data.yaml model=yolo26n.pt imgsz=1024 epochs=100
```

Training writes `runs/detect/train/weights/best.pt`. It needs a GPU (or Google
Colab) to finish in reasonable time. The demo does not use trained weights yet: it
still loads `yolo26n.pt`, so pointing the backend at the trained model is a next step.
`python -m la.cli dataset --labels role` gives one class per sign role
(syllabogram, logogram, fraction, transaction) instead of a single `sign` class.

Known limitation: lineara.eu has crops only for signs, so numerals (tally strokes)
and the occasional sign without a crop are left unboxed. A model trained on this
data treats them as background and will not find numerals.

The tracings are CC BY-NC-SA 4.0 (SigLA, lineara.eu). The images, the dataset and
trained weights stay local and are ignored by Git; do not redistribute them.
