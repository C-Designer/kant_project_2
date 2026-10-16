import re
from datetime import date, datetime
from itertools import product
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .spicy import TITLE_MAX, TITLES, TOPICS, spicy_text_ok

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


QUESTION_MAX = 60


class AnalysisInput(Strict):
    external_processing_consent: bool = False
    person_a: Person
    person_b: Person
    # One optional line for the explainer to answer. Sent to the LLM as data; never stored,
    # logged or put in a share link (docs/SPICY_SPEC.md §3).
    question: str | None = Field(default=None, max_length=200)
    adult_confirmed: bool = False

    @field_validator("question")
    @classmethod
    def valid_question(cls, v):
        if v is None:
            return None
        v = " ".join(v.split())
        if not v:
            return None
        if len(v) > QUESTION_MAX or re.search(r"https?://|www\.|[<>{}]|[\x00-\x1f\x7f]", v):
            raise ValueError(f"궁금한 점은 {QUESTION_MAX}자 이하의 한 줄 문장으로 적어 주세요.")
        return v


class SpicyTitle(Strict):
    id: str
    text: str


class SpicyResult(Strict):
    """Rule-picked title + LLM note per topic. Topic words are allowed here, explicit,
    profane, numeric-odds and certainty wording is not (lovecode.spicy.spicy_text_ok)."""

    titles: dict[str, SpicyTitle]
    notes: dict[str, str]

    @model_validator(mode="after")
    def consistent(self):
        if set(self.titles) != set(TOPICS) or set(self.notes) != set(TOPICS):
            raise ValueError("매운맛 주제 불일치")
        for topic, title in self.titles.items():
            # A link keeps the wording it was made with, so only the id must still exist.
            if title.id not in TITLES or title.id[0] != TITLES_PREFIX[topic]:
                raise ValueError("알 수 없는 칭호")
            if not spicy_text_ok(title.text, TITLE_MAX) or not spicy_text_ok(self.notes[topic]):
                raise ValueError("허용되지 않는 매운맛 텍스트")
        return self


TITLES_PREFIX = dict(zip(TOPICS, "SCJR"))


BANNED_RESULT_TEXT = re.compile(
    r"https?://|[<>]|[EI][SN][TF][JP]|\d{2,4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}:\d{2}"
    r"|[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]|바람기|불륜|속궁합"
)


def result_text_ok(t, max_len):
    return 1 <= len(t) <= max_len and not BANNED_RESULT_TEXT.search(t)


READING_PERSON_MAX = 240
READING_AXIS_MAX = 220


class Reading(Strict):
    """'왜 이 유형일까': each person's chart read in plain words (person_a, person_b order)
    and, per axis, why the couple landed on its pole (lovecode.reading)."""

    people: list[str] = Field(min_length=2, max_length=2)
    axes: dict[str, str]

    @model_validator(mode="after")
    def consistent(self):
        if set(self.axes) != set(AXIS_KEYS):
            raise ValueError("풀이 축 불일치")
        if not all(result_text_ok(t, READING_PERSON_MAX) for t in self.people) or not all(
            result_text_ok(t, READING_AXIS_MAX) for t in self.axes.values()
        ):
            raise ValueError("허용되지 않는 풀이 텍스트")
        return self


class PublicResult(Strict):
    # 1.1 adds the spicy section, 1.2 the reading (spicy optional there); 1.0 and 1.1
    # results (and links) stay valid without the newer sections.
    schema_version: Literal["1.0", "1.1", "1.2"] = "1.0"
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
    spicy: SpicyResult | None = None
    reading: Reading | None = None

    @model_validator(mode="after")
    def consistent(self):
        if (self.schema_version == "1.2") != (self.reading is not None):
            raise ValueError("스키마 버전과 풀이 불일치")
        if self.schema_version != "1.2" and (self.schema_version == "1.1") != (self.spicy is not None):
            raise ValueError("스키마 버전과 매운맛 불일치")
        if self.type_id not in TAXONOMY or self.axes != TAXONOMY[self.type_id]["axes"]:
            raise ValueError("유형과 축 불일치")
        if len(set(self.limitations)) != len(self.limitations):
            raise ValueError("중복 제한")
        texts = [self.summary, *self.strengths, *self.adjustments, self.conversation_tip]
        if not all(result_text_ok(t, 180) for t in texts):
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
        schema_version="1.2",
        reading=Reading(
            people=[
                (
                    "봄에 태어난 을목 일간이라 덩굴처럼 유연하게 주변과 어울리며 자라는 기운이에요. "
                    "자기 기운이 강한 신강이라 중심이 단단하고, 외향적이고 감정을 중시하는 성향이 "
                    "더해져 연애에서도 마음을 먼저 표현하는 편이에요."
                ),
                (
                    "가을에 태어난 정화 일간이라 촛불처럼 은은하게 오래 타는 기운이에요. 기운이 약한 "
                    "신약이라 나무 기운의 도움이 반갑고, 내향적이고 꼼꼼하게 계획하는 성향이라 "
                    "연애에서도 천천히 믿음을 쌓아 가는 편이에요."
                ),
            ],
            axes={
                "chemistry": "두 분의 오행 구성이 많이 다르고, 첫 번째 분의 나무 기운이 두 번째 분에게 "
                "필요한 기운을 많이 채워 줘요. 나무가 불을 살리듯 서로 없는 부분을 채워 주는 "
                "보완형으로 나왔어요.",
                "temperature": "두 분 사이에 육합이 있고 강하게 부딪치는 충은 없어요. 감정의 큰 파도보다 "
                "꾸준한 온기가 어울리는 안정형이에요.",
                "distance": "두 분의 월지와 일지 사이에 육합이 있어요. 육합은 서로 끌어당겨 하나로 "
                "묶이는 관계라, 함께하는 시간이 자연스럽게 늘어나는 밀착형으로 나왔어요.",
                "conflict": "일지끼리 원진이 있어 서운함이 쌓였다가 늦게 드러나기 쉬운 구조예요. 두 번째 "
                "분이 신중한 성향이라, 감정을 가라앉힌 뒤 대화하는 시간 두기가 잘 맞아요.",
            },
        ),
        spicy=SpicyResult(
            titles={t: SpicyTitle(id=i, text=TITLES[i]) for t, i in zip(TOPICS, ("S3", "C3", "J3", "R4"))},
            notes={
                "skinship": "겉으론 무덤덤한데 둘만 있으면 온도 올라가는 타입. 속도는 말로 맞추는 게 국룰이야.",
                "temptation": "각자 공간이 중요해서 한눈팔 에너지도 아까운 편. 대신 연락 텀은 미리 정해 둬.",
                "jealousy": "쿨한 척 참다가 한꺼번에 터질 수 있어. 서운한 건 그날 한 줄이라도 말해 봐.",
                "reunion": "정리할 땐 깔끔한 스타일. 그러니까 싸웠을 때 '시간 좀 줘'를 이별로 오해하지 말기.",
            },
        ),
    )


class Answer(Strict):
    """Reply to AnalysisInput.question. Lives outside PublicResult so it never enters a link."""

    question: str = Field(min_length=1, max_length=QUESTION_MAX)
    status: Literal["answered", "declined_offtopic", "declined_adult"]
    text: str = Field(min_length=1, max_length=200)


class AnalysisResponse(Strict):
    analysis_id: str
    result: PublicResult
    answer: Answer | None = None
    # Signed, compressed copy of the result for a share link; absent when sharing is off.
    share_code: str | None = None


class SharedResult(Strict):
    result: PublicResult
    created_at: datetime
