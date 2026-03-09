# Business114(동타114) 전환 Design Document

> **Summary**: Business114 시스템의 Django API 기반 설계로, 사업장 검색, 필터링, 프리미엄 리스팅 기능을 포함

> **Project**: dongta.com
> **Version**: 1.0.0
> **Author**: Team
> **Date**: 2026-03-09
> **Status**: Draft
> **Planning Doc**: [business114_전환.plan.md](../01-plan/features/business114_전환.plan.md)

---

## 1. Design Goals

1. **검색 성능**: 대량의 사업장 데이터를 지역/업종/키워드 조합으로 500ms 이내에 조회
2. **확장성**: 향후 추천 엔진, 실시간 알림 등 확장 가능한 아키텍처
3. **포인트 연동**: 프리미엄 리스팅 신청 시 포인트 차감 및 기간 관리를 원자적으로 처리
4. **사용자 경험**: 상위 노출, 최신순, 인기도 등 다양한 정렬 옵션 제공

---

## 2. API Specification

### 2.1 사업장 관리 API

| Method | Path | Description | Permission |
|--------|------|-------------|------------|
| GET | `/api/v1/business114/` | 사업장 목록 (필터/검색) | AllowAny |
| POST | `/api/v1/business114/` | 사업장 등록 | IsAuthenticated |
| GET | `/api/v1/business114/:id/` | 사업장 상세 조회 | AllowAny |
| PATCH | `/api/v1/business114/:id/` | 사업장 정보 수정 | IsOwner |
| DELETE | `/api/v1/business114/:id/` | 사업장 삭제 | IsOwner |
| POST | `/api/v1/business114/:id/premium/` | 프리미엄 신청 | IsOwner |

### 2.2 검색 필터

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `region` | string | 지역 검색 (시/도, 구/군) | region=서울 |
| `category` | string | 업종 검색 (분류 코드) | category=음식점 |
| `keyword` | string | 키워드 검색 (이름, 설명) | keyword=카페 |
| `is_premium` | boolean | 프리미엄만 조회 | is_premium=true |
| `ordering` | string | 정렬 순서 | ordering=-is_premium,-created_at |

---

## 3. Core Logic Design

### 3.1 Models

```
Business
├── id: BigAutoField
├── member: ForeignKey(Member)
├── name: CharField(200)
├── category: CharField(50) [음식점, 카페, 병원, ...]
├── description: TextField
├── address: CharField(200)
├── region: CharField(50) [지역명]
├── phone: CharField(20)
├── is_premium: BooleanField
├── premium_start_date: DateField
├── premium_end_date: DateField
├── view_count: IntegerField
├── created_at: DateTimeField
├── updated_at: DateTimeField
└── is_deleted: BooleanField
```

### 3.2 프리미엄 신청 로직

1. **포인트 확인**: 사용자의 PointAccount 잔액 확인
2. **포인트 차감**: total_used 업데이트
3. **기간 설정**: premium_start_date = Today, premium_end_date = Today + 30days
4. **트랜잭션**: 모든 과정을 atomic하게 처리

### 3.3 검색 최적화

- **지역 인덱스**: `region` 필드 인덱싱
- **카테고리 인덱스**: `category` 필드 인덱싱
- **프리미엄 정렬**: `-is_premium` 우선 정렬 후 최신순
- **키워드 검색**: `name__icontains`, `description__icontains` 사용

---

## 4. Component Structure

### 4.1 Serializers

- `BusinessSerializer`: 기본 목록/상세 조회용
- `BusinessCreateUpdateSerializer`: 등록/수정용
- `BusinessDetailSerializer`: 프리미엄 상태 포함 상세 조회

### 4.2 ViewSet

- `BusinessViewSet`: ModelViewSet 기반 CRUD + premium action

### 4.3 Services

- `BusinessService`: 프리미엄 신청 로직, 통계 계산

---

## 5. Implementation Order

1. **Step 1**: Business 모델 및 Serializers 작성
2. **Step 2**: ViewSet 기본 CRUD API 구현
3. **Step 3**: 검색 필터링 및 정렬 고도화
4. **Step 4**: 프리미엄 신청 API 및 포인트 연동
5. **Step 5**: Migration 파일 및 인덱스 설정

---

## 6. Security & Validation

- **권한**: IsOwner 권한으로 본인 정보만 수정 가능
- **필수 항목**: 이름, 주소, 지역, 카테고리는 필수 입력
- **XSS 방어**: Django 기본 이스케이프 활용
- **SQL Injection**: ORM 사용으로 자동 방어

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-03-09 | 초기 설계 작성 | Claude Code |
