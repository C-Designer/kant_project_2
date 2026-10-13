import re
from datetime import date, datetime
from itertools import product
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

AXIS_KEYS = ("chemistry", "temperature", "distance", "conflict")
AXIS_VALUES = [
    ("similar", "complementary"),
    ("passionate", "steady"),
    ("together", "independent"),
    ("immediate", "pause"),
]
AXIS_LABELS = [
    ("닮은꼴", "보완형"),
    ("열정형", "안정형"),
    ("밀착형", "독립형"),
    ("바로 풀기", "시간 두기"),
]
TAXONOMY = {
    f"T{i + 1:02}": {
        "axes": dict(zip(AXIS_KEYS, values)),
        "label": "·".join(AXIS_LABELS[j][AXIS_VALUES[j].index(v)] for j, v in enumerate(values)),
    }
    for i, values in enumerate(product(*AXIS_VALUES))
}
DISCLAIMER = "사주와 MBTI를 바탕으로 한 참고·오락용 해석이에요. 실제 관계와 미래를 단정하지 않아요."


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Person(Strict):
    gender: Literal["male", "female", "unspecified"]
    birth_date: date
    birth_time: str | None
    mbti: str

    @field_validator("birth_date")
    @classmethod
    def valid_date(cls, v):
        if not date(1940, 1, 1) <= v <= datetime.now(ZoneInfo("Asia/Seoul")).date():
            raise ValueError("생년월일은 1940년 1월 1일부터 오늘까지 입력해 주세요.")
        return v

    @field_validator("birth_time")
    @classmethod
    def valid_time(cls, v):
        if v is not None and not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", v):
            raise ValueError("시각 형식 오류")
        return v

    @field_validator("mbti")
    @classmethod
    def valid_mbti(cls, v):
        v = v.upper()
        if not re.fullmatch("[EI][SN][TF][JP]", v):
            raise ValueError("MBTI 형식 오류")
        return v


class AnalysisInput(Strict):
    external_processing_consent: bool = False
    person_a: Person
    person_b: Person


class PublicResult(Strict):
    schema_version: Literal["1.0"] = "1.0"
    type_id: str
    taxonomy_version: Literal["love-code-v1"] = "love-code-v1"
    axes: dict[str, str]
    summary: str = Field(min_length=1, max_length=120)
    strengths: list[str] = Field(min_length=2, max_length=2)
    adjustments: list[str] = Field(min_length=2, max_length=2)
    conversation_tip: str = Field(min_length=1, max_length=180)
    limitations: list[
        Literal[
            "missing_hour_a", "missing_hour_b", "boundary_time_unknown_a", "boundary_time_unknown_b"
        ]
    ] = []
    disclaimer_version: Literal["entertainment-v1"] = "entertainment-v1"
    # Public results must never imply human approval.
    evidence_status: Literal["fixture", "ai_draft_unreviewed"]

    @model_validator(mode="after")
    def consistent(self):
        if self.type_id not in TAXONOMY or self.axes != TAXONOMY[self.type_id]["axes"]:
            raise ValueError("유형과 축 불일치")
        if len(set(self.limitations)) != len(self.limitations):
            raise ValueError("중복 제한")
        texts = [self.summary, *self.strengths, *self.adjustments, self.conversation_tip]
        for t in texts:
            if not 1 <= len(t) <= 180 or re.search(
                r"https?://|[<>]|[EI][SN][TF][JP]|\d{2,4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}:\d{2}|[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]|바람기|불륜|속궁합",
                t,
            ):
                raise ValueError("허용되지 않는 결과 텍스트")
        return self


def demo_result():
    return PublicResult(
        type_id="T14",
        axes=TAXONOMY["T14"]["axes"],
        summary="서로 다른 리듬이 만나, 편안한 하루를 만드는 사이",
        strengths=[
            "서로 다른 시선이 익숙한 하루에 작은 발견을 더해 줄 수 있어요.",
            "함께 보내는 평범한 시간이 두 사람에게 든든한 기억이 될 수 있어요.",
        ],
        adjustments=[
            "같이 있고 싶은 마음과 혼자 쉬고 싶은 마음을 말로 확인해 보세요.",
            "생각을 정리할 시간이 필요하다면, 다시 이야기할 때도 함께 약속해 보세요.",
        ],
        conversation_tip="“오늘 우리 둘 다 편안했던 순간은 언제였어?”라고 물어보세요.",
        limitations=["missing_hour_a"],
        evidence_status="fixture",
    )


class AnalysisResponse(Strict):
    analysis_id: str
    result: PublicResult
