# Business114(동타114) 모듈 전환 Planning Document

> **Summary**: PHP 레거시 동타114(사업장 정보) 시스템을 Django REST API로 완전 전환하고, 지역/업종 기반 검색 및 프리미엄 리스팅 기능 강화

> **Project**: dongta.com
> **Phase**: Phase 3 (모듈별 완전 전환)
> **Version**: 1.0.0
> **Author**: Team
> **Date**: 2026-03-09
> **Status**: Planning

---

## 1. Overview

### 1.1 Purpose

현재 PHP 기반으로 운영 중인 `business114/` 모듈(사업장 정보 시스템)을 Django API 기반으로 완전히 전환하여 검색 성능 향상, 필터링 고도화, 포인트 연동을 통한 프리미엄 리스팅을 구현한다.

### 1.2 Background

- **현황**: 사업장 정보는 이미 `sync` 파이프라인을 통해 PostgreSQL로 동기화되고 있음.
- **문제점**: 비즈니스 로직(리스팅 등록, 수정, 검색)이 여전히 PHP 코드에 의존하고 있음.
- **목표**: PHP 코드를 제거하고 모든 사업장 관련 기능을 Django REST API로 통합.

---

## 2. Scope

### 2.1 In Scope

- **사업장 관리**: 회사 정보(Business) CRUD
- **프리미엄 리스팅**: 포인트 차감을 통한 상위 노출 기능
- **검색 및 필터**:
  - 지역별 검색 (시/도, 구/군)
  - 업종별 검색 (분류 코드)
  - 통합 검색 (키워드)
  - 정렬 (프리미엄 우선, 최신순, 인기도 등)
- **권한 관리**: 본인 정보에 대한 수정 권한 검증

### 2.2 Out of Scope

- 실시간 채팅 상담 (추후)
- AI 기반 추천 (추후)
- 사업장 검증 프로세스 (관리자 페이지에서 별도 처리)

---

## 3. Requirements

### 3.1 Functional Requirements

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-01 | 사업장 정보 등록 및 수정 (CRUD) | High | Pending |
| FR-02 | 지역별 검색 필터 | High | Pending |
| FR-03 | 업종별 검색 필터 | High | Pending |
| FR-04 | 통합 키워드 검색 | High | Pending |
| FR-05 | 프리미엠 리스팅 신청 (포인트 연동) | High | Pending |
| FR-06 | 프리미엄 리스팅 기간 관리 | Medium | Pending |
| FR-07 | 조회수 통계 및 인기도 계산 | Medium | Pending |

### 3.2 Non-Functional Requirements

- **성능**: 대량의 사업장 데이터 검색 시 500ms 이내 응답
- **보안**: 타인의 사업장 정보 수정을 방지하는 Object-level Permission
- **정합성**: 프리미엄 신청 시 포인트 차감 및 기간 설정을 원자적으로 처리

---

## 4. Architecture

### 4.1 핵심 컴포넌트

- **Models**: Business (사업장), BusinessCategory (분류), Region (지역)
- **Serializers**: BusinessSerializer, BusinessDetailSerializer
- **Views**: BusinessViewSet (CRUD + 검색 + 프리미엄)
- **Permissions**: IsOwnerOrReadOnly
- **Services**: BusinessService (프리미엄 신청, 통계 계산)

---

## 5. Implementation Roadmap

1. **Step 1**: Models 및 Serializers 구축
2. **Step 2**: ViewSet 기본 CRUD API 구현
3. **Step 3**: 검색 필터링 고도화 (지역, 업종, 키워드)
4. **Step 4**: 프리미엄 신청 로직 및 포인트 연동
5. **Step 5**: 통계 및 인기도 계산

---

## 6. Success Criteria

- 사업장 정보 조회/등록/수정/삭제가 Django API를 통해 정상 작동
- 지역 + 업종 + 키워드 조합 검색이 1초 이내 응답
- 프리미엄 신청 시 포인트가 정상 차감되고 기간이 30일 설정됨
- 일치율(Match Rate) 90% 이상 달성

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-03-09 | 초기 기획안 작성 | Claude Code |
