# Glyph clustering and suspected mislabels

Issue #53 orders every corpus occurrence of a sign by how much it looks like the glyph
you selected, and flags occurrences that look unlike the rest of their sign. This page
records how the embeddings were built and what clustering them shows. All numbers below
were produced by the commands shown, with seed 0.

## Pipeline

1. `python scripts/build_glyph_embeddings.py` embeds every cached SigLA sign crop
   (`fraction-solver/data/images/<tablet>/*.png`, 4,484 of the 4,723 identified signs have
   a crop on disk) with the penultimate-layer features of the trained sign classifier
   `models/linear_a_classifier.pt` (256 dimensions, CPU, about 35 s). The result is
   `models/glyph_embeddings.npz` (gitignored) with `tablet`, `position`, `sign`,
   `vectors`, `model` and `weights_sha256` of the weights used (`616b9815...aac375` for
   the run below). `--backbone` is the switch for adding another backbone (e.g. DINOv2).
2. Crops are prepared the way the reader prepares them for classification: ink mask,
   centred on a white square, aspect kept (`la.glyphembed`, `la.augment.square_crop`).
3. `cd fraction-solver && python -m la.clustering --embeddings ../models/glyph_embeddings.npz`
   runs the analysis below (about 3 minutes on a laptop CPU, mostly K-means).

## Caveat that matters

The classifier was trained on crops from this corpus (train split), so its features
separate the classes better on corpus crops than they will on a new photograph.
The scores below measure how well the embedding space matches the SigLA inventory on
data the network has partly seen; they are not a generalisation estimate.

## Clustering against the sign IDs

Signs with at least 5 examples only (116 signs, 4,104 crops of 360 signs / 4,484 crops).
Embeddings are L2-normalised. Purity is the share of crops whose cluster's majority sign
is their own sign; NMI is mutual information over the mean of the two entropies.

| Method | Setting | Clusters | Noise | Purity | NMI |
|---|---|---|---|---|---|
| K-means (spherical, k-means++, 3 restarts) | k = 116 | 116 | n/a | 0.783 | 0.813 |
| DBSCAN | eps 0.20, min 5 | 18 | 92.7 % | 0.993 (clustered points) | 0.126 |
| DBSCAN | eps 0.25, min 5 | 34 | 78.6 % | 0.978 (clustered points) | 0.323 |
| DBSCAN | eps 0.30, min 5 | 45 | 58.4 % | 0.877 (clustered points) | 0.510 |
| DBSCAN | eps 0.35, min 5 | 46 | 38.6 % | 0.457 (clustered points) | 0.492 |
| DBSCAN | eps 0.40, min 5 | 16 | 22.3 % | 0.097 (clustered points) | 0.171 |
| DBSCAN | eps 0.50, min 5 | 1 | 1.6 % | 0.042 (clustered points) | 0.014 |

DBSCAN NMI counts all noise points as one extra cluster. Reading: K-means with the
right k recovers the inventory reasonably (NMI 0.81). DBSCAN is the worse fit: sign
classes differ a lot in how tight they are, so no single eps works. Tight eps gives
very pure but tiny clusters (most points become noise), and eps of 0.4 or more
merges unrelated signs into one cluster. This is why the pane uses the SigLA sign ID
as the grouping and uses embeddings only to order and to flag.

## Suspected mislabels

For each sign with at least 5 examples, the cosine distance of each crop to the sign's
centre (mean embedding) is turned into a robust z-score within that sign (median and
MAD). A crop is flagged when z > 5.0 (`la.clustering.OUTLIER_Z`).

* 124 of 4,104 crops are flagged (3.0 %).
* For 90 of the 124 the nearest sign centre is a different sign than the label; for the
  other 34 the crop is an unusual variant of its own sign (damaged, ligatured, unusual
  ductus), which is not evidence of a wrong label.
* Largest: HT 110a #3 labelled AB34 (z 38.4, nearest centre AB53), HT 19 #7 labelled AB02
  (nearest AB46), HT 96b #14 and HT 88 #7 labelled AB31 (nearest AB30), KN Zc 7 #15
  labelled AB08 (nearest A310), PH Wc 39b #1 labelled AB02 (nearest AB46).

The full list of the first 25 is in the JSON the command prints
(`mislabels.top`). The flag means "look again". Nobody has checked these against the
tablets, so none is a confirmed error, and the threshold was chosen by eye (3.5
flagged 6.5 %, 5.0 flags 3.0 %).
