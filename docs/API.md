# CIC API

Base URL for local development: `http://127.0.0.1:5050`.
Pages, static assets and the API are served by `Backend/main.py`.

## Authentication

`POST /api/login` accepts a JSON object with `email` and `password`:

```json
{"email": "volunteer@example.com", "password": "your-password"}
```

Successful response:

```json
{
  "ok": true,
  "message": "Login successful",
  "role": "volunteer",
  "access_token": "<Supabase access token>"
}
```

Send the returned access token on protected requests:

```http
Authorization: Bearer <Supabase access token>
```

Each request uses a fresh Supabase client. Tokens are verified through Supabase
Auth, forwarded to database and Storage requests for RLS, and roles are read from
`profiles`. Client-supplied user IDs and roles do not grant permissions.

`GET /api/me` without an Authorization header returns
`{"ok": true, "logged_in": false}`. With a valid token it returns `ok`,
`logged_in`, `user_id`, and `role`. Invalid or expired tokens return 401.

The browser stores only the access token in `sessionStorage`. It survives page
navigation and reloads in that tab. Tokens are cleared on 401 and on logout.
There is no automatic refresh flow yet; sign in again when the token expires.
`POST /api/logout` acknowledges client logout; the browser must clear its token.
It does not revoke an already issued Supabase JWT.

## Response format

All API JSON bodies are objects with an `ok` boolean. Existing business fields
remain at the top level:

```json
{"ok": true, "tasks": []}
```

```json
{"ok": false, "error": "Unauthorized"}
```

List responses use `tasks`, `announcements`, `assignments`, or `history` arrays, including
when the list is empty. In particular, `/api/announcements` now returns an object
containing `announcements` rather than a bare array. Task operation responses
retain the existing `assignment` field, whose value is an array of changed rows.
API responses use `Cache-Control: no-store`.

## Endpoints

| Method | Path | Access | Request / successful business fields |
| --- | --- | --- | --- |
| GET | `/api/health` | Public | `message`; confirms the Flask app is running, without a database check |
| POST | `/api/login` | Public | JSON `email`, `password` → `role`, `access_token`, `message` |
| POST | `/api/register` | Public | JSON `email`, `password`, `first_name`, `last_name`, optional string `phone` → `message`; 201 when Supabase accepts a volunteer registration |
| POST | `/api/signup` | Public | Alias of `/api/register` |
| GET | `/api/me` | Optional token | `logged_in`, and when authenticated, `user_id`, `role` |
| PATCH | `/api/profile` | Admin or volunteer, own profile only | JSON with one or more of `first_name`, `last_name`, `phone` → `profile` |
| GET | `/api/pages/<page_name>` | Bearer token; admin pages require admin | Authorized completed template in `html`, or a dashboard `redirect` |
| POST | `/api/logout` | Public | `message`; client clears its token |
| POST | `/api/reset-password` | Public | JSON `email` → generic `message` |
| GET | `/api/tasks` | Signed in | `tasks` |
| POST | `/api/tasks` | Admin | JSON `title` and optional `description` → `task`; 201 |
| GET | `/api/tasks/<task_id>` | Admin or volunteer | `task`; volunteers can see only open tasks; neither role sees deleted tasks |
| PUT, PATCH | `/api/tasks/<task_id>` | Admin | JSON `title` and/or `description` → updated `task` |
| DELETE | `/api/tasks/<task_id>` | Admin | Soft deletes a task → `message` |
| GET | `/api/announcements` | Signed in | `announcements` |
| POST | `/api/announcements` | Admin | JSON `title`, `content` → `message`; 201 |
| PUT | `/api/announcements/<announcement_id>` | Admin | JSON `title` and/or `content` → `message` |
| DELETE | `/api/announcements/<announcement_id>` | Admin | `message` |
| POST | `/api/tasks/<task_id>/pick` | Volunteer | `message`, `assignment`; 201 |
| POST | `/api/tasks/<task_id>/cancel` | Volunteer | `message` |
| POST | `/api/tasks/<task_id>/photo` | Volunteer | Multipart field `photo` → `message`, `photo_path` |
| POST | `/api/tasks/<task_id>/submit` | Volunteer | `message`, `assignment` |
| GET | `/api/assignments/status` | Signed in | `assignments`; volunteer sees own, admin sees all |
| POST | `/api/assignments/<assignment_id>/verify` | Admin | JSON boolean `approved` → `message`, `assignment` |
| GET | `/api/history` | Admin or volunteer | `history`: completed and cancelled assignments. Admin can filter by `?volunteer_id=<uuid>`; volunteers see their own records |
| GET | `/api/hours` | Admin or volunteer | `volunteer_id` and `total_hours` for completed work. Admin must supply `?volunteer_id=<uuid>`; volunteers see their own total |

Path IDs must be UUIDs. Uploads accept `.jpg`, `.jpeg`, `.png`, and `.webp` files;
the total request size, including multipart overhead, is limited to 10 MiB.
The assignment must have a photo before submission, and an admin reviews the
submitted assignment. Business rules and database policies remain in their
existing modules. Task titles and profile names cannot be blank. An empty
description or phone string clears that field; omitted fields are preserved when
editing. Profile edits do not change login email or role. Hours are summed from
the current task estimates; cancelled work does not count toward hours.

Common errors: 400 for invalid input, 401 for absent/invalid authentication,
403 for insufficient role, 404 for missing resources, 405 for an unsupported
method, 409 for rejected assignment transitions, 413 for oversized requests,
and 500 for a backend failure. Task picking can
also return 400 when the task cannot be picked.

Public registration is for volunteers and relies on the Supabase profile creation
trigger. Password reset responses deliberately do not reveal whether an email
address exists. Supabase's reset redirect and password-update page still need
configuration for a complete recovery flow.

## Browser client

Completed member URLs initially return a neutral loader without private markup
or data. It uses this same Bearer-token client to fetch `/api/pages/<page_name>`.
The backend validates the Supabase identity and profile role before returning
rendered HTML. Only completed templates are allowed. See
[frontend integration](FRONTEND_INTEGRATION.md) for page names and routes.
The existing authentication, cookie omission, and session behavior are unchanged.

Load `/static/js/api.js` before `/static/js/site.js` on each page. All current
served pages use this shared client and login modal.

```js
const login = await CICApi.login({ email, password });
if (!login.ok) showError(login.error);

const result = await CICApi.request('/api/tasks');
if (result.ok) renderTasks(result.tasks);

const photo = new FormData();
photo.append('photo', selectedFile);
const upload = await CICApi.request(`/api/tasks/${taskId}/photo`, {
  method: 'POST',
  body: photo,
});

await CICApi.logout();
```

`CICApi.request` supports `method` and a JSON object or `FormData` body. It returns
`ok`, the HTTP `status`, and the API's business fields. Network failures have
`ok: false`, `status: 0`, and a readable `error`. It attaches the token and leaves
multipart Content-Type handling to the browser. Requests must use a same-origin
`/api/` path. The client emits `cic:session-expired` when a token receives 401.

The task management and profile editing routes provide JSON for future browser
forms. They do not create a Tasks or Account Settings page.
