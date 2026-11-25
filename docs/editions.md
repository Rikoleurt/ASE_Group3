# Editions: releases, votes and the community edition

Part of the scholars' workbench (story E). An **edition** is a copy of a tablet merged from
several versions (see [box-sets.md](box-sets.md), "Merging versions into an edition").

## Releases

Editions stay editable, so votes, citations and exports point at **releases** instead: numbered
snapshots that never change.

- **Who releases:** the edition's owner, or anyone it is shared with at manage, from the editor
  (**Release this edition for voting**), with optional notes for voters.
- **What is released:** only saved changes. The editor refuses while there are unsaved ones.
- **Visibility:** releasing opens the edition to everyone logged in, to view (if it was
  private), since releases are for others to vote on.
- **Permalink:** each release has its own page, `/editions/<id>`, showing its boxes, reading,
  contributors and sources. Anyone can open it while the edition is open to everyone;
  otherwise only those who can open the edition.

## Votes

Each logged-in account backs **one release per tablet**, on the Tablets page, and can change or
withdraw it. Two kinds of account cannot vote:

- **new accounts**, until they are a day old (accounts made before this feature count as old);
- **accounts an admin removed voting rights from.** Their votes are kept but not counted while
  the rights are removed, and come back when the rights are restored.

Counts are shown split by role ("3 backers, 1 of them reviewer").

The tablet's **community edition** is the most backed release, the earlier one on a tie. It is
listed first, and the training export can use it (below).

## The admin override

An admin can choose a tablet's accepted edition over the vote (**Choose over the vote**):

- **A reason is required:** at least 15 characters. Everyone sees it, with the admin's name and
  the date, above the votes, which stay visible.
- **Returning to the vote** needs a reason too, kept on record.
- **Record:** every override is kept, cleared overrides included.

## Voting rights

On the Admin page, **Voting rights** next to each user removes or restores their right to vote:

- **A reason is required:** at least 15 characters. The account sees it on the vote button.
- **Record:** every change is kept with its reason and admin.
- **Not your own:** admins cannot change their own rights.

## Training export

`GET /admin/export/corrections?accepted_only=true` (and the `.zip`) exports each tablet's
accepted release instead of every copy: one agreed version per tablet, with images named
`edition-<id>`. This removes the duplicates the default export has when several people
corrected the same tablet.

## Citing and exporting a release

A release never changes, so its page (`/editions/<id>`) is the permalink to cite. The page
shows a ready-made citation, with a button to copy it:

> anouk, dev. Agreed: an edition of HT 13, release 2. ASE Group 3 Linear A workbench,
> 25 November 2026. https://…/editions/9. Drawings and transcriptions: SigLA … CC BY-NC-SA 4.0.

The page also offers the release as files (`GET /editions/{id}/export.{xml,svg,png,csv,json}`).
Each carries the citation and the licence:

| Format | Holds |
|---|---|
| TEI-EpiDoc (`.tei.xml`) | the text in a minimal EpiDoc profile, described below |
| SVG | the drawing embedded (one self-contained file), a box and the sign's reading per box; marked boxes in red |
| PNG | the same as an image, with a credit line |
| CSV | a row per box: line, order, sign, reading, pixel box, certainty, damage, other readings, word end, source and its author |
| JSON | everything above, for programs |

The TEI-EpiDoc profile contains:

- **header:** the title, one `respStmt` per contributor, the permalink as `idno`, the date,
  the licence in `availability`, and the tablet in `msIdentifier`;
- **facsimile:** a `zone` per box;
- **text:** the edition `div`, with `lb` per line, `w` per word and `g ref="#AB81"` per sign;
  `unclear` for uncertain or partly preserved signs, `supplied reason="lost"` for restored
  ones and `gap` for illegible ones, each pointing to its zone (`facs`).

Set `PUBLIC_URL` on the server for absolute links in the files; otherwise they are relative.

## API

| Route | Does |
|---|---|
| `POST /box-sets/{id}/releases` `{notes?}` | release an edition (owner or manage); 201 |
| `GET /box-sets/{id}/releases` | an edition's releases, newest first |
| `GET /editions/{release_id}` | a release with its reading and citation (the permalink) |
| `GET /editions/{release_id}/export.{fmt}` | the release as `xml` (TEI-EpiDoc), `svg`, `png`, `csv` or `json` |
| `GET /tablets/{slug}/editions` | released editions open to everyone, votes, the accepted one, any override, whether you may vote |
| `PUT /tablets/{slug}/vote` `{release_id}` / `DELETE` | back a release / withdraw |
| `PUT /tablets/{slug}/edition-override` `{release_id, comment}` | admins: choose over the vote |
| `POST /tablets/{slug}/edition-override/clear` `{comment}` | admins: return to the vote |
| `GET` / `PUT /admin/users/{id}/voting` `{can_vote, reason}` | admins: see or change voting rights |

## Tables

Migration `migration-workbench/203_edition_releases_votes.sql`:

| Table or column | Holds |
|---|---|
| `edition_release` | release snapshots: boxes, sources and contributors as JSON |
| `edition_vote` | one vote per user per tablet |
| `edition_override` | admin overrides and their reasons (kept when cleared) |
| `vote_right_change` | each grant or removal of voting rights, with its reason |
| `user.can_vote` | voting rights |
| `user.created_at` | when the account was made; it defaults to now, so sign-up is unchanged |
