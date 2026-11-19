# Security notes (#98)

What the app does about abuse, and what is left to the deployment.

## Accounts and sessions
- Sessions are server-side, in an HttpOnly, SameSite=Lax cookie (Secure unless
  `SESSION_COOKIE_SECURE=0`). Every write needs the CSRF token the session gives out.
- Failed logins: at most 10 per account and per client address in 15 minutes (429 with
  `Retry-After`).
- `/users/{id}/email` and `/users/{id}/username` answer only for yourself, or for anyone to an
  admin; others get 404, so accounts cannot be listed by counting ids. The user search for sharing
  returns usernames only, to logged-in users, at most 10.
- The frontend refuses a write if, since the page loaded, another tab logged in as someone else.

## Limits
| What | Limit |
|---|---|
| Upload body | 10 MB, checked from `Content-Length` before the body is read (411 without it) |
| Uploads | 200 per user per day (429) |
| Image size | 40 megapixels, PNG or JPEG only |
| Model reading of a corpus tablet | login needed; one at a time, busy is 503; results cached for the whole corpus |
| Comments on copies | 2000 characters; 10 a minute per person; lists return the newest 500 |
| Saves | 500 changes per save, 2000 boxes per copy; coordinates must be finite and inside the image |

The rate limits are counted in the server process's memory: they reset on restart and are per
worker. A deployment with several workers should also limit at the reverse proxy.

## Training data
Anyone can register and correct boxes, so the admin export takes admins' and reviewers' copies
unless asked for everyone's (`owner_trusted` marks each copy).

## Left for later
- Deleting an account deletes its records but not its uploaded image files.
- There is no per-user disk quota beyond the daily upload count.
