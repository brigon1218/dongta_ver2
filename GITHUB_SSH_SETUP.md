# 🔐 GitHub SSH 설정 가이드 (다중 컴퓨터)

> **목적**: 집과 회사 등 여러 컴퓨터에서 GitHub을 안전하게 사용하기
>
> **소요 시간**: 약 15분

---

## 📍 개요

SSH 키는 **각 컴퓨터마다 별도로 생성**해야 합니다.

- 집 컴퓨터: SSH 키 이미 생성 ✅
- 회사 컴퓨터: 내일 새로 생성 필요 ❌

---

## 🔑 회사 컴퓨터에서 GitHub SSH 설정 (Step by Step)

### Step 1️⃣ : SSH 키 생성 (회사 컴퓨터에서)

**Terminal/PowerShell을 열고 다음 명령어 실행:**

```bash
ssh-keygen -t ed25519 -C "your-email@company.com" -f ~/.ssh/id_ed25519_github
```

**명령어 설명:**
- `ssh-keygen`: SSH 키 생성 도구
- `-t ed25519`: 암호화 방식 (최신, RSA 2048보다 안전)
- `-C`: 주석/설명 (구분용, 실제 이메일 아니어도 됨)
- `-f ~/.ssh/id_ed25519_github`: 저장 경로 및 파일명

**실행 후 입력:**

```
Enter passphrase (empty for no passphrase): [엔터 또는 비밀번호 입력]
Enter same passphrase again: [반복 입력]
```

⚠️ **비밀번호 설정 시 참고:**
- 비움 (권장): 매번 자동 연결
- 설정함: 더 안전하지만 push/pull할 때마다 비밀번호 입력

**성공 메시지:**
```
Your identification has been saved in /Users/username/.ssh/id_ed25519_github
Your public key has been saved in /Users/username/.ssh/id_ed25519_github.pub
```

---

### Step 2️⃣ : 공개키 확인 및 복사

**다음 명령어로 공개키 확인:**

```bash
cat ~/.ssh/id_ed25519_github.pub
```

**출력 예시:**
```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILqnp5/L+gjrm4pUldDt0OAaBeH9BbEf/qb7ynNYZ5Hw your-email@company.com
```

**전체 내용 복사:**
- Mac: `cat ~/.ssh/id_ed25519_github.pub | pbcopy` (자동 복사)
- Linux: `cat ~/.ssh/id_ed25519_github.pub | xclip -selection clipboard`
- Windows: 수동으로 선택 후 Ctrl+C

---

### Step 3️⃣ : GitHub에 공개키 등록

1. **GitHub 로그인**
   - https://github.com/settings/keys (또는 Settings > SSH and GPG keys)

2. **"New SSH key" 버튼 클릭**

3. **폼 작성:**
   ```
   Title (제목):        회사 컴퓨터
   Key type (타입):     Authentication Key
   Key (키):            [Step 2에서 복사한 공개키 붙여넣기]
   ```

4. **"Add SSH key" 클릭**

5. **GitHub 비밀번호 입력** (인증)

✅ **등록 완료!** 공개키가 GitHub 계정에 추가됨

---

### Step 4️⃣ : SSH 연결 테스트

**Terminal에서 실행:**

```bash
ssh -T git@github.com
```

**성공 메시지:**
```
Hi brigon1218! You've successfully authenticated, but GitHub does not provide shell access.
```

❌ **오류가 나면 확인사항:**
- SSH 에이전트가 실행 중인지 확인
  ```bash
  eval "$(ssh-agent -s)"
  ssh-add ~/.ssh/id_ed25519_github
  ```
- GitHub 공개키 등록 확인
- 파일명이 정확한지 확인 (id_ed25519_github)

---

### Step 5️⃣ : GitHub 저장소 클론 및 작업

**저장소 클론:**

```bash
git clone git@github.com:brigon1218/dongta_ver2.git
cd dongta_ver2
```

**그 이후는 평소대로 사용:**

```bash
# Pull
git pull origin main

# 작업 후 commit & push
git add .
git commit -m "작업 내용"
git push origin main
```

---

## 🔀 고급: 집과 회사 계정 분리 (선택사항)

집과 회사에서 **다른 GitHub 계정**을 사용하거나, **구분하고 싶은 경우**:

### SSH Config 파일 생성

```bash
cat > ~/.ssh/config << 'EOF'
Host github.com-personal
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519

Host github.com-company
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519_github
EOF
```

### 저장소별 URL 사용

**개인 저장소 (집 컴퓨터):**
```bash
git clone git@github.com-personal:brigon1218/dongta_ver2.git
```

**회사 저장소 (회사 컴퓨터):**
```bash
git clone git@github.com-company:company-org/company-repo.git
```

---

## 📋 간단 정리: 같은 계정 사용하는 경우

집과 회사에서 **같은 GitHub 계정, 같은 저장소**를 사용:

```bash
# 1️⃣ SSH 키 생성
ssh-keygen -t ed25519 -C "your-email@company.com"
# → 파일명 기본값 (~/.ssh/id_ed25519) 사용

# 2️⃣ 공개키 복사
cat ~/.ssh/id_ed25519.pub

# 3️⃣ GitHub Settings > SSH Keys 에 등록

# 4️⃣ 저장소 클론
git clone git@github.com:brigon1218/dongta_ver2.git

# 5️⃣ 테스트
ssh -T git@github.com
```

---

## 🆚 집 vs 회사 SSH 키 비교

| 항목 | 집 컴퓨터 | 회사 컴퓨터 |
|------|----------|-----------|
| **SSH 키 상태** | ✅ 이미 생성됨 | ❌ 새로 생성 필요 |
| **GitHub 등록** | ✅ 공개키 등록됨 | ❌ 새로 등록 필요 |
| **Push/Pull** | ✅ 가능 | ⏳ 키 등록 후 가능 |
| **개인키 저장소** | 집 컴퓨터 `~/.ssh/` | 회사 컴퓨터 `~/.ssh/` |
| **공개키** | GitHub에 등록됨 | GitHub에 등록됨 (별도) |

---

## ⚠️ 보안 주의사항

### ❌ 하지 말아야 할 것

1. **집의 개인키를 회사로 옮기기**
   - 보안 위험 증가
   - 한 곳이 해킹되면 다 영향

2. **개인키를 메일/USB로 공유**
   - 네트워크 전송 시 탈취 가능
   - 물리적 매체 도난 위험

3. **같은 SSH 키를 많은 곳에 사용**
   - 한 컴퓨터 해킹 → 모든 계정 위험

4. **GitHub에 개인키 커밋하기**
   - 저장소에 개인키 절대 금지!
   - `.gitignore`로 `~/.ssh/` 제외

### ✅ 올바른 방법

1. **각 컴퓨터마다 새로운 SSH 키 생성**
   - 집: `id_ed25519`
   - 회사: `id_ed25519_github`

2. **각 공개키를 GitHub에 등록**
   - 제목으로 구분 (예: "집", "회사")

3. **개인키는 각 컴퓨터에만 보관**
   - 절대 외부로 노출 금지

4. **.gitignore 확인**
   ```bash
   # ~/.ssh 디렉토리는 git 추적 대상 아님
   echo "~/.ssh/" >> .gitignore
   ```

5. **정기적으로 SSH 키 권한 확인**
   ```bash
   chmod 600 ~/.ssh/id_ed25519_github
   chmod 644 ~/.ssh/id_ed25519_github.pub
   ```

---

## 🚀 내일 회사에서 바로 실행할 명령어

**아래 명령어들을 순서대로 실행하세요:**

```bash
# 1️⃣ SSH 키 생성 (회사 컴퓨터에서 1회만)
ssh-keygen -t ed25519 -C "work@company.com"

# 2️⃣ 공개키 확인 및 복사
cat ~/.ssh/id_ed25519.pub

# 👉 여기서 GitHub에 공개키 등록하세요!

# 3️⃣ SSH 연결 테스트
ssh -T git@github.com

# 4️⃣ 저장소 클론
git clone git@github.com:brigon1218/dongta_ver2.git

# 5️⃣ 폴더 진입 후 테스트
cd dongta_ver2
git pull origin main
git log --oneline -3

# 6️⃣ 푸시 테스트 (다른 브랜치에서)
git checkout -b test-branch
echo "테스트" > test.txt
git add test.txt
git commit -m "테스트: SSH 연결 확인"
git push origin test-branch
```

---

## ❓ 자주 묻는 질문 (FAQ)

### Q1: 개인키와 공개키의 차이?
- **개인키**: 자신만 알아야 함 (집 컴퓨터에만 보관)
- **공개키**: 공개해도 됨 (GitHub에 등록)
- 공개키로 암호화 → 개인키로만 복호화 (SSH 원리)

### Q2: 비밀번호 없이 SSH 설정해도 안전한가?
- 충분히 안전함 (SSH 키 자체가 강력한 암호화)
- 더 높은 보안이 필요하면 비밀번호 설정 가능
- GitHub.com 접속은 별도의 2FA 설정 권장

### Q3: 여러 GitHub 계정이 있으면?
- SSH Config 파일로 계정별 키 설정
- 예: `git@github.com-personal`, `git@github.com-company`

### Q4: SSH 키를 잃어버렸으면?
```bash
# 새로운 키 생성
ssh-keygen -t ed25519 -C "new-email@company.com"

# 기존 키 GitHub에서 삭제
# → Settings > SSH Keys > Delete

# 새로운 공개키 등록
cat ~/.ssh/id_ed25519.pub
```

### Q5: 개인키가 아닌 공개키를 등록하면?
- 실수로 개인키를 등록했다면:
  1. GitHub에서 해당 키 즉시 삭제
  2. 새로운 SSH 키 쌍 생성
  3. 새 공개키 등록

### Q6: 기존 HTTPS 저장소를 SSH로 변경하려면?
```bash
# 현재 원격 저장소 확인
git remote -v

# HTTPS → SSH로 변경
git remote set-url origin git@github.com:brigon1218/dongta_ver2.git

# 변경 확인
git remote -v
```

---

## 📚 참고 링크

- **GitHub SSH 공식 가이드**: https://docs.github.com/en/authentication/connecting-to-github-with-ssh
- **SSH Key 생성 (공식)**: https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent
- **SSH Config 설정**: https://linux.die.net/man/5/ssh_config

---

## 💾 파일 저장 및 활용

**이 문서를 다음과 같이 활용하세요:**

1. **메모장/노션에 저장** → 내일 회사에서 쉽게 참고
2. **프린트** → 따라 하면서 확인
3. **북마크** → 나중에 필요할 때 다시 보기

---

**작성일**: 2026-03-09
**대상**: dongta_ver2 GitHub 프로젝트
**계정**: brigon1218

💡 **팁**: 처음 한 번 설정하면 그 이후로는 계속 사용할 수 있습니다!
