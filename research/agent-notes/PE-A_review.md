# PE-A Review of PE-B's Draft + Merged Counterproposal

Agent PE-A, 2026-09-16. I read all of PE-B_draft.md. Verification legend as before: **[V-read]** = I read the primary source myself; **[V-meta]** = listing/abstract confirmed; **[U]** = unverified.

---

## Part 1: Adversarial critique of PE-B

Overall: PE-B's draft is strong, grounded and appropriately modest. We converged independently on the same core gap: no PE model has seen real clay, so transliteration-supervised grounding is the way in. The critique below is about **where the plan would break in practice**, not the direction.

### 1.1 Technical flaws

**T1. The layout model assumes structure PE tablets don't have (most serious).**
- PE-B §6 step 1 proposes to "detect ruling lines and cases (Hough / projection profiles; PE accounts have strong row structure)". Step 4 then runs "Viterbi/DTW alignment *within each row/case*".
- That is the proto-cuneiform layout, not the PE one. Englund (2004, p. 104) **[V-read]**: PE entries "were inscribed in lines from top to bottom kept in columns defined, if at all, by the shank of the stylus", and "the notation of a particular entry often began in a column at the bottom of a tablet, and continued at the top of the adjoining column." There are no ruled cases, and entries wrap across columns.
- The obverse/reverse also differ: the scribe rotated the tablet and wrote totals along the upper edge of the reverse (secondary sources on PE format **[V-meta]**).

**T2. ATF lines are not physical lines.**
- Born et al. 2025 (arXiv:2502.00090, §2) **[V-read]**: each PE text in CDLI "contains an optional header, followed by a series of 'entries' written one per line of the transliterated file".
- So an ATF line is a *logical entry*, not a physical row. Any row-by-row DTW between ATF lines and image rows is mis-specified. Alignment has to be over the reading-order sequence of the whole face, with column wraps.
- **Fix, which is also the key technical idea of the merged thesis:** use **numeral notations as anchors**. Every entry ends in a numeral, and numerals look very different (impressed with a round stylus, not incised; Englund 2004 Fig. 5.4). Detect numerals first, and the face breaks into short ideogram segments, each matched to one ATF entry. Alignment then becomes many tiny problems instead of one hard layout-parsing problem.

**T3. Orientation and mirroring are not addressed.**
- Englund (2004, p. 104) **[V-read]** notes that the Meriggi sign list followed the "original orientation" rather than the conventional one, and printed signs as mirror images.
- Dahl's archetypes use the conventional orientation. Photos, hand copies and sign lists may not agree. Template matching must be tested under 90° rotation and mirroring, and the month-1 audit must establish the orientation of CDLI images.

**T4. Hand copies and archetypes are interpretations too (applies to my own draft as well).**
- Englund (2004, p. 103) **[V-read]**: PE publication proceeded "with little attention paid to an accurate representation in hand copies".
- My draft proposed "line art first". That is fine for bootstrapping a detector, but **line art must not be used as evidence for allograph or transliteration auditing.** PE-B's stratification by image type is the right instinct; it should say this explicitly.

**T5. Template-based alignment makes the auditor (Idea C) circular.**
- PE-Ground scores proposals by similarity to the archetype of the *expected* sign. High-confidence alignments, which are what Idea C trains and audits on, are therefore biased toward tokens that already resemble the archetype.
- Real allographs and real mislabels get low confidence and are filtered out, so the auditor systematically **under-detects exactly what it is looking for**.
- **Mitigation:**
  - The audit set should come from (a) human gold boxes, or (b) alignments that use *sequence position only* (no visual template term) inside numeral-anchored segments.
  - Report how many low-confidence tokens were excluded, per sign.

**T6. Token counts and statistical power are overstated for Idea C.**
- PE-B writes "~35k non-trivial tokens". Kelley et al. 2022 (Iranica Antiqua) **[V-read]** give ~26k tokens: ~12k numerical and **~14k non-numerical**. P6's 35k figure includes numerals and other material.
- With ~14k ideographic tokens spread over ~1,500 types, the "n ≥ 15 per sign" rule for MMD tests will leave perhaps a few hundred types. **Pairs of "~" variants where both sides reach n ≥ 15 may number only a few dozen.** This is my estimate, not measured; it must be counted in month 1.

**T7. Zero-shot SAM2 for proposals is untested on shallow incised clay.**
- EpigraphNet (Achaemenid Elamite cuneiform) uses SAM2, but on a different script and surface.
- Budget a fallback: a class-agnostic detector trained on the gold set.

### 1.2 Overclaimed or under-qualified novelty

**N1. The arithmetic auditor (Idea B) is less novel than claimed.**
- Born et al. 2025 already exploit summary lines with a subset-sum method over transliterations to disambiguate number systems **[V-read]**.
- Text-only arithmetic checking therefore already exists. The image adds: (i) reading numerals independently of the transliteration, and (ii) *diagnosing* which failures are transliteration errors.
- That is still new and useful, but the claim should be "first image-grounded numeral reading and collation aid", not "first arithmetic verification".

**N2. "The sign inventory is unstable" overreads Pandey 2023.**
- I checked L2/23-196 **[V-read, pp. 1–5]**. PE-B's numbers are correct: EPS 1,636, EPS-GH 1,332, PDF 1,434, JSON 1,796, Corpus 1,741; 6,607 raw names, 2,011 distinct.
- But Pandey also writes that "the working sign list maintained by CDLI is stable". The source differences largely reflect **different snapshot dates** (PDF 2006, corpus 2011) and **coverage of numeric signs** (EPS has numerics; PDF lacks them).
- The defensible claim: *variant status (~a/~b) and some merges are unresolved*. Not "the sign list is unsettled".

**N3. Joins.** PE-B says some of Dahl's joins are "based only on scribal design". Dahl (CDLN 2012:6) **[V-meta]** lists 14 joins (10 new, 4 old), and the summary I retrieved mentions **one** join explicitly based on scribal design. Minor, but it matters because the join-ranker backup rests on a positive set of about 14.

**N4. "RTI … free public access on CDLI".** This is a 2012 press claim. Neither of us confirmed that the RTI *files* (as opposed to rendered stills) can be downloaded today. PE-B rightly makes it a month-1 check; it should not appear in the novelty or relighting-augmentation argument until confirmed.

**N5. "CDLI text CC-BY 4.0".** The CDLI terms I read say text "may be freely copied, aggregated and re-used according to common and fair academic practice" with attribution. I did not see an explicit CC-BY 4.0 statement **[U]**; confirm before writing it into a licence section. `cdli-gh/proto-elamite_data` is CC-BY 4.0 **[V-meta]**, which is good.

### 1.3 Evaluation weaknesses and circularity

**E1. Idea C's known-answer analogues are weak matches.**
- The Neo-Assyrian CompVis set is wedge cuneiform with gold *sign classes*, not gold *allograph* structure.
- Cypro-Greek images are hand-drawn copies.
- Neither matches PE's surface, era or numeral-heavy administrative genre.
- **Proto-cuneiform**, missing from PE-B, is the natural proxy: contemporary, administrative, on CDLI with photos and transliterations, and its **numeral sign forms are the same as PE's** (Englund 2004 p. 106–107 **[V-read]**).

**E2. The arithmetic check-rate upper bound is uninformative.**
- "Transliteration-based arithmetic success as upper bound" is fine, but the interesting quantity is the **disagreement set**.
- Pre-register the three-way flag taxonomy and report a confusion table against expert collation. Otherwise a low hit rate is ambiguous: good transliterations, or a poor reader?
- Also, transliterators often worked *from these same photos/RTI*, so image-vs-transliteration disagreement will be rare and concentrated in damaged areas, which is exactly where the image reader is weakest. The expected precision@k should be discussed up front.

**E3. Semantic induction (I6).**
- PE-B correctly flags circularity. I confirm it from Englund Fig. 5.4 **[V-read]**: the system glosses are themselves semantic ("S: discrete inanimate objects…", "D: domesticated animals and human labourers", "B: grain products", "C: capacity of grain").
- Predicting commodity class from number system partly re-derives the premises. This applies equally to my Top-2 idea. Keep it a labelled hypothesis generator at most.

**E4. The gold-set cost may be underestimated.**
- 3–5k boxes in 60–80 h is about 1 min/box. That is optimistic for a non-specialist who must also map each box to the correct ATF token across column wraps, rotated reverses and damage.
- Budget 100+ h, or shrink to about 30 fully annotated tablets plus numeral-only annotation on more.
- The inter-annotator κ check is good. Keep it.

### 1.4 Feasibility problems

- **F1. Data access is the gate for both drafts.** Neither of us has counted how many PE tablets have usable photos (vs. line art only) or at what resolution. Checked example: P008805 has photo + line art, photo © National Museum Tehran **[V-read]**.
- **F2. Expert time (5–10 h) is realistic *if* an expert is secured.** PE-B budgets it well. But nothing in either plan works without a named expert in month 1. This belongs in prerequisites, not risks.
- **F3. Data freshness.** `cdli-gh/data` says "Last update was August 2022" **[V-meta]**, which confirms PE-B. The API path needs testing in week 1.
- **F4. Too many deliverables.** PE-Ground plus B *or* C in 8 months is plausible. PE-Ground plus a viewer plus B plus C plus I6 is not. The merged plan fixes this with gates.
- **F5. Heavy dependencies.** ProtoSnap relies on diffusion features and PE-B already flags the free-tier GPU problem. Use DINOv2-S as the default and ProtoSnap only as an optional comparison.

### 1.5 Citation spot-checks (not previously verified by me)

| Citation | Check | Threat to novelty? |
|---|---|---|
| **EpigraphNet**, arXiv:2608.18544 | **[V-meta]** Real. "Zero-Shot SAM2 Segmentation and Vision Transformer-Based Recognition of Elamite Cuneiform Symbols from Degraded Tablet Images", Poudel, Bhattarai, Pathak, Ramacharna, Jaswal, submitted 19 Aug 2026. Persepolis Fortification Archive (Achaemenid Elamite *cuneiform*). **No Proto-Elamite.** 1,239 annotated images; abstract mentions both 141 categories and a 132-class benchmark (PE-B cites only 141); 86.41% top-1 vs ResNet-101 69.20%. Preprint. | **No.** Different script (by ~2,500 years), different writing technique, classification of pre-segmented crops. Worth one line as a SAM2 precedent. Note that "Elamite" in titles will confuse reviewers, so state the distinction explicitly. |
| **eBL sign detection**, arXiv:2606.22608 | **[V-meta]** Real. Che, Garcés Arias, Niaz, Bender, Jiménez, 21 Jun 2026; Deformable DETR, 87,668 fragments, ~2.9M detections, 173/106 classes; CC-BY; under review. | **No** for PE (Babylonian cuneiform). But it **raises the baseline bar**: reviewers will expect a DETR-family baseline and comparable tablet-side extraction. Its tablet-side extraction step is reusable. |
| **Pandey 2023, Unicode L2/23-196** | **[V-read]** pp. 1–5; numbers match PE-B. | No threat. Useful as motivation, with the N2 caveat. Its §3 expert questions are a nice evaluation hook. |
| **Dahl 2012, CDLN 2012:6** | **[V-meta]** 14 joins (10 new + 4 old); one explicitly by scribal design. | N/A (backup idea only). |
| **cdli-gh/proto-elamite_data** | **[V-meta]** CC-BY 4.0; EPS sign images. | N/A, but a good licensing find. |
| DeepScribe venue "ACM JOCCH 18(2) 2025" | Not checked; I only verified the arXiv version. **[U]** | No (Achaemenid Elamite). |

---

## Part 2: What PE-B got right that I missed

1. **The numeral image reader plus an arithmetic check as an objective, label-free test.** This is the best evaluation idea in either draft. I used numerals only as distant supervision for semantics, which is weaker and partly circular (E3).
2. **Explicit circularity rules:** tablet-level splits, joined fragments kept in the same split, gold set kept out of EM pseudo-labelling, and "supported" vs. "correct" reporting.
3. **Licensing specifics.** Dahl's archetypes as CC-BY (`cdli-gh/proto-elamite_data`) vs. my LGPL toolkit copy. Also the CDLI bulk dump being frozen since August 2022, and version pinning against the 2018 SFU copy.
4. **Pandey's Unicode proposal** as independent, quantitative evidence of sign-list variation (with caveat N2), plus expert questions to target.
5. **A concrete expert-time budget,** blind forms, and an Ithaca-style human-plus-AI protocol.
6. **The expert-needs framing** (concordance, collation, variants, numerals, joins). It makes the thesis useful even if the "discovery" results are thin.
7. **The Software Engineering deliverable:** concordance viewer plus reproducible JSON dataset. That matters for an ASE module.
8. **Adjacent resources:** the Hatamti Linear Elamite database (45 inscriptions, 69 signs, no licence stated), Stötzner et al. 2023 relighting augmentation, CuneiML's CDLI image handling, and the Sommerschield et al. 2023 survey.

What I contribute that PE-B lacks:
- proto-cuneiform as the matched proxy and as a transfer source for numeral forms;
- synthetic structure injection for calibrated false-discovery rates;
- nonparametric estimation of inventory size;
- the Desset (2022) vs. Dahl (2023) cross-script framing, kept out of scope.

---

## Part 3: Counterproposal, the merged "best single thesis"

### Working title
**"Anchored in Numbers: Transliteration-Aligned Sign Grounding for Proto-Elamite Tablets, with an Image-Based Numeral Audit"**

### 3.1 Core idea in one sentence
Numerals are the best-understood, most frequent and most visually distinct part of PE (impressed, not incised; the same forms as proto-cuneiform). So: **detect numerals first, use them to cut each tablet face into entry-sized segments, align each segment to its ATF entry, and check the numerals against the tablet's own arithmetic.**

### 3.2 Core deliverable (must ship)
1. **PE-Ground v1**, a released dataset of token-level annotations keyed to CDLI P-numbers and image URLs (no museum pixels), containing:
   - (a) human gold boxes on ~30–40 tablets;
   - (b) machine alignments with calibrated confidence for the best-imaged subset;
   - (c) a pinned corpus manifest.
2. **The pipeline:**
   - face extraction;
   - numeral detection and counting;
   - numeral-anchored entry segmentation;
   - within-segment ideogram alignment (DINOv2-S embeddings + Dahl CC-BY archetypes + position constraints + EM);
   - baselines incl. a DETR-family detector.
3. **The numeral audit:** image-read numerals → candidate readings in the S/D/B/C systems → consistency with totals → three-way flags ("image ≠ transliteration", "transliteration fails but image passes", "both fail"), with an expert-rated top-k list.
4. **A concordance/collation viewer** ("show every M288 on clay"; "show flagged entries"), with a tested, CI'd, reproducible codebase. This is the ASE deliverable.

### 3.3 One optional extension (only if gate G2 passes)
**Real-clay variant audit.**
- For head and mid-frequency signs (n ≥ 15 gold or position-only-aligned tokens; see T5), test the "~" variant pairs and the merges proposed by Born et al. 2023 using token-embedding distributions (MMD / mixture overlap). Separate style from sign identity at tablet level.
- Validate through:
  - (i) the same pipeline on **proto-cuneiform** with known sign classes;
  - (ii) synthetic injection (planted merges/relabels) on PE gold tokens;
  - (iii) blind expert rating of the top 10 proposals mixed with 10 decoys.
- Report explicitly where the results agree or disagree with Born et al. 2023.

*Explicitly out of scope:* sound values, Linear Elamite mapping, semantic "meaning" claims, fragment joins (a backup thesis only if image access fails).

### 3.4 Eight-month plan with go/no-go gates

| Month | Work | Outputs | Gate |
|---|---|---|---|
| **M1** | Prerequisites (see 3.7). Data audit via CDLI API: count PE tablets with photo / flatbed / line art / RTI; resolution; orientation conventions (T3); pin ATF version and diff against the 2022 dump and the 2018 SFU copy. Count ideographic tokens per sign and how many "~" pairs have n ≥ 15 (T6). Count tablets with preserved totals. Read Englund 2004, Dahl 2019, Born 2023/2025; read NEA 2025 and Kelley 2026 for scooping risk. | Data audit report; corpus manifest; annotation guideline v0 | **G0 (end M1):** ≥300 tablets with usable photos/scans, AND a named expert committing ≥6 h, AND written CDLI confirmation that annotations may be released. **Fail →** switch to the fallback thesis: line-art + proto-cuneiform methodology paper, or the join ranker. |
| **M2** | Gold annotation part 1: ~20 tablets, full boxes + ATF token IDs; numeral-only boxes on ~40 more. Second annotator on 5 tablets (κ). Face extraction; class-agnostic proposal baselines (SAM2 zero-shot vs. small detector). Numeral detector pretraining: synthetic stylus-impression renders, optionally proto-cuneiform numerals. | Gold v1, IAA numbers, proposal baseline | |
| **M3** | Numeral detection + counting (per-class and count accuracy). Numeral-anchored entry segmentation handling column wraps and reverse rotation (T1/T2). | Numeral reader v1 | **G1:** numeral token recall ≥ ~0.8 and entry-segmentation accuracy ≥ ~0.7 on held-out gold (indicative thresholds, fix them in M1). **Fail →** thesis narrows to "numeral reading + audit on best-imaged subset" (still complete and publishable). |
| **M4** | Numeral audit: reading enumeration (reimplement the Born 2025 algorithm), ILP for totals, three-way flags; planted-error study (corrupt 5% of ATF numerals). **Expert session 1** (~2 h): blind review of top 30 flags + 10 decoys. | Audit results, precision@k | |
| **M5** | Ideogram alignment inside numeral-delimited segments: DINOv2-S + archetype templates (rotation/mirror-tested) + position prior; EM 3 rounds; DETR-family and raw template-matching baselines. Gold annotation part 2: ~15 held-out tablets. | PE-Ground alignments v1 | |
| **M6** | Full evaluation: token alignment accuracy, per-frequency bucket, stratified by image type / museum / damage; ablations (no numeral anchors, no EM, no position prior, no rotation handling). **Expert session 2** (~1 h): 200 random high-confidence alignments rated. Viewer MVP. | Evaluation chapter draft; viewer | **G2:** head-sign token alignment accuracy ≥ ~0.6 AND ≥ ~20 variant pairs with sufficient n. **Pass →** extension. **Fail →** spend M7 on robustness, viewer and data paper. |
| **M7** | *Extension* (variant audit with proxy + injection + expert session 3, ~2 h) **or** robustness/viewer/release hardening. | Extension results or release v1.0 | |
| **M8** | Write-up; release (code MIT/Apache; annotations CC-BY with CDLI attribution; no pixels); workshop paper draft (ML4AL / ALP / ICDAR workshop) or JOHD data paper. | Thesis, release, paper | |

Total expert time: ~5–6 h (+ ~2 h if the extension runs). Total annotation: ~100–120 h.

### 3.5 Evaluation protocol

| Claim | Ground truth available? | Metric | Controls |
|---|---|---|---|
| Signs are localised | Yes (gold boxes) | class-agnostic mAP@0.5; numeral count accuracy | IAA (κ, box IoU) as ceiling; stratify by image type / damage / museum |
| Tokens are aligned to ATF | Yes (gold token IDs) | token alignment accuracy (IoU ≥ 0.5); coverage at ≥90% precision; per-frequency bucket | Ablations (no anchors / no EM / no position prior); DETR and template-matching baselines; tablet-level splits; joins kept together; gold never used in EM |
| Numerals are read correctly | Yes (gold) + internal arithmetic | per-sign accuracy; % of tablets with totals whose image-read entries sum correctly; system-assignment agreement with the Born 2025 test set (if released) | Transliteration arithmetic as reference; planted ATF numeral corruptions (recall/precision of the "transliteration fails, image passes" flag) |
| Flags are useful to scholars | No | blind expert precision@10/30, split into real transliteration issue / scribal error / false alarm | Decoy-mixed, blind forms; pre-registered taxonomy |
| *(ext.)* Variant pairs are visually same or different | No for PE; yes for proxy | proxy: AUROC / V-measure on proto-cuneiform; PE: recovery of planted merges/relabels (FDR) | Position-only-aligned or gold tokens only (T5); n ≥ 15; blind expert rating vs. decoys; report agreement with Born 2023 merges |

Reporting rule: "correct" only where ground truth exists; everything about PE sign identity is "supported / flagged", never "deciphered".

### 3.6 Abstract (honest but compelling)

> Proto-Elamite (c. 3100–2900 BCE), the undeciphered accounting script of early Iran, survives on roughly 1,600 clay tablets. Yet every machine-learning study of it to date has worked from human transliterations or idealised sign-list drawings, never from the clay itself. This thesis builds the first image-grounded link between the Proto-Elamite corpus and its tablets. Our key observation is that numerals, the best-understood and most visually distinctive part of the script, can anchor the problem. We detect and read numeral notations, use them to divide each tablet face into entry-sized segments, and align the undeciphered signs in each segment to their transliterated counterparts using self-supervised visual features, archetype templates and iterative pseudo-labelling. We release token-level annotations keyed to the Cuneiform Digital Library Initiative, a concordance viewer, and an evaluation protocol that separates what can be measured (localisation, alignment, arithmetic consistency against the tablets' own totals) from what can only be supported (expert-rated flags of possible transliteration errors). We do not claim decipherment. We provide the infrastructure any future decipherment or palaeographic argument about Proto-Elamite will need: evidence from the clay, not only from its modern transcription.

### 3.7 Prerequisites the student must secure (before M1 ends)

1. **A named PE domain expert** willing to give ~6–8 h across three blind review sessions and answer convention questions. Candidates by publication record: Kathryn Kelley (Bologna/Uppsala), M. Willis Monroe (UNB), Jacob L. Dahl (Oxford/CDLI), and the SFU group (Logan Born, Anoop Sarkar), who are also the main scooping risk, so contact them first.
2. **Written CDLI confirmation** (and, if CDLI requires it, from the Louvre / National Museum of Iran) covering:
   - (a) bulk download of PE images for non-commercial research;
   - (b) release of derived annotations keyed to P-numbers;
   - (c) whether high-resolution or RTI files can be provided.
3. **Working CDLI API access** and a pinned transliteration snapshot (the GitHub dump has not been updated since August 2022).
4. **An academic supervisor** comfortable with CV and with humanities-data licensing; agreement on a fallback thesis if G0 fails.
5. **Compute:** Colab/Kaggle free tier or an 8–12 GB consumer GPU (DINOv2-S, small detectors). ProtoSnap-style diffusion features are optional.
6. **An annotation tool** (CVAT or Label Studio) plus ~100–120 h of annotation effort (a second annotator for ~5 tablets).
7. **Background reading** on PE conventions: Englund 2004; Dahl 2019 sign list; Born et al. 2023 and 2025; Kelley 2026 Cambridge Element; Monroe et al. 2025 NEA (paywalled, obtain via library).
8. **Access to the Born et al. 2025 numeral test set** (ask the authors) and the P6 code (`MrLogarithm/cawl-clustering`) for baselines.
