# Database Files Mirror Locations

## 📡 대용량 데이터베이스 파일 미러 위치

현재 Git에서 제외된 대용량 데이터베이스 파일들의 미러 위치입니다.

### AWS Server Mirror
```
🌐 IP: 52.79.148.197
👤 User: ubuntu
🔑 Key: /Users/yonghwanahn/Downloads/dongta_ver2.pem
📂 Path: /home/ubuntu/work_01/database_dumps/

Total Size: 2.6GB
Upload Date: 2026-03-09
```

### 파일 목록

| 파일명 | 크기 | 설명 | 복원 시간 |
|--------|------|------|---------|
| `dongta_1022.sql` | 1.1GB | 동타 MySQL 전체 덤프 | ~2-3분 |
| `mysql_data.tar.gz` | 428MB | MySQL 데이터 압축 파일 | ~1분 |
| `mysql_dongta_dump.sql` | 1.1GB | 동타 MySQL 백업본 | ~2-3분 |

### SSH로 접속하여 파일 다운로드

```bash
# 전체 파일 다운로드
scp -i /Users/yonghwanahn/Downloads/dongta_ver2.pem \
  -r ubuntu@52.79.148.197:/home/ubuntu/work_01/database_dumps \
  ./local_dumps/

# 특정 파일만 다운로드
scp -i /Users/yonghwanahn/Downloads/dongta_ver2.pem \
  ubuntu@52.79.148.197:/home/ubuntu/work_01/database_dumps/dongta_1022.sql \
  ./dongta.mysql/
```

### 직접 AWS에서 복원

```bash
# 1. AWS 서버 접속
ssh -i /Users/yonghwanahn/Downloads/dongta_ver2.pem ubuntu@52.79.148.197

# 2. 파일 확인
ls -lh /home/ubuntu/work_01/database_dumps/

# 3. MySQL로 복원
mysql -u root -p
CREATE DATABASE dongta DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
SOURCE /home/ubuntu/work_01/database_dumps/dongta_1022.sql;
```

## 🔗 더 자세한 내용

[DATABASE_SETUP.md](./DATABASE_SETUP.md)에서 다음을 확인하세요:
- ✅ Local 개발 환경 설정
- ✅ AWS 프로덕션 복원
- ✅ Docker Compose 사용
- ✅ Django ORM 마이그레이션
- ✅ 트러블슈팅

## 📝 파일 동기화

### Local에서 AWS로 업로드
```bash
# 전체 파일 업로드
scp -i /Users/yonghwanahn/Downloads/dongta_ver2.pem \
  -r dongta.mysql/* \
  ubuntu@52.79.148.197:/home/ubuntu/work_01/database_dumps/

# 진행 상황 확인
ssh -i /Users/yonghwanahn/Downloads/dongta_ver2.pem \
  ubuntu@52.79.148.197 "ls -lh /home/ubuntu/work_01/database_dumps/"
```

### AWS에서 Local로 다운로드
```bash
# 전체 파일 다운로드
scp -i /Users/yonghwanahn/Downloads/dongta_ver2.pem \
  -r ubuntu@52.79.148.197:/home/ubuntu/work_01/database_dumps/* \
  dongta.mysql/
```

## ⚠️ 중요 주의사항

1. **Git 제외**: 이 파일들은 `.gitignore`에 의해 자동으로 제외됩니다
2. **대용량**: 파일이 크므로 네트워크 연결이 안정적인 환경에서 작업하세요
3. **백업**: AWS에 업로드하기 전에 항상 로컬 백업 보관
4. **권한**: SSH 키 파일의 권한: `chmod 600 dongta_ver2.pem`

## 🚀 빠른 참조

### Local 개발 시작
```bash
# 1. AWS에서 파일 다운로드
scp -r ubuntu@52.79.148.197:/home/ubuntu/work_01/database_dumps/* dongta.mysql/

# 2. Docker MySQL 시작
docker run -d --name mysql-dongta -p 3306:3306 \
  -e MYSQL_ROOT_PASSWORD=root mysql:8.0

# 3. 데이터 복원
mysql -u root -p < dongta.mysql/dongta_1022.sql

# 4. Django 마이그레이션
cd dongta-django/
python manage.py migrate
```

### AWS 프로덕션 배포
```bash
# 1. AWS 접속
ssh -i dongta_ver2.pem ubuntu@52.79.148.197

# 2. 파일 위치 확인
ls -lh /home/ubuntu/work_01/database_dumps/

# 3. Docker 시작
cd /home/ubuntu/work_01/dongta-django/
docker-compose -f docker-compose.prod.yml up -d

# 4. 마이그레이션 실행
docker-compose -f docker-compose.prod.yml exec web python manage.py migrate
```

## 📊 대역폭 예상

| 파일 | 크기 | 10Mbps | 100Mbps | 1Gbps |
|------|------|--------|---------|-------|
| dongta_1022.sql | 1.1GB | 14.5분 | 1.5분 | 9초 |
| mysql_data.tar.gz | 428MB | 5.7분 | 34초 | 3초 |
| mysql_dongta_dump.sql | 1.1GB | 14.5분 | 1.5분 | 9초 |
| **Total** | **2.6GB** | **34분** | **3.5분** | **21초** |

---

**Last Updated**: 2026-03-09
**Status**: ✅ All files uploaded to AWS
**Next**: [DATABASE_SETUP.md](./DATABASE_SETUP.md) 참고
