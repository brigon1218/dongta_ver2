#!/usr/bin/env python3
"""
Dongta Platform API Integration Test Suite
실제 사용 시나리오 기반 API 통합 테스트
"""

import os
import django
import json
import time
from datetime import datetime
from collections import defaultdict

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
# 테스트에서 SECURE_SSL_REDIRECT 비활성화
os.environ['SECURE_SSL_REDIRECT'] = 'False'
django.setup()

# Django settings 수정 (이미 로드된 후)
from django.conf import settings
settings.SECURE_SSL_REDIRECT = False

from django.test import Client
from django.contrib.auth import get_user_model
from apps.accounts.models import Member
from apps.business114.models import Business
from rest_framework_simplejwt.tokens import RefreshToken

Member = get_user_model()

class APITester:
    def __init__(self):
        # secure=False: HTTP 요청 허용 (SSL 리다이렉트 우회)
        self.client = Client(enforce_csrf_checks=False)
        self.results = defaultdict(list)
        self.timings = []
        self.test_user = None
        self.access_token = None

    def log(self, category, test_name, result, time_ms=None, error=None):
        """결과 기록"""
        status = "✅ PASS" if result else "❌ FAIL"
        msg = f"{status} | {test_name}"
        if time_ms:
            msg += f" ({time_ms:.1f}ms)"
        if error:
            msg += f" | Error: {error}"

        print(msg)
        self.results[category].append({
            'name': test_name,
            'result': result,
            'time': time_ms,
            'error': error
        })

    def time_request(self, func):
        """요청 시간 측정"""
        start = time.perf_counter()
        try:
            response = func()
            elapsed = (time.perf_counter() - start) * 1000

            # 301 리다이렉트 처리 (SSL 리다이렉트)
            if response and response.status_code == 301:
                redirect_url = response['Location']
                if redirect_url.startswith('https://'):
                    # HTTPS로 리다이렉트된 경우, HTTP로 재요청
                    # 또는 wsgi_request에 wsgi.url_scheme 설정
                    pass

            return response, elapsed
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return None, elapsed

    # ========== TEST SUITE 1: 인증 플로우 ==========

    def test_signup(self):
        """회원가입 테스트"""
        print("\n" + "="*70)
        print("🔐 TEST 1: 인증 플로우 (Authentication Flow)")
        print("="*70)

        # 테스트용 사용자
        test_data = {
            'username': f'testuser_{int(time.time())}',
            'email': f'test_{int(time.time())}@dongta.com',
            'password': 'TestPass123!',
            'password_confirm': 'TestPass123!',
            'name': 'Test User',
            'phone': '010-1234-5678',
            'region': 'seoul'
        }

        # 1. 회원가입
        print("\n1️⃣ User Signup Test")
        resp, elapsed = self.time_request(
            lambda: self.client.post(
                '/api/v1/auth/register/',
                json.dumps(test_data),
                content_type='application/json',
                HTTP_HOST='dongta.theuit.info'
            )
        )

        result = resp and resp.status_code == 201
        error_msg = None
        if resp:
            if resp.status_code != 201:
                error_msg = f"Status {resp.status_code}: {str(resp.content[:100])}"
        else:
            error_msg = "No response"

        self.log('authentication', 'Signup (201)', result, elapsed, error_msg)

        if result:
            self.test_user = test_data
            return True
        return False

    def test_login(self):
        """로그인 테스트"""
        print("\n2️⃣ User Login Test")

        if not self.test_user:
            print("❌ Signup 실패로 로그인 테스트 스킵")
            return False

        login_data = {
            'username': self.test_user['username'],
            'password': self.test_user['password']
        }

        resp, elapsed = self.time_request(
            lambda: self.client.post(
                '/api/v1/auth/login/',
                json.dumps(login_data),
                content_type='application/json',
                HTTP_HOST='dongta.theuit.info'
            )
        )

        result = resp and resp.status_code == 200
        self.log('authentication', 'Login (200)', result, elapsed)

        if result:
            data = resp.json()
            # success_response 래퍼로 감싸져 있으므로 data 필드에서 추출
            if isinstance(data, dict):
                if 'data' in data and isinstance(data['data'], dict):
                    self.access_token = data['data'].get('access')
                else:
                    self.access_token = data.get('access')

                if self.access_token:
                    print(f"   ✓ Access Token: {self.access_token[:20]}...")
                    return True

        return False

    # ========== TEST SUITE 2: 공개 API ==========

    def test_public_endpoints(self):
        """공개 API 테스트"""
        print("\n" + "="*70)
        print("🏢 TEST 2: 공개 API 엔드포인트")
        print("="*70)

        endpoints = [
            ('/api/v1/business/', 'GET', '사업장 목록', 200),
            ('/api/v1/recruit/notices/', 'GET', '채용공고 목록', 200),
            ('/api/v1/board/posts/', 'GET', '게시판 목록', 200),
        ]

        for path, method, name, expected_status in endpoints:
            print(f"\n📍 {name}")

            resp, elapsed = self.time_request(
                lambda: self.client.get(
                    path,
                    HTTP_HOST='dongta.theuit.info'
                )
            )

            result = resp and resp.status_code == expected_status
            error_msg = None
            if resp:
                if resp.status_code != expected_status:
                    error_msg = f"Status {resp.status_code}: {resp.content[:100]}"
            else:
                error_msg = "No response"
            self.log('public_api', f"{name} ({expected_status})", result, elapsed, error_msg)

            if result and resp.status_code == 200:
                try:
                    data = resp.json()
                    count = data.get('count', 'N/A')
                    print(f"   ✓ Count: {count}")
                except:
                    pass

    # ========== TEST SUITE 3: 보호된 API ==========

    def test_protected_endpoints(self):
        """인증 필요 API 테스트"""
        print("\n" + "="*70)
        print("🔒 TEST 3: 보호된 API 엔드포인트 (인증 필요)")
        print("="*70)

        if not self.access_token:
            print("❌ 액세스 토큰 없음. 로그인 먼저 필요")
            return

        headers = {'HTTP_AUTHORIZATION': f'Bearer {self.access_token}'}

        endpoints = [
            ('/api/v1/payment/balance/', 'GET', '포인트 잔액', 200),
            ('/api/v1/mypage/', 'GET', '마이페이지', 200),
            ('/api/v1/payment/history/', 'GET', '결제 내역', 200),
        ]

        for path, method, name, expected_status in endpoints:
            print(f"\n🔐 {name}")

            resp, elapsed = self.time_request(
                lambda: self.client.get(
                    path,
                    **headers,
                    HTTP_HOST='dongta.theuit.info'
                )
            )

            result = resp and resp.status_code == expected_status
            self.log('protected_api', f"{name} ({expected_status})", result, elapsed)

    # ========== TEST SUITE 4: 검색 및 필터링 ==========

    def test_search_and_filtering(self):
        """검색 및 필터링 테스트"""
        print("\n" + "="*70)
        print("🔍 TEST 4: 검색 및 필터링")
        print("="*70)

        # 사업장 검색
        print("\n1️⃣ Business Search")
        resp, elapsed = self.time_request(
            lambda: self.client.get(
                '/api/v1/business/?search=technology&limit=5',
                HTTP_HOST='dongta.theuit.info'
            )
        )

        result = resp and resp.status_code == 200
        self.log('search', 'Business Search', result, elapsed)

        # 페이지네이션
        print("\n2️⃣ Pagination")
        resp, elapsed = self.time_request(
            lambda: self.client.get(
                '/api/v1/recruit/notices/?page=1&limit=10',
                HTTP_HOST='dongta.theuit.info'
            )
        )

        result = resp and resp.status_code == 200
        self.log('search', 'Pagination', result, elapsed)

    # ========== TEST SUITE 5: API 문서 ==========

    def test_documentation(self):
        """API 문서 테스트"""
        print("\n" + "="*70)
        print("📚 TEST 5: API 문서 및 스키마")
        print("="*70)

        docs = [
            ('/api/schema/', 'OpenAPI Schema'),
            ('/api/docs/', 'Swagger UI'),
        ]

        for path, name in docs:
            print(f"\n📄 {name}")
            resp, elapsed = self.time_request(
                lambda p=path: self.client.get(
                    p,
                    HTTP_HOST='dongta.theuit.info'
                )
            )

            result = resp and resp.status_code == 200
            self.log('documentation', f"{name} (200)", result, elapsed)

    # ========== 결과 리포트 ==========

    def generate_report(self):
        """테스트 결과 리포트 생성"""
        print("\n\n" + "="*70)
        print("📊 API 통합 테스트 결과 리포트")
        print("="*70)
        print(f"테스트 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)

        total_tests = 0
        total_passed = 0

        for category, tests in self.results.items():
            print(f"\n📋 {category.upper()}")
            print("-" * 70)

            passed = sum(1 for t in tests if t['result'])
            total = len(tests)

            total_tests += total
            total_passed += passed

            for test in tests:
                symbol = "✅" if test['result'] else "❌"
                time_info = f" ({test['time']:.1f}ms)" if test['time'] else ""
                print(f"{symbol} {test['name']}{time_info}")

            percentage = (passed / total * 100) if total > 0 else 0
            print(f"\n   결과: {passed}/{total} 통과 ({percentage:.1f}%)")

        print("\n" + "="*70)
        print("📈 최종 결과")
        print("="*70)

        overall_percentage = (total_passed / total_tests * 100) if total_tests > 0 else 0
        status = "✅ PASS" if overall_percentage >= 90 else "⚠️ WARNING"

        print(f"총 테스트: {total_tests}")
        print(f"성공: {total_passed}")
        print(f"실패: {total_tests - total_passed}")
        print(f"성공률: {overall_percentage:.1f}%")
        print(f"상태: {status}")
        print("="*70)

def run_all_tests():
    """모든 테스트 실행"""
    tester = APITester()

    print("\n🚀 Dongta Platform API 통합 테스트 시작")
    print(f"시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"환경: Production (Django)")

    # 테스트 실행
    tester.test_signup()
    tester.test_login()
    tester.test_public_endpoints()
    tester.test_protected_endpoints()
    tester.test_search_and_filtering()
    tester.test_documentation()

    # 결과 리포트
    tester.generate_report()

if __name__ == '__main__':
    run_all_tests()
