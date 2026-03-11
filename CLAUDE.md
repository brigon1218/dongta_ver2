# AWS Server Configuration

## 🔐 Server Access Information

### Connection Details
- **IP Address**: 52.79.148.197
- **Username**: ubuntu
- **Work Directory**: /home/ubuntu/work_01

### SSH Keys
- **macOS**: `/Users/yonghwanahn/Downloads/dongta_ver2.pem`
- **Windows**: `C:\Users\안용환\workspace\aws\vibe_coding\keystore\dongta_ver2.pem`

### Domain
- **Production Domain**: dongta.theuit.info (Cloudflare SSL)
- **API Endpoint**: https://dongta.theuit.info/api/v1/

## 🚀 Deployment Information

### Project Structure
- **Local Working Directory**: `/Volumes/sk-p31/workspace/vibe_coding/work_01`
- **Server Working Directory**: `/home/ubuntu/work_01`
- **Django App Directory**: `dongta-django`

### Service Ports
- **Django Dev Server**: http://localhost:8000
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

### Docker Compose Services
- `web`: Django application server
- `db`: PostgreSQL database
- `redis`: Redis cache/message broker
- `celery-sync`: Celery worker for sync queue
- `celery-payment`: Celery worker for payment queue
- `celery-beat`: Celery scheduler

## 📝 Environment Variables

Key environment variables to set on server:
```bash
SECRET_KEY=<django-secret-key>
DEBUG=False
ALLOWED_HOSTS=dongta.theuit.info,52.79.148.197,localhost

DATABASE_URL=postgresql://dongta:dongta_dev_pass@db:5432/dongtadb
REDIS_URL=redis://redis:6379/0

EMAIL_HOST_USER=<gmail-address>
EMAIL_HOST_PASSWORD=<gmail-app-password>

DANAL_MERCHANT_ID=<merchant-id>
DANAL_MERCHANT_KEY=<merchant-key>

DJANGO_SETTINGS_MODULE=config.settings.production
```

## 🔄 Common Commands

### SSH Connection
```bash
ssh -i ~/.ssh/dongta_ver2.pem ubuntu@52.79.148.197
```

### Docker Operations
```bash
cd /home/ubuntu/work_01/dongta-django/dongta-django

# View logs
docker-compose logs -f web

# Restart services
docker-compose restart web celery-sync celery-payment

# Database migration
docker-compose exec -T web python manage.py migrate

# Collect static files
docker-compose exec -T web python manage.py collectstatic --noinput
```

## 📋 Deployment Checklist

- [x] Docker images built
- [x] PostgreSQL and Redis running
- [x] Celery workers configured
- [x] Environment variables set
- [ ] Django web service verified
- [ ] Static files collected
- [ ] Admin panel accessible
- [ ] API endpoints tested

---

**Last Updated**: 2026-03-11
**Status**: Production Deployment in Progress
