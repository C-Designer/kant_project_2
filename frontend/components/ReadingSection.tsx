import { Reading } from '@/lib/api';
import { axisEntries } from '@/lib/relationship';

// Numbered like the input form (01, 02) so each reading matches the person who entered it.
const PEOPLE = ['첫 번째 분', '두 번째 분'];

/** '왜 이 유형일까요?': each person's chart in plain words, then why each axis landed where it did. */
export default function ReadingSection({
  reading,
  axes,
}: {
  reading: Reading;
  axes: Record<string, string>;
}) {
  return (
    <section className="result-section reading" aria-labelledby="reading-title">
      <h2 id="reading-title">왜 이 유형일까요?</h2>
      <div className="reading-people">
        {reading.people.map((text, i) => (
          <div key={PEOPLE[i]}>
            <h3>
              <b aria-hidden="true">0{i + 1}</b>
              {PEOPLE[i]}
            </h3>
            <p>{text}</p>
          </div>
        ))}
      </div>
      <dl className="reading-axes">
        {axisEntries(axes).map((axis) => (
          <div key={axis.key}>
            <dt>
              {axis.label} <strong>{axis.value}</strong>
            </dt>
            <dd>{reading.axes[axis.key]}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
