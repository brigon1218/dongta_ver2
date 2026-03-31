# 동타닷컴 개발 환경 가이드 (macOS & Windows 11 공통)

이 프로젝트는 집(macOS)과 사무실(Windows 11) 간의 개발 환경 차이를 최소화하기 위해 **Docker**와 **WSL2**를 기반으로 합니다.

## 1. 공통 필수 도구
- **Docker Desktop**: [다운로드](https://www.docker.com/products/docker-desktop/)
- **Git**: [다운로드](https://git-scm.com/downloads)
- **Make**: (macOS는 기본 설치, Windows는 WSL2 내에서 `sudo apt install make`)

## 2. Windows 11 사용자 (WSL2 설정)
윈도우 환경에서는 PowerShell 대신 **WSL2 (Ubuntu)** 환경에서 작업하는 것을 원칙으로 합니다.

1. **WSL2 설치**: PowerShell(관리자 권한)에서 `wsl --install` 실행.
2. **Ubuntu 설정**: 설치 완료 후 Ubuntu 앱을 열어 사용자 계정 생성.
3. **Docker 연동**: Docker Desktop 설정 -> Resources -> WSL Integration에서 'Ubuntu' 활성화.
4. **터미널**: [Windows Terminal](https://apps.microsoft.com/store/detail/windows-terminal/9N0DX20HK701) 설치 후 Ubuntu 탭에서 작업.

## 3. 개발 시작하기
모든 OS에서 동일한 명령어를 사용합니다.

```bash
# 1. 컨테이너 실행
make up

# 2. 데이터베이스 마이그레이션
make migrate

# 3. 개발 서버 접속
# Django: http://localhost:8000
# API 문서: http://localhost:8000/api/schema/swagger-ui/
```

## 4. 시크릿 및 인증서 관리
- 시크릿 키나 SSL 인증서는 절대 경로를 사용하지 마세요.
- `.env` 파일은 항상 프로젝트 루트(`dongta-django/`)에 위치해야 합니다.
- Nginx SSL 인증서는 `config/nginx/ssl/` 디렉토리에 배치하며, Git에는 업로드되지 않습니다.

## 5. 자주 쓰는 명령어 (Makefile)
| 명령어 | 설명 |
|--------|------|
| `make up` | 컨테이너 백그라운드 실행 |
| `make down` | 컨테이너 중지 및 제거 |
| `make logs` | 로그 실시간 확인 |
| `make shell` | Django 쉘 접속 |
| `make test` | 테스트 코드 실행 |
| `make db-shell` | PostgreSQL 접속 |

---

**주의**: Windows 파일 시스템(`C:\Users\...`) 경로를 직접 참조하는 코드는 지양하고, 반드시 `pathlib`을 통한 상대 경로를 사용하십시오.
