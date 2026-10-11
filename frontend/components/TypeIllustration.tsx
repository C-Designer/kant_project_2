type Props = {
  type: { name: string; image: string; crop: { x: number; y: number; width: number; height: number } };
};

// Display a cell from the original artwork without modifying or resampling it.
export default function TypeIllustration({ type }: Props) {
  const { x, y, width, height } = type.crop;
  return <div className="type-illustration" role="img" aria-label={`${type.name} 커플 일러스트`}
    style={{ aspectRatio: `${width} / ${height}`, backgroundImage: `url("${type.image}")`,
      backgroundSize: `${1024 / width * 100}% ${1536 / height * 100}%`,
      backgroundPosition: `${x / (1024 - width) * 100}% ${y / (1536 - height) * 100}%` }} />;
}
