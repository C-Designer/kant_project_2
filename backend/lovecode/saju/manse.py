"""① 만세력 계산 (규칙).

계산 규약 (docs/calc_convention.md 참고)
- 입력: 양력 생년월일, 생시(선택). 출생지는 받지 않으며 경도(진태양시) 보정을 하지 않는다.
- 시각: 입력 시각은 그 당시 한국의 시계 시각으로 본다. 서머타임과 과거 표준시(UTC+8:30)는
  tz 데이터베이스(Asia/Seoul)로 UTC로 바꾼 뒤, 현재 한국 표준시(UTC+9)로 환산해 계산한다.
- 년주·월주: 입춘과 절입 시각 기준. lunar-python의 절기표는 중국 표준시(UTC+8)이므로
  KST 시각을 UTC+8로 바꿔서 비교한다.
- 일주·시주: KST(UTC+9) 시계 기준. 23시대 출생은 다음 날 일주로 본다(sect=1, 설정 가능).
- 생시 모름: 시주를 제외한다. 일주·월주는 그날 12:00 기준이며, 절입일이라 월주가 바뀔 수 있으면 경고한다.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from lunar_python import Solar

SEOUL = ZoneInfo("Asia/Seoul")
KST = timezone(timedelta(hours=9))
CST = timezone(timedelta(hours=8))

MIN_YEAR, MAX_YEAR = 1940, 2030
DEFAULT_SECT = 1  # 1: 23시부터 다음 날 일주, 2: 23시대도 당일 일주(야자시)


class ManseInputError(ValueError):
    """사용자 입력 오류 (존재하지 않는 날짜, 지원 범위 밖 연도 등)."""


@dataclass
class Saju:
    year: str
    month: str
    day: str
    time: str | None
    time_known: bool
    std_time: str  # 계산에 쓴 KST 표준시 (YYYY-MM-DD HH:MM)
    notes: list[str] = field(default_factory=list)

    @property
    def pillars(self) -> list[str | None]:
        return [self.year, self.month, self.day, self.time]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["pillars"] = self.pillars
        return d


def _to_kst(y: int, m: int, d: int, hour: int | None, minute: int | None) -> tuple[datetime, list[str]]:
    notes: list[str] = []
    if not (MIN_YEAR <= y <= MAX_YEAR):
        raise ManseInputError(f"지원 범위 밖 연도입니다 ({MIN_YEAR}~{MAX_YEAR}년).")
    try:
        datetime(y, m, d)
    except ValueError as e:
        raise ManseInputError(f"존재하지 않는 날짜입니다: {y}-{m}-{d}") from e

    if hour is None:
        if minute is not None:
            raise ManseInputError("분만 입력할 수 없습니다. 생시를 모르면 시와 분을 모두 비워 주세요.")
        return datetime(y, m, d, 12, 0, tzinfo=KST), notes

    minute = minute or 0
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ManseInputError(f"올바르지 않은 시각입니다: {hour}:{minute}")

    clock = datetime(y, m, d, hour, minute, tzinfo=SEOUL)
    offset = clock.utcoffset()
    kst = clock.astimezone(KST)
    if offset != timedelta(hours=9):
        h = offset.total_seconds() / 3600
        reason = "서머타임" if clock.dst() and clock.dst() != timedelta(0) else "과거 표준시"
        notes.append(
            f"{reason} 보정: 당시 시계 {hour:02d}:{minute:02d}(UTC+{h:g}) → 표준시 {kst:%H:%M}"
            + (f" ({kst:%m-%d})" if kst.date() != clock.date() else "")
        )
    return kst, notes


def _eight_char(dt: datetime, sect: int):
    ec = Solar.fromYmdHms(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second).getLunar().getEightChar()
    ec.setSect(sect)
    return ec


def calc_saju(y: int, m: int, d: int, hour: int | None = None, minute: int | None = None,
              sect: int = DEFAULT_SECT) -> Saju:
    kst, notes = _to_kst(y, m, d, hour, minute)
    time_known = hour is not None

    # 년주·월주: 절입 시각과 같은 시간대(UTC+8)로 맞춰 비교
    cst = kst.astimezone(CST).replace(tzinfo=None)
    ec_ym = _eight_char(cst, sect)
    year_p, month_p = ec_ym.getYear(), ec_ym.getMonth()

    # 일주·시주: KST 시계 기준
    ec_dt = _eight_char(kst.replace(tzinfo=None), sect)
    day_p = ec_dt.getDay()
    time_p = ec_dt.getTime() if time_known else None

    if not time_known:
        notes.append("생시 모름: 시주 제외")
        s = (kst.replace(hour=0, minute=0)).astimezone(CST).replace(tzinfo=None)
        e = (kst.replace(hour=23, minute=59)).astimezone(CST).replace(tzinfo=None)
        if _eight_char(s, sect).getMonth() != _eight_char(e, sect).getMonth():
            notes.append("절입일 출생이라 생시에 따라 월주가 달라질 수 있음 (12:00 기준으로 계산)")
        if _eight_char(s, sect).getYear() != _eight_char(e, sect).getYear():
            notes.append("입춘일 출생이라 생시에 따라 년주가 달라질 수 있음 (12:00 기준으로 계산)")

    return Saju(year_p, month_p, day_p, time_p, time_known, f"{kst:%Y-%m-%d %H:%M}" if time_known else f"{kst:%Y-%m-%d} (시각 모름)", notes)


if __name__ == "__main__":
    import sys
    args = [int(a) for a in sys.argv[1:]]
    print(calc_saju(*args).to_dict())
