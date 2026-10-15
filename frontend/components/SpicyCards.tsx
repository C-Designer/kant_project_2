import type { Spicy } from '@/lib/api';
import { spicyCards } from '@/lib/spicy';

export default function SpicyCards({ spicy }: { spicy: Spicy }) {
  return (
    <ul className="spicy-cards">
      {spicyCards(spicy).map((card) => (
        <li key={card.key}>
          <small>
            <span aria-hidden="true">{card.emoji}</span> {card.name}
          </small>
          <strong>{card.title}</strong>
          <p>{card.note}</p>
        </li>
      ))}
    </ul>
  );
}
