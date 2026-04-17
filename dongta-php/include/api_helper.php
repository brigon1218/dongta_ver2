<?php
/**
 * dongta.com → Django API 연동 헬퍼
 *
 * - 파일 기반 캐시 (기본 5분 TTL)
 * - 캐시 만료 시 stale 데이터 최대 30분까지 폴백
 * - curl 타임아웃 3초 (페이지 응답 속도 보호)
 */

define('DONGTA_API_BASE', 'https://dongta.theuit.info/api/v1');
define('DONGTA_CACHE_DIR', sys_get_temp_dir() . '/dongta_api_cache');
define('DONGTA_CACHE_TTL', 300);         // 5분 (정상 캐시)
define('DONGTA_CACHE_STALE_TTL', 1800);  // 30분 (API 장애 시 stale 폴백)
define('DONGTA_API_TIMEOUT', 3);         // curl 타임아웃(초)

if (!is_dir(DONGTA_CACHE_DIR)) {
    @mkdir(DONGTA_CACHE_DIR, 0755, true);
}

/**
 * API 호출 (캐시 우선, 장애 시 stale 폴백)
 *
 * @param string $path   예) '/recruit/notices/'
 * @param array  $params 쿼리 파라미터
 * @param int    $ttl    캐시 TTL(초), 기본 DONGTA_CACHE_TTL
 * @return array|null    응답 data 배열 또는 null
 */
function dongta_api_get($path, $params = [], $ttl = DONGTA_CACHE_TTL) {
    $url = DONGTA_API_BASE . $path;
    if ($params) {
        $url .= '?' . http_build_query($params);
    }

    $cache_key  = md5($url);
    $cache_file = DONGTA_CACHE_DIR . '/' . $cache_key . '.json';

    // 1) 유효 캐시 히트
    if (file_exists($cache_file)) {
        $age = time() - filemtime($cache_file);
        if ($age < $ttl) {
            $cached = json_decode(file_get_contents($cache_file), true);
            if ($cached !== null) {
                return $cached;
            }
        }
    }

    // 2) API 호출
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => DONGTA_API_TIMEOUT,
        CURLOPT_CONNECTTIMEOUT => 2,
        CURLOPT_HTTPHEADER     => ['Accept: application/json'],
        CURLOPT_SSL_VERIFYPEER => true,
        CURLOPT_FOLLOWLOCATION => false,
    ]);
    $raw  = curl_exec($ch);
    $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $err  = curl_errno($ch);
    curl_close($ch);

    if (!$err && $code === 200 && $raw) {
        $body = json_decode($raw, true);
        if (!empty($body['success'])) {
            $data = $body['data'];
            // 캐시 저장
            @file_put_contents($cache_file, json_encode($data), LOCK_EX);
            return $data;
        }
    }

    // 3) 장애 시 stale 캐시 폴백
    if (file_exists($cache_file)) {
        $age = time() - filemtime($cache_file);
        if ($age < DONGTA_CACHE_STALE_TTL) {
            $cached = json_decode(file_get_contents($cache_file), true);
            if ($cached !== null) {
                return $cached;
            }
        }
    }

    return null; // 완전 실패
}

/**
 * 날짜 문자열을 "N일 전 / 오늘" 형식으로 변환
 */
function dongta_date_label($date_str) {
    if (!$date_str) return '';
    $ts   = strtotime($date_str);
    $diff = (int)((time() - $ts) / 86400);
    if ($diff === 0) return '<span style="color:#e44">오늘</span>';
    if ($diff === 1) return '어제';
    if ($diff < 7)  return $diff . '일전';
    return date('m/d', $ts);
}

/**
 * 문자열을 지정 바이트 길이로 자르기 (EUC-KR 호환)
 */
function dongta_cut_str($str, $max_bytes) {
    if (mb_strlen($str, 'UTF-8') * 2 <= $max_bytes) return $str;
    return mb_strimwidth($str, 0, (int)($max_bytes / 2), '..', 'UTF-8');
}
