# dongta.com 개발용 Makefile (macOS & WSL2 공통)

# 프로젝트 설정
DOCKER_COMPOSE = docker-compose
DJANGO_SERVICE = web
DJANGO_EXEC = $(DOCKER_COMPOSE) exec $(DJANGO_SERVICE)

.PHONY: up down ps logs shell migrate makemigrations test setup

# 기본 실행
up:
	$(DOCKER_COMPOSE) up -d

down:
	$(DOCKER_COMPOSE) down

ps:
	$(DOCKER_COMPOSE) ps

logs:
	$(DOCKER_COMPOSE) logs -f

# Django 명령어
shell:
	$(DJANGO_EXEC) python manage.py shell

migrate:
	$(DJANGO_EXEC) python manage.py migrate

makemigrations:
	$(DJANGO_EXEC) python manage.py makemigrations

collectstatic:
	$(DJANGO_EXEC) python manage.py collectstatic --no-input

# 데이터베이스
db-shell:
	$(DOCKER_COMPOSE) exec db psql -U postgres -d dongta_v2

# 테스트
test:
	$(DJANGO_EXEC) pytest

# 초기 설정
setup: up migrate collectstatic
	@echo "초기 셋업이 완료되었습니다. http://localhost:8000 (개발용) 에 접속 가능합니다."
