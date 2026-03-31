import logging
import requests
from typing import Any, Dict
from .config import DANAL_CPID, DANAL_CPPWD, DANAL_API_URLS

logger = logging.getLogger(__name__)


class DanalResponse:
    """다날 API 응답 객체 래퍼"""
    def __init__(self, raw_data: Dict[str, str]):
        self.raw = raw_data
        self.return_code = raw_data.get('RETURNCODE', '9999')
        self.return_msg = raw_data.get('RETURNMSG', '알 수 없는 오류')
        self.is_success = self.return_code == '0000'

    def __getitem__(self, key):
        return self.raw.get(key)

    def get(self, key, default=None):
        return self.raw.get(key, default)


class DanalClient:
    """
    다날 CPAY SDK Python 래퍼
    """
    def __init__(self, is_test: bool = True):
        self.cpid = DANAL_CPID
        self.cppwd = DANAL_CPPWD
        # 실서버와 테스트서버 URL 전환 로직 (필요 시 config에서 처리)
        self.urls = DANAL_API_URLS

    def _post(self, url: str, params: Dict[str, Any]) -> DanalResponse:
        """
        다날 서버에 POST 요청을 보낸다 (EUC-KR 인코딩 필수)
        """
        # 필수 공통 파라미터
        params.update({
            'CPID': self.cpid,
            'CPPWD': self.cppwd,
        })
        
        try:
            # 다날은 EUC-KR로 파라미터를 인코딩하여 전송해야 함
            response = requests.post(
                url, 
                data=params, 
                timeout=10,
                headers={'Content-Type': 'application/x-www-form-urlencoded; charset=euc-kr'}
            )
            response.raise_for_status()
            
            # 응답 데이터 파싱 (key=value&key2=value2 형태)
            # requests의 response.text는 인코딩 추정 과정에서 깨질 수 있으므로 수동 디코딩 권장
            raw_text = response.content.decode('euc-kr', errors='replace')
            parsed_data = {}
            for item in raw_text.split('&'):
                if '=' in item:
                    k, v = item.split('=', 1)
                    parsed_data[k] = v
            
            return DanalResponse(parsed_data)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"다날 API 통신 오류: {e}")
            return DanalResponse({
                'RETURNCODE': 'PAY_002', 
                'RETURNMSG': f"결제 서버 통신 실패: {str(e)}"
            })

    def ready(self, order_id: str, amount: int, item_name: str, 
              user_id: str, return_url: str, cancel_url: str) -> DanalResponse:
        """
        결제 준비 (CallCredit READY)
        """
        params = {
            'TXTYPE': 'AUTH',
            'SERVICETYPE': 'DANALCARD',  # 기본 카드결제
            'ORDERID': order_id,
            'AMOUNT': str(amount),
            'CURRENCY': '410',           # KRW
            'ITEMNAME': item_name,
            'USERID': user_id,
            'RETURNURL': return_url,
            'CANCELURL': cancel_url,
            'CHARSET': 'UTF-8',          # 결과 수신 시 UTF-8 사용 요청
        }
        return self._post(self.urls['READY'], params)

    def approve(self, tid: str) -> DanalResponse:
        """
        결제 승인 (CallCredit APPROVE)
        """
        params = {
            'TXTYPE': 'APPROVE',
            'TID': tid,
        }
        return self._post(self.urls['APPROVAL'], params)

    def cancel(self, tid: str, amount: int, reason: str) -> DanalResponse:
        """
        결제 취소 (CallCredit CANCEL)
        """
        params = {
            'TXTYPE': 'CANCEL',
            'TID': tid,
            'AMOUNT': str(amount),
            'CANCELREASON': reason,
        }
        return self._post(self.urls['CANCEL'], params)
