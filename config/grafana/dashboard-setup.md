# Grafana Dashboard 설정 가이드

## 1. Grafana 접속

```
URL: http://localhost:3000
Default Credentials:
- Username: admin
- Password: admin (docker-compose에서 설정)
```

## 2. Prometheus Data Source 추가

### UI를 통한 설정:
1. Grafana 로그인
2. Configuration → Data Sources → Add data source
3. **Name**: Prometheus
4. **URL**: http://prometheus:9090
5. **HTTP Method**: GET
6. Save & Test

### API를 통한 자동 설정:
```bash
curl -X POST http://localhost:3000/api/datasources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Prometheus",
    "type": "prometheus",
    "url": "http://prometheus:9090",
    "access": "proxy",
    "isDefault": true
  }'
```

## 3. 대시보드 생성 (패널별)

### Panel 1: Request Rate (req/s)
```
Title: Request Rate
Type: Graph
Query: rate(django_http_requests_total[5m])
Legend: {{method}} {{view_name}}
Y-axis: Requests/sec
```

### Panel 2: Response Time (P95)
```
Title: Response Time (P95)
Type: Gauge
Query: histogram_quantile(0.95, rate(django_http_request_duration_seconds_bucket[5m]))
Unit: seconds
Thresholds: 0.3 (green), 0.5 (yellow), 1.0 (red)
Gauge Max: 2.0
```

### Panel 3: Error Rate
```
Title: Error Rate (5xx)
Type: Graph
Query: rate(django_http_requests_total{status=~"5.."}[5m]) / rate(django_http_requests_total[5m]) * 100
Format: Percent
Y-axis: Error Rate (%)
Alert Threshold: 1%
```

### Panel 4: DB Active Connections
```
Title: Active DB Connections
Type: Gauge
Query: pg_stat_activity_count
Unit: short
Thresholds: 10 (green), 15 (yellow), 20 (red)
Gauge Max: 25
```

### Panel 5: Top 10 Slow Queries
```
Title: Top 10 Slow Queries
Type: Table
Query: topk(10, pg_stat_statements_mean_time)
Columns: query, calls, mean_time
Sort By: mean_time (DESC)
```

### Panel 6: Cache Hit Rate
```
Title: Redis Cache Hit Rate
Type: Gauge
Query: rate(redis_keyspace_hits_total[5m]) / (rate(redis_keyspace_hits_total[5m]) + rate(redis_keyspace_misses_total[5m])) * 100
Unit: Percent
Thresholds: 50% (red), 70% (yellow), 85% (green)
```

### Panel 7: CPU Usage
```
Title: CPU Usage
Type: Graph
Query: (1 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m]))) * 100
Unit: Percent
Y-axis: CPU Usage (%)
Alert Threshold: 70%
```

### Panel 8: Memory Usage
```
Title: Memory Usage
Type: Graph
Query: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100
Unit: Percent
Y-axis: Memory Usage (%)
Alert Threshold: 80%
```

## 4. Alert 설정

### Alert Notification Channel
1. Alerting → Notification channels → New channel
2. **Name**: Slack (또는 이메일)
3. **Type**: Slack
4. **Webhook URL**: [Slack webhook URL]
5. **Save**

### Alert Rule (Panel에서)
1. Panel 편집 → Alert
2. **Evaluate every**: 1m
3. **For**: 5m
4. **When**: avg() of query is above 500ms
5. **Send to**: Slack channel
6. **Save**

## 5. Dashboard JSON Import

### 전체 Dashboard를 JSON으로 저장/불러오기:
```bash
# Dashboard 내보내기
curl -X GET http://localhost:3000/api/dashboards/db/{dashboard-slug} \
  -H "Authorization: Bearer $API_TOKEN" \
  > dashboard.json

# Dashboard 가져오기
curl -X POST http://localhost:3000/api/dashboards/db \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d @dashboard.json
```

## 6. 자동 프로비저닝 (선택)

### docker-compose에 자동 대시보드 로드:
```yaml
grafana:
  image: grafana/grafana:latest
  volumes:
    - ./config/grafana/provisioning:/etc/grafana/provisioning:ro
  environment:
    - GF_PATHS_PROVISIONING=/etc/grafana/provisioning
```

## 7. Backup & Restore

### Dashboard 목록 내보내기:
```bash
# 모든 dashboard 다운로드
for slug in $(curl -s http://localhost:3000/api/search -H "Authorization: Bearer $TOKEN" | jq -r '.[].slug'); do
  curl -s http://localhost:3000/api/dashboards/db/$slug -H "Authorization: Bearer $TOKEN" > $slug.json
done
```

---

## 모니터링 메트릭 요약

| 메트릭 | 정상 범위 | 주의 | 경고 |
|--------|----------|------|------|
| Response Time (P95) | < 300ms | 300-500ms | > 500ms |
| Error Rate | 0% | 0.1-1% | > 1% |
| Cache Hit Rate | > 80% | 60-80% | < 60% |
| DB Connections | < 10 | 10-15 | > 15 |
| CPU Usage | < 50% | 50-70% | > 70% |
| Memory Usage | < 60% | 60-80% | > 80% |
| Disk Free | > 20% | 10-20% | < 10% |

---

## 다음 단계

- Week 3: Canary 배포 구현 (10% → 100% 트래픽 전환)
- Week 4: Slow query 최적화 및 최종 부하테스트
