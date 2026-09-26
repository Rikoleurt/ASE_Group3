# Sources

Every external fact this project relies on, with how well it was checked.

**Verification levels**
- **Read** — the primary source was opened and the passage read.
- **Secondary** — taken from a reliable secondary account, not the original.
- **Unchecked** — used, but not confirmed at source. Nothing load-bearing should sit here.

---

## Data

| Source | What we take from it | Licence | Level |
|---|---|---|---|
| [lineara.eu](https://lineara.eu) (M. Navarre) | All 1,883 document transcriptions, via `/documents/<slug>/data.json`; the re-encoded sign crops | Own work CC BY 4.0; SigLA-derived fields **CC BY-NC-SA 4.0** | Read |
| [SigLA](https://sigla.phis.me) (E. Salgarella & S. Castellan) | The sign tracings underlying the above; crop URL pattern `document/<siglum>/<siglum>_<n>.png` | **CC BY-NC-SA 4.0** | Read |
| [Unicode UCD](https://www.unicode.org/Public/UCD/latest/ucd/) | Sign-id to letter-label mapping, from names of the form `LINEAR A SIGN A707 J` | Unicode licence | Read |
| [DAMOS](https://damos.hf.uio.no) (F. Aurora, Univ. of Oslo) | All Linear B transliterations and per-document metadata, via `/ajaxitem/{id}/`; facet counts via `/ajaxgetfilter` | Content **CC BY-NC-SA 4.0**; software GPL-3.0 (site footer) | Read |

**DAMOS access notes**, recorded because both cost time to find and neither is documented:
- **The trailing slash is required.** `/ajaxitem/1` serves the React HTML shell; `/ajaxitem/1/` serves JSON. `/ajaxitemcontent/1` is the opposite — no slash.
- **A missing id returns the shell with HTTP 200**, not a 404, and ids are sparse (5905 and 5920 are gaps below the maximum), so absence must be detected by the payload failing to parse.
- Endpoints were taken from the site's own published bundle (`/dist/static/js/main.*.js`), not guessed.
- Corpus size per `/ajaxgetfilter`: **5,932 documents over 29 collections** — Knossos 4,224, Pylos 1,004, Thebes 363, Mycenae 87, Tiryns 27, Khania 8, plus a long tail including inscribed vases. 281 writer values and 86 stylus values are exposed as facets.
- Each record's `meta` block carries Site, Series, Subseries, Set, **Hand**, Stylus, Seal, Chronology and Preserved. An unattributed hand is written `-`, which must be read as absent rather than as a label.

**Use.** Non-commercial research, held locally, not redistributed. `data/cache/` (Linear A) and `data/damos/` (Linear B) are both gitignored, and both manifests carry per-file checksums so a rebuild is reproducible without shipping the data. Any published output must carry the SigLA credit line for Linear A and the DAMOS credit line for Linear B. Derived measurements computed from the tracings are adaptations and inherit the non-commercial share-alike terms.

**Not used:** `lineara.xyz` carries no licence at all; GORILA plate scans and the INSCRIBE 3D models are not openly licensed.

---

## Literature

### Corazza, Ferrara, Montecchi, Tamburini & Valério (2021)
*"The mathematical values of fraction signs in the Linear A script: A computational, statistical and typological approach"*, **Journal of Archaeological Science 125, 105214**. DOI [10.1016/j.jas.2020.105214](https://doi.org/10.1016/j.jas.2020.105214). Open access, CC BY-NC-ND.

Open-access copies: `https://hdl.handle.net/11585/789546` and `http://hdl.handle.net/2158/1265255`. The publisher and both repositories were unreachable behind bot protection; the full text was retrieved through the Wayback Machine at
`https://web.archive.org/web/20250923102402id_/https://flore.unifi.it/bitstream/2158/1265255/1/Ferrara-Montecchi-Val%c3%a9rio_JAS_125_2021.pdf`

Note the percent-encoding of "Valério": the unencoded form 404s, and the working URL was recovered from the Wayback CDX index (`http://web.archive.org/cdx/search/cdx?url=flore.unifi.it/bitstream/2158/1265255/*`).

| Claim used | Level |
|---|---|
| Table 8 — the twelve values (J 1/2, E 1/4, D 1/6, B 1/5, K 1/10, L2 1/20, F 1/8, H 1/16?, A 1/24?, L3 1/30, L4 1/40, L6 1/60) | **Read** |
| Table 9 — combinations JE 3/4, DD 1/3, BB 2/5 | **Read** |
| H and A printed with "(?)" as tentative | **Read** |
| *"Clay tablet HT 104: Contains a sum and its total: 45 + J + 20 J̣ + 29 = 95. We deduce that J = 1/2."* | **Read** |
| *"As no Linear A inscription containing totals of numeral phrases is without reading or calculation problems … it is difficult to deduce these mathematical values."* | **Read** |
| Method: constraint programming (MiniZinc/Gecode) over logical, statistical and typological constraints, **not** systematic ku-ro arithmetic | **Read** |
| PE 1, verbatim: *"The second entry registers 72 people and 36 GRA + PA, suggesting that each person is assigned or contributes 1/2 of grain. The same proportion appears in the first entry, where 50[ (i.e. 50 plus something) people are registered along with 26 J of GRA + PA. In this case, 26 J corresponds to 26 + 1/2 and the damaged count of people is to be restored as double this amount, hence 53 (Tsipopoulou and Hallager, 1996). This supports the decipherment of J as 1/2."* | **Read** |
| HT 104 gives J = 1/2 *"assuming the damaged J cannot be followed by any additional fractional sign"* | **Read** |
| Constraint (4): *"Any fractional sign or sum of combined fractions … in a numeral phrase is less than 1."* | **Read** |

**What the PE 1 passage does and does not say.** Their direction of inference is: assume J = 1/2, read `26 J` as 26.5, double it, restore the headcount as 53. PE 1 is then offered as *support* for J = 1/2. As written that support has **no discriminating power**: for any proper fraction J the headcount is 52 + 2J, which lies strictly between 52 and 54 and is therefore compatible with the surviving `50[` whatever J is.

The reverse inference — requiring only that the headcount be a whole number and that J be a proper fraction, giving 2J as an integer strictly between 0 and 2, hence **J = 1/2 and the headcount 53 both forced** — is not in the paper. Both ingredients are, however: Constraint (4) is exactly "0 < J < 1", and the ration of 1/2 is established from the intact 72 : 36 entry, which contains no fraction sign at all. So the argument can be assembled from their own materials, and would give a derivation of J = 1/2 independent of HT 104 and of the assumption HT 104 requires.

**The one link not checked.** **Tsipopoulou & Hallager, "Inscriptions with hieroglyphs and linear A from Petras, Siteia", SMEA 37 (1996) 7–46** — the *editio princeps*, cited by Corazza et al. for the restoration of 53. Not available online; not read. An editor restoring a broken headcount is exactly the person who would ask which values are arithmetically possible, so this is the most likely place for the argument to exist already. **Until it is read, novelty is unconfirmed.**
| W and X left unvalued, suspected to be BB and AA | Secondary |
| KH 86.2 re-read as `A A` rather than `A B B` | Secondary |
| Restriction to LM IB; MM II Phaistos readings excluded on dating grounds | Secondary |

### John G. Younger, *Linear A Texts & Inscriptions in Phonetic Transcription*
**The site is offline.** Formerly `people.ku.edu/~jyounger/LinearA/`; reachable only through the Wayback Machine. Snapshots used:

- Index — `https://web.archive.org/web/20231222205430/https://www.people.ku.edu/~jyounger/LinearA/`
- Haghia Triada texts — `https://web.archive.org/web/20231222005230/http://people.ku.edu/~jyounger/LinearA/HTtexts.html`
- Miscellaneous texts — `https://web.archive.org/web/20231222205430/https://www.people.ku.edu/~jyounger/LinearA/misctexts.html`

| Claim used | Level |
|---|---|
| KU-RO = "total"; KI-RO = "owed, deficit"; PO-TO-KU-RO = "grand total" | Secondary |
| HT 9a: *"the total 29+3J+2E equals 31, not 31+J+E"*, with the missing amount placed in the broken entry at side b.1, possibly JE | Secondary |
| HT 13: line .2 broken on both sides — `RE-ZA 5[ ]J[ ]` | Secondary |
| HT 46a: *supra mutila*, entry list physically missing | Secondary |
| HT 116b: *"perhaps the last stroke in the number 6 in a.3 OLE+MI 6 was a slip"* | Secondary |
| H = 1/6 and A = 7/12 derived from HT 123 | Secondary |
| W occurs only at Khania; L-series combinations concentrated there | Secondary |
| Minoan dry unit ≈ Mycenaean 96 litres; liquid ≈ 28.8 litres | Secondary |

**These drive parser behaviour** (inline KI-RO, *supra mutila* exclusion, open quantities), so they are load-bearing despite being secondary. Confirming them against a stable copy of Younger's work is outstanding.

### Other literature
| Source | Used for | Level |
|---|---|---|
| Montecchi 2009, *AIIN* 55, 29–52 | The audit listing HT 9a, 123a/b, 94a, 118 as miscalculations and HT 13, 102, 116, 119, 127 as having calculation problems | Secondary |
| Montecchi 2013, *AIIN* 59, 9–26 | Competing values (D = 1/3, K = 1/16) | Unchecked |
| Schrijver 2014, *Kadmos* 53, 1–44 | Competing value table; the L-series read as divisive; fraction values argued from food rations | Secondary (paywalled) |
| Bennett 1950, Stoltenberg 1955, Was 1971, Facchetti 1994, Cash & Cash 2012 | Historical value tables, via Corazza et al.'s Table 3 | Secondary |
| **Chadwick 1976, *The Mycenaean World*, 102–105** | Linear B metrology: L = 30 M, M = 4 N, N *probably* = 12 P — *"the doubt is due to the fact that we find P 12 and P 20"*; and p. 105, *"the 65.5 g unit is only one of a number of competing systems current in the Minoan world"* | Secondary |
| **Correction** | This passage was earlier attributed here to *Linear B and Related Scripts* (1987). It is *The Mycenaean World* (1976). | — |

### Palaima, "Mycenaean Ideograms and How They Are Used" (2005)
Retrieved as PDF from `https://sites.utexas.edu/scripts/files/2020/08/2005-TGP-MycenaeanIdeogramsAndHowTheyAreUsed.pdf` and read as extracted text. This is the load-bearing source for Linear B metrology in `la/lb/metrology.py`.

| Claim used | Level |
|---|---|
| *"Nine signs stand solely for units of weight or measure \*110 - \*118. These are an invention in Linear B, since Linear A deals with weights and measures in a different way."* (p. 267-268) | **Read** |
| Dry commodity ideograms *"equal, as units of measure, 10 of the largest pure unit of dry measure T (= 9.6 liters), i.e., 96 liters"* — so **1 dry unit = 10 T** | **Read** |
| *"in contrast to the dry commodities, the convention with liquid commodities is that the substance ideogram equals only 3 of the largest pure unit of liquid measure S (= 9.6 liters), i.e., 28.8 liters"* — so **1 liquid unit = 3 S**, and S equals T in absolute size | **Read** |
| **T = 6 V and V = 4 Z** — *not* in this source. Taken from two independent secondary tables (T = 12 l, V = 2 l = 1/6 T, Z = 0.5 l = 1/4 V), which agree with each other and are consistent with Palaima's chain | Secondary |

**On the absolute calibration.** Palaima's dry unit is 96 litres; other tables give 120. The project uses **ratios only** and never litres, so nothing here depends on the disputed figure — an audit of whether a scribe's sum matches their own total is scale-free. Stated because it would be easy to import the wrong constant and never notice.

### The Pylos Ma assessment ratio — and a misattribution corrected

**Correction.** This project first cited the ratio as "Palaima 2004, 292". That is wrong. The proportion was **first identified by E. L. Bennett in 1951** and is, in Shelmerdine's words, *"usually cited as 7 : 7 : 2 : 3 : 1.5 : 150"* — a standard figure seventy-five years old, not a recent observation.

Primary source read for this correction: **C. W. Shelmerdine, "Mycenaean Taxation"**, retrieved as PDF from `antiquitasviva.com/wp-content/uploads/2021/07/sp07.12.-shelmerdine-c.-w.-mycenaean-taxation.pdf` and read as extracted text.

| Claim | Level |
|---|---|
| *"They record assessments of six different commodities, labelled A through F, in a fixed ratio of fiscal units first identified by Bennett, and usually cited as 7 : 7 : 2 : 3 : 1.5 : 150."* | **Read** |
| Commodity letters map to our sign order: **A** = `*146` (textiles), **B** = `RI`, **C** = `KE`, **D** = `*152` (oxhides), **E** = `O`, **F** = `ME`. A and D are *"the two securely identified commodities"* | **Read** |
| Two long-standing theories of how the figures were reached: **Lejeune's "bottom-up"** (tax based on taxable population) versus **Wyatt's "top-down"** (kingdom total fixed first, then divided between provinces, subgroups and fiscal groups) | **Read** |
| **de Fidio 1982**: the extant figures *"are not those originally intended, but reflect systematic reductions of a larger assessment"* | **Read** (via Shelmerdine) |
| Rounding is a central, quantified feature, not a discovery: *"The adjusted ratio … requires many fractions, and consequently much rounding off of numbers to reach the extant figures. Some rounding off will be needed on any scheme"*, with per-commodity offsets given as **A/B −1.5; C 0; E −0.75; F +87** | **Read** |
| **PY Ma 225's `*152 22`**: *"The figure on the tablet is 22, but this is likely to be scribal error since 12 fits the ratio; see Wyatt 25 n. 41"* | **Read** |
| **PY Ma 221**: *"For E and F the figures extant are 4[ and 400[. It is clear from the breaks that 5 and 500 could be restored (though nothing higher), and these numbers do fit the ratio."* | **Read** |
| **PY Ma 346**: *"The extant figure for F is 200[; 400 fits the ratio. De Fidio 89 restores 450"* | **Read** |
| **PY Ma 120**: commodity E was *predicted* as 14 from the ratio, restored in PTT I rather than a fractional 13.5, and later *confirmed* by a new reading of the tablet | **Read** |

**What this does to our results.** Everything the Ma pilot produced is already published: the ratio, the rounding, the Ma 225 anomaly (Wyatt 1962), and each of the restorations. It also shows the pilot was measuring the wrong quantity — deviations from the ratio are read in the literature as **deliberate reductions and exemptions**, i.e. fiscal policy, not scribal error, with Ma 225 the one case singled out as an actual mistake. The pilot therefore stands as a validation of the parser, not as a finding. See `FINDINGS.md` §7.

### Ma series, further reading (not yet read)
| Source | Why it matters | Level |
|---|---|---|
| Wyatt, "The Ma Tablets from Pylos", **AJA 66 (1962) 21–41** | The foundational study; n. 41 on p. 25 is the Ma 225 scribal-error judgement | Unchecked |
| de Fidio, "Fiscalità, redistribuzione, equivalenze", **SMEA 23 (1982) 83–136** | The reductions thesis, and the competing restoration of 450 for Ma 346 | Unchecked |
| Killen, "The Commodities on the Pylos Ma Tablets", **Pasiphae 2 (2008) 431–448** | The current treatment of what the six commodities are | Unchecked |
| Bennett, "The Undeciphered Minoan Script", *Yale Scientific Magazine* (1951) 36 | Where the ratio was first stated | Unchecked |

### Method precedents
| Source | Used for | Level |
|---|---|---|
| Born, Monroe, Kelley & Sarkar, arXiv 2502.00090 | Methodological precedent: enumerating numeral readings to constrain an ancient accounting corpus | Secondary |
| Assael et al., *Nature* 603:280 (2022), "Ithaca" | The held-out-corruption protocol for restoration without ground truth | Secondary |
| Corazza et al. 2022, *PLOS ONE* (Cypro-Minoan) | The caution that visual similarity does not establish grapheme identity | Secondary |

---

## Literature checked for possible extensions (checked 2026-09-24)

Gathered to test whether four proposed extensions are novel. Recorded here because
several are negative results — "no prior work found" — which are load-bearing in the
opposite direction from a normal citation: if one is wrong, an extension loses its point.

### Gaps found (searched, nothing located)

| Claim | Level |
|---|---|
| No published systematic arithmetic audit of Linear B; no published error rate for Mycenaean accounting | **Searched, not found** |
| No corpus-wide search for uniquely recoverable damaged numerals, in any ancient accounting corpus | **Searched, not found** |
| "Uniquely recoverable restoration" is not an established named concept; nobody distinguishes *uniquely determined* from *probabilistically suggested* | **Searched, not found** |
| No computational Linear A ↔ Linear B shape metric; no computational identification of Linear A scribal hands | **Searched, not found** |
| No open Linear B *palaeographic tracings* exist (only standardised type designs) | Read |

A negative from targeted searching is weaker than a read positive. Braović et al.,
*Computational Linguistics* 50(2) (2024) 725–779 reviews computational Aegean work and
should be read as the definitive gap check; it was unreachable (403).

### Nearest prior art — read before claiming novelty

| Source | Bearing | Level |
|---|---|---|
| Born, Monroe, Kelley & Sarkar, *"Disambiguating Numeral Sequences to Decipher Ancient Accounting Corpora"*, CAWL 2023 (arXiv 2502.00090) | The closest existing method: rule-based candidate readings + a **subset-sum solver** over 24 proto-Elamite summary tablets + Yarowsky bootstrapping; F1 0.88→0.94 on 8,011 intact numerals (only 1,899 unambiguous). **It explicitly discards damaged numerals** — arithmetic disambiguates, never restores | **Read** |
| Salgarella & Castellan, *SigLA: The Signs of Linear A*, in Haralambous (ed.), *Grapholinguistics in the 21st Century 2020*, Fluxus 2021, 945–962, doi 10.36824/2020-graf-salg | Linear A scribal hands are *"at present still not clearly identified nor identifiable"*, listed as future work. Godart's attributions (GORILA V, 83–113) were made *"without explaining the reasons of his choices"* | **Read** |
| Judson, *"Scribes as Editors"*, **AJA 124.4 (2020) 523–549**, open access | Catalogues Linear B scribal edits corpus-wide; may already contain counts that pre-empt an error-rate study. **Read before starting one** | Unchecked |
| Assael et al., *Nature* 603 (2022), "Ithaca" | Held-out-corruption protocol; vocabulary of 35,884 words, top-20 ranked, **no numeral handling at all** | **Read** |

### Method baselines (treat as prior art, not research questions)

| Source | Result | Level |
|---|---|---|
| Linear B scribal hands, arXiv 2108.04199 (ICDAR-W 2021) | Adversarial *disentanglement* of hand from sign identity; 4,134 glyphs, 88 sign types, 74 hands (48 Knossos / 26 Pylos), Otsu-binarised 64×64, 16-dim embeddings. Findplace F1 0.154 → 0.292. **No public data release found** | **Read** |
| Corazza et al., *PLOS ONE* 17(7):e0269544 (2022), "Sign2Vec" (Cypro-Minoan) | DeepCluster-v2, 2,899 signs / 213 inscriptions; **69% top-1, 81% top-2**. Dominant axis of variation is **palaeographic style conditioned on writing medium, not sign inventory** — a direct confounder for any hand study | **Read** |
| Chen et al., *"LogogramNLP"*, ACL 2024 (2024.acl-long.768) | Linear A (772 SigLA tablets) used only for find-place classification; **textual 16.56 macro-F1 beat visual ResNet 8.24** — visual features *lost* on Linear A while winning on Egyptian, Akkadian and Old Chinese | **Read** |
| Hu et al., Maya glyph retrieval, ACM MM'14 | HOOSC ≈ +8% MAP over GF-HOG; **glyph co-occurrence re-ranking improved average rank by ~40 positions** — precedent for adding contextual priors to shape retrieval | **Read** |
| Dencker et al., *PLOS ONE* 2020 (cuneiform) | Weakly-supervised detection 45.3 mAP → 63.2 semi-supervised | **Read** |
| Vlachou-Efstathiou et al., arXiv 2606.09446 (2026) | Prototype-based quantitative palaeographic measurement across four hands **without hand labels** — method template | **Read** |

### Linear B data and metrology

| Source | Used for | Level |
|---|---|---|
| **DAMOS** (Database of Mycenaean at Oslo) | Transliterations only, **CC BY-NC-SA 4.0**; `ajaxitemcontent/{id}`, ids 1–5899. Totals present but **not structurally tagged** (`to-so OLE 3 S 2 V 2`); `Hand` / `Stylus` fields machine-readable; 66 hands at Knossos, 26–38 at Pylos | **Read** |
| Palaima 2004, p. 292 | Every Pylos **Ma** district tablet records six commodities in the fixed ratio **7 : 7 : 2 : 3 : 1.5 : 150**, across ~18 tablets — an exact machine-checkable invariant in a script with known values | Secondary |
| Palaima (same) | Linear B metrology is *"universal, with no valid proof of significant regional or chronological variation"* — so the adjudication target is **ratios and absolute values**, not competing systems as in Linear A | Secondary |
| Salgarella 2020 (CUP), via *BMCR* 2021.04.30 | Linear A regional palaeography **is** covered, by eye: Ayia Triada and Phaistos isolated, Khania and Zakros closest to Linear B | Secondary |
| Salgarella & Judson, *Ariadne* Suppl. 5 (2025) 359–379, doi 10.26248/ariadne.vi.1861 | Ten-sign chronological test; concludes no systematic directional trend. Whether it uses statistics is **unknown** (403) | Unchecked |
| Revesz, *IJAMI* 10 (2016) 67–76 | Reportedly a numeric symbol-similarity measure across nine Cretan scripts via UPGMA. **Snippet only; PDFs 404/403, and this author's decipherment claims sit outside mainstream scholarship — verify before citing** | Unchecked |

### Open Linear B glyph sources (all archetypes, not tracings)

| Source | Licence | Level |
|---|---|---|
| Noto Sans Linear B | SIL OFL 1.1 | Read |
| CTAN `linearb` | LPPL 1.3 | Read |
| Wikimedia Commons per-sign SVGs | per file | Read |

**Closed:** Douros *Aegean* font (non-commercial personal use), Unicode code charts (font
extraction forbidden), LiBER and CaLiBRA images, GORILA, CoMIK.

**The blocker, stated plainly:** all three open options are standardised type designs. Measuring
SigLA tracings against them compares a scribe's hand to a typographer's archetype, so it can
speak to sign identity but not to scribal variation. There is no open SigLA equivalent for
Linear B.

### Our own corpus, counted directly

| Fact | Level |
|---|---|
| 591 documents carry a `scribe` value under 102 distinct labels — but only **37 labels over 178 documents** are tablet-level hands (HT 22, KH 6, ZA 5, AR 2, ARKH 1, PS 1). The other 65 labels / 413 documents are `Wa`/`Wc` **sealing groups**, attributed from seal impressions and nodule batches, not handwriting. `gorila_scribe` is populated for 107 documents / 33 values | **Read** (counted in `corpus.json`) |

---

## Outstanding

1. Confirm Younger's tablet commentary against a stable copy — several parser rules depend on it.
2. Read Montecchi 2009 directly; it is the only dedicated arithmetic audit of these tablets.
3. Read Schrijver 2014 for the ration argument; only his value table is known here, at second hand.
4. Read **Judson 2020** (*AJA* 124.4, open access) before any further Linear B error-rate work — it may already count what such a study would count.
5. Read **Braović et al. 2024** (*Computational Linguistics* 50(2)) as the definitive check on the "no computational Aegean palaeography" gaps above. Unreachable (403) at time of writing; every gap claim in this section is provisional until it is read.
6. Confirm the **T = 6 V and V = 4 Z** subunit ratios at a primary source. Palaima 2005 was read and gives only the top of each chain (1 dry unit = 10 T, 1 liquid unit = 3 S); the subunit ratios rest on two agreeing secondary tables. An attempt to corroborate them from the corpus produced **no usable equations**, so they remain the least-verified load-bearing numbers in `la/lb/metrology.py`.
7. Check whether **PY Ma 225's `*152 22`** — where the series implies 12, a difference of one ten-stroke — is already discussed in the Ma literature. It is the largest anomaly the audit surfaces and the one most likely to be known.
