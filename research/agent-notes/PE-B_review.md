# PE-B Review of PE-A's Draft and Merged Counterproposal

Reviewer: Agent PE-B (data, evaluation and feasibility lens). Date: 2026-09-16.
Inputs: `PE-A_draft.md` (read in full) and my own `PE-B_draft.md`.

Status key: **[V]** = I read the source myself in this session. **[S]** = seen only in search snippets.

---

## 0. Summary verdict

- **Where we agree.** PE-A and I independently found the same main gap. Every visual model of Proto-Elamite (PE) so far feeds in Dahl's idealised type drawings, never token images from clay (Born et al. 2023 §3 [V]). The top pick should be a weakly supervised token-localisation dataset built by aligning CDLI transliterations to images, in the style of Dencker et al. 2020.
- **PE-A Top 1 (PE-Tokens) is sound, with three weak points:**
  1. **Line art first.** Starting with hand copies undercuts the "real clay" novelty claim.
  2. **Proto-cuneiform "known answers".** They aren't known answers.
  3. **Inventory size.** The sign-inventory-size claim is ill-posed.
- **PE-A Top 2 (numeracy-grounded semantic induction) is mostly already done and leaks labels.**
  - Born et al. 2025 (arXiv:2502.00090, §5 [V]) already read off sign→number-system associations: M346, M362, M367 and M417 predict decimal; M376 predicts sexagesimal; M288 goes with capacity; M388 vs M124 differ in ration size. The paper explicitly calls this "a novel approach to determine the function of signs with unknown meanings".
  - The planned held-out evaluation is circular, because the "known" glosses were themselves partly inferred from numerals and metrology.
- **PE-A Top 3 (cross-script correspondence test) should be dropped.**
  - The visual test is circular: Desset's pairs were chosen *because* they look alike.
  - The distributional test is ill-posed: Linear Elamite (LE) is glottographic (writes language) while PE is administrative.
  - LE has only ~45 inscriptions (Hatamti database [V]).
- **My draft has a flaw of its own.** Idea B (arithmetic auditor) overlaps Born et al. 2025's subset-sum analysis, which disambiguated only **24 texts** via summary lines [V]. So arithmetic ground truth is thin, and the novel part must be the *image* side, not the arithmetic.
- **Merged thesis.**
  - **Core:** image-grounded PE sign tokens, with a collation-flag tool that reports where image and transliteration disagree. Validation uses gold boxes, Born et al. 2025's expert-verified numeral test set, and the history of transliteration corrections across CDLI versions.
  - **Extension:** a pre-registered, token-level allograph audit.

---

## 1. Adversarial critique of PE-A

### 1.1 Technical flaws

| # | Issue in PE-A | Why it matters | Fix |
|---|---|---|---|
| T1 | **"Start with line art (much easier), then photos (stretch, M7)."** | Line art (MDP hand copies back to Scheil 1905–1935, plus Dahl 2019) is a human interpretation, like the archetypes the gap criticises. Many transliterations were made *from* those copies, so image–transliteration agreement on line art is partly guaranteed. Any "transliteration error" found there could just as well be a copy error. A line-art-only MVP gives up the "clay" novelty claim. | Use photos from month 2 on a curated high-quality subset. Keep line art only as an auxiliary domain (bootstrapping proposals, domain-adaptation source), and never use it for collation claims. |
| T2 | **"Box-level ground truth is obtainable by non-experts because the transliteration tells you which sign it is."** | Partly true for clean tablets. On damaged photos it's hard: tokens must be matched to shapes when entries run right-to-left, cross rulings, spill onto the reverse, or include broken signs (`x`, `[...]`). There are also ~1,300–2,000 names, many with near-identical tilde variants. CDLI transliterations may reflect collations that differ from the copy or photo. | Budget annotation realistically (≈1–1.5 h per mid-size tablet at first). Measure inter-annotator agreement. Allow an "unsure / label mismatch" tag, which itself feeds the collation-flag evaluation. |
| T3 | **Nonparametric clustering gives "the first principled estimate of PE sign-inventory size"** (novelty item 3, G6). | The 287 vs 1,623 spread (Born et al. 2023 fn. 2 [V]) comes mainly from *definitions*: whether numerals, complex graphemes and tilde variants count as signs. No clustering hyperparameter resolves a definitional question. HDBSCAN/DP-means counts on a Zipfian corpus with many hapaxes (signs attested once) are also dominated by hyperparameters and the minimum cluster size. | Drop the inventory-size claim. Report only pairwise merge/split evidence for pre-registered sign pairs with enough tokens. |
| T4 | **Utility check: "real merges should reduce held-out perplexity/MDL."** | Merging labels shrinks the vocabulary, so perplexity falls for *any* merge. The test is biased toward merging. | Compare against random merges with matched frequencies, or score in the original label space (e.g. a class-based LM that assigns each merged class's probability back to its member labels). |
| T5 | **Style/sign disentanglement à la Srivatsan et al. 2021** | Their Linear B setup had scribal-hand labels and find-place evaluation [V]. PE has no hand attributions, and almost everything comes from one site (Susa), so find-place can't serve as a check. A tablet-level latent also mixes up the scribe with the content (the tablet's topic decides which signs appear). | Keep it as a *control* (does a proposed allograph split just track tablet ID?), not as a claimed contribution. |
| T6 | Detector choice: class-agnostic YOLO, then the top-K frequent signs | This is fine. But PE entries mix *impressed* numerals (round and cylindrical stylus marks) with *incised* ideograms. One detector head will do badly on the tiny numeral impressions. | Use two proposal heads (numeral impressions / incised signs), or a separate numeral counter. This also serves the numeral collation core in §3. |
| T7 | Top 2 plans to train on P7's disambiguation outputs as soft labels | P7's bootstrap classifier uses OBJECT, SAME_ENTRY and FIRST_SIGN sign features (Table 2 [V]). Predicting number system from sign spans with P7's outputs as targets largely relearns P7's feature weights: **target leakage**. | If the direction is kept at all, use only the 1,899 numerals that are unambiguous from digit shape alone [V] as targets. |

### 1.2 Overclaimed novelty

- **Top 2 is largely pre-empted.** P7 §5 already:
  - lists signs associated with each number system;
  - proposes that "qualifying" signs (M388, M124, M001, M387, …) appear beside several systems;
  - revises a gloss (M376 as a high-status human rather than livestock) on numeral evidence;
  - reports magnitude differences (M288 vs M263 containers; M388 vs M124 team size).

  PE-A cites P7 but frames semantic induction as new. What is left is modest: calibrated per-sign probabilities, adding image embeddings, and a proper null model. That's a chapter, not a thesis, and it isn't computer vision.
- **Top 3's "first quantitative test of PE↔LE correspondences".** Kelley et al. 2022 (P5 [V]) already applied the Desset values across the whole PE corpus and discussed plausibility against the distributions: 18 of Desset's signs are hapaxes, 7 are absent from the corpus, and M2 vs M387 are distributionally distinct. A permutation test would add formality but little evidence (see §1.3).
- **Top 1's "first token-level allograph analysis".** This is fair *if* done on photos. It's weaker if done on line art (T1).

### 1.3 Evaluation weaknesses, circularity and leakage (focus areas)

**(a) Proto-cuneiform as a "known-answer" proxy.** It is not ground truth in either Top 1 or Top 2.

1. **The inventory isn't settled either.** Proto-cuneiform sign names follow ZATU and the Oracc PCSL list, with lowercase sub-variants that editions differentiate differently. One CDLB count finds ~1,990 sign names over ~53k non-numerical tokens [S: CDLB 2021-6 snippet]. V-measure against ZATU labels measures agreement with *another expert convention from the same Berlin/CDLI tradition* (Englund, Damerow), not recovery of truth.
2. **PE's semantics were borrowed from proto-cuneiform.** The meaning of PE number systems (capacity = grain, etc.) was set largely by analogy with proto-cuneiform metrology (Damerow & Englund 1989; Friberg 1978; Englund 2004; P7 §6 [V]). A method that recovers commodity classes in proto-cuneiform only shows it can find an association that is known to exist by construction there. That transfers **no evidence** about PE: this is **cross-script leakage of the prior**.
3. **Proto-cuneiform is easier.** It has commodity-specific metrological systems and ~3× the corpus. Its "known meanings" mostly come from continuity with later Sumerian lexical lists, which PE lacks. Subsampling to PE size fixes the size mismatch, not the difference in how strongly commodity and number system are tied.
4. **Detection transfer is still legitimate.** Using proto-cuneiform (CDLI photos + ATF) to sanity-check the *weak-supervision loop* is fine, because bounding boxes are objective there. Keep proto-cuneiform for detection and alignment only.

**Better known-answer proxies for allograph and inventory recovery:**
- Cypro-Greek, with gold sign identities (Corazza et al. 2022, used in Born et al. 2023 [V]);
- Srivatsan et al.'s Linear B glyph dataset, with sign and hand labels [V];
- planted-structure tests on PE itself (PE-A already proposes this, and it's the strongest item in their plan).

**(b) Top 2 semantic-class held-out ("leave-known-out") evaluation.**

1. **Too little ground truth.** Signs with "broadly accepted" meanings number perhaps 10–20, and PE-A lists several they haven't verified (M346 "sheep", M288 "grain container", M054 "yoke", M388). Even with n = 20 and four categories, a 95% CI on accuracy is roughly ±20 points. Frequency-matched random baselines help but can't fix that sample size.
2. **Label leakage.**
   - Many of these glosses were *derived from* numeral and metrology context. Dahl 2005 argued for livestock signs from animal-husbandry accounts, whose counts are in decimal/sexagesimal notation. The capacity link for M288 is inferred from its capacity numerals.
   - Hiding the sign from "any semantic prior" doesn't remove the leak: the *label itself* was produced by the same kind of feature the model uses. Agreement is therefore expected, not confirmatory.
   - Leakage-free "known" signs would need independent evidence: a pictographic resemblance agreed on *without* numeral arguments, or a proto-cuneiform correspondence established graphically. These are few, and debatable.
3. **Target leakage via P7 outputs** (T7).
4. **The label-permutation null is necessary but weak.** Shuffling numerals within a tablet type preserves header/topic effects that already correlate sign and system. A better null shuffles within tablet *and* keeps the entry position.
5. **Verdict.** Report number-system association of undeciphered signs purely as *descriptive hypotheses* with calibrated uncertainty. Don't report "semantic accuracy".

**(c) Top 3 cross-script test.**

1. **Selection bias.** Desset et al. picked PE↔LE pairs partly by visual similarity (P5: no method stated [V]). Scoring that table on visual similarity against random mappings is **guaranteed to pass**. The only valid null is conditional on the selection process, which is unknown.
2. **Distributional incomparability.** PE is spreadsheet accounting punctuated by numerals; LE inscriptions are largely royal/votive glottographic texts. Positional statistics aren't comparable across these genres.
3. **Tiny LE corpus.** 45 inscriptions per the Hatamti database [V]; PE-A's "~51" is unverified. The image licence for LE is unclear, and Hatamti states none [V].
4. **The positive control is trivial.** PE↔proto-cuneiform numerals are near-identical in shape and value, so recovering them doesn't validate ideogram matching.
5. **Sensitive topic.** Dahl 2023 (Akkadica 144(2), 107–126 [V]) disputes continuity. A thin null result will be read as taking sides.
6. **Recommendation.** Future work only.

**(d) Other evaluation gaps in PE-A.**
- **No plan for the corpus-version problem.** Token counts differ between papers: Kelley et al. 2022 say "26 thousand tokens … approximately 12,000 numerical; 14,000 non-numerical" [V, IA p.6]; Born et al. 2023 say 35k tokens [V]. P7 used a 3 Oct 2022 download [V]. Pin one version and report the differences.
- **Split hygiene.** PE-A doesn't say that joined fragments and duplicate records must stay in one split, or that the gold test set must be excluded from pseudo-labelling rounds. (It says "never used in bootstrapping", which is good, but joins aren't mentioned.)
- **Blinded expert review with decoys is good, but no hours are budgeted.** Expert time is the binding constraint.

### 1.4 Feasibility

- **Timeline is inverted.** Photos arrive in M7, after allograph analysis in M5–6. So the risky, novel modality is tested last. Put a photo go/no-go gate at the end of M3.
- **Three tops is too many for one person.** Top 1 alone (detector + alignment + SSL embeddings + clustering + proxies + expert review) fills 8 months.
- **Compute:** agreed, not a risk.
- **Data audit:** the "scrape the CDLI catalogue to count photos vs line art" action item is correct and must be week 1. The CDLI bulk dump dates from Aug 2022 [V]; image metadata needs the API.

### 1.5 Citation spot-checks (sources I hadn't verified before)

| PE-A claim | Check | Result |
|---|---|---|
| Dahl (2023). *Proto-Elamite and Linear Elamite, a Misunderstood Relationship?* Akkadica 144(2): 107–126. ORA link | Fetched ORA record | **Correct.** The abstract argues LE was a new creation inspired by recovered PE tablets plus Old Akkadian cuneiform [V]. |
| Srivatsan, Vega, Skelton, Berg-Kirkpatrick (2021). *Neural Representation Learning for Scribal Hands of Linear B*. arXiv:2108.04199 | Fetched arXiv | **Correct.** ICDAR 2021 Workshop on Computational Paleography. Dual hand/sign embeddings; evaluated on find-place prediction [V]. |
| Nair (2026). arXiv:2604.17828, Indus synthetic-baseline scorecard | Fetched arXiv | **Exists as described.** Single-author preprint, 1,916 inscriptions, 584 signs [V]. Low relevance to PE; fine as a methodological aside. |
| *The Learnable Typewriter* (ICDAR 2024), authors "not verified" | Search | Siglidis, Gonthier, Gaubil, Monnier, Aubry; arXiv:2302.01660 [S: multiple consistent listings]. PE-A can fill in the authors. |
| P7: "Of 8,011 intact numerals, only 1,899 unambiguous"; test set exists | Read P7 pp. 1–9 | **Correct** [V]. Extra details PE-A omitted: the test set is only **48 numerals** (B 3, C 18, D 14, S 13), expert-verified and biased toward easy cases. Subset-sum resolved **24 texts**. Best F1 0.94 (4-way). |
| P5 corpus "~26k tokens (~12k numerical, ~14k non-numerical)" | Read IA p.6 | **Correct** [V]. It conflicts with Born et al. 2023's 35k, which shows version/counting drift. |
| CDLI P008805 = MDP 26, 117; photo © NMI, line art © publications | Fetched CDLI artifact page | **Correct** per CDLI [V]. Note P7's Fig. 2 caption gives "MDP 26, 177" for P008805, apparently a typo in P7, not in PE-A. |
| MahmoodKhalil57/ProtoElamite GitHub repo | Not checked (PE-A already marked it [U]) | Recommend removing it from any proposal bibliography. |

---

## 2. What PE-A got right that I missed

1. **Dahl 2023 (Akkadica)** as the explicit scholarly counterweight to the PE↔LE continuity claim. I only had Kelley et al. 2022's cautions.
2. **Scoop / concentration risk.** Nearly all PE computation comes from one group (SFU/Bologna/UBC/Uppsala), so contacting them early is both a risk mitigation and an expert-access strategy. I mentioned them only as reviewers.
3. **P7 details.** 1,899/8,011 unambiguous numerals, the feature table, and the core insight that numeracy carries semantic signal, even though P7 already exploited it.
4. **Null-model discipline** (Rao vs Sproat on the Indus script) and **stability/consensus across seeds and architectures** as reporting rules. My protocol lacked explicit stability criteria.
5. **Cluster-number selection is unaddressed in P6 (fn. 6).** A real gap, even though I argue it can't be solved by clustering.
6. **Line art as a cheap bootstrap modality.** I under-used it. It's valuable for proposal generation and domain adaptation, just not for collation claims.
7. **Style vs sign confound.** Apparent allographs may just be scribal-hand or tablet effects. My allograph audit needs a "does the split track tablet ID?" control.
8. **Software-engineering deliverables for an *Advanced Software Engineering* course:** DVC data versioning, CI for experiments, a tested ATF parser, annotation-tool integration. My draft only mentioned a viewer.
9. **Layout priors:** right-to-left reading, entries delimited by numerals (confirmed in P7 [V]).
10. **Honest-negatives section** (what was searched and not found). Good practice to keep.

---

## 3. Counterproposal: merged "best single thesis"

### 3.1 Title

**From Archetype to Clay: Image-Grounded Sign Tokens and Collation Support for the Proto-Elamite Corpus**

### 3.2 Core deliverable (must ship)

1. **PE-Tokens dataset.** Token-level bounding boxes on real PE tablet images, each linked to a CDLI transliteration token (P-number, side, entry, token index, sign name, confidence).
   - Released as annotations + image references + code, not pixels, following the Dencker et al. licensing precedent.
   - Includes a hand-annotated **gold set** (≈50 tablets, stratified).
2. **Weakly supervised alignment pipeline.**
   - Tablet-face and ruling/entry segmentation.
   - Two proposal heads: impressed numerals and incised signs.
   - DINOv2 template scoring against the CC-BY Dahl archetypes (cdli-gh/proto-elamite_data [V]).
   - Monotone right-to-left sequence alignment with damage-aware insertions/deletions.
   - EM retraining.
3. **Collation-flag tool.** A ranked list of tokens where the image evidence disagrees with the transliteration.
   - For **numerals**: count/shape mismatch between image and ATF, with Born et al. 2025's rule-based readings as a validity check (an "invalid notation in every system" case gets flagged).
   - For **frequent signs**: the embedding says "looks like Y, labelled X".
   - Served in a small web viewer (concordance "show all M388 in clay" plus flag review with accept/reject logging). The logged expert decisions become an evaluation asset.
4. **Engineering.** Versioned data pipeline (DVC), tested ATF parser, CI running unit tests + a smoke evaluation, reproducible configs, and a licence-compliant release checklist.

**Why this core:**
- It sits squarely on the verified gap (clay vs archetypes).
- Every headline metric has real ground truth (gold boxes; expert-verified numerals; documented transliteration corrections).
- It's useful to epigraphers even if the ML results are only moderate.
- It is primarily CV plus software engineering.

### 3.3 Optional extension (only if Gate G3 passes)

**Pre-registered token-level allograph audit.**
- **Scope.** Before looking at results, freeze a list of ≤30 sign pairs, drawn from:
  - (i) Dahl tilde-variant pairs;
  - (ii) Born et al. 2023's proposed merges (e.g. M362/M362~a, M209~a/M210~f [V]);
  - (iii) matched random control pairs.

  Include only pairs with ≥15 gold or high-confidence tokens per member.
- **Test.** MMD two-sample test on SSL embeddings, with permutation p-values and FDR control.
- **Confound control.** Repeat with tablet-ID-balanced sampling, and check whether the split just predicts tablet ID (style confound).
- **Known-answer validation.**
  - Identical pipeline on Cypro-Greek and/or Linear B glyphs with gold identities.
  - Planted merges and splits on PE gold tokens.
- **Output.** "Visually indistinguishable on clay / visually distinct / insufficient evidence", explicitly *not* sign-identity claims.

**Explicitly out of scope (future work, with reasons from §1):**
- numeracy-based semantic induction (pre-empted by P7 §5; label leakage);
- PE↔LE correspondence testing (selection-biased null; tiny incomparable corpus);
- sign-inventory size estimation (definitional);
- any decipherment or sound values.

### 3.4 Month-by-month plan (~8 months, 1 student; notes for 2)

| Month | Work | Exit artefacts |
|---|---|---|
| **M1** | Data audit via CDLI API: count PE artefacts with photo / line art / RTI; sample resolution; check whether RTI stills can be downloaded. Pin the transliteration version and diff it against the 2018 SFU copy, the 2022 dump and the current API. Email CDLI (research-use confirmation) and the SFU/Bologna group (overlap, P7 test set). Secure the expert advisor. Read Dahl 2019's sign-list introduction and P7. Set up the repo, DVC, ATF parser with tests. | Data-audit report, version manifest, parser tests. **Gate G0.** |
| **M2** | Annotation guidelines. Gold set part 1: 25 photo tablets + 10 line-art tablets, stratified by museum (Louvre/NMI), size and damage. Second annotator on 5 tablets. Face and ruling segmentation baseline. | Gold v0.5, IAA report, segmentation baseline. **Gate G1.** |
| **M3** | Proposal heads (numeral impressions / incised signs) trained on gold plus line art. DINOv2 archetype scoring. Sequence alignment v1 (no EM). Numeral-only alignment first. | Alignment v1 metrics on the gold dev split. **Gate G2 (photo viability).** |
| **M4** | EM bootstrapping over the full photo subset (3 rounds). Relighting and erosion augmentation. Gold set part 2 (to ~50 tablets; frozen test split). Ablations: no EM, no sequence constraint, no archetypes, line-art-only training. | PE-Tokens v1, ablation table. |
| **M5** | Collation flags: numerals (image count/shape vs ATF; validity per P7 rules) and frequent signs (embedding outliers). Build the **correction-history benchmark** (tokens changed between CDLI versions, filtered to token-level reading changes rather than global renames). Planted-error set. | Flag ranker, benchmark results. **Gate G3 (extension go/no-go).** |
| **M6** | Viewer / concordance + flag-review UI with decision logging. **Expert blind review session 1** (≈3 h): flags mixed with decoys. Start the extension if G3 passed (pre-registration frozen first), otherwise harden the core (more tablets, better numeral counting). | Viewer v1, expert precision@k. |
| **M7** | Extension experiments (known-answer scripts, planted merges, MMD tests, tablet-ID control) **or** core hardening. **Expert session 2** (≈2 h): 200 random high-confidence alignments + extension outputs. | Extension results or core v2. |
| **M8** | Write-up, release (annotations + references + code + model cards + licence statement), reproducibility run from a clean clone, report the remaining open questions to the experts. | Thesis, release tag, demo. |

*With 2 people:* person A owns M2–M4 alignment; person B owns the parser, viewer and CI from M1, and the collation benchmark from M3. The extension becomes feasible by default.

### 3.5 Go/no-go gates

| Gate | When | Go criterion | If no-go |
|---|---|---|---|
| **G0: access** | End of week 3 | (a) ≥300 PE tablets with photos at usable resolution (legible signs at ≥~8 px stroke width) **and** transliterations; (b) written CDLI confirmation that research use + annotation release (references only) is acceptable; (c) a named PE specialist commits ≈8–10 h. | (a) fails → line-art + Dencker-style method paper with a proto-cuneiform detection check, with the novelty claim downgraded. (c) fails → drop expert-dependent metrics and rely on the correction-history benchmark and planted errors; pause until an expert is secured. |
| **G1: annotability** | End of M2 | Sign-label agreement between annotators κ ≥ 0.75 on legible tokens; box IoU agreement ≥ 0.6; annotation speed ≤ 1.5 h per median tablet. | Restrict gold labels to numerals + top-100 signs, and label the rest "sign (unspecified)". |
| **G2: photo viability** | End of M3 | On the gold dev split (photos): class-agnostic proposal recall ≥ 0.7 at IoU 0.5; numeral token alignment accuracy ≥ 0.6 before EM. | Pivot the core to numerals-only on photos + all signs on line art; state the reduced claim. |
| **G3: extension** | End of M5 | Photo token alignment accuracy ≥ 0.7 for head signs; ≥ 15 aligned tokens per member for ≥ 15 pre-registered pairs; known-answer script data obtained. | No extension; spend M6–M7 on coverage, numeral counting and expert review. |

The thresholds are initial proposals, to be set properly once the M1 audit numbers are known. Record them in the pre-registration before M2.

### 3.6 Evaluation protocol

**Pre-registration (frozen end of M1, amended only with a dated log):** data version, splits, metrics, thresholds, pair lists, expert-review design.

1. **Splits.** At tablet level. Joined fragments (Dahl 2012 joins [V] and CDLI join metadata) and duplicate records stay in one split. The gold test split (≈20 tablets) is never used for pseudo-labelling, augmentation tuning or threshold selection.
2. **Detection and alignment (ground truth: gold boxes).**
   - Class-agnostic mAP@0.5.
   - Token alignment accuracy (the predicted box for ATF token *i* hits gold with IoU ≥ 0.5).
   - Coverage at 90% precision.
   - All stratified by image type (photo / line art / RTI still), museum, sign frequency bucket (head / mid / tail) and damage.
   - Baselines: raw template matching; nearest-archetype without sequence constraint; Dencker et al. pipeline adapted off the shelf.
   - Ablations as in M4.
   - Bootstrap 95% CIs over tablets.
3. **Numeral reading (ground truth: gold + external).**
   - Digit-class accuracy and count accuracy on gold numerals.
   - Agreement of image-derived notations with the **48 expert-verified numerals of the P7 test set** [V] where they overlap the imaged tablets. This is small; report it as a sanity check with exact counts.
   - Validity rate under P7's reading rules.
4. **Collation flags: three independent, non-circular checks.**
   1. **Planted errors.** Corrupt 3% of ATF tokens in the gold split (sign substitutions to visually similar and dissimilar signs; numeral count ±1). Report precision/recall and AUROC.
   2. **Correction-history benchmark.** Take token-level reading changes between CDLI versions (e.g. 2018 SFU copy → 2022 dump → current), excluding global renames such as M483→M346~d (P5 [V]). Use the *old* reading as the label and ask whether the image flags it. These are real expert corrections the model never saw as labels. Report recall@k. Include known cases from P7 (e.g. P008791 N39B [V]).
   3. **Blind expert review.** Top-30 flags mixed with 30 random tokens, order shuffled, source hidden. The specialist marks each as transliteration issue / copy or photo artefact / fine. Report precision difference vs decoys with a Fisher exact test.
5. **Extension (if run).**
   - Known-answer script: V-measure and AUROC of merge/split decisions vs gold identities.
   - Planted merges/splits on PE gold.
   - Per-pair MMD p-values with Benjamini–Hochberg correction.
   - Tablet-ID confound test.
   - Stability: ARI across 3 seeds × 2 backbones. Report only findings stable in ≥ 5 of 6 runs.
6. **Reporting language.**
   - "Accuracy" only where ground truth exists (items 2–4.1/4.2).
   - PE-level interpretations are "flagged", "supported by visual evidence" or "insufficient evidence".
   - No "decipherment" wording anywhere.
7. **Expert-time budget.** ≤ 10 h total, split into two sessions, with forms designed in M1.

### 3.7 Abstract (honest but compelling)

> Proto-Elamite, the writing system of Iran around 3100–2900 BCE, survives on roughly 1,600 clay tablets and remains undeciphered apart from its numerals. Recent computational studies have revealed structure in the script, but all of them work from scholars' transliterations or from a single idealised drawing per sign. None has looked at the signs as they were actually pressed and drawn into clay. This thesis builds the first image-grounded dataset of Proto-Elamite sign tokens. We align the Cuneiform Digital Library Initiative's transliterations to photographs of real tablets using weak supervision, bootstrapped from published sign drawings and a small hand-annotated gold standard. On top of this alignment we build a collation-support tool that ranks places where the clay and the transliteration appear to disagree, with a focus on the well-understood numeral notations. We evaluate it against planted errors, against corrections that specialists have already made to the corpus over successive versions, and in a blinded review by a Proto-Elamite specialist. We don't claim to decipher the script. The contribution is infrastructure the field lacks: a way to see, query and check every attestation of a sign on the tablets themselves, released in a form that respects museum image rights. That infrastructure is a precondition for testing future claims about sign variants, scribal practice and meaning against physical evidence.

### 3.8 Prerequisites the student must secure

1. **CDLI written confirmation.** Research use of downloaded images, acceptable bulk-download rate/API use, and permission to release annotations keyed to CDLI image references. Ask about access to higher-resolution or RTI-derived stills of Louvre tablets.
2. **A committed PE domain advisor** (≈8–10 h over the project). Ideally someone from the Kelley/Monroe/Born/Sarkar group or Dahl's circle. Agree on authorship/acknowledgement expectations up front.
3. **Overlap check with the SFU/Bologna group.** Confirm they aren't releasing a PE token dataset or detector. Request the P7 numeral test set and code if not public.
4. **Library access** to Dahl 2019 (*Textes Cunéiformes du Louvre* 32, sign list pp. 185–227), Dahl 2005 and Englund 2004; the NEA 2025 overview (Monroe et al.) and Kelley 2026 (Cambridge Element), to confirm no newer overlapping work.
5. **Pinned data versions.** Current CDLI API export plus the 2022 dump plus the 2018 SFU copy (all three are needed for the correction-history benchmark).
6. **Licences confirmed.** Dahl archetypes CC-BY 4.0 (cdli-gh/proto-elamite_data [V]); SFU toolkit LGPL-3.0 [V]; Dencker code/data licence; DINOv2 licence; known-answer script datasets (Cypro-Greek / Linear B glyphs) and their terms.
7. **Compute and tooling.** University GPU or Colab/Kaggle quota (T4-class is enough); CVAT or Label Studio instance; storage for ≈ tens of GB of images kept private (not in the public repo).
8. **Supervisor sign-off on framing.** CV + software-engineering thesis with collation support as the application, and decipherment explicitly out of scope. Also confirm whether ethics or data-management review is needed for museum-owned imagery.
9. **A short primer** (1 week, M1) in PE conventions: sign-list notation (M/N numbers, tilde variants), ATF format, right-to-left entry structure, numeral systems (P7 Fig. 1 [V]).

---

## 4. Self-critique carried into the merge (from my own draft)

- My idea B (arithmetic auditor) overstated novelty: P7's subset-sum analysis already exploits summary lines and found transliteration errors [V]. Only 24 texts were resolvable that way, so arithmetic can't be a primary benchmark. In the merge it survives only as a validity check on image-read numerals.
- My idea I6 ("semantic class without a key") has the same label-leakage issue I identify in PE-A's Top 2. It is dropped.
- My draft had no stability or null-model reporting rules and no scribal-hand confound control. Both are adopted from PE-A.
