"""간지·오행·관계 상수표. 모든 판정 표는 여기에서만 관리한다."""

STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
STEM_KO = dict(zip(STEMS, "갑을병정무기경신임계"))
BRANCH_KO = dict(zip(BRANCHES, "자축인묘진사오미신유술해"))
BRANCH_ANIMAL = dict(zip(BRANCHES, ["쥐", "소", "호랑이", "토끼", "용", "뱀", "말", "양", "원숭이", "닭", "개", "돼지"]))

# 오행: 0 木, 1 火, 2 土, 3 金, 4 水
ELEMENTS = "木火土金水"
ELEMENT_KO = dict(zip(range(5), ["목", "화", "토", "금", "수"]))
ELEMENT_PLAIN = dict(zip(range(5), ["나무", "불", "흙", "쇠", "물"]))

STEM_ELEMENT = {s: i // 2 for i, s in enumerate(STEMS)}
STEM_YANG = {s: i % 2 == 0 for i, s in enumerate(STEMS)}
BRANCH_ELEMENT = dict(zip(BRANCHES, [4, 2, 0, 0, 2, 1, 1, 2, 3, 3, 2, 4]))
BRANCH_YANG = {b: i % 2 == 0 for i, b in enumerate(BRANCHES)}

# 지장간 (여기·중기·정기, 일수). 한국 통용 표 기준. 마지막 항목이 정기.
HIDDEN_STEMS = {
    "子": [("壬", 10), ("癸", 20)],
    "丑": [("癸", 9), ("辛", 3), ("己", 18)],
    "寅": [("戊", 7), ("丙", 7), ("甲", 16)],
    "卯": [("甲", 10), ("乙", 20)],
    "辰": [("乙", 9), ("癸", 3), ("戊", 18)],
    "巳": [("戊", 7), ("庚", 7), ("丙", 16)],
    "午": [("丙", 10), ("己", 9), ("丁", 11)],
    "未": [("丁", 9), ("乙", 3), ("己", 18)],
    "申": [("戊", 7), ("壬", 7), ("庚", 16)],
    "酉": [("庚", 10), ("辛", 20)],
    "戌": [("辛", 9), ("丁", 3), ("戊", 18)],
    "亥": [("戊", 7), ("甲", 7), ("壬", 16)],
}
MAIN_HIDDEN = {b: v[-1][0] for b, v in HIDDEN_STEMS.items()}

SEASON = {}
for _b in "寅卯辰":
    SEASON[_b] = "봄"
for _b in "巳午未":
    SEASON[_b] = "여름"
for _b in "申酉戌":
    SEASON[_b] = "가을"
for _b in "亥子丑":
    SEASON[_b] = "겨울"

# 조후(온도) 점수
SEASON_TEMP = {"봄": 0.0, "여름": 2.0, "가을": 0.0, "겨울": -2.0}
CHAR_TEMP = {
    "丙": 1, "丁": 1, "巳": 1, "午": 1,
    "壬": -1, "癸": -1, "亥": -1, "子": -1,
    "未": 0.5, "戌": 0.5, "丑": -0.5, "辰": -0.5,
}

# ---- 관계표 ----
STEM_COMBINE = {frozenset("甲己"): 2, frozenset("乙庚"): 3, frozenset("丙辛"): 4,
                frozenset("丁壬"): 0, frozenset("戊癸"): 1}  # 값: 합화 오행
STEM_CLASH = {frozenset(p) for p in ["甲庚", "乙辛", "丙壬", "丁癸"]}

BRANCH_SIX_COMBINE = {frozenset("子丑"): 2, frozenset("寅亥"): 0, frozenset("卯戌"): 1,
                      frozenset("辰酉"): 3, frozenset("巳申"): 4, frozenset("午未"): 1}
BRANCH_CLASH = {frozenset(p) for p in ["子午", "丑未", "寅申", "卯酉", "辰戌", "巳亥"]}
BRANCH_HARM = {frozenset(p) for p in ["子未", "丑午", "寅巳", "卯辰", "申亥", "酉戌"]}
BRANCH_WONJIN = {frozenset(p) for p in ["子未", "丑午", "寅酉", "卯申", "辰亥", "巳戌"]}
BRANCH_PUNISH = {frozenset(p) for p in ["寅巳", "巳申", "寅申", "丑戌", "戌未", "丑未", "子卯"]}
SELF_PUNISH = set("辰午酉亥")

# 삼합 (세 글자, 가운데가 왕지), 방합
TRIPLE_COMBINE = [("申子辰", 4), ("亥卯未", 0), ("寅午戌", 1), ("巳酉丑", 3)]
DIRECTION_COMBINE = [("寅卯辰", 0), ("巳午未", 1), ("申酉戌", 3), ("亥子丑", 4)]

POS_NAMES = ["년", "월", "일", "시"]
POS_MEANING = {"년": "뿌리·집안", "월": "생활환경·사회", "일": "나·배우자 자리", "시": "미래·자녀"}

TEN_GOD_FAMILY = {"비겁": ("비견", "겁재"), "식상": ("식신", "상관"), "재성": ("편재", "정재"),
                  "관성": ("편관", "정관"), "인성": ("편인", "정인")}

MBTI_AXES = [("E", "I"), ("S", "N"), ("T", "F"), ("J", "P")]
