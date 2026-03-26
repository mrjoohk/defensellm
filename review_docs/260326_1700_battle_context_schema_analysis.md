# Phase 2 — BattleSituationPrompt JSON 스키마 설계 분석

**작성일**: 2026-03-26
**대상**: `battle_context.py` 구현을 위한 전투 상황 입력 레이어 스키마 설계
**목적**: 실제 전장 시나리오 구조 도입 전 구조 검증용 가상 전투 상황 입력 모델

---

## 1. 설계 목표

| 항목 | 내용 |
|------|------|
| 용도 | 의사결정 지원 응답 생성을 위한 전투 상황 컨텍스트 주입 |
| 교체 전제 | 실제 전장 시나리오 데이터 확보 후 동일 인터페이스로 교체 |
| 지원 입력 방식 | ① 구조화된 JSON 직접 입력 / ② 자연어 텍스트 (파서 변환) |
| 출력 | `BattleSituationContext` 객체 → Executor 프롬프트에 주입 |

---

## 2. 제안 JSON 스키마: `BattleSituationPrompt`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "BattleSituationPrompt",
  "description": "전투 상황 의사결정 지원 요청을 위한 입력 스키마",
  "type": "object",
  "required": ["scenario_id", "timestamp", "threat", "friendly_forces", "query"],
  "properties": {

    "scenario_id": {
      "type": "string",
      "description": "시나리오 식별자 (예: 'SCN-2026-001'). 추적·감사 로그 연계용.",
      "example": "SCN-2026-001"
    },

    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "상황 발생 시각 (ISO 8601). 시간 민감도 계산에 사용.",
      "example": "2026-03-26T14:30:00Z"
    },

    "classification": {
      "type": "string",
      "enum": ["UNCLASSIFIED", "CONFIDENTIAL", "SECRET", "TOP_SECRET"],
      "default": "CONFIDENTIAL",
      "description": "시나리오 보안 등급. RBAC 접근 제어 및 청크 마스킹 수준 결정."
    },

    "threat": {
      "type": "object",
      "description": "위협 정보 블록",
      "required": ["type", "count", "location"],
      "properties": {
        "type": {
          "type": "string",
          "enum": ["ARMOR", "INFANTRY", "AIR", "NAVAL", "MISSILE", "DRONE", "CYBER", "MIXED"],
          "description": "위협 유형"
        },
        "count": {
          "type": "integer",
          "minimum": 1,
          "description": "위협 병력/장비 수량"
        },
        "location": {
          "type": "object",
          "description": "위협 위치 (MGRS 또는 위경도)",
          "properties": {
            "mgrs": {
              "type": "string",
              "description": "Military Grid Reference System 좌표",
              "example": "52SCB1234567890"
            },
            "lat": { "type": "number", "description": "위도 (WGS-84)" },
            "lon": { "type": "number", "description": "경도 (WGS-84)" },
            "description": {
              "type": "string",
              "description": "자연어 위치 설명",
              "example": "동부 능선 북쪽 3km 지점"
            }
          }
        },
        "movement": {
          "type": "string",
          "enum": ["STATIONARY", "ADVANCING", "RETREATING", "FLANKING", "UNKNOWN"],
          "default": "UNKNOWN",
          "description": "위협 이동 상태"
        },
        "speed_kmh": {
          "type": "number",
          "description": "추정 이동 속도 (km/h). 0이면 정지 또는 불명."
        },
        "identified_systems": {
          "type": "array",
          "items": { "type": "string" },
          "description": "식별된 무기체계 목록",
          "example": ["T-80", "BMP-3", "2S19 MSTA"]
        },
        "confidence": {
          "type": "number",
          "minimum": 0.0,
          "maximum": 1.0,
          "description": "위협 정보 신뢰도 (0.0~1.0)"
        }
      }
    },

    "friendly_forces": {
      "type": "object",
      "description": "아군 전력 현황",
      "required": ["unit_id", "location"],
      "properties": {
        "unit_id": {
          "type": "string",
          "description": "아군 부대 식별자",
          "example": "1BDE-3BN-A-CO"
        },
        "unit_type": {
          "type": "string",
          "enum": ["INFANTRY", "ARMOR", "MECH_INF", "ARTILLERY", "AVIATION", "COMBINED"],
          "description": "부대 유형"
        },
        "strength": {
          "type": "object",
          "properties": {
            "personnel": { "type": "integer", "description": "가용 인원 수" },
            "vehicles": { "type": "integer", "description": "가용 차량/장갑차 수" },
            "readiness_pct": {
              "type": "number",
              "minimum": 0, "maximum": 100,
              "description": "전투 준비 완료율 (%)"
            }
          }
        },
        "location": {
          "type": "object",
          "properties": {
            "mgrs": { "type": "string" },
            "description": { "type": "string" }
          }
        },
        "available_fires": {
          "type": "array",
          "items": { "type": "string" },
          "description": "가용 화력 자산 목록",
          "example": ["155mm SPH Battery", "MLRS", "Close Air Support"]
        },
        "logistics_status": {
          "type": "string",
          "enum": ["FULL", "ADEQUATE", "LIMITED", "CRITICAL"],
          "description": "군수 지원 상태"
        }
      }
    },

    "terrain": {
      "type": "object",
      "description": "지형 환경 정보",
      "properties": {
        "type": {
          "type": "string",
          "enum": ["URBAN", "FOREST", "OPEN", "MOUNTAIN", "COASTAL", "DESERT", "MIXED"],
          "description": "지형 유형"
        },
        "visibility_km": {
          "type": "number",
          "description": "현재 관측 가능 거리 (km)"
        },
        "weather": {
          "type": "string",
          "enum": ["CLEAR", "CLOUDY", "RAIN", "FOG", "SNOW", "STORM"],
          "description": "기상 상태"
        },
        "time_of_day": {
          "type": "string",
          "enum": ["DAWN", "DAY", "DUSK", "NIGHT"],
          "description": "주야 구분"
        }
      }
    },

    "intelligence": {
      "type": "object",
      "description": "정보 상황",
      "properties": {
        "last_update_minutes": {
          "type": "integer",
          "description": "마지막 정보 갱신 후 경과 시간 (분)"
        },
        "source_reliability": {
          "type": "string",
          "enum": ["A", "B", "C", "D", "E", "F"],
          "description": "정보 출처 신뢰도 (NATO 2자리 코드 A~F)"
        },
        "info_credibility": {
          "type": "string",
          "enum": ["1", "2", "3", "4", "5", "6"],
          "description": "정보 내용 신빙성 (1~6)"
        },
        "known_gaps": {
          "type": "array",
          "items": { "type": "string" },
          "description": "알려진 정보 공백 항목",
          "example": ["적 2제대 위치 불명", "화력 자산 수량 미확인"]
        }
      }
    },

    "constraints": {
      "type": "object",
      "description": "작전 제한 사항",
      "properties": {
        "roe_level": {
          "type": "string",
          "enum": ["HOLD", "RETURN_FIRE", "FIRE_AT_WILL", "WEAPONS_FREE"],
          "description": "교전규칙 수준"
        },
        "no_fire_areas": {
          "type": "array",
          "items": { "type": "string" },
          "description": "사격 금지 구역 식별자 목록"
        },
        "time_constraints": {
          "type": "object",
          "properties": {
            "ttl_minutes": {
              "type": "integer",
              "description": "결심 소요 시간 제한 (Time-To-Live, 분). 검색 우선순위 가중치에 사용."
            },
            "h_hour": {
              "type": "string",
              "format": "date-time",
              "description": "공격 개시 예정 시각"
            }
          }
        }
      }
    },

    "query": {
      "type": "object",
      "description": "사령관 질의 (의사결정 지원 요청의 핵심)",
      "required": ["intent", "text"],
      "properties": {
        "intent": {
          "type": "string",
          "enum": [
            "THREAT_ASSESS",
            "COA_RECOMMEND",
            "FIRES_RECOMMEND",
            "INTEL_REQUEST",
            "ROE_CHECK",
            "LOGISTICS_CHECK",
            "COMPOSITE"
          ],
          "description": "질의 의도 분류. Planner 라우팅 및 도구 선택에 사용."
        },
        "text": {
          "type": "string",
          "description": "자연어 질의 본문",
          "example": "현 적 위협을 평가하고 대응 방책을 제시하라."
        },
        "priority_factors": {
          "type": "array",
          "items": { "type": "string" },
          "description": "사령관이 강조하는 우선 고려 요소",
          "example": ["병력 보존", "신속 기동", "ROE 준수"]
        }
      }
    },

    "metadata": {
      "type": "object",
      "description": "처리 메타데이터 (시스템 내부 사용)",
      "properties": {
        "schema_version": {
          "type": "string",
          "default": "1.0.0",
          "description": "스키마 버전. 실제 전장 데이터 교체 시 버전 관리."
        },
        "source": {
          "type": "string",
          "enum": ["HYPOTHETICAL", "EXERCISE", "REAL_OPS"],
          "default": "HYPOTHETICAL",
          "description": "데이터 출처 구분. 현재는 HYPOTHETICAL (구조 검증용)."
        },
        "language": {
          "type": "string",
          "default": "ko",
          "description": "질의 언어"
        }
      }
    }

  }
}
```

---

## 3. 설계 결정 사항 및 판단 근거

### 3.1 필수 필드 선정 (required: 5개)
`scenario_id`, `timestamp`, `threat`, `friendly_forces`, `query`

**판단 근거**: 의사결정 지원 최소 필요 정보. 이 5개가 없으면 어떤 판단도 불가능.
나머지 필드(`terrain`, `intelligence`, `constraints`)는 있으면 응답 품질이 높아지지만, 없어도 기본 위협 평가·방책 추천은 가능.

### 3.2 `query.intent` ENUM 설계
| 값 | Planner 라우팅 |
|----|---------------|
| `THREAT_ASSESS` | `threat_assess` 도구 → `search_docs` (위협 유형 문서) |
| `COA_RECOMMEND` | `search_docs` → `generate_answer` (방책 생성) |
| `FIRES_RECOMMEND` | `search_docs` (화력 운용 교범) + `query_structured_db` (자산 DB) |
| `INTEL_REQUEST` | `web_search` (online) 또는 `search_docs` (offline) |
| `ROE_CHECK` | `search_docs` (ROE 규정 문서) → `security_refusal` 가드 |
| `LOGISTICS_CHECK` | `query_structured_db` (물자 DB) |
| `COMPOSITE` | 위 모두 순차/병렬 처리 |

### 3.3 `constraints.time_constraints.ttl_minutes` 필드
**판단 근거**: 전투 상황에서 결심 가능 시간(TTL)이 짧을수록 내부 문서(RAG) 검색 우선도를 높이고, 웹 검색은 TTL이 충분할 때만 허용해야 함. 이 필드를 Executor의 `timeout` 및 검색 전략 결정에 활용할 수 있음.

### 3.4 `intelligence.source_reliability` + `info_credibility` (NATO 2자리 코드)
**판단 근거**: 방산 도메인 표준. 출처 신뢰도(A~F: 완전신뢰~불명)와 내용 신빙성(1~6: 확인됨~불명)의 분리는 청크 신뢰도 가중치 계산에 직접 사용 가능.

### 3.5 `metadata.source` = `"HYPOTHETICAL"` 기본값
**판단 근거**: 실제 전장 데이터 교체 전까지 모든 입력이 가상임을 명시. Executor가 이를 감지해 응답에 "가상 시나리오 기반" 면책 문구 자동 삽입 가능.

---

## 4. 예시 인스턴스 (가상 시나리오)

```json
{
  "scenario_id": "SCN-HYPO-001",
  "timestamp": "2026-03-26T09:00:00Z",
  "classification": "CONFIDENTIAL",
  "threat": {
    "type": "ARMOR",
    "count": 12,
    "location": {
      "description": "북부 계곡 진입로, 아군 전방 8km"
    },
    "movement": "ADVANCING",
    "speed_kmh": 25,
    "identified_systems": ["T-72B3", "BMP-2"],
    "confidence": 0.78
  },
  "friendly_forces": {
    "unit_id": "3BDE-1BN-B-CO",
    "unit_type": "MECH_INF",
    "strength": {
      "personnel": 140,
      "vehicles": 14,
      "readiness_pct": 85
    },
    "location": {
      "description": "방어 진지, 능선 남쪽"
    },
    "available_fires": ["155mm SPH Battery x2", "AT Missiles"],
    "logistics_status": "ADEQUATE"
  },
  "terrain": {
    "type": "MOUNTAIN",
    "visibility_km": 4.5,
    "weather": "CLOUDY",
    "time_of_day": "DAY"
  },
  "intelligence": {
    "last_update_minutes": 25,
    "source_reliability": "B",
    "info_credibility": "2",
    "known_gaps": ["2제대 규모 미확인", "포병 지원 여부 불명"]
  },
  "constraints": {
    "roe_level": "RETURN_FIRE",
    "no_fire_areas": ["NFZ-VILLAGE-01"],
    "time_constraints": {
      "ttl_minutes": 30,
      "h_hour": "2026-03-26T10:00:00Z"
    }
  },
  "query": {
    "intent": "COMPOSITE",
    "text": "현재 적 기갑 위협을 평가하고, ROE 준수 범위 내에서 최적 방어 방책 2가지를 제시하라.",
    "priority_factors": ["병력 보존", "마을 피해 최소화", "30분 내 결심"]
  },
  "metadata": {
    "schema_version": "1.0.0",
    "source": "HYPOTHETICAL",
    "language": "ko"
  }
}
```

---

## 5. 구현 계획

### 5.1 파일 구조
```
src/defense_llm/agent/
├── battle_context.py          ← NEW: BattleSituationPrompt 파서·데이터클래스
├── executor.py                ← 수정: BattleSituationContext 주입 지원
tests/unit/
├── test_battle_context.py     ← NEW: 단위 테스트 12개
```

### 5.2 `battle_context.py` 주요 구성

```
BattleSituationContext (dataclass)
  ├── ThreatBlock
  ├── FriendlyForcesBlock
  ├── TerrainBlock (Optional)
  ├── IntelligenceBlock (Optional)
  ├── ConstraintsBlock (Optional)
  └── QueryBlock

BattleSituationParser
  ├── from_json(json_str) → BattleSituationContext   # 구조화 입력
  ├── from_dict(d)       → BattleSituationContext   # dict 직접 변환
  └── to_prompt_text(ctx) → str                     # Executor 주입용 텍스트 직렬화

validate_battle_situation(ctx) → List[str]          # 검증 오류 목록 반환
```

### 5.3 Executor 연계 포인트
`Executor.execute(query, battle_context=None)` — `battle_context`가 있으면 시스템 프롬프트에 직렬화된 전투 상황 컨텍스트를 주입.

---

## 6. 테스트 계획 (12개 테스트 케이스)

| # | 케이스 | 유형 |
|---|--------|------|
| T-01 | 최소 필수 필드만으로 파싱 성공 | 성공 |
| T-02 | 전체 필드 파싱 및 데이터클래스 매핑 검증 | 성공 |
| T-03 | 예시 인스턴스 JSON 파싱 → 결과 검증 | 성공 |
| T-04 | `scenario_id` 누락 시 ValidationError | 실패 |
| T-05 | `threat.type` ENUM 위반 시 ValidationError | 실패 |
| T-06 | `threat.confidence` 범위 위반 (>1.0) | 실패 |
| T-07 | `query.intent` 미지원 값 → 실패 | 실패 |
| T-08 | `to_prompt_text()` 출력에 필수 항목 포함 확인 | 성공 |
| T-09 | `to_prompt_text()` TTL 정보 포함 확인 | 성공 |
| T-10 | `from_dict()` 와 `from_json()` 결과 동일성 검증 | 성공 |
| T-11 | `metadata.source = HYPOTHETICAL` 기본값 확인 | 성공 |
| T-12 | Executor 프롬프트 주입 후 `_run_agent_loop` 호출 확인 (mock) | 통합 |

---

## 7. 판단 근거 (종합)

> Phase 2의 핵심은 "실제 전장 데이터 구조를 모르는 상태에서도 교체 가능한 인터페이스를 만드는 것"이다.
> 따라서 스키마는 실제 전장에서 공통으로 요구되는 최소 정보(위협, 아군, 질의)를 필수로 하고,
> 나머지는 선택으로 처리하여 미래 교체 시 충격을 최소화한다.
> `metadata.source`와 `schema_version` 필드는 향후 `HYPOTHETICAL → REAL_OPS` 전환을 추적하기 위한 장치다.
