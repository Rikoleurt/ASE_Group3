# HTR-A Cross-Review of HTR-B + Merged Counterproposal

**Reviewer:** HTR-A (method-first lens)
**Reviewed:** HTR-B_draft.md (read in full)
**Date:** 2026-09-16

---

## 1. Citation spot-checks (verified this session by opening the arXiv abstract pages)

| Citation | What it actually is | Accuracy of HTR-B's description | Does it already do what we propose? |
|---|---|---|---|
| **Athar / Phoenix**, arXiv:2608.19385, "Beyond Recognition: Compact Multi-Domain Arabic Manuscript HTR with Candidate-Selection Analysis and Evidence-Preserving Review" (Ali et al., 19 Aug 2026) | 4.99M-param CNN-BiLSTM-CTC for Arabic manuscripts. Review workflow "preserves the visual reading, exposes bounded alternatives, uses local language models conservatively… abstain states, and exports auditable TEI and PAGE-XML records." | Accurate. **One omission matters a lot:** "a 2.15-point oracle gap between beam decoding and Oracle@25, while neural text rerankers, consensus MBR, CTC-posterior quality estimation, and local pre-CTC hidden-state quality estimation **recovered less than 4% of this gap**." | **Partially.** It already does evidence-preserving review, bounded alternatives, abstention and auditable PAGE-XML provenance, so HTR-B's provenance/audit-trail contribution is *not novel by itself*. No LLM/VLM proposer, no forced-alignment verification of edits, no statistical guarantee, no hallucination metrics. **Direct negative evidence against my idea A:** reranking inside the N-best barely helps, and CTC-posterior quality estimation was weak. |
| **GRC**, arXiv:2603.19790. v1 title "From Plausibility to Verifiability: Risk-Controlled Generative OCR for VLMs"; v2 (Jul 2026) retitled "Geometric Risk Control for Vision-Language Model OCR" (Gong et al.) | Black-box controller. Applies geometric transforms to the image, screens implausible continuations, and releases a candidate only with coherent cross-view agreement. Otherwise abstains. | Mostly accurate, with the v1 title. **Overstated in HTR-B's novelty section:** "Conformal risk control for VLM OCR (GRC) on scene text only" is wrong. The abstract claims "empirical selective exposure control… under a reproducible fixed decision rule". Neither version mentions conformal prediction or a distribution-free guarantee. | **Partially.** It covers the "abstain when visual support is weak" idea for VLM OCR, but only by self-consistency across views of *one* model, on scene text. No handwriting, no historical material, no cross-architecture verifier, no formal guarantee. **Must be cited as the closest method competitor** to our gate. It is also a strong, cheap baseline to include. |
| **WildHandBench**, arXiv:2608.22959 (Zhang et al., 24 Aug 2026) | 500 modern handwritten documents, 4 languages, 9 degradation scenarios, covering free text, tables and formulas. **"Understanding and recognition"** benchmark. Defines **Prior-Driven Error (PDE)**: 63–91% of model errors are prior-driven, vs 49% for humans. No mitigation proposed. | Mostly accurate. **Mild misread:** 71.85% is overall benchmark accuracy across understanding tasks including tables and formulas, not a transcription accuracy comparable to CER. | **Partially.** PDE already names the "language prior overrides vision" error class, so neither draft can claim to have *invented* a prior-driven or plausible-hallucination metric. Our novelty narrows to: historical cursive, token-class stratification, controlled occlusion probes, and edit-level (introduced vs fixed) accounting. |
| **CHURRO**, arXiv:2509.19768 (Semnani et al., **EMNLP 2025**) | 3B open-weight VLM for historical text. 70.1% normalised Levenshtein similarity on handwriting (+6.5 over Gemini 2.5 Pro), 82.3% on print; 15.5× cheaper. CHURRO-DS: 99,491 pages, 155 corpora. | Accurate. The venue (EMNLP 2025) was not stated. | No. It is a *proposer* candidate. Note that a 70% similarity score on handwriting means about 30% normalised edit distance, so on hard hands it is not a drop-in "near-zero" component. |

**Net novelty check:** no checked paper combines (i) VLM/LLM proposer, (ii) cross-architecture CTC visual verification of each edit, (iii) a statistical acceptance guarantee, and (iv) hallucination-specific evaluation, on historical handwriting. The *combination* is still open. Every individual ingredient now has close prior art: Athar for review and provenance, GRC for abstaining VLM OCR, WildHandBench/OmniHandwritingOCR for prior-driven errors, conformal ASR/KIE for guarantees. Both drafts must drop "first X" language for individual components.

---

## 2. Adversarial critique of HTR-B's draft

### 2.1 Technical flaws

1. **The forced-alignment gate as written rejects exactly the edits we want.**
   - HTR-B: "edit accepted only if visual likelihood drop < tau_class".
   - Whenever the CTC model is confidently wrong, the correct edit *lowers* CTC likelihood, often a lot. That is precisely the case where correction is needed.
   - A raw likelihood-drop threshold therefore trades recall of real fixes for safety in a way that depends on how miscalibrated the CTC model is on that hand.
   - Needed:
     - a length-normalised, temperature-calibrated ratio (my VSR);
     - a *learned* decision over several features;
     - explicit reporting of Correction Recall, not only hallucination reduction.
   - HTR-B's "learn the gate on the calibration split" fix creates the leakage problem in 2.2.1.
   - Athar's result (CTC-posterior quality estimation recovered <4% of the oracle gap) suggests CTC signals alone may be weak. This hits my draft equally.

2. **The risk being controlled is a ratio, and it is not monotone.**
   - "Expected token error on auto-accepted tokens ≤ α" is error among accepted tokens. It is not monotone in the threshold, so plain Conformal Risk Control does not apply.
   - Use Learn-then-Test (fixed-sequence testing over thresholds with binomial/Hoeffding–Bentkus p-values), or control the *joint* risk P(accepted ∧ wrong), which is monotone.
   - HTR-B cites only the Gentle Introduction and never names the procedure.

3. **Per-class guarantees at the stated targets are statistically infeasible with the stated calibration budget.**
   - Target: "≤ 0.1% wrong names/numbers on auto-accepted tokens"; budget: "~100–300 calibration lines".
   - Even with *zero* observed errors, certifying α at confidence 1−δ needs roughly n ≥ ln(1/δ)/α class tokens: about 3,000 names/numbers for α=0.1%, δ=0.05.
   - 300 lines ≈ 3,000 words total, of which maybe 5–10% are names or numbers, i.e. about 150–300 tokens. That can certify at best about 1–2%.
   - So the headline target is **unachievable as a guarantee**. It must be reported as an empirical point estimate, or α must be relaxed.
   - This also applies to my draft's "≤0.5%" aside.

4. **Exchangeability unit.**
   - HTR-B correctly splits by document/writer for *test*.
   - But it states the guarantee per token. Tokens within a line or page are dependent, so the calibration unit must be the page or document (grouped conformal), with fewer effective samples. That further weakens item 3.

5. **Wrong kind of "consistency" check for the verifier.**
   - GRC-style augmentation consistency re-uses the same model, so it detects instability, not prior-driven fluency.
   - A VLM can be *consistently* wrong across rotations when its language prior dominates. WildHandBench's PDE finding implies exactly that.
   - Keep it as a feature and a baseline. It is not a substitute for cross-architecture verification.
   - Its query cost also multiplies API spend by the number of views.

6. **"Temptation score" circularity.**
   - The trap tokens are chosen by a *modern LM's* preference against the GT form, and the systems evaluated are LMs from overlapping families.
   - That is a valid adversarial design, but it inflates measured modernisation relative to a random sample.
   - Report both a stratified-trap slice and a *random* slice, and never pool them into a headline number.

7. **PrIx re-implementation from N-best is a likely strawman.**
   - Real PrIx computes relevance probabilities over lattices or character posteriorgrams, marginalising over segmentations.
   - An N-best approximation systematically under-recalls rare words, which is exactly the rare-entity queries idea 3 cares about.
   - Beating "PrIx-approx" with VLM transcripts would be an unfair conclusion.
   - Cheaper and more faithful: lexicon-free CTC keyword scoring P(query ∈ line | x) via the CTC forward algorithm with wildcard padding. It is standard, and a few hundred lines of code.

### 2.2 Evaluation weaknesses / leakage

1. **Three-way leakage in the gate.**
   - If the gate (thresholds or learned combiner) is fit on the same split used for conformal calibration, the guarantee is invalid.
   - Needed: **four disjoint document-level splits**: HTR fine-tune / gate-train / conformal-calibrate / test.
   - HTR-B lists only calibration and test.

2. **VOC/Dutch data is doubly contaminated.**
   - (a) GLOBALISE published 4.8M VOC transcriptions online, so VOC is as contaminated for VLMs as Bentham.
   - (b) Loghi/"IJsberg" pretrained models were likely trained on the very Nationaal Archief GT HTR-B proposes to test on. That is a train/test overlap for the CTC baseline.
   - Also, Zenodo 4159268's "3,000,000 HTR" part is *machine output, not GT* and must never be used as reference.
   - HTR-B flags contamination for Bentham but not for VOC.

3. **Lexicon leakage in search evaluation.**
   - If the KWS/PrIx lexicon or the n-gram LM is built from collection GT including test pages, in-vocabulary rare names inflate retrieval.
   - Build lexicons and LMs from train documents only, and report OOV-query performance separately.

4. **Hallucination metric circularity (applies to both drafts).**
   - "Not visually supported" measured with the *same* CTC model used as the gate makes the gated system look good by construction.
   - Use a **different** reference optical model (e.g. HTR-VT or Kraken if the gate uses PyLaia) plus **human annotation** of a sample of about 300 errors, with κ agreement, as the ground truth for the hallucination taxonomy.

5. **No controlled fabrication probe.** HTR-B deliberately avoids synthetic images. Without some controlled illegibility (my occlusion probes), "fabrication" cannot be separated from "hard but correct inference". Offer both: real damaged lines plus graded synthetic occlusion, reported separately.

6. **Counterfactual number/date pairs** ("real lines where context suggests another value") are under-specified and probably rare in natural data. Drop them or treat them as qualitative.

7. **Cost per useful page extrapolated to 10⁶ pages.**
   - It is a model, not a measurement. Human review minutes will dominate, and HTR-B's user study is optional and ethics-gated.
   - Without measured per-decision review times, the headline cost number rests on assumptions.
   - Present it as a sensitivity analysis over the review-time and wage parameters, not as a finding.

8. **Missing related work that undercuts some "nobody" claims:**
   - OmniHandwritingOCR (CIKM 2026, "plausible but visually unsupported corrections")
   - SHROOM-Visions 2026 (character-level VLM hallucination detection shared task)
   - Consensus Entropy (multi-VLM agreement)
   - KIE-HVQA (NeurIPS 2025)
   - PINK over-correction metric (2026)
   - METATR (2026 ATR benchmark and normalisation protocol)
   - Humphries' Gemini 3 analysis (about 61% of errors are "statistical corrections")
   - conformal ASR (Ernez et al. 2023), conformal KIE (IJDAR 2026)

   Also, G4 "Nobody measures how VLM hallucinations affect retrieval" is softened by HIPE-OCRepair 2026's retrieval-oriented scoring. That covers printed text only, so the handwriting claim may still stand, but phrase it carefully.

### 2.3 Overclaimed novelty (summary)

- "First token-class-stratified, contamination-aware benchmark": contamination-aware protocols exist (Levchenko, METATR), and prior-driven error metrics exist (WildHandBench PDE). Defensible form: *first for historical cursive with edit-level and occlusion-controlled fabrication measures*.
- "Provenance tracking / audit trail": Athar already exports auditable PAGE-XML/TEI with bounded alternatives and abstain states. It is a good engineering deliverable, not a research novelty.
- "Conformal risk control… GRC": GRC is not conformal, and our guarantee claim needs LTT.

### 2.4 Feasibility

**Over-scoped for 8 months and 1–2 people.** The system sketch has 9 stages: capture QA, layout, HTR fine-tuning, proposer, multi-signal verifier, per-class risk controller, review UI, active learning, cost simulator. It also adds a benchmark, a user study and an optional PrIx search study.

Cuts:
- **Layout:** use existing line segmentation from GT PAGE-XML for evaluation, and do not research it.
- **Capture QA:** a single robustness slice, no app.
- **Active learning:** future work.
- **User study:** simulated review by default. File ethics paperwork in month 1 only if a real study is genuinely wanted; approval lead times often exceed 2 months.

**Local VLM throughput.** A 3B VLM on a consumer GPU for thousands of pages is plausible, but it is unmeasured ([U] in HTR-B). This is a gate item.

---

## 3. Where HTR-B beats my draft (what I missed)

1. **It treats search as the real goal.** HTR-B grounds this in real deployments (HIMANIS, Carabela, PARES) and in precision-vs-recall cost asymmetry (J. Imaging 2020). My set-valued indexing idea had no concrete retrieval protocol or real baseline.
2. **Token-class-specific risk inside the controller.** Names, numbers and dates get stricter thresholds or are never auto-edited. I only *measured* entity errors; HTR-B *acts* on them. This is the right design for historians.
3. **"Verify, don't rewrite" as the system philosophy,** with span-level edits plus reasons. It is simpler and more robust than my token-level constrained decoding, and Athar's <4% oracle-gap recovery now supports that choice.
4. **CHURRO 3B as a local, open proposer.** It removes API drift and budget risk and fits "zero-hardware / cheap". I missed CHURRO entirely.
5. **The software-engineering deliverable fits the course.** This is an *Advanced Software Engineering* project, and my draft was too ML-centric. HTR-B's list is exactly what examiners of an SE project will look for:
   - PageXML in/out interoperability (eScriptorium, Transkribus, Loghi)
   - provenance schema
   - containerised modular stages
   - pip-installable scorer with CI tests
   - dataset cards, license table
   - cost instrumentation
6. **Cost per useful page** as an explicit outcome, and **human effort** (minutes per page to reach target quality).
7. **Real Dutch production data and pipelines** (Loghi, GLOBALISE/VOC, Nationaal Archief GT, HTR-United), plus the **selection-bias gap** (NER annotated only where HTR worked).
8. **Split by document and writer** stated explicitly for calibration validity.
9. **Concrete "zero-hardware" definition**, with phone capture as a robustness condition rather than an assumption.
10. **Athar, GRC and WildHandBench:** three highly relevant 2026 papers I did not find.

What my draft contributes that HTR-B lacks:
- controlled occlusion fabrication probes;
- the edit-level decomposition (introduced error / fixed error / correction precision);
- the normalised VSR definition;
- the LTT-vs-CRC distinction;
- OmniHandwritingOCR, SHROOM-Visions, Consensus Entropy, KIE-HVQA, PINK and METATR;
- conformal ASR/KIE analogues;
- conformal prediction sets for guaranteed-recall indexing.

---

## 4. Merged counterproposal: best single thesis

### 4.1 Title and abstract

**Working title:** *Verify, Don't Rewrite: Evidence-Gated, Risk-Certified Transcription of Historical Handwriting*

**Abstract.** Large vision-language models now transcribe historical handwriting cheaply and often better than specialised recognisers. But their errors change character: instead of garbled strings they produce fluent, plausible words the page does not contain, such as modernised spellings, "corrected" names and altered numbers. CER does not show this, and it quietly damages archival search and scholarship.

We build and evaluate an open, modular pipeline in which a VLM (a local open model, with a commercial model as a capped comparison) only *proposes* edits to a CTC recogniser's reading. Each edit must pass a visual-support check by that architecturally independent recogniser before it is accepted. A Learn-then-Test risk controller, calibrated per collection on a few hundred lines, then decides which words are auto-accepted, flagged for review or marked illegible. Names, numbers and dates are held to stricter rules.

We contribute a contamination-aware probe suite for historical cursive (English, German, Latin/medieval, plus a never-published held-out slice). It separates recognition errors from introduced, prior-driven and fabricated ones, using controlled occlusions and edit-level accounting. On it we report accuracy, faithfulness, risk–coverage with empirical guarantee validity under writer shift, and cost per useful page.

We do not promise error-free transcription. We aim to show how much of a collection can be auto-accepted with a stated, checked error bound, and exactly where that bound breaks.

### 4.2 Reframing "near-zero error"

- Replace "near-zero error" with **"near-zero *silent* error"**. Every output word is in one of three states:
  - **auto-accepted**, with a certified error rate;
  - **flagged**, with bounded alternatives;
  - **illegible**.
  - No edit is accepted without visual support, and every edit carries provenance.
- Headline claims take the form: *"On collection X, calibrated with 300 lines, N% of words were auto-accepted with word error ≤ α guaranteed at confidence 1−δ (empirical violation rate over 100 re-splits: v%). Names/numbers: empirical error e% at coverage c% (not certified; insufficient calibration mass)."*
- State the statistics honestly: with n calibration tokens and zero errors you can certify at best α ≈ ln(1/δ)/n (about 3/n at δ=0.05). **Realistic certified α is about 1–3% for all words, and not certifiable below about 1–2% for names/numbers** at archive-realistic calibration sizes.
- Also report the *whole-page* CER/WER so readers can compare with the literature. The pitch is "honest guarantees + fewer silent errors", not "lower CER than Gemini".

### 4.3 Core deliverable

1. **Pipeline (SE core).** PAGE-XML in → CTC recogniser (PyLaia with n-gram LM; fine-tuned per collection) → VLM proposer (CHURRO 3B local; one commercial VLM on capped subsets) → span-level edit extraction by alignment → **evidence gate** → **LTT risk controller** (word level, with protected classes for names/numbers/dates) → PAGE-XML out, with per-word confidence, alternatives and provenance (`htr` / `vlm-edit-verified` / `flagged` / `illegible`) + JSONL export.
2. **Evidence gate (ML core).** A small learned combiner (logistic regression/GBDT) over:
   - VSR, the length-normalised, temperature-calibrated CTC forced-alignment log-likelihood ratio of the edited vs original span;
   - whether the edit is in the CTC N-best/confusion network;
   - CTC–VLM agreement, and CHURRO-vs-commercial agreement where available (Consensus-Entropy-style);
   - GRC-style geometric-view consistency (cheap, local model only);
   - period-LM vs modern-LM surprisal gap (a modernisation signal);
   - token class.
3. **HalluTrap-HTR probe suite + scorer (evaluation core, released as a pip package with CI).** Slices:
   - random slice
   - archaic-spelling/abbreviation traps
   - names/numbers/dates
   - clean control lines
   - real damaged lines
   - graded synthetic occlusions
   - held-out never-online slice

**Explicitly out of core:** token-level lattice-constrained LLM decoding (Athar's evidence says the reranking payoff is small; high engineering cost), layout research, active learning, capture app, real user study.

### 4.4 Optional extension (choose at Gate 4; only one)

**Search impact: do hallucinations break archival search?** Compare entity-query retrieval over:
- (a) lexicon-free CTC keyword relevance (a CTC forward algorithm approximation of PrIx);
- (b) raw VLM transcripts;
- (c) gated output;
- (d) gated output + **conformal prediction sets indexed as alternatives** (a recall-guarantee variant).

Metrics:
- MAP and recall@k on rare-entity queries;
- false-hit rate attributable to hallucinated tokens (using the human-annotated taxonomy);
- OOV-query performance;
- index size and build cost.

Lexicons/LMs come from train documents only.

### 4.5 Evaluation protocol

**Datasets.** Licenses to be confirmed in M1.

| Dataset | Role | Notes |
|---|---|---|
| **Bentham** (ICFHR 2014) | English cursive, multi-hand | **Contaminated slice**, labelled as such |
| **READ 2016** (Ratsprotokolle) | Early Modern German, CC-BY-4.0 | Main non-English dev/test |
| **CATMuS Medieval subset** (1–2 manuscripts in Latin/Old French cursive-ish scripts) | Abbreviations kept graphematic | Tests silent expansion/normalisation |
| **Nationaal Archief VOC/notarial GT** (Zenodo 11209325/4159268, *GT portion only*) | Dutch | Optional. **Contaminated** (GLOBALISE online); **do not** use Loghi/IJsberg models trained on it as the baseline |
| **Held-out slice** | 300–500 lines from a local or university archive, never transcribed online | Double-keyed; the primary "uncontaminated" test |
| **IAM** | Pipeline sanity only | Not reported as a result |

**Splits.** Four disjoint document-level (and where possible writer-level) splits per collection:
- HTR fine-tune
- gate-train
- conformal-calibrate (≈300 lines)
- test

Plus **shift tests**: leave-one-writer-out, cross-collection calibration transfer, and one phone-recapture slice (about 50 pages re-photographed under controlled conditions).

**Systems.**
- S0 CTC (+n-gram LM)
- S1 CHURRO zero-shot
- S2 commercial VLM zero-shot (capped)
- S3 CTC + text-only LLM correction
- S4 CTC + multimodal VLM correction (ungated, Greif-style)
- S5 GRC-style view-consistency abstention on the VLM (baseline)
- S6 CTC confidence thresholding only (selective, no VLM)
- **S7 ours:** gated proposer + LTT controller
- Ablations: remove each gate feature; no protected classes; local vs commercial proposer

**Metrics.**

| Dimension | Metrics |
|---|---|
| Accuracy | CER/WER, strict and METATR-style normalised; per slice; document-bootstrap 95% CIs |
| Edit faithfulness | **FER** (fixed error rate), **IER** (introduced error rate), **Correction Precision** = FER/(FER+IER), **Correction Recall** = FER / (errors in S0), **Clean-Line Change Rate** |
| Hallucination | **Entity/number exact match**; **Modernisation Rate** on trap tokens (and AIR-style archaic insertion); **Occlusion Fabrication Rate** by severity; **Plausible Unsupported Word Rate**, judged with a *different* reference recogniser than the gate + 300-error human taxonomy (κ reported); PDE-style prior-driven share |
| Reliability | Risk–coverage curves, AURC, coverage@α; **empirical guarantee violation rate** over 100 random calibration/test re-splits, in-distribution and under each shift; ECE of the gate |
| Cost/effort | GPU-seconds/page, API USD/page (dated prices), words flagged per page, simulated review minutes (sensitivity analysis over per-decision time), cost per useful page |
| Reproducibility | Container images, configs + seeds, dataset cards, license table, scorer unit/property tests |

### 4.6 Month-by-month plan with go/no-go gates

| Month | ML track | SE track | Gate at end of month |
|---|---|---|---|
| **M1** | Verify [S]/[K] citations; re-run novelty search (Athar, GRC, WildHandBench, SHROOM-Visions, OmniHandwritingOCR). Fine-tune PyLaia baselines (Bentham, READ2016). | Repo, CI, PAGE-XML loaders, data/license table, split generator (document/writer-disjoint, 4-way). Start held-out slice acquisition. | **G0 (data):** licenses OK; held-out slice source confirmed; S0 CER ≤ ~15% on at least 2 collections (otherwise the verifier has no signal). *No-go:* swap collection. |
| **M2** | Proposer runs: CHURRO + capped commercial VLM. Span-edit extraction. First VSR computation. | Pipeline skeleton end to end with provenance schema; experiment tracking; cost instrumentation hooks. | **G1 (verifier signal):** on gate-train, VSR alone reaches AUROC ≥ 0.75 for separating correct from incorrect VLM edits, and the learned combiner ≥ 0.80. *No-go:* if combiner < 0.70, pivot to benchmark + analysis thesis (the probe suite plus a systematic comparison of S0–S6) and drop certification claims. |
| **M3** | Gate combiner + ablations. Period-LM surprisal feature (optional). | Probe suite v1: trap tagging, occlusion generator, clean/control slices. Scorer package with tests for every metric. | — |
| **M4** | Full dev-set comparison S0–S7 on faithfulness metrics. | Human error-annotation tool (simple web or notebook). Begin the 300-error taxonomy annotation (2 annotators). | **G2 (faithfulness payoff):** S7 cuts IER by ≥ 50% vs S4 at ≤ 1.0 pt absolute CER cost vs S4, on ≥ 2 collections. *No-go:* report the trade-off frontier honestly; keep the certification work on S0/S4 outputs. |
| **M5** | LTT controller; protected classes; grouped (page-level) calibration; 100-re-split validity study. | PAGE-XML export with confidence/alternatives; review simulator (flagged spans + time model). | **G3 (certification):** at α = 2% word error, δ = 0.1, coverage ≥ 50% with ≤ 300 calibration lines in-distribution, and violation rate ≤ δ. *No-go:* relax to α = 5%, or switch to an expected-risk (CRC on joint risk) formulation, and say so. |
| **M6** | Shift experiments: leave-one-writer-out, cross-collection, phone-recapture slice. Final test-set runs (test split touched once). | Cost-per-useful-page model + sensitivity analysis; containers; docs. | **G4 (scope):** core frozen and all core results on test? *Go* → extension (search). *No-go* → skip extension, extra writing/robustness. |
| **M7** | *Extension:* CTC keyword relevance, conformal-set indexing, retrieval eval on entity queries. *Or* finish analysis. | Search index (inverted index/OpenSearch) + query harness; release probe suite v1.0 with dataset card. | — |
| **M8** | Writing: results, limitations (shift, contamination, statistical ceilings). | Reproducibility pass: fresh-machine rerun from containers; final release; demo. | Submission. |

### 4.7 Division of work: ML side vs SE side

| ML / research (HTR-A-style role) | Software engineering / systems (HTR-B-style role) |
|---|---|
| CTC fine-tuning and temperature calibration | Modular pipeline architecture; stage interfaces so proposers, verifiers and controllers are swappable plug-ins |
| VLM prompting for span-level edits; proposer comparison | PAGE-XML/ALTO I/O; provenance and confidence schema; eScriptorium/Transkribus import compatibility |
| VSR forced alignment; gate feature engineering and combiner | Data layer: loaders, license table, 4-way leakage-safe split generator with tests that assert disjointness |
| LTT/conformal procedure, grouped calibration, validity study, shift analysis | Probe-suite *packaging*: occlusion generator implementation, trap tagging pipeline, pip scorer with unit + property-based tests, CI |
| Metric *definitions* (FER/IER/CP, OFR, modernisation, unsupported-word rate) and human taxonomy protocol | Annotation tool; experiment tracking; config/seed management; containers |
| (Extension) CTC keyword relevance, conformal-set indexing | Cost/throughput instrumentation and cost-per-useful-page model; review simulator; (extension) search index + query harness |
| Joint: results analysis, writing, gate decisions | Joint: architecture decision records, final reproducibility run |

With a single student, prioritise down each column in order. The SE column's first four rows are non-negotiable for an *Advanced Software Engineering* assessment.

### 4.8 Top risks of the merged plan

1. **G1 failure.** CTC evidence may be too weak to verify VLM edits on hard hands (Athar's weak CTC quality estimation is a warning). Fallback: the benchmark + comparison thesis is still complete.
2. **Statistical ceilings.** Certified α will be modest. Framing must be set early with the supervisor so a "2% certified at 60% coverage" result counts as a success.
3. **Novelty erosion.** 2026 is moving fast (GRC, Athar, WildHandBench, SHROOM-Visions, OmniHandwritingOCR all within months). Re-search at M1 and M5, and position on the *combination + historical cursive + guarantee validity under shift*.
4. **Contamination/licensing.** The held-out slice is the single most important data asset. Start acquiring it in week 1.
5. **Local VLM throughput** on consumer hardware is unmeasured. Benchmark CHURRO pages/hour in M2 before committing to scale claims.

---

## 5. Sources checked in this review

- Athar/Phoenix: https://arxiv.org/abs/2608.19385
- GRC (v1 and current): https://arxiv.org/abs/2603.19790v1 , https://arxiv.org/abs/2603.19790
- WildHandBench: https://arxiv.org/abs/2608.22959
- CHURRO (EMNLP 2025): https://arxiv.org/abs/2509.19768
- All other references: see HTR-A_draft.md §1 and §7.
