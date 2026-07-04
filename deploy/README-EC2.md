# AWS EC2 deployment guide for PBQMS

## 1. Prepare the EC2 instance
Use an Ubuntu 22.04+ instance with at least:
- 2 vCPUs
- 4 GB RAM
- 20 GB storage
- Security group allowing TCP 80, 443, and 22

## 2. Install dependencies on the server
```bash
sudo apt update
sudo apt install -y git
```

## 3. Run the setup script
```bash
sudo bash -c 'REPO_URL=https://github.com/your-org/pbqms.git BRANCH=main bash -s' < deploy/ec2-setup.sh
```

If you are deploying from the current workspace, copy the repo to the server first and run:
```bash
sudo bash deploy/ec2-setup.sh
```

## 4. Configure environment variables
Edit the app environment file:
```bash
sudo nano /home/ubuntu/pbqms/.env
```

Recommended production values:
```env
FLASK_ENV=production
SECRET_KEY=replace-with-a-long-random-string
DATABASE_URL=sqlite:////home/ubuntu/pbqms/pbqms_dev.sqlite3
BASE_URL=http://YOUR_EC2_PUBLIC_IP
SMS_PROVIDER=mock
```

For production MySQL, use a MySQL URI such as:
```env
DATABASE_URL=mysql+pymysql://user:password@host:3306/dbname
```

## 5. Initialize the database
```bash
cd /home/ubuntu/pbqms
source venv/bin/activate
flask db upgrade
flask seed-db
flask create-admin
```

## 6. Verify the deployment
```bash
sudo systemctl status pbqms
curl http://127.0.0.1:8000/
```

## 7. Optional: HTTPS with Nginx and Let's Encrypt
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## Notes
- The app is served through Gunicorn and Nginx.
- Socket.IO traffic is proxied through Nginx.
- For production, replace the SQLite fallback with MySQL or another managed database.
