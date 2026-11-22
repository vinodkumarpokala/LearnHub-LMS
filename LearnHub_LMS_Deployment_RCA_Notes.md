# LearnHub LMS – Deployment Troubleshooting & RCA Notes

**Project:** LearnHub LMS  
**Environment:** Ubuntu EC2, Python/Flask, SQLite, Gunicorn, systemd, Nginx, Git/GitHub  
**Purpose:** Record deployment and publishing errors, their impact, root causes, fixes, validation, and prevention.

> These notes reflect the terminal output and events observed during this project. Where the exact cause was not conclusively established, it is described as a likely cause rather than a confirmed fact.

## 1. Executive summary

The LMS was deployed on Ubuntu EC2 using Flask, SQLite, Gunicorn, systemd, and Nginx. The application was ultimately confirmed healthy through Gunicorn:

```bash
curl http://127.0.0.1:8000/health
```

Observed response:

```json
{"database":"connected","status":"healthy"}
```

The systemd status also showed `lms.service` as `active (running)` with Gunicorn as the main process. Nginx was subsequently configured and the user reported that deployment steps 1–5 were working.

Issues encountered:
- Incorrect assumption about the ZIP extraction directory.
- Python module import failure during database initialization.
- systemd unit file not installed.
- Manual Flask process unable to open the SQLite database.
- SQLite database file mistakenly entered as a shell command.
- GitHub HTTPS password authentication failure.
- Branch-name capitalization mismatch (`Main` vs `main`).
- Non-fast-forward push rejection because remote history already existed.
- README add/add conflict during rebase.
- AWS PEM private key accidentally included in an earlier local commit.

## 2. Incident summary

| ID | Area | Error / symptom | Resolution |
|---|---|---|---|
| INC-01 | Linux paths | `cd simple_lms_project`: No such file or directory | Locate extracted files and use the actual directory |
| INC-02 | Python | `ModuleNotFoundError: No module named 'app'` | Run from project directory or set `PYTHONPATH` |
| INC-03 | systemd | `Unit file lms.service does not exist` | Copy unit file into `/etc/systemd/system/`; reload systemd |
| INC-04 | SQLite | `unable to open database file` | Use correct DB path and service-user permissions |
| INC-05 | Linux shell | `Permission denied` after entering `lms.db` path | Do not execute a database file as a command |
| INC-06 | GitHub auth | Password authentication not supported | Use PAT, GitHub CLI, or SSH |
| INC-07 | Git branch | `Main cannot be resolved to branch` | Use lowercase `main` |
| INC-08 | Git push | `[rejected] main -> main (fetch first)` | Fetch and integrate remote history |
| INC-09 | Git rebase | README add/add conflict | Resolve conflict or abort rebase |
| INC-10 | Git security | PEM key included in local commit | Untrack it, ignore it, review history before publishing |

---

# 3. Detailed root-cause analyses

## INC-01 – Project directory not found

### Symptom

```text
-bash: cd: simple_lms_project: No such file or directory
```

### Root cause

The ZIP archive was extracted directly into `/home/ubuntu`, not into a directory named `simple_lms_project`. The files (`app.py`, `requirements.txt`, `templates/`, `static/`, and `deploy/`) were visible directly in the home directory.

### Impact

- Deployment commands expected a directory that did not exist.
- Work was delayed until the actual extraction location was identified.
- No data loss was indicated.

### Resolution

```bash
pwd
ls -la
```

Work from the directory containing `app.py`, or create a dedicated project directory and place the files there.

### Prevention

- Inspect archive contents before extraction.
- Use a consistent project directory.
- Document the expected working directory.

---

## INC-02 – Python could not import the `app` module

### Symptom

```text
ModuleNotFoundError: No module named 'app'
```

### Root cause

Python could not locate `app.py` on its module search path. The application was under `/opt/simple-lms`, while the initialization command was initially run from another directory.

### Impact

- Database initialization failed during the affected attempts.
- The production database was not ready until the command was run with the correct module path.
- This was a path/configuration issue, not proof that Flask itself was broken.

### Resolution

The successful command used an explicit module path:

```bash
sudo -u www-data env \
  LMS_DB_PATH=/var/lib/simple-lms/lms.db \
  PYTHONPATH=/opt/simple-lms \
  /opt/simple-lms/venv/bin/python \
  -c "from app import init_db; init_db()"
```

Alternatively:

```bash
cd /opt/simple-lms
```

### Validation

```bash
ls -lh /var/lib/simple-lms/
```

The `lms.db` file was subsequently present.

### Prevention

- Use absolute paths in deployment commands.
- Set `WorkingDirectory=/opt/simple-lms` in systemd.
- Keep the runtime and virtual environment paths consistent.

---

## INC-03 – systemd could not find `lms.service`

### Symptom

```text
Failed to enable unit: Unit file lms.service does not exist.
```

### Root cause

The service unit existed in the project's `deploy/` directory but had not been installed in systemd's unit directory.

Expected location:

```text
/etc/systemd/system/lms.service
```

### Impact

- systemd could not start or enable the LMS service.
- Gunicorn was not yet managed by systemd.
- Automatic startup after reboot was not configured.

### Resolution

```bash
sudo cp /opt/simple-lms/deploy/lms.service \
  /etc/systemd/system/lms.service

sudo systemctl daemon-reload
sudo systemctl enable --now lms
```

### Validation

```bash
sudo systemctl status lms
```

Observed successful state included:

```text
Loaded: loaded (/etc/systemd/system/lms.service; enabled)
Active: active (running)
Main PID: ... (gunicorn)
```

### Prevention

- Include service installation in the deployment checklist.
- Verify the source unit exists before copying.
- Run `daemon-reload` after adding or changing a unit.
- Use service name `lms`, not database filename `lms.db`.

---

## INC-04 – SQLite could not open the database file

### Symptom

Running Flask manually:

```bash
python app.py
```

returned:

```text
sqlite3.OperationalError: unable to open database file
```

### Likely root cause

The manually launched Flask process did not necessarily use the same runtime context as the Gunicorn systemd service. The production database was located at `/var/lib/simple-lms/lms.db` and owned by `www-data`. A manual process running as `ubuntu` may not have had the correct database path or write permissions. The exact cause of this manual invocation failure was not independently established from the traceback alone.

### Impact

- The manual Flask process could not open its configured database.
- This did not prove that the production Gunicorn application was unhealthy.
- Running a second development process could cause confusion by using a different database path.

### Resolution and validation

The database directory and file were checked:

```bash
ls -ld /var/lib/simple-lms
ls -l /var/lib/simple-lms/lms.db
```

They were owned by `www-data`. The production health check then returned:

```json
{"database":"connected","status":"healthy"}
```

For a separate manual development test, use a separate writable database:

```bash
cd /opt/simple-lms
LMS_DB_PATH=/tmp/lms-dev.db python app.py
```

Do not change production database ownership just to make a manual development process work.

### Prevention

- Keep development and production database paths separate.
- Run production under its configured service account.
- Check directory permissions as well as file permissions.
- Verify `LMS_DB_PATH` before starting the application.
- Avoid starting a second Flask process while Gunicorn is serving the application.

---

## INC-05 – SQLite database file entered as a shell command

### Symptom

```bash
/var/lib/simple-lms/lms.db
```

returned:

```text
-bash: /var/lib/simple-lms/lms.db: Permission denied
```

### Root cause

The database path was entered by itself. Bash attempted to execute the SQLite database file as if it were a program.

### Impact

- No evidence of database corruption was shown.
- The command did not perform a valid database inspection.

### Resolution

Inspect metadata:

```bash
ls -l /var/lib/simple-lms/lms.db
```

Inspect tables using SQLite CLI, if installed:

```bash
sudo apt install -y sqlite3
sudo -u www-data sqlite3 /var/lib/simple-lms/lms.db ".tables"
```

### Prevention

Understand the difference between:
- Execute a program: `python app.py`
- List metadata: `ls -l file`
- Read text: `cat file`
- Query a database: `sqlite3 database.db`

---

## INC-06 – GitHub rejected account-password authentication

### Symptom

```text
remote: Password authentication is not supported for Git operations.
fatal: Authentication failed
```

### Root cause

The Git remote used HTTPS, but GitHub does not accept the normal account password for Git over HTTPS.

### Impact

- The local commit remained on the computer.
- The repository was not published by that failed push.

### Resolution

Use one of:
1. GitHub Personal Access Token (PAT) over HTTPS.
2. GitHub CLI authentication.
3. SSH authentication.

For HTTPS, enter the GitHub username and use the PAT when Git requests a password.

### Prevention

- Configure authentication before the first push.
- Give a fine-grained PAT only the required repository access and permissions.
- Never commit or share a PAT.
- Revoke a token if exposed.

---

## INC-07 – Branch-name capitalization mismatch

### Symptom

```bash
git push -u origin Main
```

returned:

```text
fatal: Main cannot be resolved to branch
```

### Root cause

The local branch was named `main` in lowercase. `Main` is a different name; Git branch names are case-sensitive.

### Impact

- Git could not find the requested local branch.
- No push was performed by that command.

### Resolution

```bash
git push -u origin main
```

Check the branch:

```bash
git branch
```

### Prevention

- Use a consistent branch naming convention.
- Copy the exact name from `git branch`.
- Remember branch names are case-sensitive.

---

## INC-08 – Non-fast-forward push rejection

### Symptom

```text
! [rejected] main -> main (fetch first)
error: failed to push some refs
```

### Root cause

The GitHub repository already contained a commit not present in the local branch. This can happen when a README, license, or other file is created on GitHub before the first local push.

### Impact

- Git rejected the push to protect remote history.
- The local project was not published by that attempt.
- Local and remote histories needed to be integrated.

### Resolution approach

Fetch and inspect:

```bash
git fetch origin
git log --oneline --graph --decorate --all
```

If histories are related:

```bash
git pull --rebase origin main
```

If histories are unrelated, an intentional merge may be required:

```bash
git pull --no-rebase origin main --allow-unrelated-histories
```

Resolve conflicts before pushing.

### Prevention

- Decide whether GitHub or the local project will create the initial README.
- If GitHub already has files, clone it first and add the project to that clone.
- Fetch and inspect remote history before the first push.
- Do not use `git push --force` as a routine fix.

---

## INC-09 – README add/add conflict during rebase

### Symptom

```text
CONFLICT (add/add): Merge conflict in README.md
error: could not apply ...
```

A later pull also reported that local changes were unmerged.

### Root cause

Both local and remote branches had independently added a file named `README.md`. Git could not automatically decide which version to keep.

The rebase remained in progress, so another pull or push could not safely proceed until the conflict was resolved or the rebase was aborted.

### Impact

- The rebase stopped before completion.
- The branch remained in a rebase-in-progress state.
- Further Git operations failed until the repository state was cleaned up.

### Resolution options

**Option A – Abort the rebase:**

```bash
git rebase --abort
```

**Option B – Resolve the conflict:**

1. Open `README.md`.
2. Review markers:

```text
<<<<<<<
local content
=======
remote content
>>>>>>>
```

3. Keep or combine the required content.
4. Remove all conflict markers and save.
5. Stage the file:

```bash
git add README.md
```

6. Continue:

```bash
git rebase --continue
```

Do not start another pull while a rebase is unresolved.

### Prevention

- Maintain one authoritative root-level `README.md`.
- Avoid independently creating the same file in local and remote repositories.
- Check `git status` before starting another Git operation.
- Abort and inspect if unsure.

---

## INC-10 – AWS private key accidentally included in a local commit

### Symptom

The initial commit output included:

```text
create mode 100644 mylmsproject1.pem
```

This showed that the AWS private-key file was tracked in that commit.

### Root cause

The `.pem` file was inside the project directory and was not excluded before `git add .` and the commit.

### Impact

- The private key entered local Git commit history.
- If that commit had been pushed to an accessible remote, the EC2 credential could have been exposed.
- Removing the file from the latest working tree alone would not remove it from earlier commits.

### Resolution and prevention

Untrack the file while retaining the local copy:

```bash
git rm --cached mylmsproject1.pem
```

Add patterns to `.gitignore`:

```gitignore
*.pem
*.ppk
.env
*.db
*.zip
venv/
__pycache__/
```

Check tracked sensitive files:

```bash
git ls-files | grep -Ei '\.(pem|ppk|zip|db|sqlite3)$'
```

Expected: no output.

Before creating a new commit, review:

```bash
git status
git diff --cached --name-only
```

The local branch history was being cleaned before publishing because the push had not succeeded. A soft reset to the remote branch can create a new clean commit from staged project changes:

```bash
git reset --soft origin/main
```

Then review the staged files before committing again.

**Credential response:** If a private key was ever pushed to a remote or otherwise exposed, treat it as compromised. Replace/rotate the key or remove the old key's access. Deleting it from a later commit does not invalidate the credential.

---

# 4. Final validation checklist

## Application and server

- [ ] EC2 instance is running and status checks pass.
- [ ] SSH works from the approved client IP.
- [ ] Application files are in `/opt/simple-lms`.
- [ ] Production virtual environment is present.
- [ ] Database exists at `/var/lib/simple-lms/lms.db`.
- [ ] Database directory and file have appropriate `www-data` access.
- [ ] `lms.service` is enabled and active.
- [ ] Gunicorn listens on `127.0.0.1:8000`.
- [ ] Nginx configuration passes `sudo nginx -t`.
- [ ] Nginx service is active.
- [ ] `curl http://127.0.0.1:8000/health` returns healthy.
- [ ] `curl http://localhost/health` returns healthy through Nginx.
- [ ] LMS is accessible through the EC2 public IP.

## Git and GitHub

- [ ] Current branch is `main`.
- [ ] Root-level `README.md` exists.
- [ ] `.gitignore` excludes keys, database files, archives, virtual environments, and secrets.
- [ ] `git ls-files` shows no sensitive files.
- [ ] No unresolved merge or rebase is in progress.
- [ ] Local and remote histories are integrated.
- [ ] `git push -u origin main` succeeds.
- [ ] GitHub repository displays the source code and README.

---

# 5. Useful incident-response commands

| Task | Command |
|---|---|
| Current directory | `pwd` |
| List files | `ls -la` |
| Check ownership | `ls -ld /path` |
| Check disk | `df -h` |
| Check memory | `free -h` |
| Check service | `sudo systemctl status lms` |
| Restart service | `sudo systemctl restart lms` |
| Read service logs | `sudo journalctl -u lms -n 100 --no-pager` |
| Check listening ports | `sudo ss -tulpn` |
| Test Gunicorn | `curl http://127.0.0.1:8000/health` |
| Test Nginx path | `curl http://localhost/health` |
| Validate Nginx | `sudo nginx -t` |
| Check Git status | `git status` |
| Check current branch | `git branch --show-current` |
| Inspect history | `git log --oneline --graph --decorate --all` |
| Check remote | `git remote -v` |
| Check tracked sensitive files | `git ls-files \| grep -Ei '\.(pem|ppk|zip|db|sqlite3)$'` |

---

# 6. Interview-ready RCA explanation

### Question: Describe a deployment issue you faced and how you resolved it.

**Sample answer:**

"During my LearnHub LMS deployment on AWS EC2, I faced configuration and deployment issues while setting up a Flask application with Gunicorn, systemd, SQLite, and Nginx.

One issue occurred when systemd could not find the LMS service unit. I investigated the service configuration, found that the unit file had not been copied into `/etc/systemd/system/`, installed it, reloaded systemd, and enabled the service. I verified that Gunicorn was active using `systemctl status lms`.

I also faced a Python module import error during database initialization. I checked the application path and corrected the Python module search path using `PYTHONPATH`.

For database access, I checked the ownership and permissions of `/var/lib/simple-lms/` and confirmed that the production database was owned by the `www-data` service account. I validated database connectivity through the application's health endpoint.

During GitHub publishing, I encountered authentication, branch-name, non-fast-forward, and README merge-conflict issues. I corrected the authentication method, used the correct `main` branch name, fetched remote history, and worked through the README conflict rather than force-pushing.

I also identified that an AWS PEM key had accidentally entered a local commit. I excluded sensitive files and reviewed the Git history before publishing.

Finally, I validated the deployment through Gunicorn and Nginx using HTTP health checks."

### RCA structure to remember

1. **Problem:** What failed?
2. **Impact:** What was affected?
3. **Investigation:** Which commands and logs did you check?
4. **Root cause:** Why did it happen?
5. **Resolution:** What change fixed it?
6. **Validation:** How did you prove recovery?
7. **Prevention:** What will stop it happening again?

---

# 7. Lessons learned

1. Verify the working directory before running application commands.
2. Use absolute paths in deployment scripts and service files.
3. Understand Linux ownership and permissions, especially for service users.
4. Know the difference between a development server and a production WSGI server.
5. Understand systemd install, reload, enable, start, and status operations.
6. Check upstream application health when troubleshooting Nginx 502 errors.
7. Fetch and inspect remote Git history before pushing.
8. Review staged files before committing.
9. Never commit AWS private keys, tokens, or application secrets.
10. Validate every fix rather than assuming a command succeeded.

**End of deployment RCA notes – LearnHub LMS v1.0**
