# Can tablet evidence determine Linear A's fraction values?

**Corpora:** all 1,883 Linear A documents from lineara.eu, cached 23 September 2026; all ~5,900 Linear B documents from DAMOS, cached 24 September 2026 · **Code:** `python -m la.cli` · **Tests:** 193 passing

---

## Summary

**No — not from arithmetic, and not from the writing order either.** The evidence is far thinner than the corpus size suggests, and this document sets out exactly how thin, which is the useful part.

Five channels were tested:

| Channel | What it yields |
|---|---|
| **Tablet arithmetic** | 2 exact equations and 1 bound, in 1,883 documents |
| **Writing order** | A well-evidenced convention, but value inferences resting on single attestations |
| **Ration ratios** | 1 usable tablet — which nonetheless gives a result worth having |
| **Numeral restoration** | 0 of 195 Linear A gaps uniquely restorable, against 39 of 40 in Linear B — the difference is a carry rule, which Linear A lacks |
| **A Linear B baseline** | Attempted and **not obtained**. Within-tablet totals yield 2 auditable sections in 5,932 documents; the Pylos Ma series measures tax reductions, not error (§7) |

Along the way the tooling reproduced three things the literature already knew, which is the best available check that it works: it derived J = 1/2 from the same tablet the field uses for that purpose, flagged exactly the tablets a published audit lists as miscalculations, and arrived at the same reason the original authors gave for not relying on arithmetic.

**Two findings are new, one is a software gap rather than a discovery, and two earlier claims have been withdrawn after a literature check.**

*New, probably:* PE 1's broken headcount, which Corazza et al. restore by assuming J = 1/2, can instead be **derived** together with J. Requiring only a whole number of people and a proper fraction, the headcount is 52 + 2J with 0 < 2J < 2, so **2J = 1 and both J = 1/2 and the headcount 53 are forced**. Their version of the argument has no discriminating power — *any* proper fraction gives a headcount between 52 and 54, compatible with the surviving `50[`. Ours is independent of HT 104: the condition HT 104 must *assume* — that no further fraction sign followed the J — is on PE 1 a matter of reading, since the break falls on the headcount and not on the grain. **It proves a conditional, not a fact**, and the full assumption list is in the appendix to `ASE_LinearA_Pitch.docx`. **Novelty unconfirmed:** the *editio princeps* (Tsipopoulou & Hallager, SMEA 37, 1996), cited for the restoration of 53, could not be obtained and is the likeliest place for this argument to exist already.

*New:* **Linear A numerals are not uniquely restorable, and the reason is structural.** Linear B's carry rule (six V make a T) makes a value's written form essentially canonical, so a restorable gap is either unique or impossible. Linear A has no carry rule, so a shortfall can be spelled many ways. Held-out corruption: 39 of 40 Linear B truncations uniquely restored, **0 of 195** Linear A ones. The Linear B side comes from a single section, so the argument rests on the mechanism — which is proved as a test, not inferred from the corpus (§6).

*A gap, not a discovery:* lineara.eu's arithmetic check sums integers only, so **HT 13 is reported there as balancing when it is off by exactly 1/2**. The imbalance itself is not new — Younger states it directly: *"KU-RO here records 130.5, but the numbers total 131."* What our tooling adds is that the discrepancy is invisible to the digital corpus, and that the residual is computed exactly rather than by hand.

*Withdrawn:* **"`ME` was assessed to the nearest 50."** True, and not new — Shelmerdine quantifies the per-commodity rounding offsets (F = `ME` at +87 against −1.5, 0 and −0.75 for the others), and de Fidio restores `ME` in multiples of 50 as a matter of course (§7).

*Withdrawn:* **"a quantified figure for Mycenaean accounting exactness."** The 14.9% deviation over 74 Ma values is a correct measurement of deviation from Bennett's 1951 ratio, but the literature reads such deviations as **deliberate tax reductions**, not scribal error. It cannot serve as the base rate it was built to supply, so the Linear A comparison that rested on it is withdrawn too (§7).

---

## 1. Arithmetic

### What exists

| Measure | Count |
|---|---|
| Documents | 1,883 |
| Containing fraction signs | 189 |
| Containing a total (`ku-ro` / `po-to-ku-ro`) | 35 |
| Containing **both** | 11 |
| Sections with fraction arithmetic | 6 |
| **Yielding an exact equation** | **2** |
| Yielding a bound (something is broken) | 1 |

### The constraints

| Tablet | Constraint | Implication |
|---|---|---|
| HT 104 | 2·J = 1 | **J = 1/2** — matches the published value |
| HT 9a | E + 2·J = 2 | forces **E = 1** — impossible for a fraction |
| HT 13 | 1·J ≤ 0 | a bound; the line is broken on both sides |

The two equations are mutually **consistent**, and together they determine J = 1/2 correctly and then demand an impossible E. The fault therefore localises to **HT 9a alone** — which Montecchi's audit already lists as a miscalculation, and which Younger analyses in the same terms we arrived at independently: *"the total 29+3J+2E equals 31, not 31+J+E"*.

### Can the unvalued signs be reached?

**No.** Every usable equation involves only J and E, the two most frequent signs, both long since published. None of W, X, Y, Ω or L appears in a tablet whose arithmetic works.

### Validation

Hiding each published value and re-deriving it from the corpus alone recovers **0 of 15**. A method that cannot reproduce known values is in no position to propose new ones. The best assignment explains 1 of 3 constraints; chance explains 1 of 3.

---

## 2. Writing order

Fractions are written in decreasing value, so `J E` asserts J > E without any arithmetic.

**Compound signs must be decomposed first.** The corpus records the same thing two ways — DD as one token 6 times, as two adjacent D tokens 11 times — and SigLA's tracing settles which is canonical: on HT 100 the transcription reads `JE` while the tracing records **two separate marks**, J then E. Treating compounds as single signs hides the evidence:

| | Raw encoding | Decomposed |
|---|---|---|
| Runs of adjacent fractions | 61 | **95** |
| Transitions between different signs | 41 | **73** |
| J → E attestations | 1 | **32** |

The 32 matches Corazza et al.'s own count of the JE sequence, which is a good sign the decomposition is right.

**The convention is well evidenced.** J precedes E 32 times against **one** counter-example — ZA 8 line 6, a reading the authors themselves call doubtful. The graph is acyclic on majority directions (p = 0.027 under random orientation), and published values respect 17 of 19 checkable pairs.

**The value inferences are not.** Both violations rest on a single attestation:

| Pair | Tablet | Published | Note |
|---|---|---|---|
| H → K | HT 34.6 | 1/16 vs 1/10 | H is tentative in the paper |
| A → B | KH 86.2 | 1/24 vs 1/5 | A is tentative; Corazza et al. re-read this line as `A A` |

Implied windows, and how little weight they bear:

| Scenario | A | H |
|---|---|---|
| All pairs (n ≥ 1) | 1/5 < A < 1/2 | 1/10 < H < 1/2 |
| **Pairs with n ≥ 2** | **no constraint** | **no constraint** |
| Remove KH 86 | no lower bound; Corazza's 1/24 fits | unchanged |
| Remove HT 34 | unchanged | no lower bound; Corazza's 1/16 fits |

**Remove one attestation and the published values are perfectly consistent.** The channel mildly favours Younger's H = 1/6 over Corazza's tentative 1/16, and points at two tablets worth re-examining. It cannot do more than that.

---

## 3. Ration ratios

Some tablets record a headcount beside the commodity issued to it. **PE 1 (Petras)** has a complete statement and a broken one:

```
VIR 72   ...  A574 36      ->  ration = 1/2 per person
VIR 50[  ...  A574 26 J    ->  (50 or more) x 1/2 = 26 + J
```

The literature restores the broken headcount as 53 by conjecture, then argues J = 1/2. Leaving the headcount unknown and requiring only that a fraction sign denote a *proper* fraction, **exactly one of 41 candidate headcounts survives: 53 people, J = 1/2**. The restoration is derived rather than assumed, and J = 1/2 gains a confirmation independent of HT 104.

**Scope.** Pairing a headcount line with the line below it is a guess about layout, and most such guesses are wrong: 8 of 17 candidate pairs imply absurd rations and are discarded. Nine plausible statements remain, and PE 1 is the only one where a complete pair fixes the ration and a broken pair can then be solved.

---

## 4. Shape analysis

A classical pipeline — binarise, trim, scale, centre, then compare by Hu moments, overlap and contour distance — with no training data.

**It works.** Leave-one-out retrieval over 325 fraction tracings:

| Descriptor | top-1 | top-5 |
|---|---|---|
| Frequency baseline | 19.4% | — |
| Hu moments | 45.3% | 76.1% |
| Overlap (IoU) | 79.5% | 90.1% |
| **Contour (Hausdorff)** | **88.2%** | **92.5%** |

Per sign: J 97%, B 95%, K 95%, E 94%, A 93%, D 92% — and 50% for L2, 0% for X, L3, L4 and L6. **Attestation count is the limit, not method.**

### Does KH 86 read `A B B` or `A A`?

Our A-window depends on the first reading. Comparing each mark to the A and B populations, excluding all glyphs from KH 86 so one scribe's hand cannot match itself:

| Position | Transcribed | to A | to B | Nearer |
|---|---|---|---|---|
| 5 | A | **25.6** | 26.4 | A, narrowly |
| 6 | B | 27.9 | **23.5** | B |
| 7 | B | 26.1 | **19.0** | B |

The disputed marks sit with the B population, supporting GORILA and Younger. **The confound is unavoidable:** SigLA's tracer drew what they read, so this cannot fully separate "looks like B" from "was read as B".

### Does this scale to the whole sign inventory?

The 88% figure covers 16 fraction signs — the easy case. Repeating the measurement over **5,076 tracings across 233 sign types**, the entire traced corpus, gives a very different picture.

Overlap (IoU) is used rather than contour distance: it scores a few points lower but computes as a matrix product, which is the difference between two minutes and a day at this size.

| | Result |
|---|---|
| top-1 | **35.1%** |
| top-5 | 58.2% |
| Frequency baseline | 1.76% |
| Random baseline | 0.28% |

Twenty times the baseline, and useless as a headline. **The gradient is the finding:**

| Attestations per sign | Sign types | Glyphs | top-1 |
|---|---|---|---|
| 2–4 | 79 | 186 | **3.8%** |
| 5–9 | 32 | 206 | 7.3% |
| 10–24 | 34 | 559 | 12.2% |
| 25–49 | 21 | 771 | 29.1% |
| 50+ | 31 | 3,152 | **44.3%** |

Even the best-attested signs reach only 44%. Fractions score 64% against 36% for syllabograms and 33% for logograms — they really are the easy subset, and generalising from them would have been badly misleading.

**What the corpus offers, for anyone designing around this:**

| Threshold | Sign types | Share of corpus |
|---|---|---|
| ≥ 5 attestations | 118 | 92% |
| ≥ 10 | 86 | 88% |
| ≥ 25 | 52 | 77% |
| ≥ 50 | 31 | 62% |

So 88% of all written marks belong to a sign with ten or more examples — but at ten examples accuracy is only 12%.

**The same-tablet leak is small here (+0.7%)**, unlike in the fraction work, because most signs recur across many tablets. It is still excluded everywhere.

**Conclusion: classical shape descriptors do not solve Linear A sign classification.** They work well on frequent, visually distinct signs and fail on everything else, which is most of the inventory. Any reader built on this needs either learned features, stroke-level representations, or a design that only ever claims the signs it can actually identify.

### Are W and X compound signs? — tested, then retracted

See the appendix. The test could not be calibrated with these data, and its conclusions are withdrawn. The only thing left standing is structural: **W and X are each traced as a single mark**, while JE and DD are traced as two — weak evidence against the compound reading, carrying the same circularity as everything else resting on the tracings.

---

## 5. How much image evidence exists

| | Count |
|---|---|
| Documents with a SigLA tracing | 776 |
| …whose tracing **includes** fraction marks | **112** |
| Fraction crops obtainable | **326 — the complete set** |
| Fraction marks in transcriptions of traced documents | 434 |

The 138-mark shortfall was never drawn, so it cannot be recovered: probing SigLA directly, ZA 8's crops run `_1` to `_30` and `_31` returns 404, and its traced signs are all syllabograms plus one logogram. **ZA 8** (our lone E→J counter-example) and **KH 7a** (the sole basis for B = 1/5) have no fraction tracings at all.

A visual reference of one attestation per sign is at `out/fraction_signs.png`.

---

## 6. Which damaged numerals the arithmetic determines

Where a break has swallowed part of a quantity, the tablet's own total sometimes forces the reading. This asks, corpus-wide, when that happens — and the answer turned out to depend on a property of the script rather than of the tablets.

### The distinction the literature has no name for

Restoration work splits cleanly into two kinds, and nothing found in a targeted search separates them for numerals:

- **Ithaca** (Assael et al., *Nature* 603, 2022) restores Greek inscriptions probabilistically, ranking a top-20 from a 35,884-word vocabulary. It handles **no numerals at all**.
- **Born, Monroe, Kelley & Sarkar** (CAWL 2023) come closest: a subset-sum solver over proto-Elamite summary tablets. But it *disambiguates* which metrological reading an intact numeral carries and **explicitly discards damaged numerals**. Arithmetic disambiguates there; it never restores.

So the verdict a gap receives is the output here, not a ranking:

| Verdict | What it licenses |
|---|---|
| `UNIQUE` | One amount, one place, one spelling. The signs in the gap are determined. |
| `AMOUNT_DETERMINED` | Every gap's amount is fixed but several sign sequences express it. **With a single gap this follows from arithmetic alone** and is not a contribution of the notation. |
| `AMBIGUOUS` | The shortfall divides between the gaps in more than one way. |
| `IMPOSSIBLE` | No legal amount balances the section, so the break cannot explain it. |
| `ERROR_NO_DAMAGE` | Nothing is broken and it still does not balance. |
| `OVERFULL` | Entries exceed an intact total; a break cannot subtract. |

### What makes uniqueness possible is bundling, not arithmetic

An amount is not a free number: it is a sequence of signs obeying conventions that make most values unwriteable in a given gap. Two of them do the work.

**Writing order.** Units descend, so a break after `S 2` can hide more S, or V and Z after them, but never a whole unit — that would have been written first. This holds in both scripts; Linear A's decreasing-value convention is the one established in §2.

**Bundling.** Six V make a T, so a scribe writes `T 1 V 1`, not `V 7`. This is the decisive one, and **Linear A does not have it.** A carry rule makes the written form of a value essentially canonical, so where a restoration is possible at all it is usually the *only* one. Without it, a shortfall can be spelled many ways.

**The mechanism is provable, not just observed.** Under a carry rule every value has essentially one written form, so a single-gap restoration is either unique or impossible — never merely likely. That is asserted as a test over residuals 1 to 24 (`tests/test_recover.py::TestBundlingMakesRestorationUnique`), not inferred from the corpus, because the corpus is far too thin to establish it.

The held-out corruption test then measures the difference on real tablets. Sections that balance and carry no damage are truncated at a legal break point, and recovery is asked to restore what it cannot see — the true answer known by construction, which is the only way to get an accuracy figure when the real lost text is gone.

| Script | Sections that balance | Truncations | `UNIQUE` | Exact signs recovered |
|---|---|---|---|---|
| **Linear B** (bundled units) | **1** | 40 | **39** | **39** |
| **Linear A** (fraction signs, no carry rule) | **7** | 195 | **0** | — |

**Read "sections that balance", not "`UNIQUE`".** The Linear B corpus yields exactly *one* section that both balances and is complete enough to corrupt, so its 40 truncations are 40 views of one tablet, not 40 independent samples. Its single failure is an `IMPOSSIBLE` — a residual no legal sequence could express in that gap, which is itself the notation doing work.

Linear A's 195 truncations come from 7 sections and returned **0 `UNIQUE`**: 181 `AMOUNT_DETERMINED`, 10 `IMPOSSIBLE`, 4 where the search exceeded its bound. The amount was right every time it was claimed and never *only* right one way. Here the asymmetry is not a sampling artefact — Linear A has the larger sample and still yields nothing unique.

So the corpus illustrates the mechanism rather than establishing it, and the conclusion rests on the proof: **Linear A numerals are not uniquely restorable, and the reason is structural — no carry rule.**

**Sensitivity.** Switching the carry rule off — modelling a scribe who violated it — turns Linear A's determinations into ambiguity, with most of the rest exceeding the search bound. Nothing on the Linear A side survives relaxing the repetition assumption, which is stated in the code as an assumption rather than a fact about the script.

### The two Linear A sections that reach a verdict

Of 1,883 documents, two sections have arithmetic that says something is missing, and **both reproduce a published observation**:

| Tablet | Verdict | Residual | The published claim it matches |
|---|---|---|---|
| **HT 9a** | `ERROR_NO_DAMAGE` | **+3/4** | Younger places the missing amount on side b.1, reading it as possibly **JE** — and JE *is* 3/4 |
| **HT 13** | `OVERFULL` | **−1/2** | Younger: *"KU-RO here records 130.5, but the numbers total 131"* |

HT 9a is the better check. The residual 3/4 was computed with no knowledge of Younger's proposal, and it is exactly the value of a sign already on that tablet. What the pipeline cannot do is complete the restoration: this corpus stores sides a and b as separate documents, so no single section holds both his broken entry and the total it belongs to.

**A negative worth stating.** HT 116b is not reached at all — its section has a total and no surviving entries, so there is nothing to constrain. A numeral-misreading hypothesis of the kind Younger proposes there (a stray last stroke on `OLE+MI 6`) is a different error model from the one built here, which only ever *adds* to a broken quantity.

---

## 7. A Linear B baseline — attempted, and not obtained

Everything in §1 is uncalibrated. **"HT 9a is short by 3/4" is uninterpretable without a base rate.** If competent Mycenaean accountants failed to balance one tablet in seven, a handful of Linear A failures is unremarkable; if they failed one in fifty, they are anomalies needing explanation. A targeted search found **no published systematic arithmetic audit of Linear B and no published error rate for Mycenaean accounting**, which is what motivated this section.

**That search asked the wrong question, and the error runs through everything below.** No corpus-wide arithmetic *audit* of Linear B has been published — but the arithmetic of the tablet series this section then used has been studied exhaustively since 1951, and the quantity it measures is understood there as fiscal policy rather than error. The section is kept in full, with the correction at the end, because how it went wrong is more useful than the numbers were.

Linear B is the right control — same administrative tradition, same genre, roughly the same century, but deciphered, with published metrology and a scribal hand on most documents. **Corpus:** all of DAMOS (F. Aurora, Univ. of Oslo), CC BY-NC-SA 4.0.

> **Retracted as a finding, retained as a validation.** A literature check done after this section was written establishes that everything the Ma pilot produced is already published, and that the pilot was measuring the wrong quantity. The corrected reading is at the end of §7 under *"What the literature check did to this section"*. The numbers below are correct; their interpretation as an error rate is not.

### The parser reproduces a published ratio

Before any error rate, a check that these documents are being read correctly. The **Pylos Ma assessment ratio was re-derived from the tablets** by consensus fitting over simple fractions, returning all six published values exactly: `*146 : RI : KE : *152 : O : ME = 7 : 7 : 2 : 3 : 1.5 : 150`. That is the strongest available evidence that the transliterations are being tokenised right.

The ratio is **Bennett's, from 1951**, and is standard — Shelmerdine calls it *"a fixed ratio of fiscal units first identified by Bennett, and usually cited as 7 : 7 : 2 : 3 : 1.5 : 150."* An earlier draft of this document attributed it to Palaima 2004; that was a misattribution and is corrected in `docs/sources.md`. The literature labels the six commodities **A–F**, which map onto our sign order exactly: A = `*146` (textiles), B = `RI`, C = `KE`, D = `*152` (oxhides), E = `O`, F = `ME`.

**What could not be done, and is worth recording as a negative.** The plan was to re-derive the *unit* ratios (1 T = 6 V, 1 V = 4 Z) the same way, treating each balanced section as a linear equation over unit sizes and solving exactly — the machinery §1 applies to Linear A. Run over the whole corpus it produces **zero usable equations**: no surviving section combines two units of one capacity series, balances, and is complete. So the subunit ratios stay at the verification level their sources give them (see `docs/sources.md`) and are not corroborated here.

### The first channel is nearly empty, and that is the finding

| | |
|---|---|
| DAMOS documents | **5,932** |
| containing a total word (`to-so`, `to-sa`, `ku-su-to-ro-qa`, `ku-su-pa`) | 197 |
| yielding a parsed total quantity | 122 |
| yielding a section with two or more entries | **36** |
| of those: content certainly missing above the total | **28** |
| of those: tablet breaks off within the span (edge) | 7 |
| of those: complete throughout (clean) | **1** |
| **auditable** (complete, units resolved, nothing editor-restored) | **2** — of which 1 fails |
| **scorable at the clean tier** | **0** |

Only **3 of the 61 Knossos documents carrying a total word are free of brackets and *mutila* notes altogether.** The archives burned and broke; entries lost above a total make its sum unauditable however legible the total itself is. A further within-tablet relation was tried and is equally thin: *assessment = delivery + deficit* is checkable on **2** tablets.

Two auditable sections cannot support anything. The channel is reported so that the next person does not spend the effort discovering the same.

**This explains the gap in the literature.** No one has published a Mycenaean accounting error rate from within-tablet totals because the evidence for one does not exist. Anyone repeating this should not expect that channel to deliver, and that is worth knowing before spending the effort.

### The second channel does deliver: the Pylos Ma series

The Ma assessments' fixed ratio constrains every value on eighteen tablets whether or not a total survives. That makes it the usable baseline — and it required separating two things first.

**Rounding is not error.** The assessment scale is `*146 / 7`; where that is not a whole number the scribe had to round. Scored at unit precision, `ME` matched the ratio only 42% of the time against 70–94% for the other five commodities — which looked like carelessness about the largest commodity. But every `ME` deviation was a multiple of 7, the signature of dividing by 7 and then writing a round number, and the attested values are 400, 500, 600, 900, 1000, 1350, 1500. Fitting the granularity rather than assuming it:

| Commodity | Best granularity | Match rate | at unit precision |
|---|---|---|---|
| RI | 1 | 0.94 | 0.94 |
| KE | 1 | 0.80 | 0.80 |
| `*152` | 1 | 0.81 | 0.81 |
| O | 1 | 0.80 | 0.80 |
| **ME** | **50** | **0.92** | 0.42 |

**`ME` was assessed to the nearest 50; the other five to the nearest unit.** That converts 22 apparent arithmetic errors into a rounding convention.

**Not new.** Shelmerdine quantifies the per-commodity rounding directly — *"Rounding off from 149x to extant figures for other commodities: A/B −1.5; C 0; E −0.75; F +87"* — where F is `ME`, and its offset is two orders of magnitude larger than any other commodity's. The literature also works in multiples of 50 for `ME` as a matter of course: de Fidio restores 450 for it on Ma 346. That `ME` is the coarsely-rounded commodity is established, and rounding in general is treated as unavoidable: *"The adjusted ratio … requires many fractions, and consequently much rounding off of numbers to reach the extant figures. Some rounding off will be needed on any scheme."*

There is also a confound I can't remove: `ME` is the only commodity whose values are large enough (400–1500) for coarse rounding to be visible at all. The other five run from 1 to 70, where "nearest unit" is not a choice. And anchoring the ratio on `ME` instead of `*146` fits the remaining commodities equally well (76.8% against 77.0%), so **the data does not establish that `ME` is the derived figure rather than the base** — which is the seventy-year-old Lejeune "bottom-up" versus Wyatt "top-down" question, not something this project can settle.

**The baseline.** With rounding modelled, over 74 undamaged assessment values on 18 tablets:

| | |
|---|---|
| values checked | **74** |
| deviating from the ratio | **11** |
| **deviation rate** | **14.9%** |
| mean absolute deviation | 0.49 |
| tablets matching exactly | 8 of 18 |
| (before modelling rounding) | 17/74 = 23.0%, MAD 1.30 |

Four deviations are too large to be rounding:

| Tablet | Commodity | Written | Ratio implies | | Status in the literature |
|---|---|---|---|---|---|
| PY Ma 193 | ME | 362 | 350 | +12 | — |
| **PY Ma 225** | `*152` | **22** | **12** | **+10** | **Wyatt 1962, 25 n. 41: *"likely to be scribal error since 12 fits the ratio"*** |
| PY Ma 216 | O | 20 | 15 | +5 | — |
| PY Ma 126 | RI | 1 | 3 | −2 | — |

The largest and most obvious of the four — Ma 225's 22 for 12, one extra ten-stroke — was identified as a scribal error by Wyatt in **1962**. Finding it independently is a check on the pipeline, not a contribution.

**Validation.** Hiding each surviving value and predicting it from `*146` alone recovers **63 of 74 exactly (85%)**, and 94.6% within 1. A method that could not re-predict values that survive would have no standing to propose values that do not.

**The ratio also restores — as epigraphers have long used it to.** Twelve broken assessment values get a prediction; six change a surviving reading. Each is falsifiable against the clay, because a break cannot shrink a numeral, so a prediction below what survives refutes itself.

| Tablet | Commodity | Survives | Ratio predicts | Already published? |
|---|---|---|---|---|
| PY Ma 221 | O | `M 4[` | 5 | **Yes** — Shelmerdine n. 11: *"the figures extant are 4[ and 400[ … 5 and 500 could be restored (though nothing higher), and these numbers do fit the ratio"* |
| PY Ma 221 | ME | `400[` | 450 | **Yes** — same note restores 500; de Fidio restores 450 on the parallel Ma 346 |
| PY Ma 244 | KE | 4 | 7 | — |
| PY Ma 244 | ME | 400 | 500 | — |
| PY Ma 365 | RI | `M 14[` | 17 | — |
| PY Ma 397 | KE | `M 2[` | 7 | Likely; PTT I carries ratio-based restorations of this kind |

The other six confirm that the break hid nothing.

Two things to notice. Shelmerdine's parenthesis — *"though nothing higher"* — **is the admissibility check I implemented as "a break cannot shrink a numeral", done by hand in the 1980s.** And on Ma 120 the literature records commodity E being *predicted* as 14 from the ratio, restored in PTT I in preference to a fractional 13.5, and then **confirmed by a new reading of the tablet**. That is precisely the workflow this module automates, already completed and already vindicated — which is reassuring about the method and fatal to its novelty.

### What the literature check did to this section

The Ma pilot was built to supply a base rate for Mycenaean accounting error. Reading the taxation literature afterwards establishes that **it does not measure error at all**, and this is the most important correction in the document.

**Deviation from the ratio is, in the mainstream reading, fiscal policy.** de Fidio's 1982 thesis is that the figures on the tablets *"are not those originally intended, but reflect systematic reductions of a larger assessment"*; the Ma tablets themselves record exemptions (`o-u-di-do-si`, "they do not give") and arrears (`o-pe-ro`) explicitly. Shelmerdine's paper is an evaluation of competing *reduction schemes*. So a district assessed below the ratio is, on the standard view, a district granted relief — not a scribe who miscalculated. Out of the four deviations my audit flags, the literature calls exactly one a scribal error: Ma 225's 22 for 12, and Wyatt said so in 1962.

**That makes the headline figure a category error.** "11 of 74 values deviate, 14.9%" is a correct measurement of deviation from Bennett's ratio. It is not a Mycenaean accounting error rate, and it cannot calibrate HT 9a, which was the entire purpose. Reporting it as one would put a number on scribal incompetence that is mostly a record of tax relief.

The Linear A comparison that followed is therefore withdrawn:

| | Sections scored | Failures | Rate | |
|---|---|---|---|---|
| **Linear A**, intact sections | 12 | 5 | 41.7% | n too small to support a rate |
| — integers only (no value system assumed) | 10 | 4 | 40.0% | |
| **Linear B**, Pylos Ma values | 74 | 11 | 14.9% | **measures reductions, not errors** |

The two sides never measured the same thing, and the Linear B side does not measure what its label claimed. **No base rate for Mycenaean accounting error was obtained, and the question "is HT 9a's 3/4 shortfall unusual?" remains open.**

### What survives

1. **The scarcity result.** Two auditable sections in 5,932 documents. Within-tablet totals cannot supply an error rate, and that is worth knowing before anyone spends the effort. Unaffected by the above.
2. **A validated pipeline.** Every substantive output independently matched a published conclusion: the ratio (Bennett 1951), the coarse rounding of `ME` (Shelmerdine's F +87), the Ma 225 anomaly (Wyatt 1962), and the Ma 221 restorations including the *"nothing higher"* break-capacity argument. Four independent agreements with the literature is strong evidence the parser reads these documents correctly — which is what makes the scarcity result above trustworthy.
3. **Nothing else.** The Ma pilot yielded no new claim about the ancient world.

### If the base rate is still wanted

The measurement needs a channel where deviation cannot be policy. Two candidates, neither attempted here:

- **Internal sums on a single tablet**, where a scribe's own total must match their own entries — the channel §7 has just shown to be nearly empty at 2 sections. Widening it would mean cross-tablet totalling (the Knossos Dn-series totals the Da–Dg sheep tablets), which needs scholarly knowledge of which tablets a totalling tablet covers that DAMOS does not encode.
- **Judson's *"Scribes as Editors"*** (AJA 124.4, 2020, open access), which catalogues scribal corrections corpus-wide. Errors a scribe *caught and fixed* are unambiguously errors. That is the right source, it was flagged as "read first" before this work began, and it was not read.

### Caveats that stand regardless

- The subunit ratios (1 T = 6 V, 1 V = 4 Z) remain the least-verified load-bearing numbers here: Palaima was read and gives only the top of each chain, and the attempt to corroborate the rest from the corpus produced zero usable equations.
- The per-hand and per-site breakdowns the audit computes are empty at this corpus size.

---

## What this means

**For the field:** nothing here overturns a published value, and the Linear A imbalances we detect were found by hand long ago — Montecchi's audit lists them, and Younger's commentary discusses each tablet individually. The contribution is narrower and mostly methodological: a precise account of what the arithmetic and ordering evidence can and cannot support, a derived rather than assumed restoration for PE 1, and exact fraction-aware checking that the digital corpus currently lacks.

The Linear B work adds less than intended, and the honest accounting is short. Its one surviving contribution to the field is the observation that **restorability is a property of the notation**: Linear B's carry rule makes numerals recoverable and Linear A's absence of one makes them not, which sets a ceiling on any future Linear A restoration work however good the method. The intended contribution — a base rate for Mycenaean accounting error — **was not obtained**, and §7 sets out both why the within-tablet channel cannot supply one and why the Ma series measures something else. Everything the Ma pilot did produce turned out to be published between 1951 and 1990.

That leaves the Linear B side as a **validated reimplementation**: four independent agreements with the literature, which is good evidence the parser is right and no evidence that anything new was learned. Worth saying plainly, because the cost of the exercise was real and the temptation to bank the near-miss as a result is exactly what the rest of this document is written to resist.

**For the team project**, two decisions follow:

1. **A fraction solver expecting new values would fail** — the evidence does not exist. The same code as an **arithmetic auditor** has clear value: it finds real discrepancies the source misses, HT 13 being the example.
2. **Classical shape descriptors will not carry sign classification.** Across the full inventory they reach 35% top-1, and only 44% even for signs with fifty or more attestations. The 88% measured on fraction signs does not generalise: fractions are few, distinct and well attested. A reader built on this needs learned or stroke-level features, or a design that claims only the signs it can identify — 88% of marks belong to a sign with ten or more examples, but accuracy at ten examples is 12%.

---

## Appendix: corrections made along the way

Recorded because how these failed is more useful than the claims were.

**The damage model was wrong, and fixing it sharpened the result.** Quantities beside a break were read as exact. HT 13 reads `RE-ZA 5[ ]J[ ]` — broken on *both* sides — which manufactured the impossible equation `1·J = 0`. Damaged quantities now yield bounds, and the direction depends on which side is broken: a broken entry gives `entries ≤ total`, a broken total (HT 116b's `KU-RO GRA 100[`) gives `entries ≥ total`. Getting that backwards silently inverts the constraint.

**Two structural rules had to be modelled.** A bare `ki-ro` line is a heading, not an entry — on HT 88 the total covers only the entries after it (6 = 6, not 39 = 6). And KI-RO appearing inline marks a balance owed, not an addend; five deficit amounts on HT 123+124a were being summed as entries.

**Tablets whose entry list is physically missing are excluded by rule.** HT 46a is *supra mutila*; its 42.5 shortfall *is* the missing list.

**A silent bug nearly produced a false negative.** The first retrieval run scored 14.9%, below baseline, and looked like a clean negative result. lineara.eu re-encodes SigLA's transparent PNGs as opaque images on white, so keying the mask on the alpha channel marked *every* pixel as ink: the descriptors were comparing solid rectangles. Only rendering the normalised glyphs and looking at them caught it.

**The compound test was invalid and its results are retracted.** Two flaws combined to manufacture a clean separation:

1. *The bands were measured differently.* Positive controls compared a composed pair against composites — both built by the same function. The real test compares a single traced glyph against composites. Measuring one sign both ways: a composed `DD` pair scores 20.5–25.1 against D+D composites, a single `D` glyph scores **38.3–40.0**.
2. *The negative controls were skewed simple.* J, E and K are the simplest strokes. Adding complex signs collapses the gap — **F scores 24.5, inside the supposed "true doubling" band**, and nobody claims F is a compound.

It cannot be repaired with these data: a sound positive control needs a sign traced as *one* glyph that is genuinely a doubling, and none exists, because SigLA traces compounds as their parts.

**A leak found and closed.** Comparisons now exclude all glyphs from the tablet under test, so one scribe's hand cannot match itself. The KH 86 conclusion survived the fix.

### From the Linear B round

**The first "uniquely recoverable" claim was an overclaim, twice over.** KN Fp 1 was reported as "the missing amount is 1 S, in one of two gaps". Both halves were wrong. First, with two damaged entries the shortfall can be **split** between them — three V in each gap balances exactly as well — and the search only ever tried putting the whole residual in one gap. Second, the verdict ignored that with a *single* gap the missing amount follows from arithmetic alone, so labelling that a "uniquely recoverable numeral" claims credit the notation never earned. KN Fp 1 is in fact `AMBIGUOUS`, with 24 legal ways to divide the missing S. A scholar preferring `S 2` is applying a simplicity prior — which is precisely the unique-versus-suggested distinction this section set out to draw, so getting it wrong here would have been self-refuting.

**A safety bound was being reported as a negative result.** The relaxed pass admits strictly more readings than the strict one, yet came back with six times as many `IMPOSSIBLE` verdicts. The enumeration was hitting its cap and the empty result was read as "no legal amount exists". Truncation now yields `UNRESOLVED`, and a truncated search can never report `UNIQUE`. **The tell was that a sensitivity check moved a number the wrong way** — worth remembering, because the code was not crashing and the output looked plausible.

**Square brackets mean three different things, and adjacency is what distinguishes them.** `1[` is a break the numeral may run into; `]VIR 1` means text was lost earlier; `[VIR 1]` is text the **editor restored**. Pairing any `[` with any later `]` misread PY Ma 397's `KE M 2[ ... ]ME 500` as a restoration enclosing the intervening text, when the two brackets are the *two edges of one lacuna*. That hid the break, so `KE M 2` was scored as a sound value disagreeing with the series instead of a damaged one the series could restore as 7. A restoration hugs its content; a lacuna edge does not.

**Auditing an editor's restoration would have been circular.** `[VIR 1]` is a numeral an editor supplied — quite possibly *because* it makes the total work. Scoring such a section tests the editor, not the scribe, so restored sections are excluded from the error rate and counted separately.

**`vacat` is not `sup. mut.`** Clay deliberately left blank means nothing is missing; a broken-away top means entries may be gone. Treating the second as merely empty made two fragmentary Knossos tablets look like scribal errors. Relatedly, a section's span has to start at the **top of the tablet**, not at its first surviving entry — otherwise entries lost above the first survivor are invisible, which is the same mistake *supra mutila* forced on the Linear A side.

**A bare number after a word does not always count that word.** `MUL 1 ko-wa 2` is one woman and two girls, so `ko-wa` counts itself. But on the Knossos As tablets `a-ma-no 1` is one *man*, the `VIR` understood from nearby lines. Nothing in the spelling separates a counted category from a personal name, so the distinction is inferred from the corpus: `ko-wa` and `ko-wo` take a bare number on roughly fifty documents each, a personal name on one or two. Getting it wrong detached every unlabelled entry from its total.

**`OLE S 1` is one S of oil, not a commodity called S.** A metrogram following a commodity named a token earlier on the same line was being read as a new commodity, which deleted the oil from every entry on KN Fp 1 and cascaded into the next line through commodity inheritance.

**A numeral can be cut in half by a bracket.** PY Ma 120 reads `[O M  1]4` — the editor restored the `1`, the `4` survives, and the amount is **14**. Read as two numbers it becomes `O M 1` plus a stray `4`, which is both wrong and entirely plausible-looking. The first fix then swallowed the closing bracket, leaving the restoration open so every later measure on the line was flagged as the editor's work.

**Two estimators were caught inventing values no scribe used.** Taking the median of an even-sized sample of ratios returned `O = 35/23` — a number produced by averaging the two middle observations rather than found in the corpus, which then looked like a disagreement with Palaima. Switching to consensus scoring fixed that but introduced the opposite failure: with an unbounded candidate space the fit preferred `*152 = 70/23` because it matched one more tablet than 3 does. Bounding candidates to simple fractions, on the stated prior that administrative ratios *are* simple, recovers all six published values exactly. **The prior did more work than the extra data point.**

**`*146` was listed under weight and is actually counted.** The hand-written commodity-to-series map was wrong for the Ma series, which would have compared whole units against subunits. Series assignment is now inferred from which subunit signs each commodity actually takes, with the hand-written convention kept only as a cross-check.

**The largest error was doing the literature check last.** The Ma pilot was built, validated, written up and reported before anyone read the taxation literature — at which point the ratio turned out to be Bennett's from 1951, the rounding to be quantified by Shelmerdine, the flagged anomaly to be Wyatt's from 1962, the restorations to be in PTT I and de Fidio, and the measured quantity to be tax relief rather than error. Every one of those is a thing a single afternoon with the standard bibliography would have caught. The lesson is the same one this project recorded once already in a different form — *"the check I should have run first was: what does the paper say about this exact method?"* — and it was not applied, because the search that preceded the work asked whether an **arithmetic audit of Linear B** had been published (it has not) rather than whether **the Ma series arithmetic** had been (it has, exhaustively, for seventy-five years). A gap in the literature on one framing is not a gap on another, and the narrower question is the one that decides whether the work is new.

---

## Reproducing

```bash
# Linear A
python -m la.cli fetch      # crawl and cache the corpus (resumable, ~15 min)
python -m la.cli census     # what evidence exists
python -m la.cli solve --include-damaged --treat-all-unknown
python -m la.cli order      # writing-order evidence
python -m la.cli compare    # competing published value systems
python -m la.cli ratios     # ration constraints
python -m la.cli validate   # leave-one-out recovery
python -m la.cli recover    # which damaged numerals the arithmetic determines

# Linear B, the deciphered control corpus
python -m la.cli lb-fetch   # crawl and cache DAMOS (resumable, ~30 min)
python -m la.cli lb-audit   # arithmetic audit and the accounting error rate
python -m la.cli lb-ma      # the Pylos Ma fixed-ratio pilot

python -m pytest tests/ -q
```

Sources and their verification levels: `docs/sources.md`.

**Data and licences.** Linear A from lineara.eu (M. Navarre), derived from SigLA (E. Salgarella & S. Castellan), CC BY-NC-SA 4.0. Linear B from DAMOS (F. Aurora, University of Oslo), content CC BY-NC-SA 4.0. Both used non-commercially with attribution. The Linear A cache is committed with the project; the Linear B cache stays local.
