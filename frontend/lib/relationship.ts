/** Stable API keys: display order must never depend on JSON property order. */
export const AXES = [
  { key: 'chemistry', label: '연애 케미' },
  { key: 'temperature', label: '연애 온도' },
  { key: 'distance', label: '관계 거리' },
  { key: 'conflict', label: '갈등 해결' },
] as const;

export const AXIS_VALUES: Record<string, string> = {
  similar: '닮은꼴',
  complementary: '보완형',
  passionate: '열정형',
  steady: '안정형',
  together: '밀착형',
  independent: '독립형',
  immediate: '바로 풀기',
  pause: '시간 두기',
};

export function axisEntries(axes: Record<string, string>) {
  return AXES.map((axis) => ({ ...axis, value: AXIS_VALUES[axes[axis.key]] ?? '확인 필요' }));
}

/** What each axis value looks like in everyday life, shown on the type guide pages. */
export const AXIS_MEANINGS: Record<string, string> = {
  similar: '취향과 생활 감각이 비슷해 설명하지 않아도 통하는 순간이 많아요.',
  complementary: '서로 다른 점이 많아, 상대가 내가 몰랐던 세계를 보여 주는 사이예요.',
  passionate: '마음을 자주, 크게 표현하며 관계에 에너지를 쏟는 편이에요.',
  steady: '큰 이벤트보다 꾸준하고 한결같은 표현으로 마음을 전해요.',
  together: '일상을 많이 나누고, 함께 보내는 시간에서 안정을 느껴요.',
  independent: '각자의 시간과 공간을 지키는 것이 관계를 건강하게 한다고 느껴요.',
  immediate: '불편한 일이 생기면 그 자리에서 이야기해 정리하고 싶어 해요.',
  pause: '감정을 가라앉히고 생각을 정리한 뒤에 대화하는 편이 편해요.',
};

/** Types that differ from `axes` in exactly one axis, in AXES order. */
export function oneAxisApart<T extends { axes: string[] }>(axes: string[], types: readonly T[]) {
  return AXES.flatMap((axis, i) => {
    const type = types.find((t) =>
      t.axes.every((v, j) => (j === i ? v !== axes[j] : v === axes[j])),
    );
    return type ? [{ axis: axis.label, type }] : [];
  });
}
