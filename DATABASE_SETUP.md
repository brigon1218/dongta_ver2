# Database Setup Guide

## 📍 대용량 데이터베이스 파일 위치

### Local (로컬 개발 환경)
```
./dongta.mysql/
├── dongta_1022.sql (1.1GB) - 동타 MySQL 전체 덤프
├── mysql_data.tar.gz (428MB) - MySQL 데이터 압축 파일
├── mysql_dongta_dump.sql (1.1GB) - 동타 MySQL 백업
└── create_user_db.txt - 데이터베이스 사용자 생성 스크립트
```

### AWS Server (운영 서버)
```
Host: 52.79.148.197
User: ubuntu
Key: /Users/yonghwanahn/Downloads/dongta_ver2.pem
Path: /home/ubuntu/work_01/database_dumps/

Remote Location:
├── dongta_1022.sql (1.1GB)
├── mysql_data.tar.gz (428MB)
└── mysql_dongta_dump.sql (1.1GB)
```

## 🔧 데이터베이스 복원 방법

### 1. Local MySQL 복원

#### Option A: SQL 파일로 복원
```bash
# 1. MySQL 접속
mysql -u root -p

# 2. 데이터베이스 생성
CREATE DATABASE dongta_dev DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

# 3. 덤프 파일로 복원
mysql -u root -p dongta_dev < dongta.mysql/dongta_1022.sql
# 또는
mysql -u root -p dongta_dev < dongta.mysql/mysql_dongta_dump.sql

# 4. 복원 확인
USE dongta_dev;
SHOW TABLES;
```

#### Option B: Compressed 파일로 복원
```bash
# 1. 압축 해제
cd dongta.mysql/
tar -xzf mysql_data.tar.gz

# 2. Docker MySQL 컨테이너에 복원 (권장)
docker-compose -f docker-compose.yml up -d postgres redis
# PostgreSQL에서는 migration 필요 (Python script 사용)
cd dongta-django/
python manage.py migrate
python data_migration/migrate_members.py
```

### 2. AWS Server MySQL 복원

#### SSH 접속
```bash
ssh -i /Users/yonghwanahn/Downloads/dongta_ver2.pem ubuntu@52.79.148.197

# AWS 서버에서
cd /home/ubuntu/work_01/database_dumps/

# MySQL 접속
mysql -u root -p

# 데이터베이스 복원
CREATE DATABASE dongta DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE dongta;
SOURCE /home/ubuntu/work_01/database_dumps/dongta_1022.sql;
```

### 3. Docker로 복원 (Production)

#### docker-compose.prod.yml 사용
```bash
cd /home/ubuntu/work_01/dongta-django/

# PostgreSQL 마이그레이션 (Django ORM)
docker-compose -f docker-compose.prod.yml up -d

docker-compose -f docker-compose.prod.yml exec web python manage.py migrate

# MySQL 데이터 동기화 (필요시)
docker-compose -f docker-compose.prod.yml exec web python ../data_migration/migrate_members.py
```

## 📊 파일 크기 및 추정 시간

| 파일 | 크기 | 복원 시간 |
|------|------|---------|
| dongta_1022.sql | 1.1GB | ~2-3분 |
| mysql_data.tar.gz | 428MB | ~1분 (해제) |
| mysql_dongta_dump.sql | 1.1GB | ~2-3분 |

## 🔐 MySQL 사용자 설정

```bash
# 1. MySQL 접속
mysql -u root -p

# 2. 사용자 생성
CREATE USER 'dongta'@'localhost' IDENTIFIED BY 'password';

# 3. 권한 부여
GRANT ALL PRIVILEGES ON dongta.* TO 'dongta'@'localhost';
GRANT ALL PRIVILEGES ON dongta_dev.* TO 'dongta'@'localhost';
FLUSH PRIVILEGES;

# 4. 원격 접속 허용 (AWS)
CREATE USER 'dongta'@'%' IDENTIFIED BY 'password';
GRANT ALL PRIVILEGES ON dongta.* TO 'dongta'@'%';
FLUSH PRIVILEGES;
```

## 📝 Django 설정

### settings/base.py
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'dongta'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

# MySQL 백업 데이터 접근 (마이그레이션 용)
LEGACY_DB = {
    'ENGINE': 'django.db.backends.mysql',
    'NAME': os.getenv('LEGACY_DB_NAME', 'dongta'),
    'USER': os.getenv('LEGACY_DB_USER', 'root'),
    'PASSWORD': os.getenv('LEGACY_DB_PASSWORD'),
    'HOST': os.getenv('LEGACY_DB_HOST', 'localhost'),
    'PORT': os.getenv('LEGACY_DB_PORT', '3306'),
}
```

### .env 파일
```env
# PostgreSQL (Primary)
DB_NAME=dongta
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=postgres
DB_PORT=5432

# MySQL (Legacy - for migration)
LEGACY_DB_NAME=dongta
LEGACY_DB_USER=root
LEGACY_DB_PASSWORD=your_password
LEGACY_DB_HOST=localhost
LEGACY_DB_PORT=3306
```

## 🚀 빠른 시작

### Local Development
```bash
# 1. Docker로 MySQL 시작
docker run --name mysql-dongta -e MYSQL_ROOT_PASSWORD=root -p 3306:3306 -v mysql_data:/var/lib/mysql -d mysql:8.0

# 2. 데이터베이스 복원
docker exec mysql-dongta sh -c 'mysql -u root -proot < /docker-entrypoint-initdb.d/dongta_1022.sql'

# 3. Django 마이그레이션
cd dongta-django/
python manage.py migrate

# 4. 서버 시작
python manage.py runserver
```

### AWS Production
```bash
# AWS 서버에서
ssh -i /Users/yonghwanahn/Downloads/dongta_ver2.pem ubuntu@52.79.148.197

cd /home/ubuntu/work_01/dongta-django/

# Docker Compose 실행
docker-compose -f docker-compose.prod.yml up -d

# 마이그레이션 실행
docker-compose -f docker-compose.prod.yml exec web python manage.py migrate

# 정적 파일 수집
docker-compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput

# 서버 상태 확인
docker-compose -f docker-compose.prod.yml ps
```

## ⚠️ 주의사항

1. **대용량 파일**: 이 파일들은 Git에서 제외됨 (.gitignore)
2. **백업**: 프로덕션 전에 항상 백업 수행
3. **권한**: AWS에서 데이터베이스 복원 시 sudo 권한 필요
4. **인증**: SSH 키 권한: `chmod 600 dongta_ver2.pem`

## 📞 트러블슈팅

### MySQL 연결 실패
```bash
# MySQL 상태 확인
mysql -u root -p -e "SELECT 1;"

# 포트 확인
lsof -i :3306

# Docker 로그 확인
docker logs mysql-dongta
```

### 대용량 파일 업로드 실패
```bash
# AWS 서버 디스크 공간 확인
ssh -i dongta_ver2.pem ubuntu@52.79.148.197 "df -h"

# SCP로 재시도
scp -i dongta_ver2.pem dongta.mysql/dongta_1022.sql ubuntu@52.79.148.197:/home/ubuntu/work_01/database_dumps/
```

## 📅 최종 업데이트

- **Date**: 2026-03-09
- **Status**: ✅ AWS 업로드 완료
- **Total Size**: 2.6GB
- **Location**: `/home/ubuntu/work_01/database_dumps/`

---

**Note**: 이 파일들은 개발/테스트용입니다. 프로덕션에서는 정기적인 자동 백업 시스템을 구성하세요.
