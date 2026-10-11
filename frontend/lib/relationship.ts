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
