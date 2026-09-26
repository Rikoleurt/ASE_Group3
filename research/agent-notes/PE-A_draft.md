# PE-A Draft: Proto-Elamite x Computer Vision / ML (Method-First Lens)

Author: Agent PE-A. Date of literature check: 2026-09-16.
Verification legend: **[V-read]** = I read the paper PDF/abstract page myself; **[V-meta]** = existence/venue/abstract confirmed via publisher, ACL Anthology, arXiv or PubMed listing, but full text not read; **[U]** = could not verify, treat with caution.

---

## 0. TL;DR

- The pitch "AI that infers meaning without a translation key" is **already an active research line** for Proto-Elamite (PE), led by one group (Born, Kelley, Monroe, Sarkar; SFU / Bologna / UBC-UNB). They have done sign clustering + LDA (2019), image+text sign embeddings (2021), header detection (2022), VAE-based "script clustering" of the sign inventory (2023), LE-value mapping (2022), and numeral-system disambiguation (arXiv 2025). A Master's project that re-does "cluster PE signs with deep learning" will **not be novel**.
- **The single most important gap for a CV project:** every PE "visual" model so far uses **Dahl's archetypal sign-list drawings (one image per sign *type*, ~1,300 images)** substituted into the transliteration, *not* token images cut from actual tablets. Born et al. 2023 state these images "smooth over many of the irregularities of the original shapes drawn on clay". So the visual models cannot see real allographic variation, scribal hands, or signs mis-transliterated by humans. **Nobody has built a token-level image dataset or a sign detector for PE.**
- Recommended top ideas:
  1. **PE-Tokens**: weakly-supervised sign localisation on PE tablet photos / hand copies, aligned to CDLI transliterations (Dencker et al. 2020 style) → first token-level PE image dataset → token-level allograph / sign-inventory audit with self-supervised embeddings. (Strongest CV fit, most defensible.)
  2. **Numeracy-grounded semantic induction**: use the *understood* part of PE (numerals / metrology / number-system choice) as distant supervision to infer semantic *categories* of undeciphered signs (grain vs. livestock vs. labour vs. persons), evaluated by leave-known-out on the handful of signs whose meaning is agreed. (Best fit for the "meaning without a key" pitch, done honestly.)
  3. (Stretch / smaller) **Statistical test of cross-script correspondences** (PE ↔ Linear Elamite, PE ↔ proto-cuneiform) with visual + distributional embeddings and permutation nulls — turns the contested Desset-2022 vs. Dahl-2023 debate into a measurable question.
- Biggest risks: (a) image access/licensing (CDLI images are non-commercial, owned by Louvre / National Museum Tehran; cannot be redistributed), (b) no annotation for PE boxes at all, (c) the evaluation-without-ground-truth problem, (d) scooping by the SFU group, (e) need for a domain expert to validate outputs.

---

## 1. Literature Check (with URLs)

### 1.1 Proto-Elamite: computational work (core prior art)

| # | Citation | What they did | Data used | Status |
|---|---|---|---|---|
| P1 | Born, Kelley, Kambhatla, Chen, Sarkar (2019). *Sign Clustering and Topic Extraction in Proto-Elamite.* LaTeCH-CLfL (SIGHUM) workshop @ NAACL, pp. 122–132. https://aclanthology.org/W19-2516/ | Hierarchical clustering (neighbour-based, HMM, Brown), n-grams, LDA; "stable clusters" across methods; replicates manual results + new sign relations. | CDLI transliterations (text only). | [V-meta] |
| P2 | Born, Kelley, Monroe, Sarkar (2021). *Compositionality of Complex Graphemes in the Undeciphered Proto-Elamite Script using Image and Text Embedding Models.* Findings of ACL-IJCNLP 2021, pp. 4136–4146. https://aclanthology.org/2021.findings-acl.362/ | LM over sequences of sign images (CNN) and/or labels (BiLSTM); evidence that complex graphemes (CGs) are partly compositional (meaning mostly from outer component). Image LM "abstracts away from annotator bias". | ~1,399 tablets, ~33.8k tokens (cleaned CDLI); sign images = sign-list drawings. | [V-meta] (secondary summary of limitations via Lacuna aggregator — [U] for exact wording) |
| P3 | Born, Monroe, Kelley, Sarkar (2022). *Sequence Models for Document Structure Identification in an Undeciphered Script.* EMNLP 2022, pp. 9111–9121. https://aclanthology.org/2022.emnlp-main.620/ | Unsupervised neural + statistical sequence models give independent evidence for "header" signs; anomalies flag possible expert errors. | CDLI transliterations. | [V-meta] |
| P4 | Kelley, Born, Monroe, Sarkar (2022). *Image-aware language modeling for Proto-Elamite.* Lingue e linguaggio 2/2022, 261–294. https://rivisteweb.it/doi/10.1418/105965 | Image-aware LM; per Born et al. 2023 it uses softmax over a fixed vocabulary initialised to the working sign list, "which biases it towards recovering the same divisions speculated by experts", and "does not test on any known scripts". | Sign-list images + transliterations. | [V-meta] |
| P5 | Kelley, Born, Monroe, Sarkar (2022). *On Newly Proposed Proto-Elamite Sign Values.* Iranica Antiqua LVII. doi:10.2143/IA.57.0.3291506. PDF: https://anoopsarkar.github.io/papers/pdf/IA57001.pdf ; data: https://github.com/sfu-natlang/pe-sign-value-data | Applies Desset et al.'s LE sound values mechanically to the whole PE corpus; lists candidate "words"/personal-name spans; notes 18 of Desset's PE signs are hapax, 7 not in CDLI corpus. | Full CDLI PE corpus (~26k tokens: ~12k numerical, ~14k non-numerical per the paper). | **[V-read]** |
| P6 | Born, Monroe, Kelley, Sarkar (2023). *Learning the Character Inventories of Undeciphered Scripts Using Unsupervised Deep Clustering.* CAWL 2023 @ ACL, pp. 92–104. https://aclanthology.org/2023.cawl-1.11/ ; code: https://github.com/MrLogarithm/cawl-clustering | VAE, VAE+Neighbour, VAE+LSTM, VAE+Transformer with DeepCluster-style pseudolabels (~0.2M params); beats Sign2Vec on Cypro-Greek (V-measure 0.76 vs 0.75); proposes PE sign merges (e.g., M209~a / M210~f), qualitatively checked with experts. | PE: 35k tokens, **1,319 images — one archetypal Dahl drawing per sign type**, 64×64 grayscale. English handwriting / Japanese fonts / Cypro-Greek as known-script proxies. | **[V-read]** |
| P7 | Born, Monroe, Kelley, Sarkar (2025). *Disambiguating Numeral Sequences to Decipher Ancient Accounting Corpora.* arXiv:2502.00090 (v2 Apr 2025; venue not stated on arXiv page). https://arxiv.org/abs/2502.00090 | Rule-based enumeration of possible readings for each numeral under the Sexagesimal / Decimal / Bisexagesimal / Capacity systems; subset-sum over summary lines; Yarowsky-style bootstrapped classifiers; new test set. Of 8,011 intact numerals, only 1,899 are unambiguous. Finds correlations between tablet content and magnitude. | CDLI corpus downloaded Oct 2022. | **[V-read]** (first 3 pages) |
| P8 | Monroe, Kelley, Born, Sarkar (2025). *Recent Progress in Deciphering Proto-Elamite.* Near Eastern Archaeology 88(4): 314–323. https://www.journals.uchicago.edu/doi/10.1086/738240 | Overview of the computational programme (BiLSTM, HMM, topic models). | — | [V-meta] (paywalled, 403) |
| P9 | Kelley, K. (2026). *Proto-Elamite: Writing and Society in Early Iran.* Cambridge Elements, CUP. https://www.cambridge.org/core/elements/protoelamite/3684B7262E21A8B6AF8657D948A5B1A6 | Survey incl. computational methods. | — | [V-meta] (via news listing; not read) |
| P10 | SFU NatLang. *pe-decipher-toolkit* (LGPL-3.0). https://github.com/sfu-natlang/pe-decipher-toolkit | Notebook "A Guided Tour of Proto-Elamite"; CDLI-derived data; sign PNGs (PE_mainforms, PE_num). | — | [V-meta] |
| P11 | MahmoodKhalil57/ProtoElamite (GitHub). https://github.com/MahmoodKhalil57/ProtoElamite | Claims "9 reproducible, falsifiable claims" from 1,467 CDLI tablets. Not peer-reviewed. | — | [U] — not assessed; do not rely on it. |

### 1.2 Proto-Elamite: philology / data sources

- Dahl, J. L. (2019). *Tablettes et fragments proto-élamites / Proto-Elamite Tablets and Fragments.* Textes Cunéiformes du Louvre XXXII. CDLI record: https://cdli.earth/publications/148123 — source of the working sign list (~1,500–1,900 signs depending on counting; Born 2023 footnote: 287 to 1,623 depending on methodology) and the archetypal sign drawings. [V-meta]
- Dahl, Englund, Damerow et al. — numerals/metrology (Damerow & Englund 1989, *The Proto-Elamite Texts from Tepe Yahya*; Friberg 1978; Englund 2004/2011) — cited within P6/P7. [V-meta via citing papers]
- Oxford/Southampton **RTI imaging of ~1,100 Louvre PE tablets**; "half of which can now be viewed" on CDLI (2012 press). https://www.ox.ac.uk/news/2012-10-22-technology-helping-crack-oldest-undeciphered-writing-system [V-meta]. Note: RTI files themselves are not confirmed to be publicly downloadable — [U].
- CDLI: PE artifact pages have **photos and line art** (checked P008805 = MDP 26, 117: photo © National Museum Tehran; lineart © publication authors). https://cdli.earth/artifacts/8805 [V-read]
- CDLI Terms of Use: images for **non-commercial** use of students/scholars; copyright of owning institutions; commercial use prohibited without permission; text data freely reusable with attribution. https://cdli.earth/terms-of-use [V-meta]
- CDLI bulk text/catalogue dump (ATF + CSV, git-lfs): https://github.com/cdli-gh/data [V-meta]

### 1.3 Linear Elamite and cross-script

- Desset, Tabibzadeh, Kervran, Basello, Marchesi (2022). *The Decipherment of Linear Elamite Writing.* ZA 112(1): 11–60. https://doi.org/10.1515/za-2022-0003 [V-meta]. Proposes LE values and a PE↔LE correspondence chart. P5 notes "No description is given for the methodology by which signs in the two scripts were equated."
- Dahl, J. L. (2023). *Proto-Elamite and Linear Elamite, a Misunderstood Relationship?* Akkadica 144(2): 107–126. https://ora.ox.ac.uk/objects/uuid:51adb1c2-61de-438c-9b29-125addf3d2a1 [V-meta]. Argues against continuity (LE as a new creation possibly inspired by recovered PE tablets). → The PE↔LE link is **contested**; any cross-script model must be framed as hypothesis testing.
- Linear Elamite corpus is tiny (tens of inscriptions; e.g., OCLEI concordance on Academia, ~51 inscriptions mentioned in secondary sources) [U — numbers not verified from primary source].

### 1.4 Visual sign-inventory / allograph learning on other undeciphered scripts

- Corazza, Tamburini, Valério, Ferrara (2022a). *Contextual unsupervised clustering of signs for ancient writing systems* (Sign2Vec). LT4HALA @ LREC 2022. (cited in P6) [V-meta via P6]
- Corazza, Tamburini, Valério, Ferrara (2022b). *Unsupervised deep learning supports reclassification of Bronze age cypriot writing system.* PLOS ONE 17(7): e0269544. https://doi.org/10.1371/journal.pone.0269544 [V-meta]
- Srivatsan, Vega, Skelton, Berg-Kirkpatrick (2021). *Neural Representation Learning for Scribal Hands of Linear B.* ICDAR 2021 Workshops. https://arxiv.org/abs/2108.04199 — disentangles hand vs. sign-shape embeddings; evaluates on find-place prediction. [V-meta]
- *The Learnable Typewriter: A Generative Approach to Text Analysis* (ICDAR 2024, Springer). https://link.springer.com/chapter/10.1007/978-3-031-70536-6_18 — sprite-based unsupervised glyph discovery. [V-meta, title/venue only; authors not verified here]
- Yin, Aldarrab, Megyesi, Knight (2019). *Decipherment of historical manuscript images.* ICDAR 2019. (cited in P6) [V-meta via P6]

### 1.5 Cuneiform computer vision (transferable methods and data)

- Dencker, Klinkisch, Maul, Ommer (2020). *Deep learning of cuneiform sign detection with weak supervision using transliteration alignment.* PLOS ONE 15(12): e0243039. https://doi.org/10.1371/journal.pone.0243039 ; code https://github.com/CompVis/cuneiform-sign-detection-code ; dataset (image *references* + annotations, Neo-Assyrian) https://github.com/CompVis/cuneiform-sign-detection-dataset [V-meta]. **Key template**: bootstraps a detector from transliterations without boxes; releases image references rather than images (licensing workaround).
- Williams et al. (2023). *DeepScribe: Localization and Classification of Elamite Cuneiform Signs Via Deep Learning.* arXiv:2306.01268. https://arxiv.org/abs/2306.01268 — Persepolis Fortification Archive (Achaemenid Elamite *cuneiform*, not PE); 5k+ images, 100k boxes; RetinaNet mAP 0.78, top-5 0.89. [V-meta; first author surname per arXiv listing—verify]
- Mikulinsky et al. (2025). *ProtoSnap: Prototype Alignment for Cuneiform Signs.* ICLR 2025. https://arxiv.org/abs/2502.00129 ; https://tau-vailab.github.io/ProtoSnap/ — snaps skeleton prototypes (from fonts) onto photographed signs using deep diffusion features; improves rare-sign recognition. [V-meta]. **Very relevant**: PE has "prototype" drawings (Dahl) + photos.
- Mara et al. HeiCuBeDa Hilprecht (3D scans of cuneiform tablets, Jena; ~1,977 tablets per heiDATA listing; ED IIIb–Old Babylonian, i.e. *no* PE). https://heidata.uni-heidelberg.de/dataset.xhtml?persistentId=doi:10.11588/data/IE8CCN [V-meta]
- Mainz Cuneiform Benchmark Dataset series (sign annotations of 3D renderings), JOAD. https://openarchaeologydata.metajnl.com/articles/10.5334/joad.172 [V-meta]
- CuneiML (JOHD). https://openhumanitiesdata.metajnl.com/articles/10.5334/johd.151 [V-meta]
- Che, Garcés Arias, Niaz, Bender, Jiménez (2026, preprint). *Automated sign detection across the Electronic Babylonian Library.* arXiv:2606.22608 — Deformable DETR on 87,668 fragments. [V-meta; under review]
- Diao et al. (2025). *Ancient Script Image Recognition and Processing: A Review.* arXiv:2506.19208 — class imbalance, degradation, few-shot as open problems. [V-meta]

### 1.6 Decipherment as optimisation / distributional analysis

- Snyder, Barzilay, Knight (2010). *A Statistical Model for Lost Language Decipherment.* ACL 2010. https://aclanthology.org/P10-1107/ — Ugaritic↔Hebrew, 29/30 letters. [V-meta]
- Luo, Cao, Barzilay (2019). *Neural Decipherment via Minimum-Cost Flow: From Ugaritic to Linear B.* ACL 2019. https://aclanthology.org/P19-1303/ [V-meta]
- Luo, Hartmann, Santus, Cao, Barzilay (2021). *Deciphering Undersegmented Ancient Scripts Using Phonetic Prior.* TACL. https://arxiv.org/abs/2010.11054 — Gothic, Ugaritic, Iberian. [V-meta]
- Tamburini (2023). *Decipherment of Lost Ancient Scripts as Combinatorial Optimisation Using Coupled Simulated Annealing.* CAWL 2023. https://aclanthology.org/2023.cawl-1.10/ ; extended journal version (2025): https://pmc.ncbi.nlm.nih.gov/articles/PMC12162589/ — k-permutation encoding, Aegean scripts. [V-meta]
- Rao et al. (2009). *Entropic evidence for linguistic structure in the Indus script.* Science. https://www.science.org/doi/10.1126/science.1170391 ; critique: Sproat (2010/2014); reply: Rao et al. (2010) Computational Linguistics 36(4). https://aclanthology.org/J10-4016.pdf [V-meta]. Lesson: **conditional-entropy tests alone do not discriminate linguistic from non-linguistic systems without proper controls.**
- Nair (2026, preprint). *How Non-Linguistic Is the Indus Sign System? A Synthetic-Baseline Scorecard.* arXiv:2604.17828 — multi-metric test vs. synthetic heraldic/administrative baselines. [V-meta; single-author preprint, not peer reviewed]

### 1.7 Things I searched for and could NOT find (honest negatives)

- No PE **sign detector / OCR** or **token-level PE image dataset** (searched arXiv, ACL, general web). 
- No PE **3D scan dataset** comparable to HeiCuBeDa (the Louvre RTI captures exist, but I could not confirm public bulk download).
- No PE paper at ML4AL 2024 (checked proceedings listing via search; not exhaustive).
- No application of NeuroCipher / Luo-style models to PE (expected: PE has no known related language, and few signs are hypothesised to be phonetic).
- Could not access full text of P8 (NEA 2025, paywall) or P9 (Cambridge Element) — they may contain newer work I am unaware of. **Action item: email the SFU group / read these before committing.**

---

## 2. Gap Mining

Explicit or near-explicit statements from the papers, plus gaps I infer (marked *inferred*).

| Gap | Source / evidence | Opening |
|---|---|---|
| G1. Visual models use archetypal sign-list images, not token images from clay. "These images smooth over many of the irregularities of the original shapes drawn on clay"; they represent "an intermediate level of detail that is cleaner than segmented images of the original texts". | P6 §3 **[read]** | Token-level images from tablet photos / hand copies → real allograph discovery, scribal-hand analysis, detection of transliteration errors. |
| G2. Visual clustering cannot split a sign type into allographs or detect mis-transliterated tokens, because identical labels always get identical images. | *Inferred* from P6 design | Token-level clustering where two tokens with the same label may land in different clusters. |
| G3. No ground truth for PE; validation is qualitative expert review. "Our results on this script cannot be compared to any known ground truth." | P6 Limitations **[read]** | Principled proxy benchmarks (proto-cuneiform, Cypro-Greek, Linear B), leave-known-out tests, pre-registered null models. |
| G4. Evaluation proxies don't cover PE's typology: "we cannot cover all possible cases". Proxies used were English handwriting, Japanese fonts, Cypro-Greek — none is an early *administrative, numerically dominated, largely non-glottographic* system. | P6 Limitations **[read]** | Use **proto-cuneiform** (contemporary, accounting, partially understood, on CDLI with photos) as the matched proxy. |
| G5. Earlier image-aware LM (P4) used fixed softmax vocabulary initialised to expert sign list → biased; "does not test on any known scripts". | P6 §6 **[read]** | Open-vocabulary, token-level, tested on known scripts. |
| G6. Choosing the number of clusters is ignored ("The present work will otherwise ignore the problem of selecting the correct number of clusters"). | P6 fn. 6 **[read]** | Model-selection / MDL / nonparametric (DP-means, HDBSCAN) inventory estimation with uncertainty — directly answers "how many signs does PE have?" (287 vs 1,623). |
| G7. Data sparsity: most signs are rare; annotation bias in transliterations; suggested relabelling signs contextually and comparing with structurally similar known scripts. | P2 limitations (via secondary summary **[U] wording**) | Few-shot / prototype methods (ProtoSnap), contextual relabelling. |
| G8. Numerals: only 1,899 / 8,011 intact numerals are unambiguous; authors found "previously-unknown correlations between tablet content and numeral magnitude". | P7 **[read]** | Use disambiguated number system + magnitude as *weak semantic labels* for adjacent undeciphered signs. |
| G9. PE↔LE correspondences in Desset et al. have no stated method; many proposed PE signs are hapax or absent from corpus; Dahl (2023) disputes continuity. | P5 **[read]**, Dahl 2023 [V-meta] | Quantitative, null-model-controlled test of visual + distributional correspondence. |
| G10. PE sign detection work does not exist; cuneiform detection is mature (Dencker 2020 weak supervision; DeepScribe; ProtoSnap; eBL 2026). PE signs are *incised/drawn* (curvilinear, not wedge-only), so cuneiform models don't transfer directly. | *Inferred* from §1.5 + negative search | Adapt weakly-supervised transliteration alignment to PE. |
| G11. Entropy analyses of undeciphered scripts are contested without controls (Rao vs. Sproat). | §1.6 | Any "is it language?" analysis on PE must include synthetic and real non-linguistic baselines; target sub-question: do putative syllabic/PN spans behave differently from object/numeral spans? |
| G12. Licensing: CDLI images non-commercial; owned by museums. | CDLI ToU | Release *references + annotations + code*, not pixels (Dencker precedent). |

---

## 3. Brainstorm: 6 Candidate Ideas

Scored 1–5 (5 = best) on Novelty (N), Feasibility for 6–9 months / free GPU (F), Evaluability without ground truth (E), CV-centrality for a CV project (CV).

| # | Idea | N | F | E | CV | Notes |
|---|---|---|---|---|---|---|
| I1 | **Weakly-supervised PE sign localisation** aligning photos/hand copies with CDLI transliterations → first token-level PE dataset | 5 | 3 | 5 | 5 | Directly fills G1/G10; box-level ground truth *is* obtainable by non-experts because the transliteration tells you which sign it is. |
| I2 | **Token-level allograph discovery & sign-inventory audit** (SSL embeddings on I1 crops + context; nonparametric cluster count) | 4 | 3 | 3 | 5 | Depends on I1; extends P6 from types to tokens (G2, G5, G6). |
| I3 | **Numeracy-grounded semantic category induction**: predict number system / commodity class of entries from sign sequence (+ image embeddings); read off learned sign→category associations for undeciphered signs | 4 | 4 | 4 | 2–3 | Honest version of "meaning without key" (G8). Mostly NLP unless visual features are central. |
| I4 | **Cross-script correspondence test** PE↔LE / PE↔proto-cuneiform via visual similarity (+ distributional embeddings), optimal transport, permutation nulls | 4 | 3 | 3 | 4 | Addresses G9; LE data tiny, contested, licensing of LE images unclear. |
| I5 | **Controlled "linguistic-ness" profile of PE sub-corpora** (candidate syllabic spans vs. object/numeral spans) vs. synthetic + real non-linguistic baselines (G11) | 3 | 5 | 3 | 1 | Cheap, but not CV and risky to over-claim; good as a side chapter. |
| I6 | **Combinatorial decipherment of candidate personal-name spans** (Luo 2021 / Tamburini 2025 style) against Elamite onomastics | 3 | 2 | 1 | 1 | Unknown language relationship, few phonetic signs, contested values; near-certain null result. Reject as main project. |

Rejected/merged: I5 becomes an evaluation component; I6 dropped (list as "future work"). I2 is merged with I1 as a two-phase project.

---

## 4. Top Picks (detailed)

### 4.1 TOP 1 — "PE-Tokens": From Sign-List Archetypes to Clay — Weakly-Supervised Sign Localisation and Token-Level Allograph Discovery in Proto-Elamite

**Problem statement.** All prior visual ML on PE represents each sign type with a single idealised drawing. We don't know how much genuine visual variation exists per sign, whether the ~1,500-sign working list over- or under-splits signs, or where human transliterations are inconsistent. Answering this needs token-level images, which do not exist.

**Novelty claim.** (1) First sign localisation model and token-level image dataset (as image references + boxes) for PE [G1, G10]. (2) First *token*-level allograph/inventory analysis for PE, able to split a sign label into sub-forms or merge labels based on real clay evidence [G2, G5]. (3) First principled estimate (with uncertainty) of PE sign-inventory size from visual evidence [G6].

**Data.**
- CDLI PE photos + line art (hand copies from MDP volumes, Dahl 2019 TCL XXXII) — non-commercial academic use; owned by Louvre / National Museum Tehran / publication authors. *Must* confirm (a) how many PE tablets have usable photos (press release: ~half of ~1,100 Louvre tablets; verify count by scraping CDLI catalogue metadata), (b) permission for research use of downloaded images; write to CDLI for high-res research images (ToU mentions this).
- CDLI ATF transliterations (freely reusable text) via https://github.com/cdli-gh/data.
- Dahl sign-list archetype images (in pe-decipher-toolkit, LGPL) as prototypes.
- Proxy with known answers: **proto-cuneiform** tablets on CDLI (photos + ATF; contemporary accounting script) and the CompVis Neo-Assyrian detection dataset for sanity-checking the weak-supervision loop.
- Release: code + annotations keyed by CDLI P-number + bounding boxes (no pixels), following Dencker et al.

**Method sketch.**
1. *Preprocessing*: tablet-face extraction (obverse/reverse from CDLI fat-cross photos), line art binarisation. Start with **line art** (much easier: clean strokes), then photos.
2. *Bootstrap detection* (Dencker 2020 pattern): 
   - Manually box ~50–100 tablets (non-expert task — sign identity given by transliteration; ~2–4 weeks).
   - Train a light detector (YOLOv8-n / RT-DETR-small; class-agnostic "sign" + "numeral" first, then top-K frequent signs).
   - Align detections to ATF lines/entries (PE entries are delimited by numerals; reading direction right-to-left, lines top-to-bottom) with dynamic programming over (visual similarity to Dahl prototype × sequence order), accept high-confidence alignments as pseudo-labels, retrain; iterate.
   - Optional: ProtoSnap-style prototype-to-photo matching using DINOv2 features for rare signs.
3. *Token embeddings*: self-supervised (DINOv2-S/ViT-S fine-tuned with augmentation that respects clay artefacts; or the VAE+Transformer of P6 as baseline) plus context (neighbour-token embeddings).
4. *Inventory analysis*: nonparametric clustering (HDBSCAN / DP-means) on token embeddings; disentangle "hand/tablet style" from "sign identity" (Srivatsan et al. 2021 idea: tablet-level latent vs. sign-level latent). Report (a) labels split into consistent sub-clusters (candidate allographs or distinct signs), (b) cross-label merges, (c) outlier tokens (candidate transliteration errors).

**Evaluation plan (ground truth partially unknown).**
- *Detection/alignment* (has ground truth!): mAP@0.5 and line-level alignment accuracy on a held-out, manually boxed PE test set (≥30 tablets never used in bootstrapping). Report per-frequency-bin recall (rare signs).
- *Inventory recovery on proxies with known answers*: run the *identical* pipeline on proto-cuneiform (and Cypro-Greek / Linear B glyph data if accessible) subsampled to match PE's corpus size, Zipf slope and hapax rate. Metrics: V-measure, homogeneity/completeness, estimated vs. true inventory size. This makes G3/G4 concrete.
- *Synthetic allograph injection*: in PE line art, deliberately relabel a random subset of tokens (or split a label into two artificial classes) → measure whether the method recovers the injected structure (precision/recall of recovered splits/merges). Gives a calibrated false-discovery rate.
- *Internal consistency*: stability across seeds / backbones / clustering algorithms (Adjusted Rand Index between runs); only report "stable" findings (P1's consensus idea).
- *Agreement with expert "silver" structure*: Dahl's tilde variants (~a, ~b = suspected variants; numbered = graphical variants) — does the model tend to merge tilde-variants more than unrelated signs? Report enrichment vs. random pairs with permutation p-values. (Not ground truth, but an independent expectation.)
- *Utility*: does replacing labels with discovered clusters reduce held-out perplexity / MDL of a sequence model? (Merges that are real should not hurt predictive power.)
- *Blinded expert review* of top-N proposals (ask SFU/Bologna/Oxford PE experts; present shuffled with decoys).

**Risks & mitigations.**
- Image access / quality / licensing → start with line art; secure CDLI permission in month 1; fall back to proto-cuneiform-only methodological paper + PE line art.
- Photo quality (RTI-derived stills, damage, curvilinear incised signs) → detector may be poor on photos; line-art-only version is still a novel contribution.
- Transliteration ↔ image alignment ambiguity (damaged lines, reading order) → restrict to well-preserved tablets; confidence thresholds.
- Hand copies are themselves human interpretations (annotator bias re-enters) → report photo vs. line-art results separately; flag it as a limitation.
- Scoop risk by SFU group → contact them early; a collaboration or at least awareness is valuable.

**Scope (6–9 months, 1–2 people, free GPU).**
- M1: data audit, CDLI permissions, scraping metadata, ATF parsing, reading-order conventions. 
- M2: manual boxing of ~80 line-art tablets; baseline detector. 
- M3–4: weak-supervision bootstrap loop; held-out evaluation; proto-cuneiform replication. 
- M5–6: SSL token embeddings, clustering, synthetic-injection and stability evaluation. 
- M7: photos (stretch), expert review, write-up. 
- Compute: YOLO-n/ViT-S on 64–128px crops — fits Colab/Kaggle T4 comfortably.
- MVP (guaranteed deliverable): line-art PE detector + aligned token dataset + evaluation. Research upside: allograph findings.

**Software-engineering angle** (course is ASE): reproducible data pipeline (DVC), annotation tool integration (Label Studio/CVAT), tested ATF parser, CI for experiments, licence-compliant release design.

---

### 4.2 TOP 2 — Numeracy-Grounded Semantic Induction: Inferring What Undeciphered Proto-Elamite Signs Count

**Problem statement.** The part of PE we *do* understand — numerals and metrological systems — co-occurs with undeciphered signs in every entry. The number system chosen (sexagesimal for discrete animals/humans/objects, bisexagesimal for rations, capacity for grain, etc.) and the magnitudes carry semantic information about *what was counted*. Can we use this as distant supervision to infer semantic categories of undeciphered signs, without a translation key?

**Novelty claim.** P7 disambiguates numerals and notes content–magnitude correlations, but does not turn the numeracy into a *semantic labelling* signal for the rest of the sign inventory [G8]. P1/P2 learn sign similarity from co-occurrence only. Novel: (1) numeral-supervised sign embeddings; (2) calibrated, leave-known-out-evaluated semantic category predictions for undeciphered signs; (3) (CV variant) show whether *visual form* of complex graphemes predicts commodity class beyond context (tests P2's compositionality claim with an extrinsic signal).

**Data.** CDLI ATF (free), P7's disambiguation outputs / test set (check availability — contact authors), Dahl sign images (for visual variant), proto-cuneiform ATF as proxy where commodity meanings are known (Englund's work).

**Method sketch.**
1. Parse entries → (sign span, numeral, candidate systems). Use unambiguous numerals (1,899 per P7) + P7-style disambiguation for others (propagate uncertainty as soft labels).
2. Train a small model (BiLSTM/Transformer; optionally with image embeddings per token) to predict number system and log-magnitude bin from the sign span + header sign.
3. Extract per-sign attributions (integrated gradients / ablation) and learned embeddings; cluster signs into semantic categories; produce a ranked table "sign → P(counted in capacity system), P(sexagesimal), …".
4. Multi-task variant with header prediction (P3) and tablet-level topic (P1).

**Evaluation plan.**
- *Leave-known-out*: pick the small set of PE signs with broadly accepted meanings (e.g., grain/capacity-related containers, livestock signs, worker/person signs — build list from Dahl 2005, Englund, P6/P7 mentions such as M288 container, M346 "sheep", M054 "yoke", M388 person/class marker; *verify every gloss with literature before use*). Hide them from any semantic prior; check whether predicted categories match. Report accuracy vs. frequency-matched random baseline.
- *Proxy replication* on proto-cuneiform where many commodity signs are understood: train same pipeline, measure category recovery (macro-F1), matched corpus size.
- *Label-permutation null*: shuffle numerals across entries within tablet type; the signal should vanish.
- *Calibration*: reliability diagrams; only report predictions above calibrated thresholds.
- *Consistency with independent evidence*: agreement with P1 LDA topics / P6 clusters, measured, not assumed.

**Risks.** Circularity (number-system values themselves partly inferred from content by earlier scholars — must document which assumptions feed labels); small number of known signs → high-variance evaluation; mostly NLP rather than CV (mitigate with the visual-compositionality sub-study); overlap with SFU group's ongoing work.

**Scope.** Most feasible of the three (text data freely available, CPU/T4 enough). 1 person, ~6 months. MVP: numeral parser + number-system prediction + leave-known-out results. Could be combined as Phase 2 of Top 1 for a 2-person team (one CV, one sequence modelling).

---

### 4.3 TOP 3 (stretch / smaller) — Testing Cross-Script Sign Correspondences with Visual and Distributional Evidence

**Problem statement.** Desset et al. (2022) propose PE↔LE sign correspondences without a stated method; Dahl (2023) argues similarities may be incidental. Similarly, PE shares some sign shapes/numerals with proto-cuneiform. Can we quantify whether proposed correspondences are more visually and distributionally consistent than chance?

**Novelty claim.** First quantitative, null-controlled test of the PE↔LE correspondence table [G9]; method generalises (Gromov-Wasserstein/OT between sign embedding spaces, cf. unsupervised bilingual lexicon induction) to any pair of scripts.

**Data.** PE sign images + CDLI corpus; LE sign forms (Desset et al. 2022 tables; Unicode LE proposal L2/21-233 https://www.unicode.org/L2/L2021/21233-linear-elamite.pdf [V-meta]); proto-cuneiform sign list/fonts + CDLI ATF. LE inscription corpus is very small and image licensing unclear.

**Method.** Visual similarity (SSL embeddings, shape-context / skeleton matching) + distributional role (position in entry, adjacency to numerals, co-occurrence) → cost matrix → (a) score the Desset mapping vs. 10k random mappings with matched sign-frequency constraints; (b) unsupervised OT alignment and check overlap with the proposed table. Positive control: PE↔proto-cuneiform numerals (known shared forms/values) must be recovered.

**Evaluation.** Permutation p-values; positive-control recovery; sensitivity to embedding choice. A *negative* result (Desset mapping indistinguishable from chance on PE distributional evidence) is publishable and useful.

**Risks.** LE corpus too small for distributional evidence; visual similarity of simple geometric signs is inherently high (inflated false positives → strong nulls needed); politically/scholarly sensitive topic—tone matters. **Scope:** 3–4 months; better as a chapter or workshop paper than a whole thesis.

---

## 5. Cross-cutting: How to Evaluate When Ground Truth Is Unknown (reusable framework)

1. **Matched proxy scripts** with known answers, degraded to PE's statistics (corpus size, Zipf, hapax ratio, numeral density). Proto-cuneiform is the best proxy (same era, same genre, CDLI-hosted).
2. **Leave-known-out**: the understood subset of PE (numerals, metrology, a few object signs) as held-out ground truth.
3. **Synthetic injection**: plant known structure (fake allographs, fake mergers, shuffled labels) and measure recovery → calibrated error rates.
4. **Null models / permutation tests** for every claim (lesson from Rao vs. Sproat).
5. **Stability/consensus** across seeds, architectures, algorithms (P1's "stable clusters").
6. **Predictive utility** (held-out perplexity / MDL) as an intrinsic check.
7. **Pre-registered, blinded expert review** with decoys, reported as agreement rates — not as proof.

---

## 6. Biggest Risks (overall)

1. **Data access & licensing of images** (CDLI non-commercial; museum copyright; RTI originals may not be public). Mitigation: line art first, request research access early, release references not pixels.
2. **Novelty/scoop**: one active group dominates PE computation (P1–P8). Mitigation: position explicitly on G1/G2/G8; contact them; read P8/P9.
3. **Domain expertise**: PE reading conventions (right-to-left, entry structure, sign-list versions changing over time — P6 fn. 2). Need an Assyriologist contact.
4. **Over-claiming**: "decipherment" language will not survive review. Frame as sign-inventory, allography, semantic category, and hypothesis-testing tools.
5. **Compute** is *not* a real risk (small images, small corpora).

---

## 7. Open Questions for PE-B / the user

- Does the user have any Assyriology contact (Oxford/Dahl, Bologna/Kelley, SFU/Sarkar)? This changes feasibility of Top 1 a lot.
- Is a "CV project" strictly required? If yes, Top 1; if a mixed CV+NLP is fine, Top 1 + Top 2 as a 2-person project.
- Need to verify: number of PE tablets on CDLI with photos vs. line art only (scrape catalogue CSV); availability of P7 test set; whether Louvre RTI data can be obtained.
