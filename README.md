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

# Module 6: Docker Data Persistence – LearnHub LMS

## Overview

In this module, we configured persistent storage for the LearnHub LMS application using Docker volumes.

The objective was to ensure that application data stored in the SQLite database remains available even after the Docker container is stopped, removed, or recreated.

This module demonstrates an important real-world DevOps concept: **container lifecycle and application data lifecycle should be managed separately.**

## Learning Objectives

By completing this module, I learned:

- How Docker containers store application data
- Difference between container storage and persistent storage
- How Docker named volumes work
- How to configure a volume for SQLite database persistence
- How to inspect database records inside a container
- How to validate application health
- How to test persistence after container recreation

## Architecture

```text
User / Browser
      |
      | HTTP :8080
      |
EC2 Ubuntu Instance
      |
      | Docker Port Mapping
      |
LearnHub LMS Container
      |
      | SQLite Database
      |
/data/lms.db
      |
      | Docker Named Volume
      |
learnhub-data
```

## Environment

| Component | Configuration |
|---|---|
| Cloud | AWS EC2 |
| Operating System | Ubuntu |
| Application | Flask LMS |
| Application Server | Gunicorn |
| Database | SQLite |
| Container Runtime | Docker |
| Container Name | learnhub-lms |
| Docker Image | learnhub-lms:v1 |
| Host Port | 8080 |
| Container Port | 8000 |
| Database Path | /data/lms.db |
| Docker Volume | learnhub-data |

## Step 1: Stop and Remove the Existing Container

Before recreating the container, remove the existing container.

```bash
sudo docker stop learnhub-lms
```

```bash
sudo docker rm learnhub-lms
```

Removing a container does not remove a separately managed named volume.

## Step 2: Create a Container with Persistent Storage

Run the following command:

```bash
sudo docker run -d \
  --name learnhub-lms \
  -p 8080:8000 \
  -e LMS_DB_PATH=/data/lms.db \
  -v learnhub-data:/data \
  --restart unless-stopped \
  learnhub-lms:v1
```

### Explanation

| Command | Purpose |
|---|---|
| `-d` | Run container in background |
| `--name learnhub-lms` | Assign container name |
| `-p 8080:8000` | Map host port 8080 to container port 8000 |
| `-e LMS_DB_PATH=/data/lms.db` | Configure SQLite database location |
| `-v learnhub-data:/data` | Mount named volume |
| `--restart unless-stopped` | Restart container automatically unless manually stopped |
| `learnhub-lms:v1` | Specify Docker image |

## Step 3: Verify the Container

```bash
sudo docker ps
```

Expected result:

```text
CONTAINER ID   IMAGE             STATUS
xxxxxxxxxxxx   learnhub-lms:v1   Up
```

Check container logs:

```bash
sudo docker logs learnhub-lms
```

Expected log output:

```text
Starting gunicorn
Listening at: http://0.0.0.0:8000
```

## Step 4: Verify Database Records

Execute the following command:

```bash
sudo docker exec learnhub-lms python -c "
import sqlite3
c = sqlite3.connect('/data/lms.db')
print('Courses:', c.execute('SELECT COUNT(*) FROM courses').fetchone()[0])
print('Students:', c.execute('SELECT COUNT(*) FROM students').fetchone()[0])
print('Enrollments:', c.execute('SELECT COUNT(*) FROM enrollments').fetchone()[0])
c.close()
"
```

### Output from my deployment

```text
Courses: 3
Students: 2
Enrollments: 0
```

This confirms that the SQLite database contains the expected records.

## Step 5: Verify the Docker Volume

List Docker volumes:

```bash
sudo docker volume ls
```

Inspect the volume:

```bash
sudo docker volume inspect learnhub-data
```

The volume is managed by Docker and mounted at `/data` inside the container.

## Step 6: Verify Application Health

```bash
curl http://127.0.0.1:8080/health
```

Expected output:

```json
{
  "database": "connected",
  "status": "healthy"
}
```

This confirms that the application is running and can connect to its database.

## Step 7: Persistence Test

### Test A: Restart the container

```bash
sudo docker restart learnhub-lms
```

Check database records again:

```bash
sudo docker exec learnhub-lms python -c "
import sqlite3
c = sqlite3.connect('/data/lms.db')
print(c.execute('SELECT COUNT(*) FROM courses').fetchone()[0])
"
```

Expected result:

```text
3
```

### Test B: Remove and recreate the container

Stop and remove the container:

```bash
sudo docker stop learnhub-lms
sudo docker rm learnhub-lms
```

Recreate it using the same volume:

```bash
sudo docker run -d \
  --name learnhub-lms \
  -p 8080:8000 \
  -e LMS_DB_PATH=/data/lms.db \
  -v learnhub-data:/data \
  --restart unless-stopped \
  learnhub-lms:v1
```

Verify the database:

```bash
sudo docker exec learnhub-lms python -c "
import sqlite3
c = sqlite3.connect('/data/lms.db')
print('Courses:', c.execute('SELECT COUNT(*) FROM courses').fetchone()[0])
print('Students:', c.execute('SELECT COUNT(*) FROM students').fetchone()[0])
"
```

Expected output:

```text
Courses: 3
Students: 2
```

The records remain available after container recreation.

## Troubleshooting Notes

### Issue: Database table does not exist

Error:

```text
sqlite3.OperationalError: no such table: courses
```

Possible cause:

The application was connected to a new or empty SQLite database.

Investigation:

```bash
sudo docker exec learnhub-lms env | grep LMS_DB_PATH
```

```bash
sudo docker exec learnhub-lms ls -l /data
```

Resolution:

Ensure the application uses the correct database path and that the existing database is mounted through the Docker volume.

### Issue: Application returns HTTP 500

Investigation:

```bash
sudo docker logs --tail 100 learnhub-lms
```

Check database connectivity:

```bash
curl http://127.0.0.1:8080/health
```

A healthy database connection does not guarantee that every application table exists. Review the application traceback and database schema.

## Root Cause Analysis

### Problem

Application data can be lost when it is stored only inside a container's writable layer.

### Root Cause

Docker containers are designed to be replaceable. When a container is removed, data stored only in its writable layer is removed with it.

### Resolution

A Docker named volume was configured:

```bash
-v learnhub-data:/data
```

The SQLite database was configured to use:

```text
/data/lms.db
```

This separates database storage from the container lifecycle.

### Validation

- Container started successfully
- Application health endpoint returned healthy
- SQLite database connected successfully
- Course and student records were verified
- Data remained available after container recreation

## Important DevOps Concepts

### Container vs Volume

| Container | Volume |
|---|---|
| Runs the application | Stores persistent data |
| Can be recreated | Exists independently |
| Contains application runtime | Contains database files |
| Replaceable | Retained until explicitly deleted |

### Important Warning

Do not remove the named volume during normal container replacement.

Avoid:

```bash
sudo docker rm -v learnhub-lms
```

Also avoid deleting the volume itself:

```bash
sudo docker volume rm learnhub-data
```

These commands can remove persistent data.

## Interview Explanation

"In my LearnHub LMS project, I implemented Docker data persistence using a named volume.

Initially, the SQLite database was stored inside the container. I understood that if the container was removed, the database could be lost.

To solve this, I created a Docker named volume called `learnhub-data` and mounted it at `/data` inside the container. I configured the Flask application to use `/data/lms.db`.

I validated the setup by checking database records, restarting the container, removing it, and recreating it with the same volume.

The course and student records remained available, confirming that persistent storage was working correctly."

## Outcome

Successfully completed the Docker persistence module.

The LearnHub LMS application now uses Docker-managed persistent storage for its SQLite database.

**Next Module:** Docker Compose – Managing the LMS application using declarative configuration.

