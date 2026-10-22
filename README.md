# ASE Group 3 — Linear A Character Detection

The project combines a Vue frontend, a FastAPI backend and a MySQL database.
Its goal is to train YOLO26 to locate Linear A characters and display their
associated readings, such as `AB77 (ka)`, with bounding boxes and confidence scores.

Run commands from the repository root unless a step says otherwise.

## 1. Requirements

| Requirement | Used for |
|---|---|
| Python 3.12+ | Backend, data preparation and training |
| Node.js `^22.18.0` or `>=24.12.0`, with npm | Frontend and application startup |
| uv | Backend dependency management |
| Docker with Docker Compose, or a local MySQL server | User accounts |
| PyTorch and Ultralytics `>=8.4,<9.0` | Model training |
| Compatible GPU and drivers | Faster training; CPU training is supported but slower |

Data preparation and training do not require Node.js, MySQL or a running web app.
Python dependencies are listed in [backend/pyproject.toml](backend/pyproject.toml)
and [fraction-solver/requirements-data.txt](fraction-solver/requirements-data.txt).
The pretrained starting weights are `yolo26n.pt` at the repository root.

## 2. Install and run the application

Install the frontend and the backend. `uv sync` also installs SciPy, which the
backend needs for the `fraction-solver` code it imports:

```bash
npm install
npm --prefix frontend install
uv sync --project backend
```

Create `.env` by copying [.env.example](.env.example). `npm run dev` also creates
it automatically if it is missing. The defaults are for local development.
Keep `MYSQL_DATABASE=ase3`, as the initialization script uses that name.

Start Docker, then run:

```bash
docker compose up -d --wait mysql
npm run dev
```

Docker creates the database and runs
[init.sql](backend/app/database/init.sql) the first time the database volume is
created. It includes the demo account **`dev@ase3.com` / `dev`**. Database data
persists between restarts; initialization is not repeated for an existing volume.
If port 3306 is already occupied, set `MYSQL_PORT=3307` in `.env` before startup.

For a development database created before username uniqueness was added, stop
the application, back up the database, then run
[fix_29.sql](backend/app/database/fix-29/fix_29.sql) once. It lists duplicate
usernames, **keeps the account with the smallest ID for each username**, deletes
the other accounts, reports the number deleted, and adds the UNIQUE constraint.
For example, `jason` with IDs 4, 14 and 20 keeps only ID 4, with its original
email and password. The `utf8mb4_unicode_ci` collation also treats case variants
as duplicates. If the accounts must all be kept, rename the duplicates manually
instead of running the deletion statement. Run the complete file in your SQL
client or from the repository root:

```bash
mysql -h 127.0.0.1 -P 3306 -u YOUR_MYSQL_USER -p ase3 < backend/app/database/fix-29/fix_29.sql
```

Adjust the host, port and user to your local configuration. MySQL DDL commits
implicitly: a failure when adding the constraint does not undo the deletions.
Restarting Docker or rerunning `init.sql` does not update an existing table;
the migration is required for registration to reject an already used username
with HTTP 409.

To use an existing MySQL server instead, run `init.sql` as an administrator,
create a database user with access to `ase3`, and set `MYSQL_HOST`, `MYSQL_PORT`,
`MYSQL_USER` and `MYSQL_PASSWORD` in `.env`. `MYSQL_ROOT_PASSWORD` is only used
by Docker during initialization.

| Address | Purpose |
|---|---|
| http://localhost:5173 | Web application |
| http://localhost:5173/tablet-demo | HT13 detection demo |
| http://127.0.0.1:8000/docs | API documentation |
| http://127.0.0.1:8000/health | Backend health check |

To run the services separately, use `npm run dev:backend` and
`npm run dev:frontend` in two terminals at the repository root.
`npm --prefix frontend run build` builds the frontend into `frontend/dist/`.

Stop the application with `Ctrl+C`. Stop the Docker database with:

```bash
docker compose stop mysql
```

The trained Linear A sign reader (a sign detector and a classifier) ships as
assets of the `signs-v1` GitHub release, not in git. Download it into `models/`:

```bash
python scripts/fetch_models.py
```

The repository is private: the script uses `GITHUB_TOKEN` (or `GH_TOKEN`) if set,
otherwise the GitHub login git has saved. Files already present are kept; pass
`--force` to replace them, or `--tag` for another release. Without these files
the app still runs, using the generic `yolo26n.pt`, which has not been trained
on Linear A characters (responses then say `"trained": false`).

HT13 inference runs on CPU at image size 1024; a GPU and the training dataset
are not needed to serve predictions. The model is loaded on the first request
and reused. Restart the backend after changing its configuration.

- `GET /tablet-demo/ht13/predictions`: JSON containing image dimensions,
  `trained` (true for the Linear A detector) and detections. Each detection has
  a `label` from the model (sign ID and proposed reading when available),
  `confidence` in percent, a PNG crop in `imageUrl`, and a normalized
  `box` (`x`, `y`, `w`, `h`; top-left origin, values from 0 to 1).
- `GET /tablet-demo/ht13`: PNG with predicted boxes and labels.
- `GET /tablet-demo/ht13?annotated=false`: original image.

Both prediction routes accept `?confidence=0.10` to lower the default threshold
of 0.25 (allowed range: greater than 0, up to 1). Lower thresholds retain more
uncertain detections. Confidence is a model score, not a verified pronunciation
or a measure of overall accuracy. The frontend demo uses these predictions
automatically. These routes do not require MySQL.

## 3. Prepare the data

The source files are already in `fraction-solver/data/`:

- `cache/`: JSON records containing sign IDs, readings and image references.
- `images/`: full tablet drawings and individual character crops.

The generator locates each crop within its full tablet drawing and associates
its bounding box with the sign information from the JSON. It does not use the
arithmetic solver to prepare the dataset.

Create a separate environment for data preparation and training. Use Python
3.12+ (`python3` or `py -3.12` instead of `python` below if needed):

```bash
python -m venv .venv-train
```

Activate it with the command for your system:

| System | Command |
|---|---|
| macOS / Linux | `source .venv-train/bin/activate` |
| Windows PowerShell | `.\.venv-train\Scripts\Activate.ps1` |

With this environment active, generate the data for the two models that read a
tablet: a **detector** that finds signs and a **classifier** that names each one.

```bash
python -m pip install -r fraction-solver/requirements-data.txt
cd fraction-solver
python -m la.cli dataset --labels sign --workers 2   # boxes, one class: "sign"
python -m la.cli crops                               # one image per sign, for the classifier
python -m la.cli synth --count 1000                  # optional: synthetic training tablets
cd ..
```

Why two models: one detector with 361 sign classes has to find and name signs at
once, while 169 of those classes have a single example. A one-class detector
learns from all 4,700 boxes at once, and a classifier trained on small crops can
be retrained in minutes and rebalanced cheaply. `--labels identity` still builds
the one-stage dataset, for comparison.

The output is `fraction-solver/out/yolo_signs/`:

```text
images/train/    labels/train/
images/val/      labels/val/
images/test/     labels/test/
data.yaml
classes.json
annotations.json
report.json
LICENCE.txt
```

An image and its annotation file share the same name. Each line in a label file
contains `class_id center_x center_y width height`, with coordinates normalized
to the image dimensions. `data.yaml` tells YOLO where the images are and how to
interpret the class numbers.

The `identity` mode creates one class per sign ID, including its reading when
available: `AB77 (ka)`, for example. Signs without readings keep their IDs; signs
without IDs use `unidentified`. The corpus also contains logogram and fraction
notations, so not every label is a pronunciation.

The split targets approximately 70% training, 15% validation and 15% testing.
Faces of the same tablet and explicitly joined fragments stay together.
HT13 is reserved for testing. Check `report.json` for actual counts, rejected
matches and class coverage. In the current generated dataset, there are
501 training images, 131 validation images and 99 test images; 82 of the 361
classes have no training examples. These classes cannot be learned from this
split, so review coverage before training a model intended to recognize all signs.

Review automatic boxes before training. Some signs and numerical marks remain
unannotated. The source images are drawings; performance on photographs must be
evaluated separately.

**Classifier crops** (`out/sign_crops/`) are cut from the detection boxes and keep
the same split. Folders are sign IDs (`AB77/`); `classes.json` gives each ID's
reading and roles. Rare signs are **resampled** in `train` only: a sign with `n`
real crops gets `sqrt(n x 100)` (1 becomes 10, 25 become 50), the extra copies
slightly tilted, stretched, thickened or thinned, or chipped at an edge, but never
mirrored. Val and test hold one crop per real sign. Signs whose ID never occurs
in train cannot be learnt; `report.json` counts them (33 of 657 test signs).

**Synthetic tablets** (`la.cli synth`) are real train tracings with further train
signs pasted into their blank space, at that tablet's sign size. Unlabelled
numerals and ruling stay in place, so the detector still learns to ignore them.
Nothing from val or test is used. The tablets are written to `images/synth/`, and
`train.txt` lists them together with the real training images. Rebuilding the
dataset deletes them.

**Missing boxes and self-training.** A sign gets a box only if its lineara.eu
crop matches the tracing, so some signs on the drawings have none. Training
then treats them as background, and testing counts a correct detection of one as
a false positive. A trained detector can point them out:

```bash
cd fraction-solver
python -m la.cli pseudo propose --weights ../runs/detect/sign_detector/weights/best.pt --split train
# review out/yolo_signs/pseudo/train/sheet_*.png; candidates.csv: accept=1 keeps a box
python -m la.cli pseudo accept out/yolo_signs/pseudo/train/candidates.csv
python -m la.cli dataset --labels sign --workers 2    # merges data/labels/extra_boxes.csv
```

In `train`, detections at confidence 0.8 or above are pre-ticked. For `val` and
`test`, nothing is pre-ticked. Accept with `--source reviewed` only after a person
has checked each box. Unreviewed boxes never reach val or test. Numerals have no
class, so reject candidates drawn on tally strokes. `data/labels/extra_boxes.csv`
is committed, because it is review work that cannot be regenerated.

**Moving to another computer:** the generated dataset and virtual environments
are ignored by Git. Recreate the environment and either regenerate the dataset
or copy `out/yolo_signs/`. If you copy it, update the absolute `path` in `data.yaml`
to its new location. Keep `classes.json` and `data.yaml` with the trained model.

The source data comes from SigLA via lineara.eu under **CC BY-NC-SA 4.0**.
Keep the attribution and licence with the dataset and derived models.

## 4. Train and evaluate the model

Keep `.venv-train` active. On the training computer, install PyTorch using the
[official installation selector](https://pytorch.org/get-started/locally/),
choosing the build for your operating system and GPU. Run its installation
command inside this environment, then install Ultralytics:

```bash
python -m pip install "ultralytics>=8.4,<9.0"
```

For an NVIDIA GPU, check that PyTorch can use CUDA:

```bash
python -c "import torch; print('CUDA available:', torch.cuda.is_available())"
```

This should print `True` for CUDA training. If it prints `False`, check your
PyTorch installation and GPU driver before starting a long run.

Train the two models from the repository root. Each run takes about 1 to 1.5
hours for the detector and 15 to 45 minutes for the classifier on a 6 GB laptop GPU:

```bash
python train.py detect   --name sign_detector    # finds signs (data: --labels sign)
python train.py classify --name sign_classifier  # names them (data: la.cli crops)
```

[train.py](train.py) sets what matters for signs and leaves the rest at
Ultralytics defaults:

| Setting | Detector | Classifier | Why |
|---|---|---|---|
| Model | `yolo26n.pt` | `yolo26n-cls.pt` | Pretrained nano models |
| `imgsz` | `1024` | `128` | The demo predicts at 1024; a sign crop needs little more than 128 |
| `epochs` / `patience` | `150` / `30` | `100` / `25` | Stops early once validation stops improving |
| `fliplr` | `0` | `0` | Never mirror: orientation is part of a sign's identity |
| `degrees` | `3` | - | Scribes tilt slightly |
| `scale` / `auto_augment` | default | `0.1` / none | Random crops keep 90-100% of the sign; variation comes from `la.augment` |
| `workers` | `2` | `2` | Use `--workers 0` if RAM runs out (each worker loads its own PyTorch) |

On a 16 GB machine, run one training at a time. Two at once ran out of memory.
Add `--epochs`, `--batch`, `--seed` or `--model` to change a run. Outputs are under
`runs/detect/<name>/` and `runs/classify/<name>/`: `weights/best.pt` (best on
validation), `weights/last.pt` (resume with `yolo train resume model=.../last.pt`),
`results.csv` and plots.

### Evaluate

```bash
python evaluate.py --detector runs/detect/sign_detector/weights/best.pt     --classifier runs/classify/sign_classifier/weights/best.pt --name two_stage
```

This scores what the demo does, on the 99 `test` tablets: a labelled sign counts
as **read** when a predicted box overlaps it (IoU at least 0.5) and names its sign
ID. Without `--classifier`, a 361-class detector names signs itself, so both
designs are scored the same way. Every rate has a 95% confidence interval from
resampling whole tablets (`runs/eval/<name>.json` also has per-tablet counts).

Results on the test split, at the demo's confidence threshold of 0.25:

| Reader | Found (recall) | Precision | Read correctly (top-1) | In top 3 |
|---|---|---|---|---|
| Detector + classifier | 89.0% (85.0-92.2) | 87.6% (83.0-91.2) | **62.1%** (54.8-68.4) | 70.2% (62.8-76.5) |
| 361-class detector, stopped at epoch 44 of 100* | 3.7% (2.2-5.2) | 77.4% (60.7-89.3) | 0.5% (0.0-1.0) | 0.5% |

\*On a 6 GB GPU, the 361-class run needed `batch=4` and still ran out of GPU
memory at epoch 45. It was far from converged (validation mAP50 0.007), so it is
not a fair verdict on a fully trained 361-class model. Score that model with the
same command to compare.

Of the 657 test signs, 33 have sign IDs never seen in training, so no model
trained on this split can name them: 62.1% read correctly is 65.4% of the signs
that can be learnt. When the detector finds a sign, the classifier names it
correctly 69.7% of the time. On HT 13, the demo tablet, 26 of its 27 signs are
found and 24 are read correctly. The test labels miss some signs (see
self-training above), so some correct detections still count as false positives.

### Use the models in the application

`python scripts/fetch_models.py` installs the released models. To use models you
trained yourself, copy three files into `models/` (create it if needed) and
restart the backend:

| File | From |
|---|---|
| `models/linear_a_signs.pt` | `runs/detect/sign_detector/weights/best.pt` |
| `models/linear_a_classifier.pt` | `runs/classify/sign_classifier/weights/best.pt` |
| `models/linear_a_classifier.json` | `fraction-solver/out/sign_crops/classes.json` (sign names and readings) |

`SIGN_DETECTOR_WEIGHTS` and `SIGN_CLASSIFIER_WEIGHTS` in `.env` can point
elsewhere; the JSON must sit beside the classifier, with the same name. Without a
classifier, the demo uses the detector's own labels, so a 361-class detector
still works on its own. With one, each prediction lists `candidates` (the top 3
signs). Its `confidence` is the detector's confidence that a sign is there, times
the classifier's probability for that sign. `detectionConfidence` gives the
detector's part alone.

## 5. Tests and continuous integration

Every pull request to `main`, and every push to `main`, runs
[.github/workflows/ci.yml](.github/workflows/ci.yml):

| Check | What it runs |
| --- | --- |
| `frontend` | ESLint and Oxlint, Vitest component and API contract tests, production build |
| `backend` | API and controller tests, the CPU YOLO demo test, the API contract snapshot, then the MySQL integration tests against a fresh Compose database |
| `research` | `fraction-solver` tests |

[CONTRIBUTING.md](CONTRIBUTING.md) lists the test tiers, the commands to
reproduce each check locally, and how known bugs and API changes are handled.
