# Activity bubbles on glyphs

Part of the scholars' workbench (story I). Switch **Show activity on glyphs** on in the account
menu (it is remembered in this browser). A glyph of a corpus tablet then shows a bubble with how
much others have said or changed about it since you last opened it. Opening the glyph (selecting
it on a tablet, in the editor, or a place on the compare or merge page) clears its bubble.

The bubbles appear on the Tablets page (scholars' boxes), in the editor of a copy, and on the
compare and merge pages.

## What counts

A glyph is a sign of a corpus tablet, keyed by the tablet and its position in the scholars'
transcription. Its activity is read from what is already recorded, with its time:

- comments saved against it in the glyph pane;
- comments on, and saved changes to, a box that started as that scholars' sign, in any copy
  you can open (yours, shared with you, or open to everyone).

Your own comments and changes never count. A glyph you have never opened counts the last two
weeks.

When you open a glyph, the time is stored in `glyph_seen` (migration
`migration-workbench/204_glyph_seen.sql`).

## Notifications

The bell in the top bar shows how many notifications are unread. It checks every minute while the
page is visible (there is no live connection). Its list marks a notification read when it is
opened, and has **Mark all read**.

You are told when someone:

| Kind | What happened | Link |
|---|---|---|
| share | shares a copy with you, and at which level | the copy |
| comment | comments on your copy or one of its boxes | the copy |
| mention | @-mentions you in a discussion | the discussion |
| vote | backs your released edition | the release |
| override | an admin chooses an accepted edition for a tablet you released one of, or returns it to the vote, with the reason | the tablet |
| merge | merges boxes from your copy into an edition | the edition |
| voting_rights | an admin removes or restores your voting rights, with the reason | none |

How it works:

- **Never for your own actions.** You are not notified of what you did yourself.
- **Never in the way.** A notification that cannot be saved is logged and never fails the change
  that caused it (`backend/app/notifications.py`).
- **Storage:** the `notification` table (migration
  `migration-workbench/207_notifications.sql`); `GET /notifications`,
  `GET /notifications/unread-count`, `POST /notifications/read` `{ids?}`.

## Not yet covered

Not counted in the bubbles yet:

- boxes merged into an edition from another copy;
- signs of uploaded analyses;
- community discussions about a symbol.

## API

| Route | Does |
|---|---|
| `GET /tablets/{slug}/glyph-activity` | `{counts: {position: n}}` since you last opened each glyph (login needed) |
| `POST /glyphs/seen` `{tablet, position}` | you opened this glyph (204) |
