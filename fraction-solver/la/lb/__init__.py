"""Linear B: the deciphered control corpus.

Everything the Linear A side of this project concluded is uncalibrated. "HT 9a
does not balance" is not interpretable without knowing how often a *competent*
Bronze Age Aegean accountant failed to balance a tablet. Linear B supplies that
baseline: same administrative tradition, same tablet genre, roughly the same
century — but deciphered, with published metrological values and machine-readable
scribal hands.

Two things live here:

* `fetch` / `parse` — the DAMOS corpus, tokenised into the same entry/total model
  `la.parse` builds for Linear A, so the same arithmetic machinery runs on both.
* `audit` / `ma` — the error-rate measurement, which is the point of the exercise.

Data licence: DAMOS content is CC BY-NC-SA 4.0 (Aurora, University of Oslo).
Non-commercial research use with attribution; the cache is local and never
redistributed.
"""
