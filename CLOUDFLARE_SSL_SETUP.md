# 🔐 Cloudflare SSL 설정 및 무한 리다이렉션 해결

**테스트 도메인**: `dongta.theuit.info`

---

## 🚨 무한 리다이렉션 문제 원인

```
Cloudflare Flexible SSL 사용 시:
┌─────────────────┐
│    브라우저     │
│  (HTTPS)        │
└────────┬────────┘
         │ HTTPS
    ┌────▼────────────────┐
    │  Cloudflare CDN     │
    │ (SSL 종료점)        │
    └────┬────────────────┘
         │ HTTP (암호화 안됨!)
    ┌────▼──────────────────────┐
    │  Origin Server (Django)   │
    │  SECURE_SSL_REDIRECT=True │◄─── HTTPS로 리다이렉트
    └─────────────────────────────┘
         │ HTTPS로 리다이렉트 요청
         │
    └────► Cloudflare로 돌아옴
             (HTTP에서 HTTPS로 → 무한 루프!)
```

---

## ✅ 해결 방법

### 방법 1: Cloudflare Full SSL/Full Strict 사용 (권장)

#### Step 1: Cloudflare 대시보드에서 SSL 설정

1. **Cloudflare 로그인**
   - https://dash.cloudflare.com
   - 도메인 선택: `dongta.theuit.info`

2. **SSL/TLS 설정**
   ```
   SSL/TLS > Overview > Encryption level

   권장 순서:
   1️⃣ Full Strict (권장)
      ├─ Cloudflare ←HTTPS→ Origin (검증된 인증서 필수)
      └─ 가장 안전

   2️⃣ Full (차선책)
      ├─ Cloudflare ←HTTPS→ Origin (자체 서명 인증서 가능)
      └─ 괜찮음

   3️⃣ Flexible (피할 것!)
      ├─ Cloudflare ←HTTP→ Origin
      └─ 무한 리다이렉션 위험!
   ```

3. **SSL/TLS 암호화 모드 선택**
   ```
   SSL/TLS > Overview > Encryption level

   선택: "Full (strict)"

   ✅ 이렇게 하면 Cloudflare가 HTTPS만 Origin으로 보냄
   ```

4. **TLS 최소 버전 설정**
   ```
   SSL/TLS > Edge Certificates > Minimum TLS Version

   선택: TLS 1.2
   ```

#### Step 2: Origin Server 인증서 설정

**자체 서명 인증서** (테스트 환경)
```bash
# 자체 서명 인증서 생성 (유효기간 365일)
openssl req -x509 -newkey rsa:2048 \
  -keyout /etc/nginx/ssl/dongta.key \
  -out /etc/nginx/ssl/dongta.crt \
  -days 365 -nodes \
  -subj "/CN=dongta.theuit.info"

# 권한 설정
sudo chmod 600 /etc/nginx/ssl/dongta.key
sudo chmod 644 /etc/nginx/ssl/dongta.crt
```

**또는 Let's Encrypt 인증서** (권장)
```bash
sudo certbot certonly --nginx \
  -d dongta.theuit.info \
  -d www.dongta.theuit.info
```

#### Step 3: Nginx 설정 수정

```nginx
# /etc/nginx/conf.d/dongta.conf

upstream dongta_app {
    server localhost:8000;
}

# HTTP → HTTPS 리다이렉트 (Cloudflare에 의해 처리되므로 제거 또는 조건부)
server {
    listen 80;
    server_name dongta.theuit.info www.dongta.theuit.info;

    # Cloudflare의 HTTPS 요청은 여기 오지 않음
    # 직접 HTTP 접근을 HTTPS로 리다이렉트
    return 301 https://$server_name$request_uri;
}

# HTTPS 처리
server {
    listen 443 ssl http2;
    server_name dongta.theuit.info www.dongta.theuit.info;

    # SSL 인증서
    ssl_certificate /etc/letsencrypt/live/dongta.theuit.info/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/dongta.theuit.info/privkey.pem;

    # SSL 설정
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Cloudflare의 X-Forwarded-Proto 헤더 신뢰
    # (이미 HTTPS이므로 추가 리다이렉트 불필요)

    # 정적 파일
    location /static/ {
        alias /app/dongta-django/staticfiles/;
        expires 30d;
    }

    location /media/ {
        alias /app/dongta-django/media/;
        expires 7d;
    }

    # API 프록시
    location / {
        proxy_pass http://dongta_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # Cloudflare로부터 이미 HTTPS이므로
        proxy_set_header X-Forwarded-Proto https;

        proxy_read_timeout 30s;
    }
}
```

#### Step 4: Django 설정 수정

**config/settings/production.py**

```python
# SSL/TLS 설정
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Cloudflare IP 범위 신뢰
CSRF_TRUSTED_ORIGINS = [
    'https://dongta.theuit.info',
    'https://www.dongta.theuit.info',
    'https://*.dongta.theuit.info',
]

# Cloudflare에서 제공하는 X-Forwarded-* 헤더 신뢰
SECURE_TRUSTED_HOSTS = [
    'dongta.theuit.info',
    'www.dongta.theuit.info',
    # Cloudflare IP 범위 (선택사항)
    # '173.245.48.0/20',
    # '103.21.244.0/22',
    # ... (모든 Cloudflare IP 범위)
]
```

또는 더 간단하게:

```python
# Cloudflare를 신뢰하는 설정
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_CF_VISITOR', 'https')
```

---

### 방법 2: Cloudflare Worker 스크립트 (고급)

Cloudflare 무한 리다이렉션을 방지하는 Worker:

```javascript
// Cloudflare Worker Script
addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  // 이미 HTTPS인 경우 Origin으로 바로 전달
  if (request.url.startsWith('https://')) {
    return fetch(request)
  }

  // HTTP 요청만 HTTPS로 리다이렉트
  const url = new URL(request.url)
  url.protocol = 'https:'
  return Response.redirect(url.toString(), 301)
}
```

---

### 방법 3: DNS Level SSL 오류 수정

#### Cloudflare DNS 설정 확인

```
DNS > Records 에서 다음 확인:

1. A 레코드: dongta.theuit.info → 서버 IP
2. Proxy status: "Proxied" (주황 구름)로 설정
3. SSL/TLS Status: "Active Certificate"
```

#### CNAME 설정 (subdomain의 경우)

```
www  CNAME  dongta.theuit.info (Proxied)
api  CNAME  dongta.theuit.info (Proxied)
```

---

## 🧪 테스트 및 검증

### 1단계: SSL 설정 확인

```bash
# Cloudflare SSL 상태 확인
curl -I https://dongta.theutil.info/

# 헤더 확인
curl -v https://dongta.theutil.info/ 2>&1 | grep -E "SSL|Cloudflare"

# 예상 응답:
# X-Cloudflare-Ray: <ID>
# CF-Cache-Status: HIT/MISS
```

### 2단계: 리다이렉트 확인

```bash
# 무한 리다이렉트 테스트 (최대 5개 리다이렉트)
curl -L -v https://dongta.theutil.info/ 2>&1 | grep -E "HTTP/|Location"

# 예상:
# < HTTP/2 200
# (리다이렉트 없음)
```

### 3단계: Origin Server 확인

```bash
# Origin 직접 접근 (테스트용)
curl -k -I https://server-ip:443/
# -k: 자체 서명 인증서 무시

# 또는
curl -I --resolve dongta.theutil.info:443:server-ip \
  https://dongta.theutil.info/
```

### 4단계: 최종 API 테스트

```bash
# Health check
curl https://dongta.theutil.info/health/

# 로그인 테스트
curl -X POST https://dongta.theutil.info/api/v1/accounts/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password123"
  }'
```

---

## 🚨 문제 해결

### 여전히 무한 리다이렉트가 발생하는 경우

```bash
# 1. Cloudflare 캐시 초기화
curl -X POST https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/purge_cache \
  -H "Authorization: Bearer {API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"purge_everything":true}'

# 2. 브라우저 캐시 초기화
# Ctrl+Shift+Delete (Windows/Linux)
# Cmd+Shift+Delete (Mac)

# 3. Django 캐시 초기화
docker-compose exec web python manage.py shell
>>> from django.core.cache import cache
>>> cache.clear()
```

### SSL 인증서 오류 (NET::ERR_CERT_AUTHORITY_INVALID)

```bash
# Cloudflare Origin CA 인증서 사용 (권장)
# 1. Cloudflare 대시보드 > SSL/TLS > Origin Server
# 2. "Create Certificate" 클릭
# 3. 다운로드한 인증서를 Nginx에 설정

# 또는 Let's Encrypt (더 안전)
sudo certbot certonly --standalone \
  -d dongta.theutil.info
```

### X-Forwarded-Proto 헤더 누락

```python
# settings/production.py에 추가
HTTP_X_FORWARDED_PROTO = 'https'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# 또는 Cloudflare CF-Visitor 헤더 사용
SECURE_PROXY_SSL_HEADER = ('HTTP_CF_VISITOR', '{"scheme":"https"}')
```

---

## 📊 Cloudflare SSL 설정 체크리스트

| 항목 | 설정 | 확인 |
|------|------|------|
| SSL/TLS Mode | Full (strict) | ✅ |
| Minimum TLS Version | TLS 1.2 | ✅ |
| Always Use HTTPS | On | ✅ |
| HTTP to HTTPS Redirect | Automatic HTTPS Rewrites | ✅ |
| Origin Certificate | Valid & installed | ✅ |
| DNS Proxy Status | Proxied (주황) | ✅ |
| DNSSEC | Enabled | ✅ |
| HTTP/2 to Origin | Enabled | ✅ |
| TLS 1.3 | Enabled | ✅ |

---

## 🔄 완전한 설정 흐름

```
1️⃣ Cloudflare Dashboard
   └─ SSL/TLS 설정 (Full Strict)

2️⃣ DNS 확인
   └─ A 레코드 Proxied 상태

3️⃣ Origin Server
   ├─ Nginx HTTPS 설정
   ├─ Let's Encrypt 인증서
   └─ Django SSL 설정

4️⃣ 테스트
   ├─ Health check
   ├─ API 테스트
   └─ 캐시 초기화

5️⃣ 모니터링
   ├─ Cloudflare 로그
   ├─ Django 로그
   └─ 성능 메트릭
```

---

## 📞 트러블슈팅 플로우차트

```
무한 리다이렉트 발생?
│
├─ [Y] Cloudflare Full Strict 설정?
│  ├─ [N] → Full Strict로 변경
│  └─ [Y] → 다음
│
├─ [Y] Origin HTTPS 설정됨?
│  ├─ [N] → Let's Encrypt 인증서 설정
│  └─ [Y] → 다음
│
├─ [Y] Django SECURE_SSL_REDIRECT = True?
│  └─ [Y] → 다음
│
├─ [Y] 캐시 초기화됨?
│  ├─ [N] → 캐시 초기화
│  └─ [Y] → 다음
│
└─ 모든 확인 완료!
   └─ curl로 최종 테스트
```

---

**Cloudflare Full Strict SSL 설정으로 안전하고 빠른 배포를 완성하세요!** 🚀
