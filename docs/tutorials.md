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
- **Files:** the videos are in `frontend/public/tutorials/<lesson>.mp4`, each with a poster
  `<lesson>.jpg`. All 15 come to about 6 MB.

## Re-recording a lesson

Re-record a lesson when the page it shows changes. The recorder drives a real browser through the
lesson and writes a captioned video:

```bash
cd e2e && npm ci
node record-tutorials.mjs out ../path/to/HT-13.png mark-damage,find-a-sign   # or no list: every lesson
```

- **What it needs:** the frontend running at `BASE` (default `http://localhost:5174`), logged in as
  an admin, with HT 13's seeded versions and edition, as in the in-memory demo. Chrome must be
  installed.
- **Encoding:** encode each `out/<lesson>.webm` into the public folder. 15 fps keeps the files small
  and the text sharp:

```bash
ffmpeg -i out/mark-damage.webm -c:v libx264 -preset slow -crf 30 -r 15 -pix_fmt yuv420p \
  -movflags +faststart -an ../frontend/public/tutorials/mark-damage.mp4
ffmpeg -ss 15 -i out/mark-damage.webm -frames:v 1 -q:v 8 -vf scale=800:-1 \
  ../frontend/public/tutorials/mark-damage.jpg
```

- **New lessons:** add the lesson in `tutorials.js` and in `record-tutorials.mjs`. A test checks that
  every lesson has its video and poster.
