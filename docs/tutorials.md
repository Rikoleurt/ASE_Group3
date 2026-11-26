# Tutorials

The **Tutorials** tab (`/tutorials`, in the top bar) helps new users get started. It has 15 short
videos, each recorded from the real site, with a written summary of the steps and a button that opens
the feature itself.

| Section | Lessons |
|---|---|
| Get started | Find your way around · Read a tablet · Browse the corpus · Find a sign |
| Correct readings | Correct the boxes · Mark uncertain and damaged signs · Work faster in the editor |
| Build editions | Compare versions · Merge an edition · Release and vote · Cite and export |
| Work together | Discuss a reading · Stay up to date · Search sign sequences · Find where to help |

- **Progress:** each lesson is marked watched when its video ends, or with **Mark as watched**.
  Progress is kept in the browser (localStorage), so it is per device and may be forgotten.
- **Links:** each lesson has its own address (`/tutorials/<lesson>`).
- **Home page:** a welcome card suggests the next unwatched lesson until it is dismissed with
  **Not now** or every lesson has been watched.
- **Content:** the lessons (titles, summaries, steps and the page each one opens) are in
  `frontend/src/state/tutorials.js`.
- **Files:** the narrated videos are in `frontend/public/tutorials/<lesson>.mp4`, each with a poster
  `<lesson>.jpg`. All 15 come to about 10 MB.

## Narration

Every caption is also read aloud, by the Windows voice "Microsoft Zira Desktop". Each caption stays
on screen until it has been read. Readings, sign numbers and file formats are spelt out for the voice
(`ka-ụ-[de] ta` is read "ka, u with a dot under it, de in square brackets, then ta"; `AB81` is
"A B 81"). The spellings are listed in `e2e/narration.mjs`. Add one there when a new caption reads
badly.

## Re-recording a lesson

Re-record a lesson when the page it shows changes. The recorder drives a real browser through the
lesson, and logs when each caption appears. On Windows it also speaks every caption.

```bash
cd e2e && npm ci
node record-tutorials.mjs out ../path/to/HT-13.png mark-damage,find-a-sign   # or no list: every lesson
node encode-tutorials.mjs out mark-damage,find-a-sign                       # into frontend/public/tutorials
```

- **What it needs:** the frontend running at `BASE` (default `http://localhost:5174`), logged in as
  an admin, with HT 13's seeded versions and edition, as in the in-memory demo. It also needs Chrome
  and ffmpeg installed.
- **What encoding does:** `encode-tutorials.mjs` mixes each caption's voice in at the moment the
  caption appears. It writes `<lesson>.mp4` (H.264 at 15 fps with mono AAC, so the files stay small
  and the text sharp) and a poster `<lesson>.jpg`.
- **Without a voice:** not on Windows, or with `NARRATION=off`, the lessons are recorded silent and
  encoded without sound.
- **New lessons:** add the lesson in `frontend/src/state/tutorials.js` and in
  `record-tutorials.mjs`. A test checks that every lesson has its video and poster.
