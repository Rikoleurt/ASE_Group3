# HTR-A Draft: Method-First Research Directions for Faithful Historical HTR

**Agent:** HTR-A (method-first / novel ML lens)
**Date:** 2026-09-16
**Topic:** Turning "dark" archival cursive pages into searchable text at scale without falling into the Hallucination Trap.

---

## 0. Executive summary

- **What's changed:** Frontier VLMs (Gemini 3, GPT-5 class, Claude) are now as good as or better than specialised HTR on *clear English* 18th–19th c. handwriting. One practitioner benchmark reports about 1.7% strict CER for Gemini 3 Pro. Still, a large share of their remaining errors are "statistical corrections": standardised spelling and capitalisation. That is the Hallucination Trap at work. On non-English, abbreviated, degraded or unusual hands, results still vary a lot.
- **What's still missing:** Nobody has faithfulness guarantees or hallucination-specific metrics for *historical handwriting*. The literature measures post-correction with aggregate CER/WER. Over-correction is noted as a "recurring challenge" (ICDAR 2026 HIPE-OCRepair, printed text only). Hallucination metrics exist for handwritten math (PINK), printed Russian (AIR/HCPR) and KIE forms (KIE-HVQA), but not for cursive archival HTR.
- **Recommended thesis (combining ideas A + B, evaluated with C):**
  - **A. Visually-grounded constrained correction.** An LLM may only choose readings that the optical (CTC) model supports. It may leave that set only when a forced-alignment "visual support" test passes.
  - **B. Conformal selective transcription.** Distribution-free risk control over the words the system auto-accepts ("≤1% word error on accepted words, with probability ≥ 90%"). Everything else is flagged for a human. Conformal *prediction sets* become index terms, which gives a search-recall guarantee.
  - **C. Hallucination Trap probe suite + metrics.** Occluded-span fabrication rate, modernisation rate, introduced-error rate, and visually-unsupported-word rate.
- **What "near-zero error" can honestly mean:** not near-zero CER on whole pages. It means a *certified low error rate on the automatically accepted portion* (for example ≤1% WER at 70–90% word coverage), holding in expectation or with high probability over exchangeable data from a calibrated collection. It degrades under writer or collection shift, and measuring that degradation is part of the contribution.

---

## 1. Literature check

Status legend:
- **[V]**: I opened the abstract or page in this session and verified it.
- **[S]**: seen in search-result snippets only (title/URL confirmed, details not read).
- **[K]**: known from background knowledge; *not* re-verified this session. Check before citing.

### 1.1 Optical HTR models and toolkits

| Work | Key points | Status |
|---|---|---|
| **TrOCR** (Li et al., 2021), arXiv:2109.10282, https://arxiv.org/abs/2109.10282 | Encoder–decoder transformer (image ViT + text transformer). Pretrained on synthetic data, fine-tuned on IAM. Strong, but its autoregressive decoder carries its own LM prior, so it can also "hallucinate". | [S] |
| **DAN** (Coquenet, Chatelain, Paquet), arXiv:2203.12273, https://arxiv.org/abs/2203.12273 | Segmentation-free, page-level attention network. | [S] |
| **Faster DAN** (Coquenet et al., ICDAR 2023), arXiv:2301.10593, https://arxiv.org/abs/2301.10593 | Predicts the first character of each line, then decodes lines in parallel. At least 4× faster than DAN, competitive on RIMES 2009, READ 2016, MAURDOR. | [V] (search abstract) |
| **DANIEL** (IJDAR 2024), https://arxiv.org/pdf/2407.09103 | Fast DAN variant that adds information extraction. | [S] |
| **HTR-VT** (Li et al., Pattern Recognition 2024), arXiv:2409.08573, https://arxiv.org/abs/2409.08573 | Data-efficient ViT encoder-only model with CNN features, SAM optimiser and span masking. Competitive on IAM/READ2016; SOTA on LAM. CTC-based, so it gives per-frame posteriors that suit lattices. Code: https://github.com/Intellindust-AI-Lab/HTR-VT | [V] |
| **HTR-ConvText** (2025), arXiv:2512.05021 | Recent CTC-style follow-up. | [S] |
| **PyLaia + LM decoding** (Tarride, …, Kermorvant, 2024), arXiv:2404.18722, https://arxiv.org/abs/2404.18722 | Adds n-gram LM decoding, which gives about 13% relative WER and 12% relative CER reduction averaged over 12 datasets. Also covers "reliable confidence scores" and calibration. 12 pretrained models on HF. **Most practical optical backbone for this project.** | [V] |
| **Kraken / eScriptorium** | Open-source OCR/HTR engine and platform, strong on historical and non-Latin scripts (https://github.com/mittagessen/kraken). | [S]/[K] |
| **HTR engine comparison** (Int. J. Digital Humanities 2025), https://link.springer.com/article/10.1007/s42803-025-00100-0 | Compares PyLaia, HTR+, IDA, TrOCR-f and Transkribus "Titan". Titan and TrOCR-f are best out of the box on Latin script. | [S] |
| **TrOCR on 16th c. Latin** (Meoded 2025), arXiv:2508.11499, https://arxiv.org/abs/2508.11499 | Gwalther manuscripts. CER 1.86 for a single model, 1.60 with an ensemble; tailored augmentations. | [V] |
| **Generalization of HTR** (Garrido-Munoz & Calvo-Zaragoza, CVPR 2025), arXiv:2411.17332, https://arxiv.org/abs/2411.17332 | 336 OOD cases, 8 models, 7 datasets. **Textual divergence matters more than visual divergence** for generalisation. OOD error is predictable within 10 pp in about 70% of cases. | [V] |
| **Few-line fine-tuning** (Kohút & Hradiš, ICDAR 2025 submission), arXiv:2503.19546, https://arxiv.org/abs/2503.19546 | 16 lines give about 10% relative CER gain; 256 lines give about 40%. **Confidence-based line selection halves annotation cost.** | [V] |
| **AT-ST self-training** (Kišš et al.), arXiv:2104.13037 | Self-training adaptation for OCR domains with few transcriptions. | [S] |
| **Calibration of HTR models** (Ayllon, Castellanos, Calvo-Zaragoza, ICDAR 2024), https://link.springer.com/chapter/10.1007/978-3-031-70536-6_9 | Studies calibration of SOTA HTR models. Snippet: calibration is "crucial" but "overly underexplored". | [S] (abstract paywalled/redirected) |
| **Context-aware confidence for rejection in Chinese HTR** (ICDAR 2024), https://link.springer.com/chapter/10.1007/978-3-031-70533-5_9 | Selective prediction/rejection for HTR, in the Chinese-script setting. | [S] |
| **Probabilistic indexing / lexicon-based KWS** (Vidal/Toselli line of work), arXiv:2104.04556 | "PrIx" probabilistic indexes: an existing *search-without-transcription* approach for archives. Prior art for idea B's set-valued indexing. | [S] |

### 1.2 Datasets and competitions

| Dataset | Notes | Status |
|---|---|---|
| **IAM** | Modern English. Sanity check only; contamination risk for VLMs. | [K] |
| **Bentham (ICFHR 2014 HTRtS)**, https://ieeexplore.ieee.org/document/6981116/ ; TC-11: https://tc11.cvc.uab.es/datasets/HTR%20Competition%202014_1 | Jeremy Bentham and secretaries, 18th–19th c. English. Several hands, variable image quality. Line-level, PAGE XML. **High contamination risk:** Transcribe Bentham transcripts are public on the web. | [V] (search) |
| **READ 2016 (ICFHR 2016)** | Ratsprotokolle, Early Modern German. Page/paragraph/line segmentation. | [V] (search) |
| **Washington (George Washington letters), Saint Gall (9th c. Latin)** | Small classic benchmarks (Fischer et al.). Saint Gall is Carolingian minuscule, *not cursive*. | [K], not re-verified |
| **LAM** (Italian, 19,830 training lines), arXiv:2208.07682 | Largest line-level single-collection benchmark. | [S] |
| **CATMuS Medieval** (ICDAR 2024), https://huggingface.co/datasets/CATMuS/medieval | Over 200 manuscripts, 10 languages, 8th–16th c., over 160k lines. **Graphematic transcription with abbreviations unresolved**, which makes it ideal for measuring whether an LLM silently expands or normalises. | [V] (search) |
| **METATR** (Boillet, Tarride, Kermorvant, May 2026), arXiv:2605.26712, https://arxiv.org/abs/2605.26712 | Evolving ATR benchmark across 29 languages, many scripts and layouts. Standardised VLM prompting and normalisation. Proprietary models are more consistent, but variance across scripts is large. **Use its protocol for comparability.** | [V] |
| **ICDAR 2025 FEST** (few-shot line segmentation), arXiv:2509.12965 | Only 3 annotated pages per manuscript. Relevant for "zero-hardware" low-annotation settings. | [V] (search) |
| **ICDAR 2024 Competition on Recognition and VQA on Handwritten Documents**, https://link.springer.com/chapter/10.1007/978-3-031-70552-6_26 | — | [S] |

### 1.3 VLM/LLM-based HTR on historical material

| Work | Findings | Status |
|---|---|---|
| **Humphries et al., "Unlocking the Archives"** (Nov 2024), arXiv:2411.03340, https://arxiv.org/abs/2411.03340 | 18th/19th c. English. LLM direct transcription 5.7–7% CER; **1.8% CER / 3.5% WER after LLM correction**. About 50× faster and about 1/50 the cost of proprietary HTR. Tool: Transcription Pearl. | [V] |
| **Crosilla, Klic, Colavizza, "Benchmarking LLMs for HTR"** (2025, J. of Documentation), arXiv:2503.15195, https://arxiv.org/abs/2503.15195 | EN/FR/DE/IT, modern and historical. Claude 3.5 Sonnet best. English bias. No consistent win over Transkribus. **"LLMs demonstrate limited ability to autonomously correct errors in zero-shot transcriptions."** | [V] |
| **Li, "Handwriting Recognition in Historical Documents with Multimodal LLM"** (Oct 2024), arXiv:2410.24034 | Gemini versus transformer HTR. | [S] |
| **Greif, Griesshaber, Greif, "Multimodal LLMs for OCR, OCR Post-Correction, and NER in Historical Documents"** (Apr 2025), arXiv:2504.00414, https://arxiv.org/abs/2504.00414 | German city directories 1754–1870, *printed*. Multimodal post-correction (image + OCR text) reaches <1% CER. Image input "reduces the task to finding mismatches". | [V] |
| **Humphries, "Gemini 3 Solves Handwriting Recognition and it's a Bitter Lesson"** (blog, 25 Nov 2025), https://generativehistory.substack.com/p/gemini-3-solves-handwriting-recognition | 50 English 18th–19th c. documents. Strict CER 1.67% / WER 4.42%; 0.69% / 1.33% ignoring punctuation and capitalisation. **"Statistical corrections" (standardising spelling/capitalisation) make up about 61% of errors; names and numbers about 6%.** Hallucinations called "vanishingly low" for English. *Not peer reviewed.* | [V] |
| **Isom, HTR-LLM workflow for abbreviated Latin court hand** (Jul 2025), arXiv:2507.04132 | Four stages: HTR → multimodal LLM correction → abbreviation expansion → NE correction. WER 2–7%. No explicit hallucination analysis in the abstract. | [V] |
| **OmniHandwritingOCR** (CIKM 2026), arXiv:2608.18586, https://arxiv.org/abs/2608.18586 | 77.57k images, 13 MLLMs. Explicitly finds **"plausible but visually unsupported corrections"**: models "correct" handwriting rather than transcribe it. Modern, not historical. | [V] |
| **Transkribus "Text Titan I"** | Reportedly about 35% full-page CER for Gemini 2.5 Flash on a 2,000-page held-out set (June 2025). | Secondhand via search snippet only; **unverified** |
| **Aggregator leaderboards** (e.g. CodeSOTA IAM CERs for GPT-5 / Claude Opus 4.7 / Gemini 3) | — | **Unverified, do not cite as evidence** |
| **VLM fine-tuning of Qwen2.5-VL-7B for early modern Spanish** (GSoC 2026 repo), https://github.com/junghare-aniket/vlm-handwriting-recognition-es | Evidence that open-weight VLM LoRA fine-tuning is feasible on a student budget. Not a paper. | [S] |

### 1.4 LLM post-correction, over-correction and hallucination

| Work | Findings | Status |
|---|---|---|
| **Kanerva et al., "OCR Error Post-Correction with LLMs in Historical Documents: No Free Lunches"** (2025), arXiv:2502.01205 | Open-weight LLMs help English CER but are impractical for Finnish. | [V] |
| **Levchenko, "Evaluating LLMs for Historical Document OCR: A Methodological Framework for DH"** (Oct 2025), arXiv:2510.06743, https://arxiv.org/abs/2510.06743 | Proposes **Historical Character Preservation Rate (HCPR)** and **Archaic Insertion Rate (AIR)**. Identifies **"over-historicization"** (inserting archaic characters from the wrong period). **"Post-OCR correction degrades rather than improves performance."** Printed 18th c. Russian. | [V] |
| **ICDAR 2026 HIPE-OCRepair** (Ehrmann et al., Jul 2026), arXiv:2607.08143, https://arxiv.org/abs/2607.08143 | LLM post-correction of historical *printed* OCR (EN/FR/DE, 17th–20th c.), **without images**. **"Over-correction on low-noise inputs emerges as a recurring challenge, highlighting the importance of evaluation beyond character error reduction."** Retrieval-oriented scoring. | [V] |
| **"When VLMs 'Fix' Students"** (Seong et al., 2026), arXiv:2604.22774 | **PINK** metric: LLM-rubric score that penalises over-correction in handwritten math OCR. GPT-4o penalised; Gemini 2.5 Flash more faithful. | [V] |
| **"Seeing is Believing? Mitigating OCR Hallucinations in MLLMs"** (He et al., NeurIPS 2025), arXiv:2506.20168 | **KIE-HVQA** benchmark (degraded IDs, invoices, prescriptions). GRPO with a refusal-aware reward. 22% absolute gain in hallucination-free accuracy over GPT-4o (Qwen2.5-VL-7B). | [V] |
| **Consensus Entropy** (Zhang et al., 2025/2026), arXiv:2504.11101 | Multi-VLM agreement as a training-free reliability score ("correct predictions converge, errors diverge"). F1 +42.1% over VLM-as-judge. Also: SOTA VLMs "struggle with detecting sample-level errors". | [V] |
| **SHROOM-Visions 2026** shared task on *character-level* VLM hallucination detection (EN/FR/IT/ZH), via Schwartz, arXiv:2609.10244 | Strong sign that the community now treats span-level VLM hallucination detection as a task. Worth checking whether its data covers handwriting. | [V] (secondhand description) |
| **PP-OCRv6** (2026), arXiv:2606.13108 | States that CTC decoding is grounded in frame-level visual features, whereas VLM language priors "can override visual evidence". Motivates CTC as a *verifier*. | [S] |
| **Post-OCR correction with LLM + constrained decoding** (Berrutti Archive, Uruguay; Research Square preprint rs-6823036), https://www.researchsquare.com/article/rs-6823036/v1 | Decoding-time character-similarity constraint between OCR input and LLM output. Printed/typed archival documents. **Closest prior art to idea A**, but not lattice-based, not handwriting, no visual verification. Authors not confirmed. | [S] |
| **ASR analogues** | N-best T5: arXiv:2303.00456, N-best/lattice-constrained generative correction, up to 15.5% relative gain with lattice constraints. NeKo: arXiv:2411.05945. The *ASR community has done constrained generative correction; HTR largely has not.* | [S] |
| **Pre-Editorial Normalization** (Clérice, Bawden et al., LT4HALA@LREC 2026), arXiv:2602.13905 | Keeps a graphemic layer and a normalised layer separate. Supports the "dual output" design. | [S] |
| **Handling heavily abbreviated manuscripts** (Camps et al., ICDAR 2021), arXiv:2107.03450 | — | [S] |
| **Postcorrection of weak transcriptions by LLMs in iterative HTR** (Springer, 2025), https://link.springer.com/article/10.3103/S0005105525701511 | Discusses hallucination risk. Recommends safe integration into an iterative annotation loop. | [S] |

### 1.5 Uncertainty, conformal prediction, selective prediction

| Work | Findings | Status |
|---|---|---|
| **Mohri & Hashimoto, "Language Models with Conformal Factuality Guarantees"** (ICML 2024), https://proceedings.mlr.press/v235/mohri24a.html | Back-off to less specific output gives high-probability correctness. The template for "abstain instead of guess". | [V] (search abstract) |
| **Conformal Risk Control** (Angelopoulos et al.), arXiv:2208.02814 | — | [S] |
| **Learn then Test** (Angelopoulos et al., arXiv:2110.01052) | Needed for non-monotone risks such as error rate among accepted words. | [K], verify |
| **Conformal prediction for wav2vec 2.0 ASR** (Ernez et al., COPA 2023, PMLR v204), https://proceedings.mlr.press/v204/ernez23a.html | CRC to control WER; ICP to flag uncertain words. **Closest methodological analogue to idea B, in speech.** | [S] |
| **"Confident and Adaptive Generative Speech Recognition via Risk Control"** (OpenReview), https://openreview.net/forum?id=ck5T7QeiDh | LTT controls WER degradation from LLM correction by choosing the number of hypotheses. Page blocked by bot check, so details come from snippets only. | [S] |
| **Conformal prediction for KIE** (IJDAR 2026), https://link.springer.com/article/10.1007/s10032-026-00572-y | Split CP on receipts: 98.3% coverage at α=0.02, 70% singletons. Printed documents. | [S] |
| **Uncertainty-aware scientific table extraction** (arXiv:2507.02009) | Conformal routing to manual review. | [S] |
| **Conformal prediction for NLP survey** (TACL), https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00715/125278 | — | [S] |
| **Confidence measures for interactive transcription** (older PRHLT work), https://www.researchgate.net/publication/221355940 | WER ≤10% by checking only 32% of low-confidence words. Old baseline for selective transcription. | [S] |

**What I could not find (absence ≠ non-existence):**
- A paper applying *conformal/risk-control guarantees* to HTR transcription.
- A paper doing *lattice-constrained LLM/VLM correction of CTC handwriting output* with explicit hallucination measurement.
- A *historical cursive* benchmark with an explicit fabrication/illegibility probe.

A proper systematic search (Scopus/DBLP, ICDAR/ICFHR 2024–2026 proceedings, and the SHROOM-Visions 2026 task paper) is needed before claiming novelty.

---

## 2. Gap mining

| # | Gap / limitation (with source) | Opening |
|---|---|---|
| G1 | **Evaluation stops at CER/WER.** HIPE-OCRepair 2026: over-correction is recurring and needs "evaluation beyond character error reduction". Levchenko 2025 had to invent AIR/HCPR. PINK was invented for math. None of these cover cursive archival HTR. | Hallucination-specific metrics and probe sets for historical HTR (idea C). |
| G2 | **Post-correction is unconstrained and can make things worse.** Crosilla et al.: limited autonomous correction. Kanerva et al.: no free lunch. Levchenko: post-correction *degrades* performance. HIPE: over-correction on clean inputs. | Constrain the LLM to optically supported readings (idea A). |
| G3 | **VLMs normalise.** Humphries 2025: about 61% of Gemini 3 errors are "statistical corrections". OmniHandwritingOCR: "plausible but visually unsupported corrections". | A modernisation-rate metric, and methods that keep a diplomatic layer separate (A, C). |
| G4 | **Models cannot detect their own sample-level errors.** Consensus Entropy: VLMs struggle with it. Crosilla: weak self-correction. | Use an *architecturally different, visually grounded* model (CTC) as verifier, instead of more VLMs (A, B). |
| G5 | **HTR calibration is "overly underexplored"** (Ayllon et al. 2024). Kohút & Hradiš show confidence is already useful for active learning. | Calibrated plus conformal word-level confidence with guarantees (B). |
| G6 | **Conformal guarantees exist for ASR WER, KIE and LM factuality, but not (as far as I found) for HTR.** | Port and extend them, including grouped/page-level exchangeability and writer shift (B). |
| G7 | **Text domain shift dominates generalisation** (Garrido-Munoz & Calvo-Zaragoza). LLMs are modern-text biased. Over-historicisation comes from the wrong period prior (Levchenko). | Period-specific LMs used *inside* a constrained space, plus measuring prior mismatch (A). |
| G8 | **Searchability needs recall, not a single best string.** Probabilistic indexing exists but without distribution-free coverage guarantees. | Conformal prediction sets used as index terms, giving guaranteed keyword recall (B). |
| G9 | **English bias.** Crosilla: English preference. METATR: large variance across scripts. Kanerva: Finnish fails. | Evaluate on at least one non-English collection (READ2016 German or CATMuS). |
| G10 | **Contamination.** Bentham/IAM transcripts are public, so VLM zero-shot numbers may be inflated. METATR and Levchenko discuss contamination protocols. | Include a held-out, recently digitised, never-transcribed-online test set. |

---

## 3. Candidate ideas (6)

### Idea 1: Visually-Grounded Constrained Correction (VGCC). SHORTLIST (A)
The LLM/VLM corrector can only output strings that are paths in a pruned lattice from the CTC optical model. Out-of-lattice words are allowed only if a CTC forced-alignment visual-support test passes.

### Idea 2: Conformal Selective Transcription and Guaranteed-Recall Indexing (CST). SHORTLIST (B)
A word-level reliability score is built from optical posteriors, lattice entropy, CTC–VLM agreement and visual support. Learn-then-Test / conformal risk control picks the acceptance threshold so that the error among auto-accepted words is ≤ α with probability ≥ 1−δ. Conformal sets are indexed so that search recall is guaranteed.

### Idea 3: Hallucination Trap Probe Suite + Faithfulness Metrics (HTPS). SHORTLIST (C, evaluation backbone)
- Controlled synthetic occlusions/fading over known words (ground truth = illegible).
- Naturally occurring archaic spellings, writer errors, abbreviations, names and numerals.
- Metrics: fabrication rate, modernisation rate, introduced-error rate, visually-unsupported-word rate.

### Idea 4: Conformally-gated writer adaptation (self-training)
Few-shot fine-tuning of the CTC model on a new hand, using only pseudo-labels the conformal procedure accepts, plus active selection of the most uncertain lines for human labels (extends Kohút & Hradiš 2025). *Good stretch goal on top of A+B.* Risk: confirmation bias, and calibration breaks after adaptation (recalibration needed).

### Idea 5: Period-aware dual-layer output (diplomatic + normalised) with abbreviation handling
Keep a graphemic layer constrained by the optical model. Produce a separate, explicitly labelled normalised/expanded layer (cf. Pre-Editorial Normalization 2026, Isom 2025). Hallucination risk is then confined to the normalised layer, where it is visible. *Useful framing, but on its own it is closer to NLP than CV.* Fold into A as a design decision.

### Idea 6: Render-and-compare verification
Synthesise candidate text in the writer's style (handwriting-generation diffusion) and compare it with the image in feature space to verify VLM output.
- **Rejected as main idea.** Style-faithful handwriting synthesis for historical cursive is a research project in itself. Comparison metrics are unreliable, and compute is heavy.
- CTC forced alignment is a much cheaper "re-render in model space" that tests the same thing: does the image support this string? Mention as future work.

---

## 4. Top ideas in detail

### 4.A Visually-Grounded Constrained Correction (VGCC)

**Problem statement.** Pure optical HTR makes character errors on messy hands. LLM/VLM correction fixes many of them but introduces plausible, visually unsupported words (modernised spellings, "corrected" writer errors, invented names). We want most of the LM's benefit while keeping every output word traceable to visual evidence.

**Novelty claim (tied to G2, G3, G4, G7).**
1. Lattice/confusion-network-*constrained* LLM correction has been shown in ASR (N-best T5, lattice constraints) and loosely for printed OCR (character-similarity constraint, Berrutti preprint). I found no work applying it to **historical cursive HTR with CTC lattices and a period-adapted LM**, and none that **measures hallucination separately from CER**.
2. A **visual support ratio (VSR)** test based on CTC forced alignment. It is an explicit, tunable gate for out-of-lattice edits, using an architecturally different model as verifier. This follows from the PP-OCRv6 and Consensus Entropy observations.
3. **Grounded arbitration** for closed API VLMs whose logits cannot be constrained: accept a VLM word only if the optical model gives it enough support.

**Method sketch.**
1. **Optical model.** PyLaia (with its n-gram LM decoding) or HTR-VT, fine-tuned per collection. Output per-line CTC posteriors. Apply temperature scaling on a validation split.
2. **Hypothesis space.**
   - CTC prefix beam search gives an N-best list (N≈50–200), aligned into a word-level confusion network ("sausage"). Alternatively, a character lattice pruned at posterior ≥ ε.
   - Report the **oracle lattice WER** at each pruning level. It is the ceiling on what constrained correction can achieve.
3. **Constrained LLM decoding** (open-weight LLM such as a 3–8B Qwen/Llama-family model, 4-bit, optionally LoRA-adapted on a period corpus):
   - A HF `LogitsProcessor` masks tokens whose character expansion leaves the lattice FSA (trie over paths).
   - Score = λ·log P_LLM(y) + (1−λ)·log P_CTC(y|x); λ tuned on validation.
   - This is shallow fusion restricted to the optical support.
4. **Escape hatch for out-of-lattice words.**
   - The LLM may propose an out-of-lattice word w′ for a segment if the constrained best path has low joint score.
   - Compute VSR(w′) = [log P_CTC(line with w′ | x) − log P_CTC(best constrained line | x)] / |w′|, via forced alignment.
   - Accept only if VSR ≥ τ. Otherwise keep the lattice word and mark it uncertain.
5. **Grounded arbitration for API VLMs.**
   - Get an independent VLM line transcription (image + optional optical hypothesis, Greif-style).
   - Align words and compute VSR for each disagreeing VLM word. Accept it if VSR ≥ τ; else keep the optical/constrained reading and flag.
   - Cheaper and more faithful than asking the VLM to "correct".
6. **Dual layer (Idea 5).** Everything above produces the *diplomatic* layer. Normalisation/abbreviation expansion is a separate, labelled layer and is never written back.

**Baselines and ablations.**
- (i) Optical only.
- (ii) Optical + n-gram LM (PyLaia).
- (iii) Unconstrained text-only LLM correction.
- (iv) Image + text VLM correction (API; Humphries/Greif style).
- (v) VLM zero-shot transcription.
- (vi) N-best reranking only.
- (vii) Lattice-constrained, no escape hatch.
- (viii) Full VGCC.
- Sweep λ, ε and τ.
- Period LM versus generic LM (tests G7 and over-historicisation).

**Datasets.**
- Development: Bentham (English cursive, multiple hands) and READ2016 (German).
- Stress test: CATMuS Medieval subset (abbreviations, graphematic GT).
- Sanity: IAM.
- **Held-out uncontaminated test:** about 30–60 pages from a local or university archive that have never been transcribed online, double-keyed by two annotators. Coordinate with HTR-B on the data pipeline.

**Evaluation.**
- CER/WER, both strict and normalised (METATR normalisation).
- The hallucination metrics from §4.C, especially **Introduced Error Rate** and **Correction Precision**, which are central to "does correction help without inventing".
- Report CER *versus* hallucination rate as a Pareto frontier over λ/τ, not a single point.

**Risks.**
- **Lattice ceiling:** on very messy hands the correct word may simply not be in the lattice. Mitigations: measure the oracle; use the escape hatch; widen ε.
- **Peaky CTC posteriors:** alignment and VSR get noisy. Mitigations: temperature scaling; label-prior alignment (arXiv:2406.02560); length normalisation.
- **Tokenizer/character mismatch** when masking subword tokens against a character FSA. This is an engineering cost; libraries such as `outlines` or `transformers-cfg` help, but plan 3–4 weeks.
- **The "bitter lesson" risk:** a frontier VLM alone may beat the whole grounded pipeline on CER for English. *Mitigation: frame the contribution as reliability (hallucination rate at matched CER, selective risk), not raw CER.* Note also that VGCC can use the VLM as proposer.
- **The optical model can be confidently wrong** too. VSR then rejects correct VLM fixes. This shows up as lower Correction Recall; report it honestly.

**Scope (1–2 people, consumer GPU).**
- PyLaia/HTR-VT fine-tuning fits in 8–12 GB.
- A 4-bit 7B LLM with constrained decoding runs on a 12–16 GB GPU or a free Colab/Kaggle T4, slowly; limit to a few thousand lines.
- API VLM calls only on the test subsets.
- Feasible as the core of a 6–9 month project.

---

### 4.B Conformal Selective Transcription and Guaranteed-Recall Indexing (CST)

**Problem statement.** "Near-zero error" cannot be promised for every word on degraded cursive. Archives still need a trustworthy statement about the automatic output, plus a principled triage of what humans should check. Search needs recall more than a single best string.

**Novelty claim (tied to G5, G6, G8).**
1. First (to my knowledge; verify) **distribution-free risk control of word error among auto-accepted words for HTR**. It uses a *multi-source nonconformity score* that includes the cross-architecture visual-support signal from A.
2. **Grouped (page/writer) exchangeability handling** and an explicit **stress test under writer/collection shift** that quantifies guarantee violations. That is an honest, publishable negative/positive result.
3. **Conformal prediction sets as search-index terms** (set-valued indexing) with guaranteed per-word keyword recall ≥ 1−α. This connects conformal prediction to archival probabilistic indexing (PrIx), which lacks such guarantees.

**Method sketch.**
1. **Per-word features:**
   - CTC word posterior (min/mean character probability).
   - Confusion-network entropy.
   - VSR of the chosen word.
   - Whether the VLM and CTC agree; if cheap, agreement across 2–3 open/API models (Consensus Entropy-style).
   - LLM surprisal under period and modern LMs (a gap between them flags possible modernisation).
   - Word length, and whether the word is a name or numeral.
2. **Reliability model:** logistic regression or a small GBDT gives p̂(correct).
3. **Calibration split** (per collection; a few hundred annotated lines, which is the realistic human cost).
4. **Acceptance threshold t:**
   - **Learn then Test** with a binomial/Hoeffding–Bentkus p-value, so that P[ error-rate among words with p̂ ≥ t > α ] ≤ δ.
   - Or **Conformal Risk Control** for an expected-risk version.
   - Pages are the exchangeable unit (words within a page are dependent), so calibration is grouped by page.
5. **Prediction sets:** for each word position, the smallest set of lattice alternatives whose cumulative calibrated score reaches the conformal quantile. Coverage is P(true word ∈ set) ≥ 1−α. Index every set member (weighted) for search.
6. **Shift handling:**
   - Mondrian (group-conditional) calibration per hand where hand labels exist.
   - Weighted conformal as an exploratory extension.
   - Leave-one-writer-out evaluation to quantify violations.
7. **Human-in-the-loop output:** a PAGE XML / ALTO export with confidence and "flagged" attributes. HTR-B's systems lens can own the UI and throughput.

**Evaluation.**
- **Risk–coverage curves** and **AURC**.
- **Coverage at target risk**: % of words auto-accepted with guaranteed WER ≤ 1% (and ≤ 0.5%).
- **Empirical guarantee validity**: violation frequency over ≥100 random calibration/test splits (should be ≤ δ in-distribution), plus violation frequency under writer and collection shift.
- **Set size versus coverage** for the prediction sets.
- **Search:** keyword recall/precision (or mAP) versus single-best indexing and versus PrIx-style probabilistic indexing, using a query set of names/terms.
- **Human effort proxy:** % words flagged, and estimated correction time. Optional small user study if HTR-B builds the UI.
- Compare the nonconformity sources (optical-only versus +VSR versus +VLM agreement). This is where A strengthens B.

**Honest statement of "near-zero error":** "On collection X, with 300 calibration lines, the system auto-accepts N% of words with WER ≤ 1% guaranteed at 90% confidence (marginal over pages). The remaining (100−N)% are flagged. The guarantee does not hold for a new writer without recalibration: empirical violation rate Y%." A realistic target, **not** a promise: N ≈ 60–85% on Bentham-like material. This depends heavily on base CER.

**Risks.**
- **Exchangeability breaks** across hands and collections. That is the central limitation; turn it into an experiment.
- **Very low α (e.g. 0.5%)** needs large calibration sets for LTT to certify anything (about several thousand words). Coverage may collapse; report the trade-off.
- **Label noise in ground truth** (transcription conventions) shows up as "errors". Use normalised scoring plus a diplomatic check, and possibly a label-error detection pass (cf. arXiv:2601.16713).
- **Guarantees are marginal, not per page/word.** Communicate this carefully to archivists.

**Scope.** Computationally light (runs on CPU once features exist). Maths and experiments fit 2–3 months. The best-value component for a Master's.

---

### 4.C Hallucination Trap Probe Suite + Metrics (HTPS)

**Problem statement.** CER/WER cannot tell "couldn't read it" from "made something up". For archives the second is worse, because plausible fabrications are hard to spot and they poison search and scholarship.

**Novelty claim (G1, G3, G10).**
- The first historical-cursive-HTR probe set focused on fabrication, modernisation and correction faithfulness.
- It adapts ideas from AIR/HCPR (printed Russian), PINK (math), KIE-HVQA (degraded forms) and OmniHandwritingOCR (modern handwriting) to archival cursive.
- It includes *controlled illegibility*, so fabrication can be measured without subjective judgment.

**Probe construction.**
1. **Occlusion probes.** Take GT-aligned words (the CTC forced alignment gives word boxes) and apply realistic damage: ink blot, fading/low contrast, tear/crop, water stain texture. The expected output is an illegibility marker (e.g. `[?]`), or at minimum a flag. *Any confident full word = fabrication.* Include partial-damage levels, where the truth is recoverable with a low-confidence flag.
2. **Orthography-trap lines.** Lines whose GT contains non-modern spellings, abbreviations, writer errors or long-s. Detect them automatically: tokens not in a modern lexicon, or with a known variant→modern mapping (e.g. VARD-style variant lists for Early Modern English; check tooling availability).
3. **Entity/numeral lines.** Proper names, place names, dates and amounts. Hard for LMs to guess, and high-impact for search.
4. **Clean control lines.** Low-noise lines where correction should change nothing. This tests over-correction on clean inputs, the HIPE-OCRepair finding.
5. **Contamination split.** Public-transcript collections versus the held-out never-online pages.

**Metrics (defined here; formalise in the thesis).** Let R = reference, O = optical output (before correction), C = system output. Use word alignments A(R,O), A(R,C).

- **Introduced Error Rate (IER)** = #{words correct in O but wrong in C} / |R|.
- **Fixed Error Rate (FER)** = #{words wrong in O, correct in C} / |R|.
- **Correction Precision (CP)** = FER / (FER + IER).
- **Net Correction Gain** = FER − IER.
  - These isolate the corrector's hallucination contribution from the optical model's errors. CP must be high (e.g. ≥ 0.95) for a corrector to be trustworthy.
- **Visually-Unsupported Word Rate (VUWR)** = #{output words that are wrong AND lie outside the optical top-K lattice for that segment AND have VSR < τ₀} / |C|. *Caveat:* it depends on the optical model; report it with a fixed reference optical model, and validate it against human judgment on a sample.
- **Plausible Hallucination Rate (PHR)** = the VUWR subset where the wrong output word is a valid lexicon word (modern or period). These are the dangerous errors.
- **Modernisation Rate (MR)** = #{errors where C_word = modern_form(R_word)} / #{trap tokens}. It is the inverse direction of Levchenko's AIR; also report AIR-style **archaic insertion** for over-historicisation.
- **Occlusion Fabrication Rate (OFR)** = #{occluded spans where the system outputs a confident word instead of abstaining/flagging} / #{occluded spans}. Report it as a function of occlusion severity, and split into "fabricated = original word" (lucky or contaminated recall) versus "fabricated ≠ original".
- **Entity Error Rate (EER)**: WER restricted to names and numerals.
- **Clean-Line Change Rate (CLCR)**: fraction of clean control lines altered in any way by correction.
- Human validation: annotate about 300 errors into {recognition, plausible hallucination, modernisation, format/punctuation, GT inconsistency}. Report inter-annotator agreement (Cohen's κ) and correlation with the automatic metrics.

**Risks.**
- Synthetic occlusions may look unrealistic, and VLMs may treat them differently from real damage. Mitigation: include a small set of real damaged lines.
- Modern-form mapping is language-specific (easier for English than Early Modern German).
- A VLM may "fabricate" the right word from context, or because the text is memorised. Split by contamination status, and report both.
- **Overlap with HTR-B's evaluation lens:** agree on ownership (HTR-A defines the metrics mathematically; HTR-B builds the harness).

**Scope.** About 6–8 weeks, including annotation. Cheap. Makes the thesis evaluable whichever method wins.

---

## 5. Recommended combined project and timeline (about 8 months, 1–2 people)

**Title (working):** *Grounded and Certified: Visually-Constrained LLM Correction with Conformal Guarantees for Historical Handwriting Transcription.*

| Month | Work |
|---|---|
| 1 | Systematic lit review (verify [S]/[K] items, confirm novelty). Get Bentham, READ2016, CATMuS subset. Collect held-out archive pages. Baseline PyLaia/HTR-VT fine-tunes. |
| 2 | Probe suite (C): occlusion generator, trap-line detection, annotation guidelines. API VLM baselines on test subsets (budget-capped). |
| 3–4 | VGCC (A): N-best/confusion network, constrained decoding, VSR forced alignment, grounded arbitration. Oracle lattice analysis. |
| 5 | Period LM LoRA (optional). Full ablations. Pareto frontiers (CER versus IER/PHR/OFR). |
| 6 | CST (B): features, LTT/CRC, prediction-set indexing, shift experiments. |
| 7 | Human error annotation and validation of the metrics. Integration with HTR-B's pipeline/UI (PAGE XML export). |
| 8 | Writing, and buffer. Stretch: conformally-gated writer adaptation (Idea 4). |

**Minimum viable thesis if things slip:** C (probe + metrics) + B (conformal selective transcription on optical + one VLM) + a simplified A (N-best rerank + VSR arbitration only, no token-level constrained decoding). That is still novel and fully evaluable.

**Budget notes.**
- Consumer GPU (≥12 GB) or free Colab/Kaggle for PyLaia/HTR-VT and a 4-bit 7B LLM.
- API VLMs only on about 2–5k lines total. Use cheap "Flash/mini" tiers for sweeps and one frontier model for the headline comparison. Check current pricing before budgeting; I did not verify prices.
- "Zero-hardware" here should mean standard phone/flatbed images and commodity compute, not special imaging (multispectral etc.).

---

## 6. Biggest risks (cross-cutting)

1. **The frontier-VLM "bitter lesson".** Gemini-3-class models may already hit about 1–2% CER on English cursive, making optical-first pipelines look obsolete on CER alone. **Mitigation:** position the contribution as *faithfulness + certification + searchability*. Use the VLM as proposer, not competitor. Emphasise non-English/abbreviated material, where VLMs are weaker.
2. **Novelty collision.** This is a fast-moving area (SHROOM-Visions 2026, HIPE-OCRepair 2026, OmniHandwritingOCR 2026 all appeared within months). Re-search before committing, and again at month 4.
3. **Guarantee fragility under shift.** Conformal guarantees need exchangeable calibration data. Every new hand or collection needs a small calibration set. Frame that cost explicitly.
4. **Ground-truth convention noise** (diplomatic versus normalised, abbreviations, punctuation) can swamp small effects. Fix a normalisation protocol early (e.g. METATR's).
5. **Engineering cost of token-level constrained decoding.** Keep the simpler N-best/arbitration fallback.
6. **Contamination** inflates VLM baselines on public collections. The held-out set is essential but costs annotation time.

---

## 7. Key references (quick list)

- TrOCR: https://arxiv.org/abs/2109.10282
- DAN: https://arxiv.org/abs/2203.12273
- Faster DAN: https://arxiv.org/abs/2301.10593
- HTR-VT: https://arxiv.org/abs/2409.08573
- PyLaia + LMs: https://arxiv.org/abs/2404.18722
- HTR generalization (CVPR 2025): https://arxiv.org/abs/2411.17332
- Few-line fine-tuning / confidence selection: https://arxiv.org/abs/2503.19546
- HTR calibration (ICDAR 2024): https://link.springer.com/chapter/10.1007/978-3-031-70536-6_9
- CATMuS Medieval: https://huggingface.co/datasets/CATMuS/medieval
- METATR: https://arxiv.org/abs/2605.26712
- Bentham ICFHR 2014: https://ieeexplore.ieee.org/document/6981116/
- Unlocking the Archives: https://arxiv.org/abs/2411.03340
- Benchmarking LLMs for HTR: https://arxiv.org/abs/2503.15195
- Multimodal LLMs for OCR/post-correction/NER: https://arxiv.org/abs/2504.00414
- Gemini 3 HTR blog (non-peer-reviewed): https://generativehistory.substack.com/p/gemini-3-solves-handwriting-recognition
- HTR-LLM Latin court hand: https://arxiv.org/abs/2507.04132
- OmniHandwritingOCR: https://arxiv.org/abs/2608.18586
- No Free Lunches: https://arxiv.org/abs/2502.01205
- Levchenko AIR/HCPR: https://arxiv.org/abs/2510.06743
- HIPE-OCRepair 2026: https://arxiv.org/abs/2607.08143
- PINK over-correction: https://arxiv.org/abs/2604.22774
- KIE-HVQA: https://arxiv.org/abs/2506.20168
- Consensus Entropy: https://arxiv.org/abs/2504.11101
- SHROOM-Visions 2026 system paper: https://arxiv.org/abs/2609.10244
- Constrained-decoding post-OCR (preprint): https://www.researchsquare.com/article/rs-6823036/v1
- N-best T5: https://arxiv.org/abs/2303.00456
- Pre-Editorial Normalization: https://arxiv.org/abs/2602.13905
- Conformal factuality: https://proceedings.mlr.press/v235/mohri24a.html
- Conformal Risk Control: https://arxiv.org/abs/2208.02814
- Conformal ASR (wav2vec 2.0): https://proceedings.mlr.press/v204/ernez23a.html
- Conformal KIE (IJDAR 2026): https://link.springer.com/article/10.1007/s10032-026-00572-y
- Probabilistic KWS indexing: https://arxiv.org/abs/2104.04556
- CTC alignment with label priors: https://arxiv.org/abs/2406.02560
