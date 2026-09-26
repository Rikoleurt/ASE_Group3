# HTR-B Draft: Reliable HTR for "Dark" Archives. Systems, Data, Evaluation and Real-World Use

Agent: HTR-B (systems / data / evaluation lens). Date: 2026-09-16.
Verification: [V] = I opened the paper's abstract or page and checked the claim. [S] = the claim comes only from a search-result snippet, so check it before citing. [U] = not verified, or my own estimate.

---

## 0. Framing: what "near-zero error" can honestly mean

- On messy early-modern cursive, a single model will not reach near-zero character error rate (CER) over whole pages. Well-funded production systems report figures like "at least 96% correct" (Loghi, [S]) or ">90% of characters correct" (the Dutch National Archives / Transkribus "IJsberg" model, [S]). LLM-based HTR gets about 5.7–7% CER on English 18th–19th c. letters (Humphries et al., [S]). Some popular reports quote <2% after LLM correction, but that was on a small corpus (50 documents) of English hands, which are the easiest case for LLMs.
- A claim we can defend and test is **near-zero *silent* error**. The pipeline sorts output into three bins: auto-accept, flag for review, or abstain. On what it auto-accepts, the error rate is provably low (for example CER ≤ 0.5% and ≤ 0.1% wrong names/numbers on auto-accepted tokens, at a stated coverage). We report the whole **risk–coverage curve**, not one CER.
- For searchability, the right target may be **retrieval quality**: recall and precision on the name, place and date queries historians actually run. This is not the same as transcription CER. Probabilistic indexing (PrIx) was built for exactly this (Vidal, Toselli et al.).
- "Zero-hardware" should mean: no special scanners, no local GPU cluster, and a pipeline that runs on a consumer GPU or free-tier Colab plus capped API spend. Phone-camera input is a *robustness condition* to evaluate, not an assumption.

---

## 1. Literature check

### 1.1 Probabilistic indexing (PrIx) and keyword spotting
| Work | Key point | URL | Status |
|---|---|---|---|
| Toselli, Puigcerver, Vidal (eds.), *Probabilistic Indexing for Information Search and Retrieval in Large Collections of Handwritten Text Images*, Springer 2024 | Book-length treatment. Probabilistic indexes represent word-level uncertainty so collections can be searched without transcripts. | https://link.springer.com/book/10.1007/978-3-031-55389-9 | [S] |
| Lexicon-based probabilistic indexing of handwritten text images, *Neural Computing and Applications* 2023 | PrIx framework, lexicon-based variant | https://link.springer.com/article/10.1007/s00521-023-08620-y | [S] |
| A Probabilistic Framework for Lexicon-based Keyword Spotting in Handwritten Text Images (arXiv 2104.04556) | Probabilistic KWS as the base of PrIx; precision/recall trade-off | https://arxiv.org/pdf/2104.04556 | [S] |
| Carabela project (Vidal, Romero, Toselli et al.) | Large-scale PrIx of ~125k images of Spanish 15th–19th c. manuscripts; public search UI | https://www.researchgate.net/publication/347177230 ; https://www.prhlt.upv.es/htr/carabela/ | [S] |
| HIMANIS (French royal chancery registers, 1302–1483) | ~75–83k page images indexed with KWS/PrIx; public search system | http://himanis.huma-num.fr/app/ ; https://eadh.org/projects/himanis | [S] |
| Large-scale PrIx of Bentham's manuscripts (English neologisms study) | Uses PrIx for humanities research questions, not only search | https://www.springerprofessional.de/en/a-study-of-english-neologisms-through-large-scale-probabilistic-/17127674 | [S] |
| Zipf Curves and Basic Text Analytics from Untranscribed Manuscript Images (ICDAR 2024) | Text analytics straight from PrIx without transcription | https://link.springer.com/chapter/10.1007/978-3-031-70543-4_16 | [S] |
| PARES (Spanish Ministry of Culture) | National archive portal offering HTR + PrIx search (production use) | https://pares.cultura.gob.es/pares/en/preguntas-frecuentes.html | [S] |
| KWS-assisted transcription cost model (J. Imaging 2020, 6(11):117) | Correcting a wrong word costs more than typing a missed one, so a KWS-assisted workflow should favour precision | https://doi.org/10.3390/jimaging6110117 | [S] |

I did not find the "TIDOP" project the brief mentions under that name. It may be a mis-remembered acronym, so I have not cited it.

### 1.2 Production and open-source HTR pipelines
| Work | Key point | URL | Status |
|---|---|---|---|
| Loghi (van Koert, Klut, Koornstra, Maas, Peters), ICDAR 2024 Workshops | End-to-end modular open-source pipeline (Laypa layout, baselines, HTR) → PageXML. KNAW HuC with the Nationaal Archief. | https://link.springer.com/chapter/10.1007/978-3-031-70645-5_6 ; https://github.com/knaw-huc/loghi | [S] |
| GLOBALISE / VOC: 4.8M scans of the VOC "Overgekomen brieven en papieren" (1610–1796) transcribed with Loghi | Real million-page deployment; published transcriptions | https://www.huygens.knaw.nl/en/5-million-scans-voc-archives-online-and-searchable/ ; https://pure.knaw.nl/portal/en/datasets/voc-transcriptions-globalise/ | [S] |
| Nationaal Archief / Noord-Hollands Archief ground truth: "6000 ground truth of VOC and notarial deeds, 3,000,000 HTR" (Zenodo) | ~6k GT scans (JPG + PAGE XML) plus HTR output. Transkribus "IJsberg" model, >90% character accuracy. | https://zenodo.org/records/4159268 ; https://zenodo.org/records/11209325 | [S] (check license per record) |
| Fine-grained NER for the East-India Company archive (ACH anthology) | Picks documents *where HTR/layout performed well* for annotation. The downstream bias this creates is itself a gap. | https://anthology.ach.org/volumes/vol0003/fine-grained-named-entity-recognition-for-east/10.63744@DRbhWNTzqNzR.pdf | [S] |
| eScriptorium (Kiessling, Tissot, Stokes, Stökl Ben Ezra), ICDAR-WS 2019; Kraken v5 (ICDAR 2025) | Open platform plus trainable baseline segmentation and recognition | https://www.semanticscholar.org/paper/a27674424ce8d86bae9f717d00e942d86025cf30 ; https://link.springer.com/chapter/10.1007/978-3-032-04624-6_26 | [S] |
| YALTAi: object detection instead of region segmentation in Kraken (arXiv 2207.11230) | Layout alternative | https://arxiv.org/pdf/2207.11230 | [S] |
| PyLaia + language models (Teklia), arXiv 2404.18722, ICDAR 2024 | n-gram LM decoding gives about −13% WER / −12% CER. **Explicit analysis of confidence scores and the need for calibration.** 12 open models on Hugging Face. | https://arxiv.org/abs/2404.18722 | [S] |
| Transkribus pricing | 1 credit ≈ 1 page for text recognition; free plan 50 credits/month; 50% API discount on organisation plans | https://www.transkribus.org/credits ; https://www.transkribus.org/plans | [S] |
| Transkribus "vision for 2026" | Plans to integrate external LLMs as opt-in, with data-sovereignty framing | https://www.transkribus.org/blog/community-ai-the-transkribus-vision-for-2026 | [S] |
| FP-THD: Full page transcription of historical documents (arXiv 2601.17040, Pattern Recognition) | Layout + MAE-ViT line recognition for 15th–16th c. Latin | https://arxiv.org/abs/2601.17040 | [V] (abstract only) |

### 1.3 Datasets and ground-truth infrastructure
| Resource | Notes | URL | Status |
|---|---|---|---|
| HTR-United (Chagué, Clérice et al.) | Catalogue of GT datasets. In Oct 2022: 56 datasets, 41.5M chars, 725k lines, 13+ languages. Mostly French. | https://htr-united.github.io/catalog.html ; https://zenodo.org/records/8107761 | [S] |
| CATMuS Medieval (ICDAR 2024) | 200+ manuscripts, 10 languages, 160k+ lines, 8th–16th c.; consistent guidelines; on HF/Zenodo | https://huggingface.co/datasets/CATMuS/medieval ; https://link.springer.com/chapter/10.1007/978-3-031-70543-4_11 | [S] |
| READ / ICFHR 2016 (Ratsprotokolle, Early Modern German) | CC-BY-4.0, PAGE XML line level | https://zenodo.org/records/1164045 | [S] |
| Bentham (ICFHR 2014 / tranScriptorium ICDAR 2015) | English, few writers | https://www.researchgate.net/publication/286924500 | [S] |
| CHURRO-DS (Semnani et al., arXiv 2509.19768) | 99,491 pages from 155 historical corpora, 46 language clusters. License not stated in the abstract. | https://arxiv.org/abs/2509.19768 | [V] |
| HCCD: handwritten camera-captured dataset (Data in Brief 2025) | Camera captures under varied degradations. **Modern** handwriting, so only a proxy for phone-captured archives. | https://pmc.ncbi.nlm.nih.gov/articles/PMC12281058/ | [S] |
| ICDAR 2025 FEST (few-shot line segmentation, U-DIADS-TL) | Only 3 annotated pages per manuscript, a realistic low-GT setting | https://arxiv.org/abs/2509.12965 | [S] |

### 1.4 VLM/LLM-based HTR and the hallucination trap (core evidence)
| Work | Key finding for us | URL | Status |
|---|---|---|---|
| Humphries et al., "Unlocking the Archives", arXiv 2411.03340; *Historical Methods* 58(3), 2025; tool: Transcription Pearl | LLMs reach 5.7–7% CER and 8.9–15.9% WER on 18th–19th c. English, beating Transkribus, and are cheaper and faster. English-only, small corpus. | https://arxiv.org/abs/2411.03340 ; https://github.com/mhumphries2323/Transcription_Pearl | [S] |
| Crosilla, Klic, Colavizza, "Benchmarking LLMs for HTR", arXiv 2503.15195 | Proprietary models beat open ones; English bias. **"LLMs demonstrate limited ability to autonomously correct errors in zero-shot transcriptions."** No consistent advantage over Transkribus. | https://arxiv.org/abs/2503.15195 | [V] |
| Levchenko, "Evaluating LLMs for Historical Document OCR", arXiv 2510.06743 | 12 MLLMs on 18th c. Russian Civil font. **Post-OCR correction made results worse.** Models insert archaic characters from the wrong period. Proposes **HCPR** (Historical Character Preservation Rate) and **AIR** (Archaic Insertion Rate), plus contamination control. | https://arxiv.org/abs/2510.06743 | [V] |
| Kanerva et al., "OCR Error Post-Correction with LLMs in Historical Documents: No Free Lunches", arXiv 2502.01205 | Helps for English, **not practically useful for Finnish** | https://arxiv.org/abs/2502.01205 | [V] |
| Greif, Griesshaber, Greif, "Multimodal LLMs for OCR, OCR Post-Correction, and NER in Historical Documents", arXiv 2504.00414 | Multimodal post-correction (image + OCR text) gives <1% CER on German city directories (**printed** text). Supplying the image cuts down guessing. | https://arxiv.org/abs/2504.00414 | [V] |
| Ehrmann et al., "ICDAR 2026 HIPE-OCRepair Competition", arXiv 2607.08143 | LLM post-correction helps on average, **but over-correction on low-noise inputs is a recurring problem**. Argues evaluation must go "beyond character error reduction". Uses retrieval-oriented scoring. Text-only, printed text. | https://arxiv.org/abs/2607.08143 | [V] |
| WildHandBench, arXiv 2608.22959 | 500 handwritten documents. Best MLLM scores 71.85% vs humans 77.09%. **63–91% of model errors are "prior-driven" vs 49% for humans.** Introduces the **Prior-Driven Error (PDE)** metric. Modern handwriting, not historical. | https://arxiv.org/abs/2608.22959 | [V] |
| CHURRO (Semnani et al.), arXiv 2509.19768 | Open 3B VLM for historical text: 70.1% normalized Levenshtein similarity on handwriting, +6.5 points over Gemini 2.5 Pro, 15.5× cheaper | https://arxiv.org/abs/2509.19768 | [V] |
| Isom, "An HTR-LLM Workflow for … Abbreviated Latin Court Hand", arXiv 2507.04132 | HTR → multimodal LLM correction → abbreviation expansion → named-entity correction; 2–7% WER. The abstract has no controlled over-correction analysis. | https://arxiv.org/abs/2507.04132 | [V] |
| Ali et al., "Phoenix and Athar" (Arabic manuscripts), arXiv 2608.19385 | CNN-BiLSTM-CTC (5M params) plus an **evidence-preserving review workflow**. Shows bounded alternatives instead of silent replacement. Large gap between beam and oracle (so N-best holds recoverable information). | https://arxiv.org/abs/2608.19385 | [V] |
| Gong et al., "From Plausibility to Verifiability: Risk-Controlled Generative OCR with VLMs" (Geometric Risk Control), arXiv 2603.19790 | Model-agnostic abstention: probes a black-box VLM with geometric transforms and releases output only when the views agree. **Scene text only, not handwriting or historical.** Code on GitHub. | https://arxiv.org/abs/2603.19790 | [V] |
| Angelopoulos & Bates, "A Gentle Introduction to Conformal Prediction", arXiv 2107.07511 | Distribution-free risk control, the basis for certified selective acceptance | https://arxiv.org/abs/2107.07511 | [S] (well-known) |
| IEEE Spectrum, "General AI Handwriting Transcription Aids Archivists" | Popular coverage: LLMs <2% CER vs ~8% for Transkribus, ~50× cheaper. **Reports no archivist hallucination concerns**, which is a gap in awareness rather than evidence that the problem doesn't exist. | https://spectrum.ieee.org/ai-handwriting-transcription-transkribus-lecun | [V] |

### 1.5 Cost studies
- **I did not find a published per-page cost study** for GLOBALISE/VOC (compute, GT creation, human correction). Transkribus credit pricing and the LLM-vs-Transkribus cost ratio in Humphries/IEEE Spectrum are the only concrete numbers I found. [U] A rigorous, reproducible **cost-per-useful-page model** (compute + API + human review minutes) is itself a gap we can fill.

---

## 2. Gap mining (explicit or strongly implied openings)

G1. **Over-correction is recognised but has no benchmark for historical *handwriting*.** HIPE-OCRepair 2026 names over-correction on low-noise inputs, but its task is text-only printed OCR. Levchenko's AIR/HCPR covers one printed Russian font. WildHandBench's PDE uses modern handwriting. No stratified test set targets **the specific tokens historians care about** (rare personal and place names, archaic spellings, abbreviations, numerals, dates, currency, ship names) in historical cursive.

G2. **LLM self-correction in HTR is unreliable.** Crosilla et al. find limited autonomous correction; Levchenko finds that correction makes results worse; Kanerva et al. find it language-dependent. Yet workflows (Transcription Pearl, Isom's pipeline, Transkribus 2026 plans) are adopting LLM correction. **There is no mechanism that decides when a proposed edit is supported by visual evidence.**

G3. **Confidence scores exist but are not calibrated or used for guarantees.** Teklia highlights the need for calibration. Athar shows N-best alternatives but gives no statistical risk guarantee. GRC gives risk control for VLM OCR but only on scene text. **No work applies conformal or selective risk control to historical HTR with token-class-specific risk (names and numbers).**

G4. **Search vs transcription.** PrIx is mature and deployed (HIMANIS, Carabela, PARES), yet the VLM-HTR literature evaluates only CER/WER. **Nobody measures how VLM hallucinations affect retrieval** (false hits and missed hits on entity queries), or compares PrIx-from-CTC with search over VLM transcripts.

G5. **Downstream selection bias.** The VOC NER corpus picked documents where HTR and layout worked well. Performance on hard pages (marginalia, tables, damaged pages) is under-reported. The ICDAR 2025 FEST competition emphasises few-shot segmentation.

G6. **No open, reproducible cost model** that combines compute, API tokens, GT creation and human review minutes at the million-page scale.

G7. **Phone-capture robustness for *historical* HTR is largely unmeasured.** Camera-captured datasets such as HCCD are modern handwriting, and dewarping work evaluates printed OCR.

G8. **Contamination.** Levchenko calls for contamination control: famous public collections (Bentham etc.) may be in VLM training data, which inflates zero-shot results. Benchmarks should include held-out or newly released material.

---

## 3. Candidate ideas (6), then the top 3

1. **HalluTrap-HTR: a benchmark and metrics for faithful historical transcription** (G1, G8)
2. **Evidence-gated correction with certified selective acceptance: "verify, don't rewrite"** (G2, G3)
3. **Search-first: do VLM hallucinations break archival search? PrIx vs VLM transcripts on entity retrieval** (G4)
4. Phone-capture robustness study for historical HTR, with a capture-quality gate app (G7)
5. Cost-per-useful-page simulator and active-learning triage for million-page projects (G6)
6. Hard-page layout stress test (marginalia, tables, multi-column) on VOC data (G5)

Ideas 4–6 fit better as **work packages inside** ideas 1–3 than as standalone theses. Idea 5's cost model belongs in idea 2's evaluation, and idea 4's capture-degradation condition can be a benchmark slice in idea 1.

**Recommendation:** combine **Idea 1 (benchmark) + Idea 2 (system)** as the main thesis, with Idea 3 as a stretch goal or a partner's parallel track. The benchmark gives the project a defensible, publishable contribution even if the system work underperforms.

---

### IDEA 1: HalluTrap-HTR, a benchmark for the hallucination trap in historical handwriting

**Problem.** CER/WER treat every character alike and reward fluent outputs. Historians are harmed most by *plausible* errors: normalising "Pieterszoon" to "Pietersen", "Batavia 1673" becoming "1678", or modernising "hath" and "Cochin" spellings. The field has no way to measure this for historical cursive.

**Novelty claim.** Existing work covers over-correction for printed OCR (HIPE-OCRepair 2026, Levchenko) and prior-driven errors for modern handwriting (WildHandBench PDE). This would be the first **token-class-stratified, contamination-aware** benchmark for historical *handwriting*. It separates (a) visual misreads from (b) prior-driven substitutions, and measures **over-correction on already-correct lines**.

**Data (all open GT; check licenses per record).**
- VOC / notarial ground truth, Dutch 17th–19th c. (Zenodo 4159268 / 11209325; license to be checked [U]).
- READ-ICFHR 2016, Early Modern German (CC-BY-4.0 [S]).
- Bentham, English (contamination-risk slice).
- One CATMuS or HTR-United French or Latin subset.
- Optional **held-out slice**: 200–500 lines transcribed by the students or a partner archive after the models' cutoffs, or from collections unlikely to be online (contamination control).

**Construction (software-engineering heavy, reproducible).**
1. Automatic token tagging on GT: named-entity tagger + regexes for numerals, dates and currency; archaic-spelling detection by distance to a modern lexicon; abbreviation marks.
2. "Temptation score" per token: how strongly a modern LM prefers a different form. Compute the LM probability of the GT token vs its top substitute; high-surprise valid tokens are the traps.
3. Stratified sampling into slices: rare names, archaic spellings, numbers/dates, abbreviations, clean control lines, degraded lines, phone-recaptured lines (optional, from idea 4).
4. **Counterfactual pairs** (if time allows): for numbers and dates, pair real lines where the context "suggests" another value. No synthetic images, so there are no rendering-validity issues.
5. A versioned dataset card, a PageXML → JSONL loader, and a scorer package (pip-installable), with CI tests for the metrics.

**Metrics.**
- Standard: CER, WER, per slice.
- **Entity/number fidelity**: exact-match rate on tagged tokens (names, numerals, dates).
- **Over-correction rate (OCR@clean)**: fraction of correct input tokens that a corrector changes into wrong ones (HIPE-style concern, adapted).
- **Hallucination rate**: substitutions that are real words or names but not visually supported, i.e. wrong *and* in-lexicon or more fluent. A PDE-style decomposition following WildHandBench.
- **Normalisation/modernisation rate**: archaic token → modern equivalent (analogous to Levchenko's AIR in reverse).
- **Insertion/deletion of whole tokens** (fabricated continuations).

**Systems compared.** (a) CTC HTR (PyLaia/Kraken/Loghi models, n-gram LM on and off). (b) CHURRO 3B open VLM. (c) 1–2 commercial VLMs, zero-shot, on a capped subset. (d) HTR + text-only LLM correction. (e) HTR + multimodal correction (Greif et al. style). (f) Idea 2's gated system.

**Expected findings (hypotheses, not claims).** Text-only correction lowers overall CER on English but raises entity/number error and modernisation; multimodal correction reduces this but does not eliminate it; CTC HTR has more random errors but fewer fluent substitutions.

**Risks.**
- License ambiguity on some GT. Mitigation: use CC-BY sets only for redistribution and ship scripts for the rest.
- NER tagger errors on historical text. Mitigation: hand-verify the benchmark slices, which is ~1–2k tokens and feasible.
- API cost. Mitigation: 1–2k lines × 2 models is small [U: estimate a few tens of USD at 2026 prices, to be measured].
- Contamination cannot be ruled out. Mitigation: a held-out slice plus reporting the delta between slices.

**Scope.** About 3 months for 1 person. Low GPU need (inference only).

---

### IDEA 2: Evidence-gated correction and certified selective acceptance ("verify, don't rewrite")

**Problem.** The practical choice today is between noisy but visually faithful CTC HTR and fluent but sometimes fabricated LLM/VLM output. Archives need to know *which* lines they can trust without reading them.

**Novelty claim.** Existing pieces are separate:
- LLM correction (Humphries, Isom, Greif) with no visual verification of edits.
- N-best review UIs (Athar) with no statistical guarantee.
- Conformal risk control for VLM OCR (GRC) on scene text only.

We combine them for historical HTR. **Every LLM/VLM edit must be re-scored by the visual (CTC) model before acceptance.** A **conformal risk controller, calibrated per token class**, decides auto-accept, human review or abstain. The pipeline is open-source and reports cost per page.

**System sketch.**
```
Image (scan or phone photo)
  -> [Capture QA] blur/skew/resolution check (reject or ask for a retake)
  -> [Layout] Loghi/Laypa or Kraken baselines + region types (main text, marginalia, table)
  -> [HTR] CTC recognizer (PyLaia/Kraken/Loghi pretrained, fine-tuned on few pages)
        outputs: 1-best, N-best / lattice, per-char posteriors
  -> [Proposer] LLM/VLM proposes edits (image + N-best in prompt), constrained to
        span-level edits with a stated reason; optional: CHURRO 3B locally
  -> [Verifier / gate] for each proposed edit:
        - CTC forced-alignment log-likelihood of edited line vs original
          (edit accepted only if visual likelihood drop < tau_class)
        - agreement checks: in N-best? cross-model agreement? GRC-style
          augmentation consistency (rotate/scale crop, re-recognize)
        - protected classes (names, numbers, dates): stricter tau, or never
          auto-edit, only flag
  -> [Risk controller] features -> score -> conformal threshold chosen on a
        calibration split so that expected token error on auto-accepted
        tokens <= alpha (per class)
  -> Outputs: PageXML with per-token confidence + alternatives + provenance
        ("HTR", "LLM-edit-verified", "flagged"); JSONL search index
  -> [Review UI] minimal web UI (or eScriptorium import) that shows only flagged
        spans with image crop + alternatives; logs time per decision
  -> [Active learning] corrected lines feed back into fine-tuning (optional)
```

**Why this is a software-engineering contribution.**
- Modular, containerised pipeline with PageXML in and out, so it interoperates with eScriptorium, Transkribus exports and Loghi.
- Provenance tracking and an audit trail for every character change, the "evidence-preserving" requirement Athar argues for.
- Cost/throughput instrumentation: GPU-seconds, API tokens and USD per page, with a simulator that extrapolates to 10^6 pages.
- Reproducible experiments (config-driven, seeds, DVC or HF datasets), CI tests and a documented API.

**Datasets.** Train/calibrate on VOC/notarial GT (Dutch) and READ-2016 (German); test on HalluTrap-HTR slices (Idea 1). Calibration and test splits are disjoint by document, and ideally by writer, to avoid optimistic conformal guarantees.

**Evaluation.**
1. **Risk–coverage curves**: CER and entity/number error on auto-accepted tokens vs fraction auto-accepted, per class, compared with (a) raw HTR, (b) HTR + ungated LLM, (c) VLM only, (d) HTR + confidence threshold without an LLM.
2. **Guarantee validity**: does empirical risk stay ≤ α on the held-out test set? Also under shift: new hand, new archive, phone capture. Report where the guarantee breaks, since exchangeability is violated under domain shift. This is an honest, useful finding either way.
3. **Hallucination metrics** from Idea 1 (over-correction on clean lines, entity fidelity, modernisation).
4. **Human effort**: small user study (5–10 participants, e.g. history students) or simulation. Minutes per page to reach a target quality: full manual vs correct raw HTR vs review flagged spans only. Keystroke/decision logs.
5. **Cost per useful page**: (compute + API + human minutes × wage) / pages meeting the quality target, extrapolated to 1M pages with stated assumptions.
6. **Ablations**: without the verifier, without protected classes, text-only vs multimodal proposer, open 3B VLM vs commercial.

**Risks.**
- *CTC forced-alignment scoring may be too lenient or too harsh* when the HTR is weak on a new hand, so the gate rejects good edits. Mitigation: combine several evidence features and learn the gate on the calibration split.
- *Conformal guarantees are marginal and assume exchangeability*; they will not hold across archives. Present them as "calibrated per collection with a small labelled sample (~100–300 lines)", which is realistic for archives.
- *Proprietary API drift and cost*. Mitigation: design around an open local VLM (CHURRO 3B, or a Qwen-VL-class model) and use commercial APIs only as a capped comparison.
- *Overlap with HTR-A* (method-first): agree on the split. HTR-A takes the proposer/verifier model design; HTR-B takes the gating, calibration, pipeline and evaluation.
- *User study logistics / ethics approval*. Fallback is simulated review using GT.

**Scope (6–9 months, 1–2 people, consumer GPU).**
- M1–2: pipeline skeleton on pretrained models; data loaders; Idea 1 benchmark v0.
- M3–4: verifier + gate; calibration experiments.
- M5–6: risk controller, UI, cost instrumentation.
- M7: user study / simulation.
- M8–9: write-up and release.

Fine-tuning a CTC recognizer (≤10M params) fits on an 8–12 GB GPU. No VLM training, only inference with a 3B model (4-bit quantised if needed) [U: throughput to be measured].

---

### IDEA 3: Search-first evaluation. Do hallucinations break archival search?

**Problem.** Archives mainly need *findability*, and users query names, places and commodities. PrIx is deployed (HIMANIS, Carabela, PARES), yet recent VLM-HTR papers evaluate only transcription. A VLM that fabricates a plausible name creates a false hit; one that normalises a spelling hides a true hit.

**Novelty claim.** The first head-to-head **retrieval** comparison of (a) PrIx-style probabilistic indexes built from open CTC posteriors, (b) search over 1-best HTR, (c) search over VLM transcripts, and (d) search over Idea 2's gated output. Queries are entity-centric and drawn from real historian information needs, and the comparison **attributes retrieval errors to hallucination vs misrecognition**.

**Data.** VOC GT (Dutch) with entity annotations, if the GLOBALISE NER annotations are accessible [U: check release/license], plus READ-2016 or Bentham. Query sets built from GT entity lists, stratified by frequency (rare names matter most).

**Method sketch.**
- Implement an open, lightweight PrIx approximation: word-level relevance probabilities from CTC lattices / N-best, with character-level posteriorgrams for lexicon-free search. PRHLT's production PrIx tooling may not be fully open [U]; a re-implementation must be described as an approximation.
- Index everything into OpenSearch/Elasticsearch or a simple inverted index with probability thresholds.
- Metrics: mean average precision, recall@k, precision at fixed recall for rare-entity queries, fuzzy-query variants (spelling variation), false-hit rate attributable to hallucinated tokens, and index size / build cost per page.

**Risks.** A faithful PrIx re-implementation is non-trivial, so scope it to N-best-based word posteriors. Query realism: involve one historian or reuse published query logs if any exist [U]. Overlaps with Idea 1's metrics, which is good for reuse.

**Scope.** 3–4 months as a standalone project, or 6–8 weeks as a chapter reusing Idea 1/2 infrastructure.

---

### Short notes on the non-selected ideas
- **Idea 4 (phone capture):** Genuine gap (G7), but a real historical phone-capture dataset needs archive access. "Print-and-rephotograph" of scans is a weak proxy (double sampling, modern paper). Best used as a *robustness slice*: re-photograph ~50 printed scans under controlled conditions, plus a simple capture-quality gate (blur/skew/DPI estimate) in Idea 2's pipeline.
- **Idea 5 (cost simulator + active learning):** Good engineering content, thin as a research contribution on its own. Fold it into Idea 2's evaluation (cost per useful page, and which lines to send for GT creation first).
- **Idea 6 (hard-layout stress test):** Real (G5), but layout is a big field in its own right. Include a "marginalia/table" slice in the benchmark and report layout-error propagation to entity fidelity.

---

## 4. Consolidated evaluation protocol (shared across ideas)
| Dimension | Metric | Notes |
|---|---|---|
| Accuracy | CER, WER (per slice, per hand) | Report CIs by bootstrap over documents |
| Faithfulness | Entity/number exact-match, over-correction on clean lines, modernisation rate, PDE-style prior-driven share, fabricated insertions | Core novelty |
| Reliability | Risk–coverage curves; empirical risk vs target α; calibration error (ECE) | Include shift conditions |
| Search | MAP, recall@k on rare entities; false-hit rate from hallucinations | Idea 3 |
| Cost | GPU-s/page, API USD/page, human min/page, cost per useful page; extrapolation to 1M pages | State hardware and prices with dates |
| Human effort | Time to target quality; decisions per page; reviewer agreement | Small study or simulation |
| Reproducibility | Containers, configs, seeds, dataset cards, license table | SE deliverable |

## 5. Biggest risks overall (candid)
1. **"Near-zero error" overclaim.** Must be reframed as near-zero *silent/unflagged* error at stated coverage. Coverage on hard cursive may be low (e.g. 50–70% of tokens auto-accepted [U]), and the thesis must report this honestly.
2. **Distribution shift breaks calibration.** Guarantees are per collection; a new hand needs a small calibration set.
3. **Data licensing/contamination.** Mitigate with CC-BY sets, a held-out slice and scripts instead of redistribution.
4. **Fast-moving field.** Transkribus is integrating LLMs in 2026 and HIPE-OCRepair already targets over-correction, so novelty must stay anchored in *handwriting + evidence gating + guarantees + retrieval impact*, and related work must be re-checked before submission.
5. **API budget and model drift.** Use an open local VLM as the primary; commercial models only as a capped, dated comparison.
6. **Unverified items in this draft** ([S]/[U]) need checking from full texts before citing, especially dataset licenses, Loghi accuracy figures and the Humphries cost numbers.
