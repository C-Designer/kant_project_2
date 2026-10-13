"""Rule checks on a drafted explanation, shared by the repair chain and the comparison script.

find_problems() returns (kind, instruction) pairs. The instruction is written for the LLM
("what to fix"); kinds are what gets logged, so no output text leaves the process.
"""

import re

from .contracts import AXIS_KEYS, AXIS_LABELS, AXIS_VALUES, TAXONOMY

ASSERTIVE = re.compile(r"반드시|무조건|틀림없|절대로?|운명|100\s?%|확실히 .{0,6}(될|할) 것")
SUPERIOR = re.compile(r"더 (좋은|나은|우월)|우월|열등|나쁜 (유형|쪽|관계)")
RELATIONS = ["천간합", "천간충", "육합", "반합", "삼합", "방합", "암합", "원진"]
MBTI_CODE = re.compile(r"[EI][SN][TF][JP]")
HANJA = re.compile(r"[一-鿿]")
MARKUP = re.compile(r"\*\*|__|`|(?:^|\s)#{1,6}\s|[<>]|https?://")
# Kinds the service rejects if they survive the repair; the rest are reported but returned.
HARD = {"length", "mbti_code", "hanja", "markup"}
LIMITS = {"summary": 120, "strengths": 180, "adjustments": 180, "conversation_tip": 180}


def poles(type_id):
    axes = TAXONOMY[type_id]["axes"]
    return [lab[val.index(axes[k])] for k, lab, val in zip(AXIS_KEYS, AXIS_LABELS, AXIS_VALUES)]


def opposite_poles(type_id):
    axes = TAXONOMY[type_id]["axes"]
    return [lab[1 - val.index(axes[k])] for k, lab, val in zip(AXIS_KEYS, AXIS_LABELS, AXIS_VALUES)]


def texts_of(parsed):
    return [
        parsed["summary"], *parsed["strengths"], *parsed["adjustments"], parsed["conversation_tip"]
    ]


def find_problems(parsed, type_id, input_text):
    problems = []
    for field, limit in LIMITS.items():
        values = parsed[field] if isinstance(parsed[field], list) else [parsed[field]]
        for v in values:
            if len(v) > limit:
                problems.append(("length", f"{field}가 {len(v)}자다. {limit}자 이하로 줄인다."))
    joined = " ".join(texts_of(parsed))
    if MBTI_CODE.search(joined):
        problems.append(("mbti_code", "MBTI 유형 이름(영문 네 글자)을 쓰지 말고 '외향적인 성향'처럼 풀어 쓴다."))
    if HANJA.search(joined):
        problems.append(("hanja", "한자를 쓰지 말고 한글로만 쓴다."))
    if MARKUP.search(joined):
        problems.append(("markup", "Markdown(**, #, `), HTML, URL 없이 평범한 문장으로 쓴다."))
    own = poles(type_id)
    for own_pole, other in zip(own, opposite_poles(type_id), strict=True):
        if other in joined:
            problems.append((
                "opposite_pole",
                f"이 커플은 '{own_pole}' 쪽이다. 반대 극 '{other}' 표현은 비교로도 쓰지 않는다.",
            ))
    made_up = [r for r in RELATIONS if r in joined and r not in input_text]
    if made_up:
        problems.append((
            "fabricated_relations",
            f"입력에 없는 관계({', '.join(made_up)})를 지우고 입력에 있는 사실만 쓴다.",
        ))
    if ASSERTIVE.search(joined):
        problems.append(("assertive", "'반드시', '운명' 같은 단정 표현 대신 제안형으로 쓴다."))
    if SUPERIOR.search(joined):
        problems.append(("superiority", "한쪽 극이 더 좋다는 표현을 쓰지 않는다. 두 극은 우열이 없다."))
    return problems
