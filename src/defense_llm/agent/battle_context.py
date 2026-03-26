"""
battle_context.py — Phase 2: Battle Situation Input Layer

BattleSituationPrompt JSON 스키마를 파이썬 데이터클래스로 표현하고,
JSON / dict 입력을 파싱·검증하여 Executor 프롬프트에 주입 가능한
BattleSituationContext 객체를 반환한다.

현재 schema_version: "1.0.0"
현재 source:         "HYPOTHETICAL" (실제 전장 데이터 교체 전 구조 검증용)

교체 시 인터페이스 변경 없이 BattleSituationParser.from_json() /
from_dict() 만 호출하면 동일하게 동작한다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# 상수 / ENUM 집합 (확장 포인트: 값을 추가·제거하면 검증 자동 반영)
# ---------------------------------------------------------------------------

# EXTENSIBLE: 새 위협 유형 추가 시 이 집합에 추가
VALID_THREAT_TYPES = {
    "ARMOR", "INFANTRY", "AIR", "NAVAL",
    "MISSILE", "DRONE", "CYBER", "MIXED",
}

# EXTENSIBLE: 이동 상태 추가 시 이 집합에 추가
VALID_MOVEMENT_STATES = {
    "STATIONARY", "ADVANCING", "RETREATING", "FLANKING", "UNKNOWN",
}

# EXTENSIBLE: 부대 유형 추가 시 이 집합에 추가
VALID_UNIT_TYPES = {
    "INFANTRY", "ARMOR", "MECH_INF", "ARTILLERY", "AVIATION", "COMBINED",
}

# EXTENSIBLE: 군수 상태 추가 시 이 집합에 추가
VALID_LOGISTICS_STATUS = {"FULL", "ADEQUATE", "LIMITED", "CRITICAL"}

VALID_TERRAIN_TYPES = {
    "URBAN", "FOREST", "OPEN", "MOUNTAIN", "COASTAL", "DESERT", "MIXED",
}
VALID_WEATHER = {"CLEAR", "CLOUDY", "RAIN", "FOG", "SNOW", "STORM"}
VALID_TIME_OF_DAY = {"DAWN", "DAY", "DUSK", "NIGHT"}

# NATO 정보 신뢰도 코드
VALID_SOURCE_RELIABILITY = {"A", "B", "C", "D", "E", "F"}
VALID_INFO_CREDIBILITY = {"1", "2", "3", "4", "5", "6"}

VALID_ROE_LEVELS = {
    "HOLD", "RETURN_FIRE", "FIRE_AT_WILL", "WEAPONS_FREE",
}

# EXTENSIBLE: 새 질의 의도 추가 시 이 집합에 추가
VALID_QUERY_INTENTS = {
    "THREAT_ASSESS",
    "COA_RECOMMEND",
    "FIRES_RECOMMEND",
    "INTEL_REQUEST",
    "ROE_CHECK",
    "LOGISTICS_CHECK",
    "COMPOSITE",
}

VALID_CLASSIFICATIONS = {
    "UNCLASSIFIED", "CONFIDENTIAL", "SECRET", "TOP_SECRET",
}

VALID_SOURCES = {"HYPOTHETICAL", "EXERCISE", "REAL_OPS"}

# 테스트 기본 보안 등급
DEFAULT_CLASSIFICATION = "CONFIDENTIAL"
DEFAULT_SCHEMA_VERSION = "1.0.0"
DEFAULT_SOURCE = "HYPOTHETICAL"


# ---------------------------------------------------------------------------
# 위치 블록 (LLA + MGRS 동시 지원)
# ---------------------------------------------------------------------------

@dataclass
class LocationBlock:
    """
    위치 표현 — MGRS, LLA(위·경·고도) 중 하나 이상 또는 자연어 설명 제공.
    실제 전장 데이터에서 MGRS 전용·LLA 전용·복합 모두 수용한다.
    """
    mgrs: Optional[str] = None          # Military Grid Reference System
    lat: Optional[float] = None         # 위도 (WGS-84, degrees)
    lon: Optional[float] = None         # 경도 (WGS-84, degrees)
    alt_m: Optional[float] = None       # 고도 (m, MSL) — LLA 3번째 축
    description: Optional[str] = None  # 자연어 위치 설명

    def is_empty(self) -> bool:
        return all(v is None for v in (
            self.mgrs, self.lat, self.lon, self.alt_m, self.description
        ))

    @classmethod
    def from_dict(cls, d: dict) -> "LocationBlock":
        return cls(
            mgrs=d.get("mgrs"),
            lat=d.get("lat"),
            lon=d.get("lon"),
            alt_m=d.get("alt_m"),
            description=d.get("description"),
        )

    def to_text(self) -> str:
        parts = []
        if self.mgrs:
            parts.append(f"MGRS={self.mgrs}")
        if self.lat is not None and self.lon is not None:
            alt_str = f", 고도={self.alt_m}m" if self.alt_m is not None else ""
            parts.append(f"LLA=({self.lat:.6f}, {self.lon:.6f}{alt_str})")
        if self.description:
            parts.append(self.description)
        return " / ".join(parts) if parts else "(위치 불명)"


# ---------------------------------------------------------------------------
# 위협 블록
# ---------------------------------------------------------------------------

@dataclass
class ThreatBlock:
    type: str                                       # VALID_THREAT_TYPES
    count: int                                      # >= 1
    location: LocationBlock
    movement: str = "UNKNOWN"                       # VALID_MOVEMENT_STATES
    speed_kmh: float = 0.0
    identified_systems: List[str] = field(default_factory=list)
    confidence: float = 0.5                         # 0.0 ~ 1.0

    @classmethod
    def from_dict(cls, d: dict) -> "ThreatBlock":
        return cls(
            type=d["type"],
            count=d["count"],
            location=LocationBlock.from_dict(d.get("location", {})),
            movement=d.get("movement", "UNKNOWN"),
            speed_kmh=float(d.get("speed_kmh", 0.0)),
            identified_systems=list(d.get("identified_systems", [])),
            confidence=float(d.get("confidence", 0.5)),
        )

    def to_text(self) -> str:
        systems = ", ".join(self.identified_systems) if self.identified_systems else "미식별"
        return (
            f"위협유형={self.type} / 수량={self.count} / 이동={self.movement}"
            f" / 속도={self.speed_kmh}km/h / 신뢰도={self.confidence:.0%}\n"
            f"  위치: {self.location.to_text()}\n"
            f"  식별체계: {systems}"
        )


# ---------------------------------------------------------------------------
# 아군 전력 블록
# ---------------------------------------------------------------------------

@dataclass
class StrengthBlock:
    personnel: Optional[int] = None
    vehicles: Optional[int] = None
    readiness_pct: Optional[float] = None

    @classmethod
    def from_dict(cls, d: dict) -> "StrengthBlock":
        return cls(
            personnel=d.get("personnel"),
            vehicles=d.get("vehicles"),
            readiness_pct=d.get("readiness_pct"),
        )

    def to_text(self) -> str:
        parts = []
        if self.personnel is not None:
            parts.append(f"인원={self.personnel}명")
        if self.vehicles is not None:
            parts.append(f"차량={self.vehicles}대")
        if self.readiness_pct is not None:
            parts.append(f"전투준비율={self.readiness_pct:.0f}%")
        return ", ".join(parts) if parts else "(강도 정보 없음)"


@dataclass
class FriendlyForcesBlock:
    unit_id: str
    location: LocationBlock
    unit_type: Optional[str] = None                 # VALID_UNIT_TYPES
    strength: Optional[StrengthBlock] = None
    available_fires: List[str] = field(default_factory=list)
    logistics_status: Optional[str] = None         # VALID_LOGISTICS_STATUS

    @classmethod
    def from_dict(cls, d: dict) -> "FriendlyForcesBlock":
        return cls(
            unit_id=d["unit_id"],
            location=LocationBlock.from_dict(d.get("location", {})),
            unit_type=d.get("unit_type"),
            strength=(
                StrengthBlock.from_dict(d["strength"])
                if isinstance(d.get("strength"), dict) else None
            ),
            available_fires=list(d.get("available_fires", [])),
            logistics_status=d.get("logistics_status"),
        )

    def to_text(self) -> str:
        fires = ", ".join(self.available_fires) if self.available_fires else "없음"
        strength_str = self.strength.to_text() if self.strength else "(강도 정보 없음)"
        return (
            f"부대={self.unit_id} / 유형={self.unit_type or '미지정'}"
            f" / 군수={self.logistics_status or '미지정'}\n"
            f"  위치: {self.location.to_text()}\n"
            f"  전력: {strength_str}\n"
            f"  가용화력: {fires}"
        )


# ---------------------------------------------------------------------------
# 지형 블록
# ---------------------------------------------------------------------------

@dataclass
class TerrainBlock:
    type: Optional[str] = None                      # VALID_TERRAIN_TYPES
    visibility_km: Optional[float] = None
    weather: Optional[str] = None                   # VALID_WEATHER
    time_of_day: Optional[str] = None              # VALID_TIME_OF_DAY

    @classmethod
    def from_dict(cls, d: dict) -> "TerrainBlock":
        return cls(
            type=d.get("type"),
            visibility_km=d.get("visibility_km"),
            weather=d.get("weather"),
            time_of_day=d.get("time_of_day"),
        )

    def to_text(self) -> str:
        return (
            f"지형={self.type or '불명'} / 관측={self.visibility_km or '불명'}km"
            f" / 기상={self.weather or '불명'} / 시간대={self.time_of_day or '불명'}"
        )


# ---------------------------------------------------------------------------
# 정보 블록
# ---------------------------------------------------------------------------

@dataclass
class IntelligenceBlock:
    last_update_minutes: Optional[int] = None
    source_reliability: Optional[str] = None       # NATO A~F
    info_credibility: Optional[str] = None         # NATO 1~6
    known_gaps: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "IntelligenceBlock":
        return cls(
            last_update_minutes=d.get("last_update_minutes"),
            source_reliability=d.get("source_reliability"),
            info_credibility=d.get("info_credibility"),
            known_gaps=list(d.get("known_gaps", [])),
        )

    def to_text(self) -> str:
        gaps = "; ".join(self.known_gaps) if self.known_gaps else "없음"
        update = (
            f"{self.last_update_minutes}분 전"
            if self.last_update_minutes is not None else "불명"
        )
        return (
            f"최종갱신={update} / 출처신뢰도={self.source_reliability or '불명'}"
            f" / 내용신빙성={self.info_credibility or '불명'}\n"
            f"  정보공백: {gaps}"
        )


# ---------------------------------------------------------------------------
# 제한 사항 블록
# ---------------------------------------------------------------------------

@dataclass
class TimeConstraintsBlock:
    ttl_minutes: Optional[int] = None
    h_hour: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "TimeConstraintsBlock":
        return cls(
            ttl_minutes=d.get("ttl_minutes"),
            h_hour=d.get("h_hour"),
        )


@dataclass
class ConstraintsBlock:
    roe_level: Optional[str] = None                # VALID_ROE_LEVELS
    no_fire_areas: List[str] = field(default_factory=list)
    time_constraints: Optional[TimeConstraintsBlock] = None

    @classmethod
    def from_dict(cls, d: dict) -> "ConstraintsBlock":
        return cls(
            roe_level=d.get("roe_level"),
            no_fire_areas=list(d.get("no_fire_areas", [])),
            time_constraints=(
                TimeConstraintsBlock.from_dict(d["time_constraints"])
                if "time_constraints" in d else None
            ),
        )

    def to_text(self) -> str:
        nfa = ", ".join(self.no_fire_areas) if self.no_fire_areas else "없음"
        ttl = (
            f"{self.time_constraints.ttl_minutes}분"
            if self.time_constraints and self.time_constraints.ttl_minutes is not None
            else "제한없음"
        )
        return (
            f"ROE={self.roe_level or '미지정'} / 결심TTL={ttl}\n"
            f"  사격금지구역: {nfa}"
        )


# ---------------------------------------------------------------------------
# 질의 블록
# ---------------------------------------------------------------------------

@dataclass
class QueryBlock:
    intent: str                                     # VALID_QUERY_INTENTS
    text: str
    priority_factors: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "QueryBlock":
        return cls(
            intent=d["intent"],
            text=d["text"],
            priority_factors=list(d.get("priority_factors", [])),
        )

    def to_text(self) -> str:
        factors = ", ".join(self.priority_factors) if self.priority_factors else "없음"
        return (
            f"[{self.intent}] {self.text}\n"
            f"  우선고려요소: {factors}"
        )


# ---------------------------------------------------------------------------
# 메타데이터 블록
# ---------------------------------------------------------------------------

@dataclass
class MetadataBlock:
    schema_version: str = DEFAULT_SCHEMA_VERSION
    source: str = DEFAULT_SOURCE
    language: str = "ko"

    @classmethod
    def from_dict(cls, d: dict) -> "MetadataBlock":
        return cls(
            schema_version=d.get("schema_version", DEFAULT_SCHEMA_VERSION),
            source=d.get("source", DEFAULT_SOURCE),
            language=d.get("language", "ko"),
        )


# ---------------------------------------------------------------------------
# 최상위 컨텍스트 객체
# ---------------------------------------------------------------------------

@dataclass
class BattleSituationContext:
    """
    파싱된 전투 상황 컨텍스트. Executor의 시스템 프롬프트에 주입된다.

    schema_version과 source 필드를 통해 실제 전장 데이터로의 교체를
    투명하게 추적한다.
    """
    scenario_id: str
    timestamp: str
    threat: ThreatBlock
    friendly_forces: FriendlyForcesBlock
    query: QueryBlock
    classification: str = DEFAULT_CLASSIFICATION   # 테스트 기본값: CONFIDENTIAL
    terrain: Optional[TerrainBlock] = None
    intelligence: Optional[IntelligenceBlock] = None
    constraints: Optional[ConstraintsBlock] = None
    metadata: MetadataBlock = field(default_factory=MetadataBlock)

    def get_ttl_minutes(self) -> Optional[int]:
        """결심 시간 제한(TTL). 검색 전략 결정에 사용."""
        if self.constraints and self.constraints.time_constraints:
            return self.constraints.time_constraints.ttl_minutes
        return None

    def is_hypothetical(self) -> bool:
        """가상 시나리오 여부. 응답에 면책 문구 삽입 판단에 사용."""
        return self.metadata.source == "HYPOTHETICAL"

    def to_prompt_text(self) -> str:
        """
        Executor 시스템 프롬프트 주입용 직렬화.
        모든 블록을 자연어 + 구조화 혼합 형식으로 렌더링한다.
        """
        lines = [
            "=== 전투 상황 컨텍스트 ===",
            f"시나리오: {self.scenario_id}  |  시각: {self.timestamp}"
            f"  |  보안등급: {self.classification}",
        ]

        if self.is_hypothetical():
            lines.append("[주의] 가상 시나리오 기반 — 실제 작전에 직접 적용 금지")

        lines += [
            "",
            "▶ 위협 상황",
            self.threat.to_text(),
            "",
            "▶ 아군 전력",
            self.friendly_forces.to_text(),
        ]

        if self.terrain:
            lines += ["", "▶ 지형·기상", self.terrain.to_text()]

        if self.intelligence:
            lines += ["", "▶ 정보 상황", self.intelligence.to_text()]

        if self.constraints:
            lines += ["", "▶ 작전 제한", self.constraints.to_text()]

        ttl = self.get_ttl_minutes()
        if ttl is not None:
            lines.append(f"\n[TTL 경고] 결심 가능 시간: {ttl}분 이내")

        lines += [
            "",
            "▶ 질의",
            self.query.to_text(),
            "=========================",
        ]

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 검증 함수
# ---------------------------------------------------------------------------

def validate_battle_situation(ctx: BattleSituationContext) -> List[str]:
    """
    파싱된 컨텍스트에 대한 의미 검증.
    오류 문자열 목록을 반환한다. 빈 목록이면 유효.
    """
    errors: List[str] = []

    if not ctx.scenario_id:
        errors.append("scenario_id: 빈 값 불가")

    if ctx.threat.type not in VALID_THREAT_TYPES:
        errors.append(f"threat.type '{ctx.threat.type}' 미지원 값. 허용: {VALID_THREAT_TYPES}")

    if ctx.threat.count < 1:
        errors.append(f"threat.count={ctx.threat.count}: 1 이상이어야 함")

    if ctx.threat.movement not in VALID_MOVEMENT_STATES:
        errors.append(f"threat.movement '{ctx.threat.movement}' 미지원 값")

    if not (0.0 <= ctx.threat.confidence <= 1.0):
        errors.append(
            f"threat.confidence={ctx.threat.confidence}: 0.0~1.0 범위 위반"
        )

    if ctx.friendly_forces.unit_type and ctx.friendly_forces.unit_type not in VALID_UNIT_TYPES:
        errors.append(f"friendly_forces.unit_type '{ctx.friendly_forces.unit_type}' 미지원 값")

    if (
        ctx.friendly_forces.logistics_status
        and ctx.friendly_forces.logistics_status not in VALID_LOGISTICS_STATUS
    ):
        errors.append(
            f"friendly_forces.logistics_status '{ctx.friendly_forces.logistics_status}' 미지원 값"
        )

    if ctx.query.intent not in VALID_QUERY_INTENTS:
        errors.append(
            f"query.intent '{ctx.query.intent}' 미지원 값. 허용: {VALID_QUERY_INTENTS}"
        )

    if not ctx.query.text.strip():
        errors.append("query.text: 빈 값 불가")

    if ctx.classification not in VALID_CLASSIFICATIONS:
        errors.append(f"classification '{ctx.classification}' 미지원 값")

    if ctx.terrain and ctx.terrain.type and ctx.terrain.type not in VALID_TERRAIN_TYPES:
        errors.append(f"terrain.type '{ctx.terrain.type}' 미지원 값")

    if ctx.terrain and ctx.terrain.weather and ctx.terrain.weather not in VALID_WEATHER:
        errors.append(f"terrain.weather '{ctx.terrain.weather}' 미지원 값")

    if ctx.intelligence and ctx.intelligence.source_reliability:
        if ctx.intelligence.source_reliability not in VALID_SOURCE_RELIABILITY:
            errors.append(
                f"intelligence.source_reliability '{ctx.intelligence.source_reliability}' 미지원 값"
            )

    if ctx.intelligence and ctx.intelligence.info_credibility:
        if ctx.intelligence.info_credibility not in VALID_INFO_CREDIBILITY:
            errors.append(
                f"intelligence.info_credibility '{ctx.intelligence.info_credibility}' 미지원 값"
            )

    if ctx.constraints and ctx.constraints.roe_level:
        if ctx.constraints.roe_level not in VALID_ROE_LEVELS:
            errors.append(f"constraints.roe_level '{ctx.constraints.roe_level}' 미지원 값")

    if ctx.metadata.source not in VALID_SOURCES:
        errors.append(f"metadata.source '{ctx.metadata.source}' 미지원 값")

    return errors


# ---------------------------------------------------------------------------
# 파서
# ---------------------------------------------------------------------------

class BattleSituationParser:
    """
    JSON 문자열 또는 dict → BattleSituationContext 변환.

    실제 전장 데이터로 교체 시 from_json() / from_dict() 만
    호출하면 동일 인터페이스로 동작한다.
    """

    @staticmethod
    def from_json(json_str: str) -> BattleSituationContext:
        """JSON 문자열 파싱. json.JSONDecodeError 또는 KeyError 발생 가능."""
        d = json.loads(json_str)
        return BattleSituationParser.from_dict(d)

    @staticmethod
    def from_dict(d: dict) -> BattleSituationContext:
        """dict → BattleSituationContext. 필수 키 누락 시 KeyError 발생."""
        ctx = BattleSituationContext(
            scenario_id=d["scenario_id"],
            timestamp=d["timestamp"],
            classification=d.get("classification", DEFAULT_CLASSIFICATION),
            threat=ThreatBlock.from_dict(d["threat"]),
            friendly_forces=FriendlyForcesBlock.from_dict(d["friendly_forces"]),
            query=QueryBlock.from_dict(d["query"]),
            terrain=(
                TerrainBlock.from_dict(d["terrain"]) if "terrain" in d else None
            ),
            intelligence=(
                IntelligenceBlock.from_dict(d["intelligence"])
                if "intelligence" in d else None
            ),
            constraints=(
                ConstraintsBlock.from_dict(d["constraints"])
                if "constraints" in d else None
            ),
            metadata=(
                MetadataBlock.from_dict(d["metadata"])
                if "metadata" in d else MetadataBlock()
            ),
        )
        return ctx
