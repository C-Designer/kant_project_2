type Props = {
  review: Record<string, string>;
  onEdit: (step: number) => void;
};
export default function PersonReview({ review, onEdit }: Props) {
  return (
    <div className="review-people">
      {['a', 'b'].map((id, i) => (
        <section key={id}>
          <div className="review-heading">
            <h3>{i === 0 ? '첫 번째 사람' : '두 번째 사람'}</h3>
            <button type="button" className="text-button" onClick={() => onEdit(i)}>
              수정
            </button>
          </div>
          <dl>
            <div>
              <dt>성별</dt>
              <dd>
                {{ male: '남성', female: '여성', unspecified: '선택 안 함' }[review[id + 'gender']]}
              </dd>
            </div>
            <div>
              <dt>양력 생일</dt>
              <dd>{review[id + 'date']}</dd>
            </div>
            <div>
              <dt>태어난 시각</dt>
              <dd>{review[id + 'unknown'] ? '모름' : review[id + 'time']}</dd>
            </div>
            <div>
              <dt>MBTI</dt>
              <dd>{review[id + 'mbti']}</dd>
            </div>
          </dl>
        </section>
      ))}
    </div>
  );
}
