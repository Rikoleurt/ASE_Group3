# HTR-B Review of HTR-A's Draft, and a Merged Counterproposal

Reviewer: HTR-B (systems / data / evaluation lens). Date: 2026-09-16.
Tags: [V] = I verified it this session. [U] = my estimate or unverified. [C] = I computed it (exact binomial, scipy).

Overall verdict: **HTR-A's draft is strong and complementary to mine.** We converged on the same core: grounded correction, selective acceptance with guarantees, and hallucination metrics. HTR-A is better on method detail and statistics vocabulary. The main problems are that (i) the statistics are stated more strongly than the data design supports, (ii) some metrics are circular with the system being evaluated, and (iii) token-level constrained decoding is costly engineering for an uncertain gain over N-best reranking.

---

## 1. Adversarial critique

### 1.1 Technical flaws

**F1. CRC and the "error among accepted words" risk are mixed up.**
- §4.B presents Learn-then-Test (LTT) and Conformal Risk Control (CRC) as interchangeable.
- CRC needs a loss that is **monotone** in the threshold. The *conditional* error rate among accepted words (errors ÷ accepted) is **not monotone**: raising the threshold can remove more correct words than wrong ones. So the headline guarantee ("≤1% WER on accepted words") can only come from LTT (or a similar multiple-testing method), not from CRC.
- CRC *can* control the **joint** rate (accepted-and-wrong words ÷ all words), which is monotone and bounded. That is a different, weaker-sounding quantity.
- The thesis must say clearly which guarantee it gives. My recommendation: report both. Use CRC on the joint rate as the "safe" headline, and LTT on the conditional rate at a looser α.

**F2. The exchangeable unit is named (pages) but not paid for.**
- HTR-A says calibration is "grouped by page" and also that "a few hundred annotated lines" is enough. These cannot both be true.
- If the page is the unit, CRC with bounded loss (B = 1) at α = 1% needs about 100 pages just to be non-vacuous. With 300 pages, the empirical risk must be ≤ 0.67% [C]. 300 fully transcribed pages is roughly 6–9k lines, not "a few hundred".
- If words are treated as i.i.d. inside full pages, the guarantee is **optimistic**. Within-page correlation (same hand, same ink, same damage) inflates the effective sample size by a design effect of 1 + (m − 1)ρ. For m ≈ 25 lines per page and ρ ≈ 0.1, that is about 3.4× [U: illustrative ρ].
- **Fix (cheap, and an engineering contribution):** annotate *one uniformly random line from each of n uniformly random pages* in the target collection. The units are then close to independent and exchangeable with "a random line from this collection" *by construction*. Labelling 300–500 single lines is a few expert hours, not months. The guarantee is marginal over the collection, which is exactly what an archive needs.

**F3. Exchangeability under writer and collection shift (the question the coordinator asked).**
- **Within one collection**, the guarantee is statistically sound *if* calibration and test units are random draws from the same collection (F2's protocol). Writer variety is then part of the distribution, not a violation. What you get is a **marginal** guarantee: rare hands can have much higher error, averaged away by common ones.
- **Across collections, or for new hands added later**, there is no guarantee. Weighted conformal needs density-ratio estimates that are unreliable for images. Mondrian (per-hand) calibration multiplies the labelling cost by the number of hands, and needs hand labels that most archives lack.
- HTR-A already proposes leave-one-writer-out violation measurement, which is right. Also add **group-conditional reporting for rare entity tokens**. A marginal guarantee over all words hides exactly the tokens (rare names, numbers) that archive users search for.
- Conclusion: sound in-collection with random sampling. Unsound as a portable claim. Position it as **"calibrate per collection with ~300–500 random lines"**.

**F4. How big must calibration sets be for ~1% word error?** (exact one-sided binomial test, i.i.d. words, counting *accepted* words only [C])

| Target α | True error on accepted | δ = 0.10 | δ = 0.05 |
|---|---|---|---|
| 1% | 0% | 230 | 300 |
| 1% | 0.5% | 390 | 780 |
| 1% | 0.8% | 3,610 | 5,990 |
| 2% | 1.0% | 270 | 390 |
| 2% | 1.6% | 1,800 | 3,050 |
| 0.5% | 0.25% | 780 | 1,550 |
| 0.5% | 0.4% | 6,990 | 11,990 |

- Certifying 1% is cheap only when the true accepted error is well below 1%, i.e. when coverage is sacrificed.
- Near the boundary (0.8%), it takes thousands of accepted *independent* words. Multiply by the design effect if words come from whole pages.
- LTT's fixed-sequence testing over thresholds avoids a Bonferroni penalty, but only if the order of thresholds is fixed in advance.
- **Practical target:** α = 1–2%, δ = 0.1, with 300–500 random *lines* (≈ 3–6k words) per collection. Report α = 0.5% as "certifiable only at low coverage".

**F5. The prediction-set search guarantee is weaker than stated.**
1. Coverage P(true word ∈ set) ≥ 1 − α is only reachable if the lattice oracle recall ≥ 1 − α. Otherwise sets need a wildcard/"other" element, which is useless as an index term. On messy hands the oracle may be below 95%.
2. Coverage assumes a correct word-position alignment. Segmentation errors (merged or split words, hyphenation across lines, which PRHLT handles with dedicated work) break the unit.
3. Per-occurrence marginal coverage is **not** per-query recall for rare names. Rare tokens get systematically lower coverage.
4. PrIx already indexes all hypotheses with posteriors and a tunable precision/recall threshold. The novelty is calibrated coverage, and it **must be compared against PrIx at a matched index size**, not only against single-best indexing.

**F6. Visually-Unsupported Word Rate (VUWR) is circular.**
- VUWR is defined using the same optical model and the same VSR gate that the proposed system uses to decide acceptance. By construction, the full system (VGCC) will score ≈ 0 on VUWR.
- The metric then rewards agreement with the CTC model, not faithfulness to the image.
- **Fix:** compute VUWR with an *independent* reference recognizer (different architecture and training data, e.g. a Kraken/CATMuS or TrOCR model when VGCC uses PyLaia). Treat the human-annotated error typology (their §4.C, κ-validated) as the primary hallucination measure and VUWR as a proxy only.

**F7. The occlusion probes' "any confident word = fabrication" rule is editorially wrong.**
- Scholarly editors legitimately *supply* text from context and mark it (e.g. `[June]`). A VLM that writes "June" in "the 3rd of [blot]" is doing reconstruction, not necessarily hallucinating. The fault is that the reconstruction is *unmarked*.
- Score **unmarked** supplied text as fabrication, and marked supplied text as acceptable. Prompts/output schema must provide a way to mark uncertainty, otherwise the probe measures the prompt rather than the model.
- Occlusions placed with CTC forced alignment boxes leak glyph fragments at word edges. Pad the boxes, and visually QA a sample.
- Synthetic blots on some collections may be out-of-distribution in ways that trigger odd VLM behaviour. HTR-A notes this. Keep the real-damage slice mandatory, not optional.

**F8. Leakage and split hygiene are not specified.** At least five disjoint roles are needed, split by **page (ideally by document or hand)**:
1. HTR fine-tuning.
2. Dev: tune λ, ε, τ and prompts.
3. Reliability-model training.
4. Conformal calibration.
5. Test, plus a shift test.

Further issues:
- Tuning τ or λ on calibration data invalidates the guarantee.
- READ 2016's official splits share hands across train and test, so the "in-distribution" numbers there will be optimistic for the shift story.
- **VLM contamination:** Bentham transcripts are public, and READ 2016 / CATMuS are on Hugging Face and GitHub. A held-out never-online slice is essential. HTR-A proposes 30–60 pages double-keyed, which is realistic but depends on archive access; make it a month-1 go/no-go.
- API VLM outputs change over time. Cache every response (record/replay) with model version and date, or results are not reproducible.

### 1.2 Is lattice-constrained decoding feasible with PyLaia + an open LLM on a consumer GPU?

**Feasible, but it is probably not worth it as the core.**
- **N-best:** PyLaia's LM decoding is built on a CTC beam-search decoder with KenLM (via torchaudio/flashlight in recent versions [U: confirm PyLaia's current decoder backend and whether it exposes N-best, since torchaudio has been deprecating parts of its API; pin versions]). N-best of 50–200 is obtainable. A true lattice is not exposed, so the "lattice" will in practice be a confusion network aligned from the N-best.
- **Constraint mechanics:**
  - A confusion network maps to a regex/FSA with alternations per slot, so `outlines`-style regex-constrained generation or HF `prefix_allowed_tokens_fn` over a character trie works.
  - The BPE-token vs character mismatch is solvable by walking the trie character by character for each candidate token.
  - FSM compilation for large alternations can be slow; cache per line.
- **Throughput [U: rough, to be measured]:**
  - A 4-bit 7B model on a T4/12 GB consumer GPU does roughly tens of tokens/s for constrained generation.
  - Reranking 100 hypotheses × ~30 tokens is ~3k tokens of prefill per line, around one to a few seconds per line. At ~30 lines/page that is ~1–2 min/page.
  - Fine for a few thousand evaluation lines (hours). **Not viable for millions of pages without a 1–3B model** or restricting the LLM to flagged lines only, which is the sensible design anyway.
- **Expected gain over N-best reranking is small:**
  - If the constraint set *is* the N-best/confusion network, token-level constrained decoding and batched N-best rescoring with λ-fusion explore nearly the same space.
  - Constrained decoding only adds recombination across slots (new combinations not in any single hypothesis).
  - ASR evidence (N-best T5 / lattice constraints) suggests modest gains [S via HTR-A].
- **Recommendation:** make **N-best/confusion-network rescoring + forced-alignment VSR arbitration** the core, and token-level constrained decoding a gated extension. Only do it if the M3 measurement shows oracle(confusion network) − oracle(N-best) ≥ ~1–2 WER points.

### 1.3 Overclaimed novelty

- **"First lattice-constrained correction for HTR":** HTR has long restricted LM influence to optical hypotheses. PyLaia n-gram shallow fusion, PRHLT lexicon-constrained KWS/PrIx and interactive-transcription work all do this. The new part is an *LLM/VLM* proposer plus an explicit out-of-lattice visual gate.
- **VSR:** a length-normalised forced-alignment likelihood ratio is a classic confidence/verification score in ASR and KWS. Present it as a component, not a contribution.
- **"First distribution-free risk control for HTR":** plausible, but it missed the close neighbours I found:
  - **GRC** (Gong et al., arXiv 2603.19790): risk-controlled abstention for VLM OCR, scene text.
  - **Athar** (arXiv 2608.19385): evidence-preserving review with bounded alternatives for Arabic manuscripts.
  - **PRHLT confidence-based interactive transcription.**
  - Novelty must be phrased narrowly: *historical handwriting + cross-architecture visual evidence + certified per-collection acceptance + shift measurement*.
- **IER/FER/Correction Precision:** "errors introduced vs fixed" accounting is common in OCR post-correction evaluation. I believe the ICDAR 2017/2019 post-OCR competitions and several papers report such splits [U: not verified this session]. Frame it as adoption plus a handwriting-specific breakdown, not an invention.
- **Prediction sets for search:** this is incremental over PrIx unless it beats PrIx at matched index size or gives guarantees PrIx can't (see F5).

### 1.4 Evaluation weaknesses (additional)

- **The "bitter lesson" is under-weighted in the design.**
  - HTR-A's own citation (Humphries' Gemini 3 blog, non-peer-reviewed) reports 0.69% normalised CER and hallucinations "vanishingly low" for English, with ~61% of errors being spelling/capitalisation standardisation.
  - A CTC-first pipeline with 60–85% coverage looks weak next to that on English.
  - The design should make **the VLM the primary transcriber and the CTC model the verifier**, and emphasise non-English, abbreviated and damaged material, where the trap is real.
- **Ground-truth convention noise:** a "modernisation" error can be a GT normalisation choice. A per-collection transcription-convention card (diplomatic vs normalised, abbreviations, long-s, punctuation) must be fixed before scoring. METATR's normalisation helps but is not diplomatic-aware.
- **No human-effort or cost outcome.** Certification is only valuable if flagged-span review is faster than full proofreading. Add review time per page and cost per useful page (from my draft).
- **Four+ datasets, three methods and a probe suite in 8 months is over-scoped.** Their fallback "minimum viable thesis" is good; promote it to the plan.

### 1.5 Citation spot-checks (abstract pages opened this session)

| HTR-A citation | Check result |
|---|---|
| **OmniHandwritingOCR**, arXiv 2608.18586 | **Confirmed.** Guo, Zhang, Jiang, CIKM 2026; 77.57K images; 13 systems; quote "hallucinate plausible but visually unsupported corrections" is accurate. HTR-A's label "modern, not historical" is *inferred*: the abstract mentions newly collected student writings but doesn't classify. Soften to "appears modern". |
| **SHROOM-Visions 2026**, via arXiv 2609.10244 | **Partly confirmed.** The paper is Eli Schwartz, "Two-Token Features and Small-Large Ensembles for VLM Hallucination Detection". It confirms character-level VLM hallucination detection in EN/FR/IT/ZH (28/21/21/22 teams). **Nothing indicates handwriting data**, and HTR-A cites a participant paper, not the task overview. Don't cite it as evidence about HTR; cite the overview once found. |
| **Consensus Entropy**, arXiv 2504.11101 | **Confirmed.** Zhang, Liang, Huang, Cui, Wang, Guo, Li, Liu; "correct predictions converge… errors diverge"; +42.1% F1 over VLM-as-Judge; "SOTA VLMs still struggle with detecting sample-level errors". Domain is general OCR, not historical handwriting. |
| **Kohút & Hradiš**, arXiv 2503.19546 | **Confirmed, with a caveat.** Actual title: "Practical Fine-Tuning of Autoregressive Models on Limited Handwritten Texts". 16 lines → 10% relative CER gain; 256 → 40%; confidence-based selection halves annotation cost. **The models are autoregressive transformers, not CTC/PyLaia**, so the results transfer to the proposed backbone only by analogy. |
| **METATR**, arXiv 2605.26712 (bonus) | **Confirmed.** Boillet, Tarride, Kermorvant; 29 languages; standardised prompting and normalisation; proprietary models more consistent; large variance across scripts. |

---

## 2. Where HTR-A beats my draft

1. **Statistical precision:** it distinguishes LTT from CRC, gives an explicit (α, δ) guarantee, groups calibration by page, and plans ≥100 random splits to check violation frequency. My draft only said "conformal risk controller".
2. **Introduced vs Fixed accounting (IER/FER/Correction Precision/Net Gain):** a cleaner way than mine to isolate the corrector's harm from the optical model's errors, and directly tied to the "does correction help without inventing" question.
3. **Controlled occlusion probes:** measure fabrication with known illegibility, which my token-class slices can't do. (Needs the editorial fix in F7.)
4. **The "bitter lesson" evidence:** the Humphries Gemini 3 blog (1.67% strict CER, ~61% of errors are standardisation). This sharpens *where* the hallucination trap actually lives. I missed it.
5. **Garrido-Munoz & Calvo-Zaragoza (CVPR 2025):** textual divergence dominates OOD generalisation, which motivates period-specific LMs and warns about modern-LM priors.
6. **Oracle lattice ceiling:** reports the upper bound of any constrained method. An essential honesty check I didn't include.
7. **Dual-layer output (diplomatic + labelled normalised layer, citing Pre-Editorial Normalization 2026):** a clean design answer to "LLMs normalise". Normalisation becomes a *visible, separate product* rather than a hidden error.
8. **Kohút & Hradiš:** few-line adaptation with confidence-based selection is a concrete active-learning hook for my human-in-the-loop story.
9. **ASR analogues** (conformal wav2vec 2.0 ASR, N-best T5, LTT for LLM-corrected ASR), plus PINK, KIE-HVQA and Mohri & Hashimoto: a wider related-work base I lacked.
10. **Pareto-frontier reporting** (CER vs introduced errors over λ/τ) instead of single points.
11. **An explicit minimum-viable-thesis fallback.**
12. **METATR as the normalisation/prompting protocol** for comparability.

What my draft adds that HTR-A lacks:
- GRC and Athar (closest neighbours)
- WildHandBench's prior-driven error share
- CHURRO 3B as an open VLM proposer
- VOC/Nationaal Archief ground truth and the GLOBALISE deployment context
- PrIx production systems (HIMANIS/Carabela/PARES) as the real search baseline
- cost per useful page, human review-time measurement, provenance-tracked PageXML, license table, record/replay reproducibility
- phone-capture slice
- entity-class-stratified slices

---

## 3. Merged counterproposal: the best single thesis

### Working title
**Trust but Verify: Certified Selective Transcription of Historical Handwriting with Visually-Grounded VLM Arbitration**

### 3.1 Core deliverable (must ship)
An open-source, reproducible pipeline plus a benchmark:

1. **Propose:** a VLM transcribes each line.
   - Open local model (CHURRO 3B or a Qwen-VL-class 3–7B, 4-bit) as primary.
   - One API frontier model on capped subsets for comparison.
   - A CTC optical model (PyLaia, fine-tuned per collection) produces N-best hypotheses and posteriors.
2. **Verify (grounded arbitration):**
   - Word-align the VLM output with the CTC N-best / confusion network.
   - Where they disagree, compute the forced-alignment visual support ratio (VSR) for each candidate.
   - Accept the VLM word if its visual support is sufficient; otherwise keep the optical reading and flag it.
   - Names, numbers and dates get stricter thresholds.
   - Output is a **diplomatic layer**. Normalisation or abbreviation expansion is optional, separate and labelled.
3. **Certify (selective acceptance):**
   - A per-word reliability model (CTC posterior, confusion-network entropy, VSR, VLM–CTC agreement, period-vs-modern LM surprisal gap, token class).
   - A threshold is chosen on **random-line calibration** from the target collection (F2).
   - Report CRC on the joint accepted-error rate, and LTT on the conditional accepted-error rate at (α = 1–2%, δ = 0.1).
4. **Deliver:**
   - PageXML/ALTO with per-word confidence, alternatives and provenance (VLM / CTC / arbitrated / flagged).
   - A minimal review UI that shows only flagged spans with image crops, and logs review time.
   - Cost/throughput instrumentation.
5. **HalluTrap-HTR benchmark + scorer package:**
   - Slices: rare names, numbers/dates, archaic spellings, abbreviations, clean control lines, real damage, synthetic occlusion (with the F7 editorial rule), and a held-out never-online slice.
   - Metrics are in §3.5.

### 3.2 One optional extension (only if gate G4 passes)
**Certified search index:** index each word's calibrated alternative set (prediction set) and compare with (a) single-best indexing and (b) a PrIx-style posterior index at **matched index size**. Evaluate on rare-entity queries.

I chose this over token-level constrained decoding because it serves the archive use case (findability) and the software-engineering side. Constrained decoding goes to future work unless M3 measurement shows an oracle gap of ≥ 1–2 WER points (see §1.2).

### 3.3 Month-by-month plan (8 months)
| Month | ML side | SE side | Gate at end of month |
|---|---|---|---|
| 1 | Verify literature ([S]/[K] items); PyLaia baselines on READ 2016 and the VOC ground truth; fix transcription-convention cards | Data ingestion (PageXML → JSONL), license registry, **page/document-grouped split generator (5 roles, F8)**, record/replay cache for API calls, CI skeleton | **G0:** baselines within ~20% relative of published CER; licenses cleared; held-out archive pages access secured (otherwise use a recently released collection as the "fresh" slice and state it) |
| 2 | VLM zero-shot + ungated multimodal correction runs; error typology annotation guidelines | Benchmark slicer (NER/regex/lexicon), occlusion generator with box padding, scorer package (CER/WER, IER/FER/CP, entity fidelity, modernisation, clean-line change, occlusion fabrication) with unit tests | **G1 (is the trap real here?):** on ≥1 non-English collection, ungated correction has Correction Precision < 0.95, OR introduces errors on ≥1% of entity tokens. If not → pivot the framing to certification + cost + search (still a thesis) |
| 3 | N-best / confusion network; forced-alignment VSR; oracle ceilings (N-best vs confusion network) | Pipeline orchestration (config-driven stages, containers), provenance-tracked PageXML writer, throughput/cost logging | Decide on the constrained-decoding extension: go only if oracle gap ≥ 1–2 WER points (default: no) |
| 4 | Grounded arbitration; sweep τ/λ on dev; Pareto frontiers; ablations (no VSR, no protected classes, text-only vs multimodal proposer, open vs API VLM) | Random-line calibration sampling tool; annotation UI for calibration lines; error-typology annotation (2 annotators, κ) | **G2:** arbitration cuts introduced errors by ≥30% relative vs ungated correction at ≤ 10% relative CER cost. If not → keep VSR only as a reliability *feature* (MVP still intact) |
| 5 | Reliability model; CRC (joint) + LTT (conditional); ≥100 random split replicates; leave-one-hand-out and cross-collection shift tests; rare-entity group reporting | Review UI for flagged spans with timing logs; exports | **G3:** coverage ≥ 50% at α = 2% (δ = 0.1) in-collection with ≤ 500 calibration lines. If not → report the risk–coverage trade-off and the expected-risk (CRC) version only |
| 6 | Held-out never-online slice evaluation; contamination delta analysis | Small user study (5–8 participants, e.g. history students; ethics approval started in M1) or simulated review: time to target quality for full proofreading vs flagged-only review; cost-per-useful-page model extrapolated to 10^6 pages | **G4:** core complete and reproducible end-to-end from one command → allow extension |
| 7 | Extension: calibrated alternative sets as index terms; coverage vs set size | Extension: search index (inverted index / OpenSearch), query set from ground-truth entities; PrIx-style baseline at matched index size; retrieval metrics | none (extension can be cut) |
| 8 | Writing, figures, threats to validity | Release: code, benchmark card, dataset scripts (no redistribution of non-CC-BY data), Docker image, docs | — |

### 3.4 Datasets
| Dataset | Role | License / notes |
|---|---|---|
| **READ-ICFHR 2016** (Ratsprotokolle, Early Modern German) | Primary non-English collection | CC-BY-4.0 [S]; official splits share hands, so add a hand-held-out split |
| **Nationaal Archief / Noord-Hollands Archief VOC + notarial ground truth** (Zenodo 4159268 / 11209325) | Primary Dutch collection; GLOBALISE-style use case | License to verify per record [U] |
| **Bentham (ICFHR 2014)** | English, contamination-risk slice; comparison with the Humphries-style VLM results | Public transcripts, so treat as contaminated |
| **CATMuS Medieval subset** | Abbreviation / graphematic stress slice (silent expansion = modernisation) | HF/Zenodo; check per-subset license |
| **Held-out never-online pages** (~30–50 pages, double-keyed) | Contamination-free test + shift test | Depends on archive partnership (G0) |
| *(Optional)* ~50 re-photographed printed scans | Phone-capture robustness slice | Weak proxy; label it as such |

### 3.5 Evaluation protocol
**Accuracy**
- CER/WER, strict and METATR-normalised, per slice.
- Bootstrap confidence intervals over pages.

**Faithfulness**
- Introduced Error Rate, Fixed Error Rate, Correction Precision, Net Gain.
- Entity/number exact-match and entity error rate.
- Modernisation rate, plus archaic insertion (Levchenko-style).
- Clean-line change rate.
- Occlusion fabrication rate: *unmarked* supplied text only, by severity.
- Prior-driven share (WildHandBench-style), from human typology (κ reported).
- VUWR computed with an **independent** reference recognizer (proxy only).

**Reliability**
- Risk–coverage curves, AURC, coverage at α ∈ {1%, 2%}.
- Guarantee violation frequency over ≥100 calibration/test resamples (in-collection), leave-one-hand-out and cross-collection.
- ECE of the reliability model.
- Group-conditional results for entity tokens.

**Human effort and cost**
- Minutes/page to target quality: flagged-only review vs full proofreading vs manual.
- GPU-seconds/page, API USD/page (dated prices), cost per useful page, and a 10^6-page extrapolation with stated assumptions.

**Search (extension)**
- MAP, recall@k on rare-entity queries, index size.
- Compare single-best vs PrIx-style vs calibrated alternative sets.

**Baselines**
1. CTC only.
2. CTC + n-gram LM.
3. VLM zero-shot.
4. Ungated text-only LLM correction.
5. Ungated multimodal correction.
6. N-best rerank only.
7. Full system.
8. Full system minus each component.

**Hygiene**
- 5-role grouped splits.
- No tuning on calibration data.
- Record/replay VLM cache with model ID and date.
- Seeds and configs committed.

### 3.6 Abstract (honest but compelling)
> Vision-language models now transcribe historical handwriting well, but on archival material they make the most dangerous kind of error. They produce fluent, plausible text that is not on the page: modernised spellings, "corrected" names, altered numbers. Aggregate character error rates hide these errors, and search engines spread them. We present *Trust but Verify*, an open-source pipeline in which a VLM proposes transcriptions and an independent, visually grounded CTC recognizer arbitrates every disputed word by forced alignment. A per-collection statistical calibration then decides which words can be released without review, with a certified bound on the error rate among released words. Everything else is flagged, with image evidence and alternatives, for a human. We also release HalluTrap-HTR, a benchmark and scoring toolkit that separates errors a corrector *introduces* from errors it *fixes*, with slices for rare names, numbers, archaic spellings, abbreviations and controlled illegibility. On Early Modern German, Dutch colonial and English collections, we report how much of each archive can be released with a certified low error rate, how quickly the guarantee breaks for unseen hands, how much reviewer time the flagging saves, and what it costs per page. The goal is not error-free transcription. It is to make every remaining error visible.

### 3.7 Reframing "near-zero error"
- **Drop:** "near-zero error" as a page-level CER claim. It is not achievable on messy cursive, and claiming it invites justified rejection.
- **Replace with "near-zero *unflagged* error, certified per collection":**
  - *"On collection X, calibrated with 400 randomly sampled lines, the system released N% of words. With 90% confidence, the error rate among released words is ≤ 2%, and released-and-wrong words are ≤ 1% of all words in expectation. The other (100 − N)% were flagged with alternatives. Rare entity tokens: M% released at an observed error rate of E%. Under an unseen hand, the bound was violated in V% of resamples."*
- **Second pillar, "no silent normalisation":** the diplomatic layer is only changed by visually supported edits. Normalisation lives in a separate, labelled layer.
- **Honest limits:**
  - The guarantee is marginal, not per word.
  - It needs recalibration per collection.
  - The error bound can be certified cheaply only by giving up coverage (F4 table).

### 3.8 Division of work
**ML side (method owner, HTR-A's strengths)**
- CTC fine-tuning, N-best and confusion networks, forced-alignment VSR.
- VLM proposer prompting (open + API).
- Arbitration and threshold sweeps.
- Reliability model; CRC/LTT implementation and proofs of which guarantee holds.
- Shift experiments; oracle analyses.
- Extension: calibrated alternative sets.
- Formal metric definitions.

**SE side (system/evaluation owner, HTR-B's strengths)**
- Data ingestion, license registry, grouped split generator.
- Benchmark slicer, occlusion generator, **scorer package** (tested, pip-installable).
- Pipeline orchestration (configs, containers, record/replay API cache, cost/throughput logging).
- Provenance-tracked PageXML/ALTO.
- Random-line calibration sampling + annotation tool.
- Flagged-span review UI with timing; user study / simulation.
- Cost-per-useful-page model.
- Extension: search index + PrIx-style baseline + retrieval evaluation.
- Release engineering (Docker, docs, CI).

**Shared:** metric definitions sign-off (M2), error typology annotation (κ), threats-to-validity chapter, writing.

**Interface contract between the two sides (fixed by end of M1):**
- A line-level JSONL schema: image crop reference; ground truth; per-system hypotheses; N-best with scores; per-word features; provenance.
- ML components are pure functions over this schema, so the SE harness can run them, cache them and score them independently.
