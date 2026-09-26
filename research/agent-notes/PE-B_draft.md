# PE-B Draft: Proto-Elamite CV Project, Data / Evaluation / Feasibility-First

Agent PE-B, 2026-09-16. Lens: what data really exists, what domain experts need, what can be checked, and what a 6–9 month Master's project can realistically deliver.

---

## 0. Bottom line

- **Full decipherment ("meaning without a translation key") can't be defended as a Master's deliverable.** A team of Assyriologists and computational linguists at SFU/UBC/Bologna/Uppsala has worked on Proto-Elamite (PE) with ML since 2019. They report progress on structure (headers, numerals, complex graphemes, candidate sign merges), not on meaning or language.
- **Gap for a CV project:** every published PE ML study I could verify works on **transliterations** or on **Dahl's idealised "archetype" sign drawings**, not on photos of the actual clay. Born et al. 2023 say so directly: they turned the transliterated corpus into image sequences by replacing each sign name with Dahl's drawing. Kelley et al. 2022 name bias introduced during transliteration as a problem. Nobody has published a real image-grounded PE sign dataset, even though RTI captures of ~1,100 Louvre PE tablets have been described as public on CDLI since 2012.
- **Most defensible project:** a weakly supervised pipeline that links CDLI transliteration tokens to regions on real tablet images. On top of that sits one expert-checkable use:
  - (a) reading numeral notations from the image and checking the tablet's arithmetic, or
  - (b) auditing transliterations and allographs (variant forms of the same sign).
- **Fallback / alternative:** ranking candidate fragment joins against the known Louvre joins.

---

## 1. Literature and data check (verified, with URLs)

Status key: **[V]** = I fetched or read the source (abstract or full text). **[S]** = seen only in search snippets or secondary summaries, so check before citing in a proposal.

### 1.1 Proto-Elamite computational work (the direct prior art)

| # | Citation | What it does / data | Relevance |
|---|---|---|---|
| P1 | Born, Kelley, Kambhatla, Chen, Sarkar (2019). *Sign Clustering and Topic Extraction in Proto-Elamite*. LaTeCH-CLfL @ NAACL, pp. 122–132. https://aclanthology.org/W19-2516/ **[V]** | Hierarchical clustering, n-grams, LDA on CDLI transliterations. Replicates expert findings and suggests new sign relations. Code: https://github.com/sfu-natlang/pe-decipher-toolkit (LGPL-3.0; data copy dated 2018-06-02) **[V]** | Text-only baseline. Its code gives us corpus loaders. |
| P2 | Born, Kelley, Monroe, Sarkar (2021). *Compositionality of Complex Graphemes in the Undeciphered Proto-Elamite Script using Image and Text Embedding Models*. Findings of ACL-IJCNLP 2021, pp. 4136–4146. https://aclanthology.org/2021.findings-acl.362/ **[V: abstract]** | Image-aware LM over sign glyph images. Finds that the meaning of complex graphemes is partly compositional (outer component dominates). | Uses glyph images, not tablet photos. |
| P3 | Kelley, Born, Monroe, Sarkar (2022). *Image-aware language modeling for Proto-Elamite*. Lingue e linguaggio 2/2022, pp. 261–294. https://rivisteweb.it/doi/10.1418/105965 **[S]** | Summary says it tackles biases introduced into the data during transliteration. | **Names the gap** we want to address: transliteration bias. |
| P4 | Born, Monroe, Kelley, Sarkar (2022). *Sequence Models for Document Structure Identification in an Undeciphered Script*. EMNLP 2022, pp. 9111–9121. https://aclanthology.org/2022.emnlp-main.620/ **[V: abstract]** | Unsupervised evidence for "header" signs (the sign that opens a tablet). | Document-structure prior for layout parsing. |
| P5 | Kelley, Born, Monroe, Sarkar (2022). *On Newly Proposed Proto-Elamite Sign Values*. Iranica Antiqua 57. doi:10.2143/IA.57.0.3291506. PDF: https://anoopsarkar.github.io/papers/pdf/IA57001.pdf **[V: pp.1–3]** | Applies Desset et al.'s Linear Elamite sound values to the PE corpus. Warns about the large time gap between the scripts and says the PE syllabary hypothesis "remains as yet unproven". Data: https://github.com/sfu-natlang/pe-sign-value-data | Evidence against overclaiming. The LE→PE link is a hypothesis, not a key. |
| P6 | Born, Monroe, Kelley, Sarkar (2023). *Learning the Character Inventories of Undeciphered Scripts Using Unsupervised Deep Clustering*. CAWL 2023, pp. 92–104. https://aclanthology.org/2023.cawl-1.11/ **[V: full text]** | VAE + context models (LSTM/Transformer) for "script clustering". PE data: ~1,581 tablets, ~1,500-sign working list, **~35k tokens rendered with ~1,319 Dahl archetype images**. PE results judged only qualitatively with experts (e.g. proposed merges M362~a with M362; M209~a with M210~f). | **Key gap source**, detailed in §2. |
| P7 | Born, Monroe, Kelley, Sarkar (2025). *Disambiguating Numeral Sequences to Decipher Ancient Accounting Corpora*. arXiv:2502.00090 (rev. Apr 2025). https://arxiv.org/abs/2502.00090 **[V: abstract]** | A PE numeral can have up to 4 readings (decimal, sexagesimal, bisexagesimal, capacity). Enumerates candidate readings plus a bootstrapped classifier, and releases a test set. Numeric tokens outnumber textual ones. v1 wrongly used values from Englund 1996, corrected in v2. | Text-only numeral work. The **image-side counterpart is open**. The correction also shows that even the reference data is fragile. |
| P8 | Monroe, Kelley, Born, Sarkar (2025). *Recent Progress in Deciphering Proto-Elamite*. Near Eastern Archaeology 88(4): 314–323. https://www.journals.uchicago.edu/doi/10.1086/738240 **[S: paywalled, 403]** | Overview of BiLSTM, HMM and topic-model results. | State-of-the-field summary. |
| P9 | Kelley, K. (2026). *Proto-Elamite: Writing and Society in Early Iran*. Cambridge Elements in Writing in the Ancient World. https://www.cambridge.org/core/elements/protoelamite/3684B7262E21A8B6AF8657D948A5B1A6 **[V: abstract]** | ~1,700 tablets. Argues for combining maths, digitisation and computation. | Most recent monograph-length overview. |
| P10 | Dahl, J. L. (2019). *Tablettes et fragments proto-élamites* (Textes Cunéiformes du Louvre 32). Sign list pp. 185–227. **[S: bibliographic]** | 121 previously unpublished Louvre tablets and fragments. Hypothesised syllabary of ~100 signs, 61 named. | Reference sign list and expert standard. |
| P11 | Dahl, J. L. (2012). *New and old joins in the Louvre proto-Elamite tablet collection*. CDLN 2012:6. https://cdli.earth/articles/cdln/2012-6 **[V]** | 10 new plus 4 earlier joins, some based only on "scribal design" with no physical contact. Unfired fragments differ in colour. | **Ground truth for join-finding** (small). |
| P12 | Dahl, J. L. (2002). *Proto-Elamite Sign Frequencies*. CDLB 2002:1. https://cdli.earth/articles/cdlb/2002-1 **[S]** | Early frequency statistics. | Background. |
| P13 | Englund, R. K. (2004). *The State of Decipherment of Proto-Elamite*. In Houston (ed.), *The First Writing*. PDF: https://cdli.earth/files-up/publications/englund2004c.pdf **[S]** | Numeral systems (sexagesimal, bisexagesimal, decimal, capacity), metrology, and comparison with proto-cuneiform. | Domain rules for numeral parsing and arithmetic checks. |
| P14 | Pandey, A. (2023). *Proposal to encode Proto-Elamite in Unicode*. L2/23-196. https://www.unicode.org/L2/L2023/23196-proto-elamite.pdf **[V: pp.1–5]** | Core repertoire of **1,636** signs with CDLI images, plus ~350 names found only in transliterations. Across CDLI sources: **6,607 raw sign names, 2,011 distinct**. The sources disagree: EPS 1,636 / PDF 1,434 / JSON 1,796 / corpus 1,741. §3 lists open questions for experts. Unicode status per search: still an ongoing project in 2025, not encoded **[S]**. | **Hard evidence that the sign list is not settled.** Directly motivates variant/allograph work. |
| P15 | Desset, Tabibzadeh, Kervran, Basello, Marchesi (2022). *The Decipherment of Linear Elamite Writing*. ZA 112(1): 11–60. https://www.degruyterbrill.com/document/doi/10.1515/za-2022-0003/html **[V: abstract]** | LE decipherment built on 8 silver beakers. Proposes that PE and LE are one system at different stages. | The user's "key" analogy, but it covers LE, not PE (see P5). |
| P16 | Hatamti Linear Elamite database, Univ. of Liège (Desset, Desert et al., 2024–25). https://hatamti-elam.uliege.be/doc_about **[V]** | 45 LE inscriptions, 69 signs, 72 allographs, images from Louvre/NMI. **PE not covered. No licence stated.** | Only a possible cross-script extension. Licence unclear. |

### 1.2 Data sources for PE (availability, licensing, size)

| Source | Content | Size | Licence / terms | Notes |
|---|---|---|---|---|
| CDLI (cdli.earth) catalogue + transliterations | ATF transliterations of nearly all PE tablets | ~1,600–1,700 tablets (sources differ: 1,581 in P6, ~1,700 in P9); ~35k tokens (P6) | Text CC-BY 4.0 / academic reuse **[V]** | Bulk dump https://github.com/cdli-gh/data was **last updated Aug 2022** **[V]**. Newer data via REST API https://cdli.earth/docs/api and https://github.com/cdli-gh/framework-api-client **[S]**. |
| CDLI images (photos, flatbed scans, line art) | Louvre (Sb numbers) and NMI Tehran | CDLN 2019 news: 486 NMI tablets (MDP 26) imaged and uploaded; "near complete" Louvre + NMI sets online **[S]** | **Non-commercial use only; copyright stays with the owning museums** (https://cdli.earth/terms-of-use) **[V]** | Research use is fine. **Redistributing crops needs permission**, so release annotations plus CDLI IDs and URLs, not pixels. |
| RTI of Louvre PE tablets (Oxford/Southampton, 2012) | Relightable RTI/PTM captures | ~1,100 tablets; a news piece claims ~19,000 sign instances **[S]** | Described as free public access on CDLI **[S]** | **Top feasibility check for month 1:** can RTI files still be downloaded in bulk today? If only rendered stills exist, synthetic relighting is limited. |
| Dahl archetype sign images (EPS) | One idealised drawing per sign name | 1,636 (EPS zip) / 1,332 on GitHub | **CC-BY 4.0** https://github.com/cdli-gh/proto-elamite_data **[V]** | Templates for ProtoSnap-style alignment and synthetic training data. |
| SFU pe-decipher-toolkit / pe-sign-value-data | Cleaned corpus copy (2018), sign PNGs (PE_mainforms, PE_num), notebooks | — | LGPL-3.0 **[V]** | Corpus version is older than the current CDLI one, so versions must be reconciled. |
| Token lists (MPIWG mirror) | signs.json / words.json | 1,796 sign names | — | URL cited in P6/P14: https://cdli.mpiwg-berlin.mpg.de/resources/token-lists **[S]**. May have moved. |
| Transfer datasets from cuneiform | See §1.3 | — | Mixed | Source domains for pretraining only. Wedge-cuneiform ≠ PE graphic style. |

### 1.3 Adjacent CV / cuneiform / undeciphered-script work

| # | Citation | Key facts | Gap it exposes |
|---|---|---|---|
| C1 | Dencker, Klinkisch, Maul, Ommer (2020). *Deep learning of cuneiform sign detection with weak supervision using transliteration alignment*. PLOS ONE 15(12): e0243039. https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0243039, code https://github.com/CompVis/cuneiform-sign-detection-code **[V: abstract]** | Aligns transliterations to images to train detectors iteratively. ~1,800 Neo-Assyrian tablets; gold boxes on only 81 tablets (8,109 signs, 186 classes). | **Recipe we can port.** Never applied to PE, which has far more classes and a spreadsheet-like layout. |
| C2 | Williams, Su, Schloen, Prosser, Paulus, Krishnan (2025). *DeepScribe: Localization and Classification of Elamite Cuneiform Signs via Deep Learning*. ACM JOCCH 18(2). arXiv:2306.01268 **[V: summary]** | Achaemenid Elamite *cuneiform* (Persepolis Fortification Archive), not PE. ~5,000 images, ~100k boxes. RetinaNet mAP 0.78; top-5 accuracy 0.89. | Stated limits: end-to-end transliteration isn't reliable yet; struggles with rare signs, damage and lighting; needs context. |
| C3 | Stötzner, Homburg, Mara (2023). *CNN based Cuneiform Sign Detection Learned from Annotated 3D Renderings and Mapped Photographs with Illumination Augmentation*. ICCV 2023 workshops. arXiv:2308.11277 **[V: abstract]** | Training on 3D renderings plus relit views improves detection on photos. ~500 annotated tablets (HeiCuBeDa/MaiCuBeDa). | Supports **relighting augmentation**, which matters if PE RTI is usable. |
| C4 | HeiCuBeDa Hilprecht. 1,977 3D tablets (ED IIIb–Old Babylonian) with MSII renderings, Open Access. https://heidata.uni-heidelberg.de/dataset.xhtml?persistentId=doi:10.11588/data/IE8CCN **[V: summary]** | No PE. | Pretraining/relighting source only. |
| C5 | Chen, Agarwal, Berg-Kirkpatrick, Myerston (2023). *CuneiML: A Cuneiform Dataset for Machine Learning*. JOHD 9(1). https://openhumanitiesdata.metajnl.com/articles/10.5334/johd.151 **[V: summary]** | 38,947 photos of Sumerian/Akkadian tablets with transliterations and line art. | No PE, but its CDLI-image handling can be reused. |
| C6 | Mikulinsky et al. (2025). *ProtoSnap: Prototype Alignment for Cuneiform Signs*. ICLR 2025. arXiv:2502.00129, https://github.com/TAU-VAILab/ProtoSnap **[V: summary]** | Unsupervised snapping of prototype skeletons onto photographed signs using diffusion features. The structure-conditioned synthetic data helps with rare signs. | **Fits PE well because Dahl's archetype drawings are exactly the prototypes.** Diffusion features may be too heavy for a free-tier GPU (DINOv2 is the lighter fallback). |
| C7 | Che, Garcés Arias, Niaz, Bender, Jiménez (2026). *Automated sign detection across the Electronic Babylonian Library*. arXiv:2606.22608 **[V: abstract, preprint]** | Deformable DETR over 87,668 fragments, ~2.9M detections; n-gram similarity. | Scale reference. Still sensitive to damage and layout. |
| C8 | Poudel et al. (2026). *Zero-Shot SAM2 Segmentation and ViT Recognition of Elamite Cuneiform Symbols* (EpigraphNet). arXiv:2608.18544 **[V: abstract, preprint]** | PFA Elamite cuneiform. 1,239 images, 141 classes, 86.4% top-1. | Classifies pre-segmented symbols only. Not PE. |
| C9 | Corazza, Tamburini, Valério, Ferrara (2022). *Unsupervised deep learning supports reclassification of Bronze Age Cypriot writing system*. PLOS ONE 17(7): e0269544. https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0269544 **[V: summary]** | Sign2Vec clustering of real hand-drawn sign images. Argues Cypro-Minoan is one unified script. | Shows palaeographic clustering on real (drawn) signs can support expert claims, and Cypro-Greek offers a known-answer test. |
| C10 | Sommerschield et al. (2023). *Machine Learning for Ancient Languages: A Survey*. Computational Linguistics 49(3): 703–747. https://aclanthology.org/2023.cl-3.5/ **[V: abstract]** | Task taxonomy: digitisation → restoration → attribution → … → decipherment. Stresses collaboration with specialists. | Framing and evaluation norms. |
| C11 | Assael, Sommerschield et al. (2022). *Restoring and attributing ancient texts using deep neural networks* (Ithaca). Nature 603: 280–283. https://www.nature.com/articles/s41586-022-04448-z **[V: summary]** | Historians alone 25% → historians with Ithaca 72% on restoration. | **Human-plus-AI evaluation protocol** we can copy at small scale. |
| C12 | Virtual Cuneiform Tablet Reconstruction (Collins, Woolley et al.), 3D fragment matching. https://www.researchgate.net/publication/269101067 **[S]** | First automated joins of 3D-scanned cuneiform fragments. | No PE 3D scans exist that I could find, so 2D/text joins are the only realistic route. |
| C13 | eBL Fragmentarium (LMU, Jiménez): join suggestions from string alignment and n-grams over transliterations. ~1,200 joins found. **[S: secondary summaries]** | Text-based join discovery works at scale for Akkadian. | Not applied to PE. PE's small size makes manual checking feasible. |

**Not verified / couldn't access (don't cite without checking):** full text of P3 and P8 (paywalled); whether PE RTI files can still be downloaded; the "19,000 sign instances" figure; Dahl's current Oxford project names and status; "Web Science for Ancient History: Deciphering Proto-Elamite Online" (Academia.edu returned 403; an Oxford/Southampton crowdsourcing annotation platform existed per snippets). Search summaries claiming a "scholarly consensus" on the LE decipherment are secondary; treat LE as widely accepted but with PE implications contested (P5).

---

## 2. Gap mining (explicit limitations → opportunities)

| Gap | Evidence | Opportunity |
|---|---|---|
| G1. No PE model has seen real clay | P6 §3: PE input is transliterations with each sign name replaced by Dahl's archetype image. Those drawings "smooth over many of the irregularities of the original shapes drawn on clay". P2 and P7 are also text or glyph based. | Build the **first image-grounded PE sign-token dataset** from real tablet images, weakly aligned to transliterations. |
| G2. Transliteration is an interpretive bottleneck with known bias | P3 addresses biases introduced during transliteration. P6 (Limitations): "cannot be compared to any known ground truth". P6 notes Kelley 2022's fixed-vocabulary softmax is biased toward experts' divisions. | Image evidence can **check transliteration choices independently**: flag suspicious readings and test proposed merges on real tokens instead of archetypes. |
| G3. The sign inventory is unstable | P14: 2,011 distinct names across CDLI sources, which disagree with each other. Sign counts range from 287 to 1,623 depending on method (P6 fn. 2). "~" variant notation encodes expert uncertainty. Unicode not yet encoded. | Allograph / variant evidence from real token distributions, directly usable for sign-list and Unicode work (P14 §3 lists expert questions). |
| G4. PE numerals are handled only in text | P7 disambiguates numeral systems from transliterations. Numerals are the majority of tokens and their systems are well understood (P13). | **Read numerals from images and check the tablet's arithmetic**, which is objective and expert-checkable. |
| G5. Existing Elamite-cuneiform OCR isn't reliable end-to-end | C2 limitations: rare signs, damage, lighting, need for context. C8 classifies pre-segmented crops only. | Use a context-constrained **alignment** task (transliteration known) rather than open OCR. That is achievable at small scale. |
| G6. Joins are still found by hand | P11: 10 new joins by one expert walking the Louvre stores, some based only on scribal design. C13's text-based join finding hasn't been applied to PE. | A candidate-join ranker evaluated on known joins. Output is a short list for curators to check. |
| G7. Qualitative-only evaluation on the undeciphered script | P6 evaluates PE only with experts, and only reports a few merges. | A **quantitative protocol** without circularity: known-script analogues, planted-error recovery, arithmetic consistency, and blind expert precision@k. |
| G8. The PE↔LE link is unproven | P5: large time gap; syllabary unproven. | Keep this out of scope, or at most as a clearly labelled exploratory visual-similarity appendix. **Don't build the project on it.** |

---

## 3. What experts actually need (domain view)

Based on the sources above; to be confirmed with an actual PE specialist, ideally one of the SFU/Bologna/Uppsala/Oxford group.

1. **Image-anchored concordance:** "show me every M388 in clay across the corpus". Today scholars reason from transliterations or archetype drawings (G1).
2. **Collation support:** flag readings where the image disagrees with the transliteration, then check the physical tablet or RTI. Low-risk, high-value, and easy to verify.
3. **Variant / allograph resolution:** evidence for or against "~a/~b" merges (G3, P14 §3).
4. **Numeral and metrology checks:** arithmetic consistency of entries against totals, plus numeral-system assignment (G4).
5. **Joins:** ranked candidates for the Louvre fragments (G6).
6. **Not needed / actively harmful:** press-release "AI deciphers Proto-Elamite". Experts are wary of this. Look at how carefully P5 treats even peer-reviewed sound values.

---

## 4. Known pitfalls (the project must design around these)

- **Tiny, long-tailed corpus.** ~35k non-trivial tokens; most sign types are rare or hapax (appear once). Classifiers won't learn the tail, so treat rare signs by alignment or retrieval, not classification.
- **Label noise and version drift.** CDLI bulk dump frozen Aug 2022; SFU copy from 2018; sign names revised over time (P14). Pin a corpus version, keep a mapping table, and report inter-version differences.
- **Circular evaluation.** Training on transliteration labels and then "discovering" the transliteration's own distinctions proves nothing. Evaluate merges and splits on (i) known-script analogues with gold labels, (ii) planted perturbations, (iii) blind expert rating. Never claim a PE result is "correct", only "supported" or "flagged".
- **Heterogeneous imaging.** Flatbed scans, photos, RTI, line art; different lighting per museum. Stratify results by image type.
- **Layout.** Obverse and reverse, rotated tablets, numerals sharing lines with signs, entries running across the reverse. Alignment needs a layout model, not line-by-line OCR.
- **Damage and fragments.** Many tablets are partial; the transliterations use "x" and "[...]" for breaks.
- **Licensing.** Images are non-commercial and museum-owned. Publish code plus annotations (bounding boxes keyed to CDLI P-numbers and image URLs), not image crops, unless CDLI/Louvre give permission.
- **Overclaiming.** Frame outputs as hypotheses for experts, with calibrated confidence.
- **Expert time is scarce.** Budget ~5–10 hours of expert review total. Design every evaluation to fit that (top-k lists, blind forms).

---

## 5. Candidate ideas (6), then top picks

| # | Idea | Novelty (gap) | Verifiability | Feasibility | Verdict |
|---|---|---|---|---|---|
| I1 | **PE-Ground:** weakly supervised alignment of transliteration tokens to real tablet images (Dencker-style EM + Dahl archetypes as ProtoSnap-style templates) | G1, G5 | High (small gold set) | Medium–High | **TOP (foundation)** |
| I2 | **Numeral reader + arithmetic auditor from images** | G4 | Very high (arithmetic is objective) | Medium | **TOP** |
| I3 | **Transliteration and allograph auditor** (image-token clustering; flag mislabels; test merges on real clay) | G2, G3, G7 | Medium–High (planted errors + expert top-k) | Medium (needs I1) | **TOP** |
| I4 | Fragment join-candidate ranker (text profile + visual cues: line spacing, sign size, ruling, clay tone) | G6 | Medium (≈14 known joins; tiny positive set) | Medium; museum confirmation out of our hands | Strong alternative |
| I5 | Scribal-hand / archive clustering from palaeography | P6 related work (scribal hands) | Low (no ground truth for PE hands) | Medium | Reject as main project |
| I6 | "Semantic class without a key": predict the commodity class of undeciphered signs from the numeral system they are counted in (capacity → grain, etc.), then validate on signs with accepted meanings | Closest to the user's pitch; builds on P7/P13 | Medium; risk of circularity (numeral systems are already partly assigned by semantics) | High (text-only) | Keep as a small chapter inside I2, clearly labelled as a hypothesis generator |

### Recommended package

**I1 is the core.** Then do **one** of I2 (safer, more objective) or I3 (closer to the sign-list debate). I4 is the backup if image access fails.

---

## 6. Top idea A: PE-Ground (image-grounded sign-token dataset via weak alignment)

**Problem.** PE ML so far works on transliterations or idealised drawings (G1). Scholars can't query or check signs as they appear on clay at corpus scale.

**Novelty claim.** First real-image, token-level grounding of the PE corpus. Transliteration alignment (C1) is adapted to a script with ~1.6k+ sign types and a spreadsheet-like numeric layout. CC-BY archetype drawings (P14 EPS set) serve as zero-shot templates (C6-style) to bootstrap before any manual labels.

**Data.**
- CDLI transliterations, pinned version (API export; compare against the 2022 dump).
- CDLI images of Louvre (Sb) and NMI tablets.
- RTI captures if downloadable (month 1 check).
- Dahl EPS archetypes (CC-BY).
- Optional pretraining: HeiCuBeDa renderings (C4), CompVis cuneiform dataset (C1).

**Method sketch** (consumer GPU, e.g. 8–12 GB, or Colab/Kaggle free tier):
1. **Tablet preprocessing.** Split obverse/reverse from CDLI composite photos (heuristics plus a small segmenter), deskew, detect ruling lines and cases (Hough transform / projection profiles; PE accounts have strong row structure).
2. **Candidate proposals.** Class-agnostic "sign blob" proposals: SAM/SAM2 zero-shot plus morphology (cf. C8), or a small detector pretrained on cuneiform.
3. **Template scoring.** Embed proposals and rendered archetypes (augmented with stroke-width jitter, relighting, erosion noise) with a frozen DINOv2-S/B. Fine-tune lightly with contrastive loss once pseudo-labels exist.
4. **Sequence alignment.** Within each row/case, run Viterbi/DTW alignment between the ordered transliteration tokens and the ordered proposals, allowing insertions and deletions for damage. The transliteration constrains *which* signs are present, which makes this far easier than open OCR.
5. **EM bootstrapping** (C1): keep high-confidence alignments → fine-tune embedding/detector → realign. 3–4 rounds.
6. **Output.** A JSON dataset: {P-number, image URL, side, bbox, transliteration token, sign name, confidence, alignment path}, plus a simple web viewer (the "Software Engineering" deliverable) for concordance queries and collation flags.

**Evaluation.**
- **Gold set:** 40–60 tablets (≈3–5k boxes) hand-annotated with the Dahl sign list (feasible in ~60–80 h using a CVAT-style tool). Stratify by image type (photo / flatbed / RTI), museum, tablet size and damage.
- **Metrics:** box mAP@0.5 (class-agnostic); **token alignment accuracy** (the predicted box for token *i* overlaps gold, IoU ≥ 0.5); per-frequency-bucket accuracy (head / mid / tail signs); coverage (% of tokens aligned with confidence > τ at ≥ 90% precision).
- **Baselines:** (a) template matching on raw pixels; (b) DINOv2 nearest-archetype without sequence constraints; (c) the Dencker pipeline off the shelf; (d) ablations without EM, without relighting augmentation, without layout.
- **Inter-annotator check:** a second annotator on 10 tablets (Cohen's κ on sign labels; IoU agreement on boxes). This bounds the achievable score.
- **Expert spot-check:** 200 randomly sampled high-confidence alignments rated right/wrong by a PE specialist (≈1 h).

**Risks → mitigations.**
- Images too poor or not bulk-downloadable → restrict to the best-imaged subset (e.g. Louvre RTI stills); I4 as fallback.
- Layout parsing harder than expected → start with the "header + entries" tablets that have clean rulings.
- Archetypes too far from real clay → rely on EM plus the gold set to fine-tune; report the domain gap as a finding.
- Licence → publish annotations and URLs, not crops.

**Scope** (1–2 people, 7–8 months):
- M1: data access audit, corpus pinning, annotation guidelines.
- M2–3: preprocessing, proposals, gold set.
- M4–5: alignment and EM.
- M6: evaluation and viewer.
- M7–8: one of B/C plus write-up.

---

## 7. Top idea B: image-based numeral reader and arithmetic auditor

**Problem.** Numeral notations are most of PE's tokens and the best-understood part of the script (P13). The notation is ambiguous (P7), and transliteration errors in numerals break metrological analyses. There is no image-based numeral reading.

**Novelty claim.** First system that reads PE numeral notations from images and checks them against the tablet's own internal arithmetic (entry sums vs. totals on the reverse). This yields **objective, label-free verification** and a ranked list of tablets where image, transliteration and arithmetic disagree, ready for collation. It complements text-only P7 (G4).

**Data.**
- PE-Ground crops restricted to numeral signs (N-series), which have a small class set and high frequency, so this is learnable.
- CDLI transliterations and numeral-system tables from Englund/Damerow (P13).
- The P7 test set (check its release and licence).

**Method.**
1. Numeral-sign detector/classifier (small classes; heavy augmentation; counting of repeated impressions via instance segmentation or density counting).
2. Grammar-based parser: numeral signs → candidate values in each system (sexagesimal, bisexagesimal, decimal, capacity), with ordering constraints.
3. Constraint solver / ILP: choose system assignments per entry that best satisfy "Σ entries = total" where a total exists. Use P7-style priors from the object sign adjacent to the numeral.
4. Flag discrepancies in three classes:
   - (i) image reading ≠ transliteration;
   - (ii) transliteration arithmetic fails but image arithmetic works (a likely transliteration error, the high-value finding);
   - (iii) both fail (scribal error or damage).

**Evaluation.**
- **Numeral recognition:** per-sign accuracy and count accuracy on the gold set.
- **Arithmetic check rate:** % of tablets with totals whose image-read entries sum correctly. Transliteration-based arithmetic success is the reference/upper bound.
- **System disambiguation:** accuracy against the P7 test set and against Englund's published readings for tablets in the gold set.
- **Planted errors:** corrupt 5% of numeral tokens in the transliteration and measure recall/precision of flag class (ii).
- **Expert check:** the top 30 flagged tablets reviewed by a specialist using CDLI images/RTI (≈2 h). Report precision@10/30 for "real transliteration issue" vs "scribal error" vs "false alarm".
- **Optional I6 chapter:** for signs with accepted meanings, does the image-verified numeral-system distribution predict their commodity class? Report as correlational only.

**Risks.**
- Only a subset of tablets have preserved totals (quantify in month 1; expected to be enough for evaluation, not for training).
- Impression counting on worn clay.
- Capacity-system sign shapes are subtle.
- Finding real errors depends on the quality of the existing transliterations. A low hit rate is still a publishable validation of the corpus.

**Scope.** ~3 months on top of PE-Ground (the numeral subset can start earlier, since numerals are the easiest classes).

---

## 8. Top idea C: transliteration and allograph auditor from real clay

**Problem.** The sign inventory is unsettled (P14: 2,011 distinct names across sources; "~" variants). Born et al. 2023 proposed merges using archetype drawings only, and evaluated them qualitatively (G2, G3, G7).

**Novelty claim.** First test of variant/merge hypotheses on the **distribution of real token images**. Also a mislabel detector producing top-k collation candidates. Evaluation is quantitative and not circular.

**Method.**
1. From PE-Ground crops, learn embeddings: self-supervised (DINOv2 fine-tune / SimCLR) plus a context channel (neighbouring-token embeddings, following P6's finding that context helps).
2. Per sign name, estimate its visual distribution (e.g. a Gaussian mixture in embedding space). Compute:
   - an overlap / two-sample test (MMD) for each pair of "~" variants and each P6-proposed merge;
   - a per-token outlier score, meaning "this crop looks like sign Y, not its label X".
3. Output:
   - (a) a ranked list of variant pairs that are visually indistinguishable on clay, or clearly distinct;
   - (b) a ranked list of suspected mislabels.

**Evaluation (non-circular).**
- **Known-answer analogues:** apply the identical pipeline to a script with gold allographs and real images/drawings (Cypro-Greek from C9, or the Neo-Assyrian CompVis set, C1). Measure how well merge/split decisions recover ground truth (V-measure, AUROC of the MMD test).
- **Planted perturbations on PE:** randomly relabel 2–5% of gold-set tokens and artificially merge a few distinct sign pairs; measure recall/precision.
- **Blind expert evaluation:** mix the top 20 model-flagged mislabels with 20 random tokens, have the specialist rate them blind, and report the precision difference. Do the same for 10 proposed merges vs 10 random sign pairs.
- **Comparison with P6's merges:** report agreement and disagreement. Disagreement is a finding in itself.

**Risks.**
- Most variant signs are rare, giving low statistical power. Report only pairs with n ≥ ~15 tokens each.
- Visual similarity ≠ same sign (P6 itself cautions on M195+M057). Always present results as visual evidence, not identity claims.
- Depends on PE-Ground quality: embedding errors propagate, so use only the gold set plus high-confidence alignments.

**Scope.** ~2.5–3 months on top of PE-Ground.

---

## 9. Alternative / backup: I4 join-candidate ranking

- **Data:** CDLI Louvre fragment images and metadata; known joins from P11 (14) plus any "joins" in CDLI catalogue fields.
- **Method:** a fragment profile made of text features (header signs, numeral systems, sign n-grams; C13-style) and visual features (row height, sign size, ruling spacing, clay colour histogram, break-edge contour descriptors from 2D photos), combined with a learned pairwise ranker.
- **Evaluation:** leave-one-join-out recall@k (k = 5, 10, 20) on known joins; since positives are few, report per-join ranks. Then send the top 20 new candidates to a specialist.
- **Risk:** the positive set is too small to learn much, so results lean on hand-crafted similarity. Physical confirmation needs museum access (out of scope; deliver candidates only).

---

## 10. Cross-cutting evaluation principles (for either top pick)

1. **Pin data versions.** Publish a manifest of CDLI P-numbers, image URLs and transliteration hashes.
2. **Separate "correct" from "supported".** Report accuracy only where ground truth exists (gold boxes, arithmetic, known-script analogues). Report PE hypotheses only as expert-rated precision@k.
3. **Stratify** every metric by image type, museum, sign frequency and damage level.
4. **No test leakage.** Split at tablet level. Keep joined fragments in the same split. Keep the gold set out of EM pseudo-labelling.
5. **Budget expert time** (≤10 h) and design blind forms up front. Contact the SFU/Bologna/Uppsala group early; they are the natural reviewers, and their code and data are open.
6. **Licensing hygiene:** code MIT/Apache; annotations CC-BY with CDLI attribution; no redistributed museum pixels without permission.

---

## 11. Biggest risks (overall, ranked)

1. **Image access and quality** (bulk download, RTI availability, resolution of the NMI flatbed scans). *Check in weeks 1–3; go/no-go gate.*
2. **Expert availability** for the evaluation steps that can't be automated.
3. **Layout complexity** of PE accounts, which makes alignment harder than in C1.
4. **Scope creep toward "decipherment"** and overclaiming. Mitigate with the framing in §0 and the reporting rules in §10.
5. **Long-tail signs** give low statistical power for I3.
6. **Licensing** of derived image data.

## 12. Candid positioning for the user's pitch

"AI that infers meaning without a translation key", reframed defensibly:
- **Structure without a key:** already partly shown in text (P4, P7). We add *image-grounded* evidence.
- **Quantities and bookkeeping logic without a key:** the arithmetic in idea B is objective, and I6 turns it into commodity-class hypotheses.
- **Sign identity without a key:** allograph evidence in idea C.
- **Language / sound values:** out of scope. The Linear Elamite values are a contested bridge (P5), not a key.
