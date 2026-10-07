# Linear A fraction solver

An MVP that asks one question: **can the arithmetic on Linear A tablets determine the values of the script's fraction signs?**

Twelve of the seventeen fraction signs have published values (Corazza et al. 2021); five do not. Every tablet that lists entries and states a total gives one linear equation over those values. This tool builds that system, solves it exactly over rationals, and reports what the corpus does and does not determine.

**Answer, in short: it cannot.** See [FINDINGS.md](FINDINGS.md).

## Install and run

Requires Python 3.11+, `requests`, `sympy`, `pytest`.

```bash
python -m la.cli fetch      # crawl and cache lineara.eu (resumable, polite, ~15 min)
python -m la.cli census     # phase 0: how much evidence exists
python -m la.cli solve      # phase 2: build and analyse the linear system
python -m la.cli validate   # phase 3: leave-one-out recovery of published values
python -m la.cli images     # tablet tracings and sign crops for the sign detector (resumable)
python -m la.cli dataset    # YOLO sign-detection dataset in out/yolo_signs/
python -m pytest tests/ -q
```

Useful flags on `solve`:

| Flag | Effect |
|---|---|
| `--treat-all-unknown` | Ignore published values; solve for every fraction sign from the corpus alone |
| `--include-damaged` | Include sections with damage next to a quantity |
| `--grid full` | Widen the hypothesis space from unit fractions to all proper fractions |
| `--null-trials N` | Random assignments used for the chance baseline (default 5000) |

## How it works

```
fetch    lineara.eu sitemap -> per-document JSON -> data/cache/ + checksum manifest
parse    lines of tokens -> entries and totals, with sections, deficits and damage
census   how many tablets carry a total, fractions, and intact arithmetic
solve    sections -> linear equations over fraction values -> exact rank and identifiability
validate hide a published value, try to re-derive it
```

### Design decisions worth knowing

- **Exact arithmetic throughout.** `fractions.Fraction`, never floats. A third stays a third.
- **A bare `ki-ro` line is a heading, not an entry.** It opens the section that the following `ku-ro` totals. Getting this wrong makes tablets appear broken (see HT 88).
- **A section only constrains fraction values if its integers already balance.** A residual of 185 cannot be closed by fractions; such tablets are damaged, not informative.
- **Identifiability is reported, not hidden.** The solver distinguishes "determined by the corpus" from "constrained to a family", and reports inconsistency rather than silently fitting.
- **A null model accompanies every result.** With few equations, chance agreement is not negligible, and the headline number is meaningless without it.
- **Published values are versioned input with provenance** (`la/values.py`), each flagged verified or not, so they can be hidden for validation.

## Layout

```
la/fetch.py     polite, resumable, cached crawler + manifest
la/parse.py     document JSON -> tablets, sections, entries, totals
la/census.py    phase 0 counts and CSV export
la/solver.py    equations, exact identifiability, enumeration, null model, leave-one-out
la/values.py    published values with provenance and verification flags
la/cli.py       fetch / census / solve / validate
tests/          22 tests: golden tests on hand-verified tablets, synthetic solver checks
out/            generated: census.json, sections.csv, solve.json, validate.json
```

## Status and caveats

- The five published values in `la/values.py` are **unverified against the primary source** and came from a secondary summary. Check them against Corazza et al. (2021), *Journal of Archaeological Science* 125, 105214 before citing any comparison.
- Grand totals (`po-to-ku-ro`) are excluded: they sum sub-totals, not entries.
- This tests arithmetic evidence only, not the statistical and typological evidence the published values rest on.

## Data and licence

Corpus data from [lineara.eu](https://lineara.eu) (M. Navarre), derived from [SigLA](https://sigla.phis.me) (E. Salgarella & S. Castellan), licensed **CC BY-NC-SA 4.0**. Used here non-commercially with attribution. The Linear A cache (`data/cache/`, `data/images/`) is committed so the project works without a crawl; the Linear B corpus (`data/damos/`) stays local.

Code in this repository is available under the MIT licence.
