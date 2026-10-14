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

Install the frontend, backend and the data libraries imported by the backend:

```bash
npm install
npm --prefix frontend install
uv sync --project backend
uv pip install --python backend/.venv -r fraction-solver/requirements-data.txt
```

Repeat the last command if a later `uv sync` removes these additional libraries.

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

The trained Linear A model is installed at `models/linear_a_signs.pt` (the
`best.pt` checkpoint from the `linear_a_signs` training run, with 361 classes).
The demo loads this file, or the path set through
`SIGN_DETECTOR_WEIGHTS` in `.env`. Otherwise, it uses the generic `yolo26n.pt`,
which has not been trained on Linear A characters.

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

With this environment active, generate the dataset:

```bash
python -m pip install -r fraction-solver/requirements-data.txt
cd fraction-solver
python -m la.cli dataset --labels identity --workers 2
cd ..
```

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

Start training from the repository root:

```bash
python train.py
```

[train.py](train.py) loads the pretrained weights, then adapts them to the
annotated character dataset. Its explicit settings are:

| Parameter | Value | Meaning |
|---|---|---|
| Model | `yolo26n.pt` | Pretrained YOLO26 nano model |
| `data` | `fraction-solver/out/yolo_signs/data.yaml` | Images, splits and class names |
| `epochs` | `100` | Maximum number of passes over the training set |
| `batch` | `8` | Images processed together in a batch |
| `imgsz` | `1024` | Target input size, in pixels |
| `patience` | `20` | Stop after 20 epochs without validation improvement |
| `project` | `runs/detect` | Parent folder for training outputs |
| `name` | `linear_a_signs` | Training run name |

Edit these values in `train.py` to change the run. Reduce `batch` if GPU memory
is insufficient. The script leaves the device, optimizer, learning rate and
augmentations at Ultralytics defaults. With no explicit device, it uses an
available CUDA GPU or falls back to CPU; Apple Silicon users can add
`device="mps"` to `model.train(...)`.

For each batch, YOLO predicts boxes and classes, compares them with the label
files, and uses the resulting errors to update its weights. Validation measures
progress on `val` and selects the best checkpoint. The `test` set is reserved for
final evaluation. The predicted reading is the label associated with a learned
sign class, not a newly inferred pronunciation.

Outputs are saved under `runs/detect/linear_a_signs/`, with a numbered suffix
if that run folder already exists:

- `weights/best.pt`: the checkpoint selected using validation performance.
- `weights/last.pt`: the last checkpoint, usable to resume an interrupted run.
- `results.csv` and plots: training losses and validation metrics.

To resume a run, adjust the path if your run has a numbered suffix:

```bash
yolo detect train resume model=runs/detect/linear_a_signs/weights/last.pt
```

Evaluate the selected model on the test set:

```bash
yolo detect val model=runs/detect/linear_a_signs/weights/best.pt data=fraction-solver/out/yolo_signs/data.yaml split=test imgsz=1024 batch=8
```

Report precision, recall, mAP50 and mAP50-95, including per-class results and
class coverage. A prediction confidence score is not the same as measured
accuracy or certainty about a historical pronunciation.

To use the trained model in the application, copy `best.pt` to
`models/linear_a_signs.pt` (create `models/` if needed), or set an absolute
`SIGN_DETECTOR_WEIGHTS` path in `.env`, then restart the backend. Its inference
image size is currently 1024, matching the training script.
