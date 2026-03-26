"""
tests/unit/test_battle_context.py

BattleSituationContext / BattleSituationParser / validate_battle_situation
에 대한 단위 테스트 (12개 케이스)
"""

import json
import pytest

from defense_llm.agent.battle_context import (
    BattleSituationParser,
    BattleSituationContext,
    LocationBlock,
    ThreatBlock,
    FriendlyForcesBlock,
    QueryBlock,
    MetadataBlock,
    ConstraintsBlock,
    TimeConstraintsBlock,
    TerrainBlock,
    IntelligenceBlock,
    validate_battle_situation,
    DEFAULT_CLASSIFICATION,
    DEFAULT_SOURCE,
    DEFAULT_SCHEMA_VERSION,
    VALID_QUERY_INTENTS,
)


# ---------------------------------------------------------------------------
# 픽스처: 최소 필수 dict
# ---------------------------------------------------------------------------

MINIMAL_DICT = {
    "scenario_id": "SCN-MIN-001",
    "timestamp": "2026-03-26T09:00:00Z",
    "threat": {
        "type": "ARMOR",
        "count": 5,
        "location": {"description": "북부 진입로"},
    },
    "friendly_forces": {
        "unit_id": "1BN-A-CO",
        "location": {"description": "방어 진지"},
    },
    "query": {
        "intent": "THREAT_ASSESS",
        "text": "위협을 평가하라.",
    },
}

# 전체 필드 포함 dict
FULL_DICT = {
    "scenario_id": "SCN-HYPO-001",
    "timestamp": "2026-03-26T09:00:00Z",
    "classification": "CONFIDENTIAL",
    "threat": {
        "type": "ARMOR",
        "count": 12,
        "location": {
            "mgrs": "52SCB1234567890",
            "lat": 37.5665,
            "lon": 126.9780,
            "alt_m": 150.0,
            "description": "북부 계곡 진입로",
        },
        "movement": "ADVANCING",
        "speed_kmh": 25.0,
        "identified_systems": ["T-72B3", "BMP-2"],
        "confidence": 0.78,
    },
    "friendly_forces": {
        "unit_id": "3BDE-1BN-B-CO",
        "unit_type": "MECH_INF",
        "strength": {
            "personnel": 140,
            "vehicles": 14,
            "readiness_pct": 85.0,
        },
        "location": {
            "mgrs": "52SCB0000099999",
            "lat": 37.5500,
            "lon": 126.9600,
            "description": "방어 진지, 능선 남쪽",
        },
        "available_fires": ["155mm SPH Battery x2", "AT Missiles"],
        "logistics_status": "ADEQUATE",
    },
    "terrain": {
        "type": "MOUNTAIN",
        "visibility_km": 4.5,
        "weather": "CLOUDY",
        "time_of_day": "DAY",
    },
    "intelligence": {
        "last_update_minutes": 25,
        "source_reliability": "B",
        "info_credibility": "2",
        "known_gaps": ["2제대 규모 미확인", "포병 지원 여부 불명"],
    },
    "constraints": {
        "roe_level": "RETURN_FIRE",
        "no_fire_areas": ["NFZ-VILLAGE-01"],
        "time_constraints": {
            "ttl_minutes": 30,
            "h_hour": "2026-03-26T10:00:00Z",
        },
    },
    "query": {
        "intent": "COMPOSITE",
        "text": "현재 적 기갑 위협을 평가하고, ROE 준수 범위 내에서 최적 방어 방책 2가지를 제시하라.",
        "priority_factors": ["병력 보존", "마을 피해 최소화", "30분 내 결심"],
    },
    "metadata": {
        "schema_version": "1.0.0",
        "source": "HYPOTHETICAL",
        "language": "ko",
    },
}


# ===========================================================================
# T-01: 최소 필수 필드만으로 파싱 성공
# ===========================================================================
def test_minimal_required_fields_parse_success():
    ctx = BattleSituationParser.from_dict(MINIMAL_DICT)
    assert ctx.scenario_id == "SCN-MIN-001"
    assert ctx.threat.type == "ARMOR"
    assert ctx.threat.count == 5
    assert ctx.friendly_forces.unit_id == "1BN-A-CO"
    assert ctx.query.intent == "THREAT_ASSESS"
    # 선택 필드는 None
    assert ctx.terrain is None
    assert ctx.intelligence is None
    assert ctx.constraints is None


# ===========================================================================
# T-02: 전체 필드 파싱 및 데이터클래스 매핑 검증
# ===========================================================================
def test_full_dict_parse_all_fields_mapped():
    ctx = BattleSituationParser.from_dict(FULL_DICT)
    # threat
    assert ctx.threat.movement == "ADVANCING"
    assert ctx.threat.speed_kmh == 25.0
    assert ctx.threat.identified_systems == ["T-72B3", "BMP-2"]
    assert ctx.threat.confidence == pytest.approx(0.78)
    # LLA + MGRS 동시 검증
    assert ctx.threat.location.mgrs == "52SCB1234567890"
    assert ctx.threat.location.lat == pytest.approx(37.5665)
    assert ctx.threat.location.lon == pytest.approx(126.9780)
    assert ctx.threat.location.alt_m == pytest.approx(150.0)
    # friendly forces
    assert ctx.friendly_forces.unit_type == "MECH_INF"
    assert ctx.friendly_forces.strength.personnel == 140
    assert ctx.friendly_forces.strength.readiness_pct == pytest.approx(85.0)
    assert ctx.friendly_forces.location.mgrs == "52SCB0000099999"
    # terrain / intel / constraints
    assert ctx.terrain.type == "MOUNTAIN"
    assert ctx.intelligence.source_reliability == "B"
    assert ctx.constraints.roe_level == "RETURN_FIRE"
    assert ctx.constraints.time_constraints.ttl_minutes == 30
    # query
    assert ctx.query.intent == "COMPOSITE"
    assert len(ctx.query.priority_factors) == 3
    # metadata
    assert ctx.metadata.schema_version == "1.0.0"
    assert ctx.metadata.source == "HYPOTHETICAL"


# ===========================================================================
# T-03: 예시 인스턴스 JSON 문자열 파싱 → from_dict 결과와 동일성 검증
# ===========================================================================
def test_from_json_equals_from_dict():
    json_str = json.dumps(FULL_DICT)
    ctx_json = BattleSituationParser.from_json(json_str)
    ctx_dict = BattleSituationParser.from_dict(FULL_DICT)

    assert ctx_json.scenario_id == ctx_dict.scenario_id
    assert ctx_json.threat.type == ctx_dict.threat.type
    assert ctx_json.threat.count == ctx_dict.threat.count
    assert ctx_json.threat.location.mgrs == ctx_dict.threat.location.mgrs
    assert ctx_json.threat.location.lat == ctx_dict.threat.location.lat
    assert ctx_json.query.intent == ctx_dict.query.intent
    assert ctx_json.metadata.source == ctx_dict.metadata.source


# ===========================================================================
# T-04: scenario_id 누락 시 KeyError 발생
# ===========================================================================
def test_missing_scenario_id_raises_key_error():
    bad = {k: v for k, v in MINIMAL_DICT.items() if k != "scenario_id"}
    with pytest.raises(KeyError):
        BattleSituationParser.from_dict(bad)


# ===========================================================================
# T-05: threat.type ENUM 위반 시 validate_battle_situation 오류 반환
# ===========================================================================
def test_invalid_threat_type_returns_validation_error():
    d = json.loads(json.dumps(MINIMAL_DICT))
    d["threat"]["type"] = "SUBMARINE"   # 미지원 값
    ctx = BattleSituationParser.from_dict(d)
    errors = validate_battle_situation(ctx)
    assert any("threat.type" in e for e in errors), f"Expected threat.type error, got: {errors}"


# ===========================================================================
# T-06: threat.confidence 범위 위반 (> 1.0) → validate 오류
# ===========================================================================
def test_confidence_out_of_range_returns_validation_error():
    d = json.loads(json.dumps(MINIMAL_DICT))
    d["threat"]["confidence"] = 1.5
    ctx = BattleSituationParser.from_dict(d)
    errors = validate_battle_situation(ctx)
    assert any("confidence" in e for e in errors), f"Expected confidence error, got: {errors}"


# ===========================================================================
# T-07: query.intent 미지원 값 → validate 오류
# ===========================================================================
def test_invalid_query_intent_returns_validation_error():
    d = json.loads(json.dumps(MINIMAL_DICT))
    d["query"]["intent"] = "UNKNOWN_INTENT"
    ctx = BattleSituationParser.from_dict(d)
    errors = validate_battle_situation(ctx)
    assert any("query.intent" in e for e in errors), f"Expected intent error, got: {errors}"


# ===========================================================================
# T-08: to_prompt_text() 에 필수 항목이 포함되는지 확인
# ===========================================================================
def test_to_prompt_text_contains_required_sections():
    ctx = BattleSituationParser.from_dict(FULL_DICT)
    text = ctx.to_prompt_text()

    assert "전투 상황 컨텍스트" in text
    assert ctx.scenario_id in text
    assert "위협 상황" in text
    assert "아군 전력" in text
    assert "질의" in text
    assert ctx.query.text in text


# ===========================================================================
# T-09: to_prompt_text() TTL 경고 포함 확인 (constraints.ttl_minutes 존재 시)
# ===========================================================================
def test_to_prompt_text_includes_ttl_warning():
    ctx = BattleSituationParser.from_dict(FULL_DICT)
    text = ctx.to_prompt_text()
    assert "TTL" in text
    assert "30분" in text


# ===========================================================================
# T-10: metadata.source 기본값 HYPOTHETICAL 확인
# ===========================================================================
def test_default_metadata_source_is_hypothetical():
    ctx = BattleSituationParser.from_dict(MINIMAL_DICT)
    assert ctx.metadata.source == DEFAULT_SOURCE
    assert ctx.is_hypothetical() is True


# ===========================================================================
# T-11: classification 기본값 CONFIDENTIAL 확인 (명시 안 했을 때)
# ===========================================================================
def test_default_classification_is_confidential():
    ctx = BattleSituationParser.from_dict(MINIMAL_DICT)
    assert ctx.classification == DEFAULT_CLASSIFICATION
    assert ctx.classification == "CONFIDENTIAL"


# ===========================================================================
# T-12: LocationBlock — MGRS + LLA 동시 저장 및 to_text() 렌더링 확인
# ===========================================================================
def test_location_block_stores_mgrs_and_lla_together():
    loc_dict = {
        "mgrs": "52SCB1234567890",
        "lat": 37.5665,
        "lon": 126.9780,
        "alt_m": 200.0,
        "description": "테스트 위치",
    }
    loc = LocationBlock.from_dict(loc_dict)

    assert loc.mgrs == "52SCB1234567890"
    assert loc.lat == pytest.approx(37.5665)
    assert loc.lon == pytest.approx(126.9780)
    assert loc.alt_m == pytest.approx(200.0)

    text = loc.to_text()
    assert "MGRS" in text
    assert "LLA" in text
    assert "37.5665" in text
    assert "200" in text          # 고도 포함 확인


# ===========================================================================
# 추가 T-13: get_ttl_minutes() — constraints 없을 때 None 반환
# ===========================================================================
def test_get_ttl_minutes_returns_none_when_no_constraints():
    ctx = BattleSituationParser.from_dict(MINIMAL_DICT)
    assert ctx.get_ttl_minutes() is None


# ===========================================================================
# 추가 T-14: VALID_QUERY_INTENTS 집합이 확장 가능 구조임을 확인
# ===========================================================================
def test_valid_query_intents_is_extensible_set():
    """query.intent ENUM은 집합(set)으로 관리되므로 런타임 추가·제거 가능."""
    original_size = len(VALID_QUERY_INTENTS)
    VALID_QUERY_INTENTS.add("CUSTOM_INTENT")
    assert "CUSTOM_INTENT" in VALID_QUERY_INTENTS
    # 정리 (다른 테스트에 영향 없도록)
    VALID_QUERY_INTENTS.discard("CUSTOM_INTENT")
    assert len(VALID_QUERY_INTENTS) == original_size
