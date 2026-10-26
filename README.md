# Food Pantry Web-Based
A web application that connects food pantry volunteers with delivery tasks, and lets the pantry organization manage tasks and verify deliveries.

# GitHub Workflow
- Switch to main and pull the latest changes
- Create your own branch for your work
- Commit changes with a clear message
- Push your branch and open a pull request
- After it's reviewed, merge it into main

NEVER commit .env as it holds your keys!

# Tech Stack
- Python
- Flask 
- Supabase 
- python-dotenv 

# How to Set Up

Use Python 3.12 or newer. From the repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

On Windows, activate the environment with `.venv\Scripts\Activate.ps1`
(PowerShell) or `.venv\Scripts\activate.bat` (Command Prompt).

Fill in `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` in `.env`.
Keep `.env` private; it is ignored by Git.

# How to Run

```sh
python -m Backend.main
```

Open http://127.0.0.1:5050. This single Flask application serves the frontend,
static assets, and all `/api/*` endpoints. `python Backend/main.py` also works.
The old `Frontend/cic-site/app.py` entry point delegates to the same application
and uses port 5050.

Do not start both entry points at once. No second frontend server or CORS
configuration is needed. The homepage is `home.html`; `/`, `/index.html`, and
`/home.html` all render it. About, Donate, and Volunteer pages are also available.

# API Contract

See [docs/API.md](docs/API.md) for endpoints, authentication, request examples,
and response shapes. The shared browser client is
`Frontend/cic-site/static/js/api.js` (`window.CICApi`).

- Every API JSON response has `ok: true` or `ok: false`.
- Errors include `error` and use an appropriate HTTP error status.
- Protected endpoints require `Authorization: Bearer <access_token>`.
- Login stores the access token in the browser tab's `sessionStorage`; requests
  attach it automatically. Flask session cookies are not used for authentication.
- Registration remains paused pending the existing Auth/Profile setup decision.

# Tests

The tests mock Supabase; they do not modify live data or send reset emails.

```sh
python -m unittest discover -s tests -v
node --test tests/api-client.test.cjs
```

Node.js is only needed for the browser-client tests, not to run the application.

To run the stateful Volunteer/Admin mock workflows and regenerate a readable
report with per-scenario evidence:

```sh
python -m scripts.verify_mock_roles
```

See [docs/MOCK_VERIFICATION.md](docs/MOCK_VERIFICATION.md) for results, including
blocked registration and business methods that do not yet have API routes.
The mock uses fictional data from `tests/fixtures/role_scenarios.json`, runs the
real business classes, and blocks all network connections during each scenario.
