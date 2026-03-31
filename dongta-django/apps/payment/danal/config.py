from django.conf import settings

# 다날 가맹점 설정 (Danal CPAY)
DANAL_CPID = getattr(settings, 'DANAL_MERCHANT_ID', '')      # 가맹점 ID
DANAL_CPPWD = getattr(settings, 'DANAL_MERCHANT_KEY', '')    # 가맹점 암호화 키 (비밀번호)

# 다날 API 엔드포인트
# 실서버: https://tx-creditcard.danal.co.kr/credit/
# 테스트: https://test-tx-creditcard.danal.co.kr/credit/
DANAL_BASE_URL = "https://tx-creditcard.danal.co.kr/credit"

DANAL_API_URLS = {
    'READY': f"{DANAL_BASE_URL}/ready",
    'APPROVAL': f"{DANAL_BASE_URL}/approval",
    'CANCEL': f"{DANAL_BASE_URL}/cancel",
}

# 다날 콜백 URL (Django API)
DANAL_RETURN_URL = getattr(settings, 'DANAL_RETURN_URL', '')
