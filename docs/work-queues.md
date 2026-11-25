# Work queues

Part of the scholars' workbench (story J). **Work queues** (`/queues`, in the account menu) list
where a scholar's attention is most useful. Each row links to the action it needs. The page is
for logged-in users, like the model's readings it draws on.

| Queue | Lists | Action |
|---|---|---|
| **Most disagreement**, scholars against the model | tablets where the model's reading differs most from the scholars' | Compare (scholars and model) |
| **Most disagreement**, scholars against the community edition | tablets whose accepted edition differs most from the scholars' | Compare (scholars and the edition) |
| **Low-confidence signs** | the model's least confident signs (below 50%) across the corpus, with its other guesses | Check, on the tablet with the model's boxes |
| **Awaiting review** (reviewers only) | sign corrections waiting for a reviewer: the Review page's queue | Review |
| **No edition yet** | tablets with a drawing here but no released edition, most signs first | Start an edition (the tablet's versions) |
| **Close votes** | tablets whose two most-backed releases are at most one vote apart, with no admin override | Vote |

**Disagreement** is counted per place on the tablet. The two readings' boxes are matched as in
Compare (`box_matching.py`). Each place either agrees (same sign), differs (different signs) or
has a box in only one reading. Tablets with the most places that differ come first, then
those where the largest share differs (the score), so a long tablet with many disagreements
comes before a two-sign fragment.

## The offline model readings

Reading the whole corpus with the model takes from half an hour to a few hours, so the
"against the model" and low-confidence queues come from an offline run:

```bash
python scripts/build_disagreement.py              # every tablet with a drawing here
python scripts/build_disagreement.py --limit 30   # only the next 30 tablets
```

- **Output:** it writes `models/disagreement.json`, which is not committed (`models/` is
  ignored). Set `DISAGREEMENT_FILE` to put it elsewhere.
- **Resuming:** the file is saved after each tablet, and tablets already read with the same
  model are skipped, so a run can be stopped and resumed.
- **A new model:** the run starts over.
- **Picking up results:** the server re-reads the file when it changes. Until it exists, the
  two queues say how to build it.

The other queues are computed live from the database.

## API

All routes take `offset` and `limit` (at most 100), and return `{total, items}` with the
items in queue order.

| Route | Does |
|---|---|
| `GET /queues/disagreement?against=model\|edition` | most places that differ first, then the largest share; `built_at` and `model_version` for the offline run, or `missing_hint` when it was not built |
| `GET /queues/low-confidence` | least confident first, with the `threshold` |
| `GET /queues/no-edition` | most signs first |
| `GET /queues/close-votes` | closest first, with the two most-backed releases |

Corrections awaiting review use the existing `GET /corrections?status=pending`.
