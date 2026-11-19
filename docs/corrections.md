# Sign corrections (#52)

Users can correct the signs the Linear A reader found on their own saved analyses.
Results of the generic fallback model (`yolo26n.pt`, used when the reader's
weights are missing) find objects, not Linear A signs, so they cannot be corrected. Every correction
is reviewed before it can become a training label; nothing changes the saved
analysis or the deployed model.

## Setup

For a database created before this feature, apply the migration once:

```bash
mysql -h 127.0.0.1 -P 3306 -u YOUR_MYSQL_USER -p ase3 < backend/app/database/migration-52/052_sign_correction.sql
```

Reviewers have the reviewer role, which admins grant on the **Admin** page (see
[roles](roles.md)), or are listed in `SIGN_REVIEWERS` in `.env`, comma-separated and
case-insensitive. The seeded `dev` account has the role, and `.env.example` also lists it.

## Reviewing

Reviewers see a **Review** link in the top bar. The page lists the corrections to
review, grouped by sign, and says when users disagree on a sign. Each correction
can be approved or rejected; the tabs show what was already decided, and **Export
approved (JSON)** downloads the export described below. The session (`/users/me`
and the login response) tells the frontend whether the user is a reviewer through
its `reviewer` field; the API checks it again on every review route.

## What is stored

Each submission keeps the analysis it belongs to, the detected sign's ID and box
(fractions of the image size), the model's original sign, label and confidence,
the model version, and either the proposed sign or an uncertainty flag, with an
optional note. The original prediction and box are read from the saved analysis
on the server, not taken from the request.

The model version names the weight files that read the tablet and a hash of each,
for example `linear_a_signs.pt@3f2a9c1d07be+linear_a_classifier.pt@91b0e4c2aa10`.
Analyses saved before this feature have no version; their corrections record
`unknown`.

Several submissions for the same sign are all kept, so a reviewer can compare
them. Reviewers cannot decide on their own corrections, and a reviewed
correction cannot be reviewed again.

Sign IDs are spelled as in the training data (`AB01`, `AB131a`, `A707`); a
proposed sign is matched however it is written (`ab1`, `AB001` and `AB01` are
the same sign).

The uploaded image is still not stored (see the history notes in the README), so
the export identifies each sign by its analysis and pixel box. Once images are
stored, the export can join them to produce training crops.

## API

All routes need a logged-in session; writes also need the `X-CSRF-Token` header.

| Route | Who | Purpose |
|---|---|---|
| `GET /corrections/catalogue` | anyone | Signs a correction may propose: the classifier's classes and every Unicode Linear A sign |
| `POST /analysis/{analysis_id}/corrections` | analysis owner | Submit `{sign_id, proposed_sign}` or `{sign_id, uncertain: true}`, with an optional `note` (up to 500 characters). Returns 201 with status `pending` |
| `GET /analysis/{analysis_id}/corrections` | analysis owner | The user's own corrections of that analysis |
| `GET /corrections?status=pending` | reviewer | The review queue, oldest first (`status` can also be `approved` or `rejected`) |
| `POST /corrections/{id}/review` | reviewer | `{decision: "approved" \| "rejected"}`. 403 for the reviewer's own correction, 409 if already reviewed |
| `GET /corrections/export` | reviewer | Approved replacement signs, grouped by analysis, for training |

Errors: 404 when the analysis is not the user's or has no such sign, 422 for a sign
outside the catalogue, equal to the model's reading or read by the generic model,
403 for non-reviewers.

## Export format

One entry per analysis, with signs as in the training annotations
(`fraction-solver/la/signboxes.py`): the sign ID, its box in pixels as
`xyxy` (x0, y0, x1, y1) and its `source`, here `"correction"`.

```json
[
  {
    "analysis_id": 12,
    "filename": "tablet.png",
    "width": 1000,
    "height": 800,
    "signs": [
      {"sign": "AB81", "xyxy": [100, 160, 150, 208], "source": "correction",
       "original_sign": "AB59", "model_version": "linear_a_signs.pt@3f2a9c1d07be", "correction_id": 9}
    ]
  }
]
```

Uncertainty flags carry no label, so they are not exported, even when approved.
