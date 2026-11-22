# LearnHub LMS – AWS EC2 Deployment (DevOps Practice)

A simple Learning Management System built with Python Flask and SQLite, deployed on Ubuntu EC2 using Gunicorn, systemd, and Nginx.

> **Learning/demo project only.** This application does not include authentication, authorization, CSRF protection, HTTPS, database migrations, backups, or production-grade data protection. Do not use it with real student or sensitive data without adding these controls.

## 1. Architecture

```text
Browser
  |
  | HTTP :80
  v
AWS EC2 Security Group
  |
  v
Nginx (reverse proxy)
  |
  | http://127.0.0.1:8000
  v
Gunicorn
  |
  v
Flask LMS
  |
  v
SQLite: /var/lib/simple-lms/lms.db
```

| Component | Purpose |
|---|---|
| AWS EC2 | Ubuntu server hosting the LMS |
| Security Group | Controls inbound traffic |
| Flask | LMS web application |
| SQLite | Practice database |
| Gunicorn | WSGI application server |
| systemd | Manages the LMS service |
| Nginx | Public HTTP entry point and reverse proxy |

## 2. Application features

- LMS dashboard with course, student and enrollment counts
- Course catalogue and add-course form
- Sample student directory
- Student enrollment
- `GET /health` checks application/database connectivity
- `GET /ready` readiness endpoint

## 3. Prerequisites and security group

You need an AWS account, Ubuntu EC2 instance, SSH key pair (`.pem`), and an SSH client such as MobaXterm.

Configure these inbound rules:

| Type | Protocol | Port | Source | Purpose |
|---|---|---:|---|---|
| SSH | TCP | 22 | Your public IP `/32` | SSH administration |
| HTTP | TCP | 80 | `0.0.0.0/0` | Public website |
| HTTPS | TCP | 443 | `0.0.0.0/0` | Add when HTTPS is configured |

Do not expose Gunicorn port `8000` publicly. Do not leave Flask development port `5000` open to the internet. If temporarily testing port 5000, restrict it to your own IP and remove the rule afterwards.

# Deployment – Steps 1–5

## Step 1 – Create and connect to EC2

1. Launch an Ubuntu EC2 instance.
2. Attach the security group rules above.
3. Wait until EC2 status checks pass.
4. Copy the instance public IPv4 address.
5. Connect:

```bash
ssh -i "your-key.pem" ubuntu@YOUR_EC2_PUBLIC_IP
```

For MobaXterm: Session → SSH; enter the public IP, username `ubuntu`, port `22`, and select your `.pem` private key under Advanced SSH settings.

Never upload or commit your `.pem` private key to GitHub.

## Step 2 – Upload and extract the project

Upload the ZIP from your **local computer** using MobaXterm SFTP or SCP. Example SCP command (run locally, not inside the EC2 SSH session):

```bash
scp -i "your-key.pem" simple_lms_devops_practice.zip ubuntu@YOUR_EC2_PUBLIC_IP:~
```

On EC2:

```bash
sudo apt update
sudo apt install -y unzip
unzip simple_lms_devops_practice.zip
pwd
ls -la
```

The archive may extract its files directly into `/home/ubuntu`. Confirm that you can see `app.py`, `requirements.txt`, `templates/`, `static/`, and `deploy/`. If they are in a subdirectory, change into that directory.

## Step 3 – Install dependencies and prepare the app

Install packages:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx
```

Create a virtual environment and install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Optional initial development smoke test:

```bash
python -c "from app import init_db; init_db()"
python app.py
```

The Flask development server listens on port `5000`. Use it only for a temporary test. Stop it with `Ctrl+C`. Do not use the Flask development server for production.

Prepare the production application and database directories:

```bash
sudo mkdir -p /opt/simple-lms /var/lib/simple-lms
sudo cp -a app.py requirements.txt templates static deploy /opt/simple-lms/
sudo python3 -m venv /opt/simple-lms/venv
sudo /opt/simple-lms/venv/bin/pip install -r /opt/simple-lms/requirements.txt
sudo chown -R www-data:www-data /var/lib/simple-lms
```

Initialize the database as the service user:

```bash
sudo -u www-data env \
  LMS_DB_PATH=/var/lib/simple-lms/lms.db \
  PYTHONPATH=/opt/simple-lms \
  /opt/simple-lms/venv/bin/python \
  -c "from app import init_db; init_db()"
```

Verify ownership and file existence:

```bash
ls -ld /var/lib/simple-lms
ls -l /var/lib/simple-lms/lms.db
```

The directory and database should be owned by `www-data`. Do not try to execute `lms.db` as a shell command.

## Step 4 – Configure Gunicorn with systemd

Copy the supplied service unit:

```bash
sudo cp /opt/simple-lms/deploy/lms.service /etc/systemd/system/lms.service
```

Generate a secret:

```bash
openssl rand -hex 32
```

Edit the service file:

```bash
sudo nano /etc/systemd/system/lms.service
```

Replace the example `SECRET_KEY` with the generated value. Do not commit the secret to GitHub or share it in screenshots.

The service is expected to use `/opt/simple-lms` as its working directory, `www-data` as its service user, `/var/lib/simple-lms/lms.db` as the database, and Gunicorn bound to `127.0.0.1:8000`.

Reload systemd and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now lms
sudo systemctl status lms
```

Test Gunicorn directly:

```bash
curl http://127.0.0.1:8000/health
```

Expected:

```json
{"database":"connected","status":"healthy"}
```

Useful service commands:

```bash
sudo systemctl status lms
sudo systemctl restart lms
sudo systemctl stop lms
sudo systemctl start lms
sudo journalctl -u lms -n 50 --no-pager
```

## Step 5 – Configure Nginx and verify public access

Edit the Nginx configuration:

```bash
sudo nano /opt/simple-lms/deploy/nginx-lms.conf
```

Use this configuration for the single-site lab:

```nginx
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Install and enable the site:

```bash
sudo cp /opt/simple-lms/deploy/nginx-lms.conf /etc/nginx/sites-available/lms
sudo ln -sfn /etc/nginx/sites-available/lms /etc/nginx/sites-enabled/lms
sudo rm -f /etc/nginx/sites-enabled/default
```

Test before restarting:

```bash
sudo nginx -t
```

Expected output includes `syntax is ok` and `test is successful`.

Enable and restart Nginx:

```bash
sudo systemctl enable nginx
sudo systemctl restart nginx
sudo systemctl status nginx
```

Test through Nginx:

```bash
curl http://localhost/health
curl -I http://localhost
```

Then open:

```text
http://YOUR_EC2_PUBLIC_IP
```

The LMS dashboard should load. Confirm that the Security Group allows inbound HTTP port `80`.

---

## 4. Troubleshooting reference

| Symptom | Investigation |
|---|---|
| SSH fails | Check EC2 state/status checks, public IP, port 22 rule, route and key |
| Website unavailable | `sudo systemctl status nginx`; verify port 80 rule |
| Nginx returns 502 | `sudo systemctl status lms`; `sudo ss -tulpn \| grep 8000` |
| LMS service fails | `sudo journalctl -u lms -n 100 --no-pager` |
| Nginx config error | `sudo nginx -t` |
| Database cannot open | `ls -ld /var/lib/simple-lms`; `ls -l /var/lib/simple-lms/lms.db` |
| Disk full | `df -h`; `df -i`; `sudo du -sh /var/log/*` |
| High memory | `free -h`; `ps aux --sort=-%mem \| head` |
| High CPU | `top`; `ps aux --sort=-%cpu \| head` |
| Port conflict | `sudo ss -tulpn` |

If Python reports `ModuleNotFoundError: No module named 'app'` during database initialization, use `PYTHONPATH=/opt/simple-lms` as shown in Step 3.

If systemd reports `Unit lms.service does not exist`, verify and copy the unit file, then reload systemd:

```bash
ls -l /opt/simple-lms/deploy/lms.service
sudo cp /opt/simple-lms/deploy/lms.service /etc/systemd/system/lms.service
sudo systemctl daemon-reload
```

Use service name `lms`, not database filename `lms.db`.

## 5. Production incident simulation (lab instance only)

This exercise intentionally stops the LMS service. Run only on your own practice EC2 instance.

**Scenario:** Nginx remains running, but Gunicorn/LMS stops. The website should return `502 Bad Gateway`.

Stop the LMS:

```bash
sudo systemctl stop lms
curl -I http://localhost
```

Investigate:

```bash
sudo systemctl status nginx
sudo systemctl status lms
sudo journalctl -u lms -n 50 --no-pager
sudo ss -tulpn | grep 8000
```

Recover:

```bash
sudo systemctl start lms
sudo systemctl status lms
curl http://127.0.0.1:8000/health
curl http://localhost/health
```

Expected health response:

```json
{"database":"connected","status":"healthy"}
```

**Interview explanation:** Nginx was running, but the upstream Gunicorn application service was stopped. I checked systemd status and application logs, confirmed the application was not listening on port 8000, restarted the LMS service, and validated recovery through the health endpoint and an HTTP request through Nginx.

## 6. Push the project to GitHub

Run these commands from your **local computer** in the project directory. Do not commit private keys, secrets, virtual environments, database files, or sensitive data.

Create `.gitignore`:

```gitignore
venv/
__pycache__/
*.py[cod]
*.db
.env
*.pem
```

Initialize and push:

```bash
git init
git add .
git status
git commit -m "Add LearnHub LMS AWS EC2 deployment project"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
git push -u origin main
```

If a remote already exists, inspect it with `git remote -v` rather than adding it again.

## 7. Next learning milestones

1. Docker – build an image and run the LMS container with persistent storage.
2. Git/GitHub – branches, pull requests and versioned changes.
3. Jenkins CI/CD – automate testing, image build and deployment.
4. Terraform – provision AWS infrastructure as code.
5. Kubernetes – Deployments, Services, ConfigMaps and probes.
6. Prometheus/Grafana – monitor infrastructure and application health.
7. AI-powered DevOps – build an incident assistant that analyses logs and suggests investigation steps.

## 8. Project checklist

- [x] EC2 instance and SSH access
- [x] Security Group configuration
- [x] Python environment and dependencies
- [x] SQLite database initialization
- [x] Gunicorn application server
- [x] systemd service
- [x] Nginx reverse proxy
- [x] Local health-check verification
- [ ] Docker containerization
- [ ] Jenkins CI/CD
- [ ] Terraform infrastructure automation
- [ ] Kubernetes deployment
- [ ] Prometheus and Grafana monitoring
