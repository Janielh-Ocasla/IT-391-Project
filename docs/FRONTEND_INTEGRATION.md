# Backend integration scope

This change adds completed Flask page routes, role-based navigation, real History
integration, and related tests. Authentication and session security remain owned
by the cybersecurity teammate.

## Existing authentication is preserved

`Backend/account.py`, `bearer_token()`, `require_api_token()`, `authenticate()`,
`/api/login`, `/api/logout`, and `/api/me` are unchanged from `origin/main`.
The shared `api.js` is also unchanged: it sends the existing `sessionStorage`
access token as `Authorization: Bearer ...` with `credentials: omit`.
No cookie authentication, cookie flags, CSRF middleware, token refresh, cross-tab
session coordination, or new logout policy is included. Supabase schema and RLS
policies are not changed.

## How completed pages load

Ordinary browser navigation does not send a token held in `sessionStorage`.
Each member URL therefore serves only `member-loader.html`, a neutral document
with a loading message and no dashboard markup, profile details, or History rows.
`pages.js` uses the unchanged `CICApi.request()` to request
`GET /api/pages/<page_name>` with the existing bearer token.

The existing API guard rejects missing tokens before constructing a Supabase
client. The endpoint then calls the existing `authenticate()` function, verifies
`profiles.role`, and reads data through that user's JWT for RLS. Only after these
checks does it return the original Jinja-rendered template in a JSON `html`
field. The loader replaces its document with that authorized HTML, preserving
existing layout, styles, scripts, and normal page links. Tokens are never put in
URLs or returned inside the rendered HTML.
The existing API response handler applies `Cache-Control: no-store` to these
responses, including role redirects and authorization errors.

A missing/expired token returns 401 and opens the existing home login form. A
volunteer requesting an admin template gets 403 and no private HTML. The public
loader is not the member/admin page itself; access control is enforced on the
API that supplies all protected markup and data. JavaScript is required.

| Completed page | Browser URLs | API page name / authorization |
| --- | --- | --- |
| Home | `/`, `/home.html`, `/index.html` | Existing public page |
| About | `/about`, `/about.html` | Existing public page |
| Donate | `/donate`, `/donate.html` | Public page |
| Volunteer | `/volunteer`, `/volunteer.html` | Existing public design |
| Member Dashboard | `/member`, `/member.html` | `member`: volunteer; admins go to Admin History |
| Tasks | `/tasks`, `/task.html` | `tasks`: volunteers can pick up open tasks; admins can view tasks |
| History | `/history`, `/history.html` | `history`: own completed work; admins go to Admin History |
| Admin History | `/admin/history`, `/history-admin`, `/history-admin.html` | `history-admin`: admin only |
| Admin landing | `/admin` | `admin`: admin only; redirects to Admin History |
| Announcements | `/announcements`, `/announcement`, `/announcement.html` | `announcement`: admin or volunteer |
| Member Donations | `/member_donate`, `/member_donate.html` | `member_donate`: admin or volunteer |
| Account Settings | `/account`, `/account.html` | `account`: member placeholder |
| Services | `/services`, `/services.html` | `services`: member placeholder |
| FAQ / Help | `/faq`, `/faq.html` | `faq`: member placeholder |

Login navigation uses the role returned by the existing backend: volunteers go
to `/member`, admins to `/admin/history`. The API also resolves admin requests
for member/history landing pages to the same completed admin page. Client-side
navigation never grants authorization. Completed templates' Sign Out links call
the existing logout client; its storage cleanup and JWT lifetime are unchanged.

## History data

`History.service_history()` retains its existing role/scope logic. Its selection
now also includes `volunteer_id` and `tasks.estimated_hours`, which the templates
need. Volunteer requests use the authenticated user ID, ignoring caller-supplied
volunteer IDs. Admin History includes organization-wide results visible under
existing RLS and looks up volunteer names through the same authorized client.
Filters distinguish volunteers by ID, including volunteers with identical names.

Only `completed` assignments count; this is the backend's existing admin approval
state. Assigned, submitted, and cancelled work does not count. Dates come from
review, submission, or assignment timestamps. Both History templates label values
as **estimated hours** and explain that actual time is not recorded. Totals use
current task estimates, not measured time or a completion-time snapshot.
Empty histories contain no invented rows. Query failures return errors instead
of pretending that a user's history is empty.

## Remaining gaps and ownership

- Account Settings, Services, and FAQ show an unavailable message and a link
  back to the appropriate dashboard. Their full browser features are pending.
  Task management, profile edits, history, and hours are available through the
  JSON endpoints in [the API contract](API.md).
- There is no separate admin dashboard design; Admin History is the landing page.
- Token expiry, refresh, logout revocation, and session-storage policy are unchanged
  and remain the cybersecurity teammate's responsibility.
- Cookie-specific findings from the excluded earlier draft (cross-origin logout,
  cookie transport flags, and cookie/tab state mismatch) concerned that draft's
  new mechanism. That mechanism and its associated fixes are excluded here;
  these are not attributed to the existing Bearer implementation.
- Live Supabase data and deployed RLS were not accessed. Tests model the existing
  authorization calls and verify that data reads use the authenticated JWT.

## Verification

```sh
python -m unittest discover -s tests -v
node --test tests/*.test.cjs
```

The original authentication/role workflow tests are retained. Page tests cover
neutral page URLs, protected template loading, both dashboard destinations,
volunteer/admin authorization, invalid tokens, real History data mapping, empty
and failed queries, HTML escaping, and verified-JWT database reads. Loader tests
execute the unchanged API client to check bearer headers and cookie omission.
Python connections/DNS are blocked and JavaScript network requests are mocked.

Responsive verification used WebKit and Chromium with 21 viewport/browser
combinations and 22 public, Volunteer, and Admin route/role checks per viewport
(462 in total). This included iPad mini (744×1133), iPad (820×1180), older and
larger iPads in both orientations, 320–700px tablet windows, mobile phones,
Android tablet, and desktop. Checks covered page overflow, overlapping header
controls, dialogs, task search, and the admin history filter. The history table
can scroll within its own container if needed. Flask checks also verified all
30 registered page URLs, including aliases. Tests use mock accounts and
substitute for external images and services; they do not certify real devices,
production authentication, or third-party forms.

No schema changes, live database changes, or deployments are included.
