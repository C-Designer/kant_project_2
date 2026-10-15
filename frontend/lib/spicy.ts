import data from '../data/spicy-titles.json' with { type: 'json' };
import type { Spicy } from './api';

export const SPICY_TOPICS = data.topics;
export const QUESTION_MAX = 60;

/** Cards in fixed topic order, whatever order the API used. */
export function spicyCards(spicy: Spicy) {
  return SPICY_TOPICS.filter((t) => spicy.titles[t.key] && spicy.notes[t.key]).map((t) => ({
    ...t,
    title: spicy.titles[t.key].text,
    note: spicy.notes[t.key],
  }));
}

/** Titles a type can get, for /types pages (the 신살 signals decide which one a couple gets). */
export function reachableTitles(typeId: string) {
  const reachable = (data.reachable as Record<string, Record<string, string[]>>)[typeId];
  if (!reachable) return [];
  const titles = data.titles as Record<string, string>;
  return SPICY_TOPICS.map((t) => ({ ...t, titles: reachable[t.key].map((id) => titles[id]) }));
}
