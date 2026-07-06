# Deploying the backend to PythonAnywhere (free tier)

PythonAnywhere's free tier only serves WSGI apps directly, not ASGI, so
`backend/wsgi.py` wraps the FastAPI app with `a2wsgi`. Free tier also has
no always-on background process, so the nightly scan runs via
PythonAnywhere's free daily **Scheduled Task** instead of the in-process
scheduler (`app/scheduler.py` is left in place and harmless -- it just
won't reliably fire under this hosting model).

## 1. Clone the repo

Open a **Bash console** (Consoles tab -> Bash) and run:

```bash
git clone https://github.com/zhan89-code/minervini-scanner.git
cd minervini-scanner/backend
mkvirtualenv --python=/usr/bin/python3.10 minervini-env
pip install -r requirements.txt
```

## 2. Set your allowed origin

Edit `wsgi.py` and change the default in this line to your actual Vercel
frontend URL once you have it (or edit it now, it's fine to update later
and reload the web app):

```python
os.environ.setdefault("ALLOWED_ORIGINS", "https://your-frontend.vercel.app")
```

## 3. Create the web app

Web tab -> **Add a new web app** -> choose **Manual configuration** (not
Flask/Django) -> pick the Python version matching your virtualenv.

- **Virtualenv** section: point it at `/home/YOUR_USERNAME/.virtualenvs/minervini-env`
- **Code** section -> **WSGI configuration file**: open it and replace the
  whole contents with:

  ```python
  import sys
  path = "/home/YOUR_USERNAME/minervini-scanner/backend"
  if path not in sys.path:
      sys.path.insert(0, path)

  from wsgi import application
  ```

- Click the green **Reload** button at the top of the Web tab.

Your API is now live at `https://YOUR_USERNAME.pythonanywhere.com`.
Sanity check: visit `https://YOUR_USERNAME.pythonanywhere.com/api/meta` --
you should see `{"last_run":null,"status":"unknown","universe_size":10}`.

## 4. Set up the daily scan (Tasks tab)

Tasks tab -> **Scheduled tasks** -> add a task (free tier gets one, daily,
UTC time -- pick a time after US market close, e.g. `21:30`):

```bash
cd /home/YOUR_USERNAME/minervini-scanner/backend && workon minervini-env && python -m pipeline.run_nightly
```

This is what actually keeps data fresh going forward -- the in-process
scheduler in `app/scheduler.py` is not reliable here since PythonAnywhere
free web workers aren't a persistent long-running process the way
Railway/Fly.io/a VPS would be.

Run it once manually right after setup (same command, in a Bash console)
so there's data to look at immediately instead of waiting for the first
scheduled run.

## 5. Point the frontend at it

On Vercel, set the env var:

```
VITE_API_BASE=https://YOUR_USERNAME.pythonanywhere.com
```

Redeploy the frontend. Done -- no further manual commands, the Scheduled
Task keeps the data current on its own.

## Known limitations of this path

- Free PythonAnywhere web apps get disabled if you don't log in to the
  site for 3 months (a one-click reactivation, not a data loss).
- CPU-second budget on free tier is limited; the nightly scan is mostly
  network-bound (waiting on yfinance), not CPU-bound, so it should stay
  well under budget for the default 10-ticker universe -- but this is
  worth watching if the universe is ever expanded to hundreds of tickers.
