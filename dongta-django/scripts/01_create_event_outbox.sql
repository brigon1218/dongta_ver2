-- =============================================================================
-- scripts/01_create_event_outbox.sql
--
-- MySQL 측 Event Outbox 테이블 및 트리거 생성.
-- 적용 대상: MySQL/MariaDB (레거시 DongtaDB)
--
-- 동기화 흐름:
--   PHP 레거시 → MySQL 변경 → 트리거 → TBL_EVENT_OUTBOX → Celery → PostgreSQL
-- =============================================================================

USE DongtaDB;

-- ---------------------------------------------------------------------------
-- 1. TBL_EVENT_OUTBOX 테이블 생성
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS TBL_EVENT_OUTBOX (
    id            BIGINT       NOT NULL AUTO_INCREMENT  COMMENT 'PK',
    event_type    VARCHAR(50)  NOT NULL                 COMMENT '이벤트 유형 (member.insert, member.update, payment.insert)',
    aggregate_type VARCHAR(50) NOT NULL                 COMMENT '집계 유형 (member, payment)',
    aggregate_id  BIGINT       NOT NULL                 COMMENT '원본 레코드 PK',
    payload       JSON         NOT NULL                 COMMENT 'MySQL 원본 데이터 스냅샷',
    status        ENUM(
        'pending',
        'processing',
        'done',
        'failed',
        'dead_letter'
    )             NOT NULL DEFAULT 'pending'            COMMENT '처리 상태',
    retry_count   TINYINT      NOT NULL DEFAULT 0       COMMENT '재시도 횟수',
    created_at    DATETIME(3)  NOT NULL
                  DEFAULT CURRENT_TIMESTAMP(3)          COMMENT '생성일시',
    processed_at  DATETIME(3)  NULL                     COMMENT '처리완료일시',
    PRIMARY KEY (id),
    INDEX idx_outbox_status_created (status, created_at),
    INDEX idx_outbox_aggregate (aggregate_type, aggregate_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='MySQL→PostgreSQL 동기화 이벤트 아웃박스';


-- ---------------------------------------------------------------------------
-- 2. 회원 INSERT 트리거 (tg_member_insert)
--    TBL_MEMB에 새 회원 삽입 시 member.insert 이벤트 생성
-- ---------------------------------------------------------------------------
DROP TRIGGER IF EXISTS tg_member_insert;

DELIMITER $$
CREATE TRIGGER tg_member_insert
AFTER INSERT ON TBL_MEMB
FOR EACH ROW
BEGIN
    INSERT INTO TBL_EVENT_OUTBOX (
        event_type,
        aggregate_type,
        aggregate_id,
        payload
    ) VALUES (
        'member.insert',
        'member',
        NEW.memb_idx,
        JSON_OBJECT(
            'memb_idx',         NEW.memb_idx,
            'memb_id',          NEW.memb_id,
            'memb_name',        NEW.memb_name,
            'memb_email',       NEW.memb_email,
            'memb_level',       NEW.memb_level,
            'memb_hp1',         IFNULL(NEW.memb_hp1, ''),
            'memb_hp2',         IFNULL(NEW.memb_hp2, ''),
            'memb_hp3',         IFNULL(NEW.memb_hp3, ''),
            'memb_tel1',        IFNULL(NEW.memb_tel1, ''),
            'memb_tel2',        IFNULL(NEW.memb_tel2, ''),
            'memb_tel3',        IFNULL(NEW.memb_tel3, ''),
            'memb_tel4',        IFNULL(NEW.memb_tel4, ''),
            'memb_region',      IFNULL(NEW.memb_region, ''),
            'memb_corp',        IFNULL(NEW.memb_corp, ''),
            'memb_post1',       IFNULL(NEW.memb_post1, ''),
            'memb_post2',       IFNULL(NEW.memb_post2, ''),
            'memb_addr1',       IFNULL(NEW.memb_addr1, ''),
            'memb_addr2',       IFNULL(NEW.memb_addr2, ''),
            'memb_mailflag',    IFNULL(NEW.memb_mailflag, 1),
            'memb_wantquitflag',IFNULL(NEW.memb_wantquitflag, '0'),
            'memb_regdate',     DATE_FORMAT(NOW(), '%Y-%m-%d %H:%i:%s')
        )
    );
END$$
DELIMITER ;


-- ---------------------------------------------------------------------------
-- 3. 회원 UPDATE 트리거 (tg_member_update)
--    TBL_MEMB 핵심 필드 변경 시 member.update 이벤트 생성
--    (이메일, 이름, 지역, 전화번호, 레벨 변경만 감지)
-- ---------------------------------------------------------------------------
DROP TRIGGER IF EXISTS tg_member_update;

DELIMITER $$
CREATE TRIGGER tg_member_update
AFTER UPDATE ON TBL_MEMB
FOR EACH ROW
BEGIN
    -- 관심 필드 변경 여부 확인
    IF (
        OLD.memb_email     <> NEW.memb_email  OR
        OLD.memb_name      <> NEW.memb_name   OR
        OLD.memb_region    <> NEW.memb_region  OR
        OLD.memb_hp1       <> NEW.memb_hp1    OR
        OLD.memb_level     <> NEW.memb_level  OR
        OLD.memb_wantquitflag <> NEW.memb_wantquitflag
    ) THEN
        INSERT INTO TBL_EVENT_OUTBOX (
            event_type,
            aggregate_type,
            aggregate_id,
            payload
        ) VALUES (
            'member.update',
            'member',
            NEW.memb_idx,
            JSON_OBJECT(
                'memb_idx',         NEW.memb_idx,
                'memb_id',          NEW.memb_id,
                'memb_name',        NEW.memb_name,
                'memb_email',       NEW.memb_email,
                'memb_level',       NEW.memb_level,
                'memb_hp1',         IFNULL(NEW.memb_hp1, ''),
                'memb_hp2',         IFNULL(NEW.memb_hp2, ''),
                'memb_hp3',         IFNULL(NEW.memb_hp3, ''),
                'memb_tel1',        IFNULL(NEW.memb_tel1, ''),
                'memb_tel2',        IFNULL(NEW.memb_tel2, ''),
                'memb_tel3',        IFNULL(NEW.memb_tel3, ''),
                'memb_tel4',        IFNULL(NEW.memb_tel4, ''),
                'memb_region',      IFNULL(NEW.memb_region, ''),
                'memb_corp',        IFNULL(NEW.memb_corp, ''),
                'memb_post1',       IFNULL(NEW.memb_post1, ''),
                'memb_post2',       IFNULL(NEW.memb_post2, ''),
                'memb_addr1',       IFNULL(NEW.memb_addr1, ''),
                'memb_addr2',       IFNULL(NEW.memb_addr2, ''),
                'memb_mailflag',    IFNULL(NEW.memb_mailflag, 1),
                'memb_wantquitflag',IFNULL(NEW.memb_wantquitflag, '0'),
                '_updated_at',      DATE_FORMAT(NOW(), '%Y-%m-%d %H:%i:%s')
            )
        );
    END IF;
END$$
DELIMITER ;


-- ---------------------------------------------------------------------------
-- 4. 결제 INSERT 트리거 (tg_payment_insert)
--    DongtaPointCharge 테이블 신규 결제 시 payment.insert 이벤트 생성
-- ---------------------------------------------------------------------------
DROP TRIGGER IF EXISTS tg_payment_insert;

DELIMITER $$
CREATE TRIGGER tg_payment_insert
AFTER INSERT ON DongtaPointCharge
FOR EACH ROW
BEGIN
    INSERT INTO TBL_EVENT_OUTBOX (
        event_type,
        aggregate_type,
        aggregate_id,
        payload
    ) VALUES (
        'payment.insert',
        'payment',
        NEW.nChargeIdx,
        JSON_OBJECT(
            'nChargeIdx',   NEW.nChargeIdx,
            'nMembIdx',     NEW.nMembIdx,
            'nChargePrice', NEW.nChargePrice,
            'nChargeDP',    NEW.nChargeDP,
            'sPayMethod',   IFNULL(NEW.sPayMethod, 'card'),
            'bSuccess',     IFNULL(NEW.bSuccess, 0),
            'sResultCode',  IFNULL(NEW.sResultCode, ''),
            'sResultMsg',   IFNULL(NEW.sResultMsg, ''),
            'sOrderId',     IFNULL(NEW.sOrderId, ''),
            '_created_at',  DATE_FORMAT(NOW(), '%Y-%m-%d %H:%i:%s')
        )
    );
END$$
DELIMITER ;


-- ---------------------------------------------------------------------------
-- 5. 검증 쿼리 (스크립트 적용 후 확인용)
-- ---------------------------------------------------------------------------
SELECT 'TBL_EVENT_OUTBOX 생성 확인' AS check_item;
DESCRIBE TBL_EVENT_OUTBOX;

SELECT 'Trigger 목록 확인' AS check_item;
SHOW TRIGGERS LIKE 'TBL_MEMB';
SHOW TRIGGERS LIKE 'DongtaPointCharge';
