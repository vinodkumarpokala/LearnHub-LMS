# LearnHub LMS – DevOps practice project

A small Flask + SQLite Learning Management System demo. It includes a dashboard, course catalogue, sample students, student enrollment, and health endpoints.

## Features
- View courses and enrollment counts
- Add courses
- View sample students
- Enroll a student in a course
- `/health` checks database connectivity
- `/ready` readiness endpoint

## Run locally (Ubuntu)
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
cd simple_lms_project
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -c "from app import init_db; init_db()"
python app.py
```
Open `http://SERVER_IP:5000`. Check `http://SERVER_IP:5000/health`.

For a production-style run, use Gunicorn behind Nginx and systemd. Do not use Flask's development server for production.

## Deploy on Ubuntu EC2 (Nginx + Gunicorn + systemd)

1. Create an Ubuntu EC2 instance. Allow inbound SSH (22) only from your IP and HTTP (80) from the internet. Do not expose port 8000.
2. Connect:
```bash
ssh -i your-key.pem ubuntu@YOUR_EC2_PUBLIC_IP
```
3. Install packages:
```bash
sudo apt update
sudo apt install -y python3-venv python3-pip nginx
```
4. Copy this project to `/opt/simple-lms` (for example with `scp`), then:
```bash
sudo mkdir -p /opt/simple-lms /var/lib/simple-lms
sudo chown -R ubuntu:ubuntu /opt/simple-lms
sudo chown -R www-data:www-data /var/lib/simple-lms
cd /opt/simple-lms
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```
5. Initialize the database and set ownership:
```bash
sudo -u www-data env LMS_DB_PATH=/var/lib/simple-lms/lms.db \
  /opt/simple-lms/venv/bin/python -c "from app import init_db; init_db()"
sudo chown -R www-data:www-data /var/lib/simple-lms
```
6. Install systemd unit:
```bash
sudo cp deploy/lms.service /etc/systemd/system/lms.service
sudo systemctl daemon-reload
sudo systemctl enable --now lms
sudo systemctl status lms
```
Before production use, replace the example SECRET_KEY in `/etc/systemd/system/lms.service` with a long random secret and restrict access to that file.
7. Configure Nginx:
```bash
sudo cp deploy/nginx-lms.conf /etc/nginx/sites-available/lms
```
Edit `server_name` to your EC2 public IP or domain, then:
```bash
sudo ln -s /etc/nginx/sites-available/lms /etc/nginx/sites-enabled/lms
sudo nginx -t
sudo systemctl reload nginx
```
8. Test:
```bash
curl -I http://127.0.0.1:8000/health
curl -I http://YOUR_EC2_PUBLIC_IP/health
```

## Useful troubleshooting commands
```bash
sudo systemctl status lms
sudo journalctl -u lms -n 100 --no-pager
sudo journalctl -u nginx -n 100 --no-pager
sudo nginx -t
sudo ss -tulpn
df -h
df -i
free -h
top
curl -v http://127.0.0.1:8000/health
```

## Docker practice
Build and run:
```bash
docker build -t learnhub-lms:1.0 .
docker run -d --name learnhub-lms -p 8000:8000 \
  -v lms-data:/data learnhub-lms:1.0
docker logs learnhub-lms
curl http://localhost:8000/health
```

## Safe failure-injection exercises (local/test environment only)
- Stop the app: `sudo systemctl stop lms`, then diagnose HTTP 502/503 and recover it.
- Break Nginx config in a disposable lab, run `sudo nginx -t`, observe why reload fails, then restore it.
- Use a test copy of the app with an invalid DB path to practise reading `journalctl`.
- Fill a disposable test filesystem only if you have a separate throwaway VM and understand the risk. Never fill a production disk.
- Block port 8000 locally in a disposable lab to understand reverse-proxy failures.

## Important limitations
This is a learning demo, not a production-ready LMS. It has no authentication, authorization, CSRF protection, HTTPS configuration, migrations, backups or multi-user security controls. SQLite is suitable for this small lab, not a high-concurrency production LMS. Add these controls before any real deployment or use with real student data.
