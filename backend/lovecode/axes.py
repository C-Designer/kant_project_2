"""Per-axis classification helpers (comparison experiment next to direct 16-type classification).

A 16-type label "보완형·안정형·독립형·시간 두기" is four binary axis decisions; bit 0 is the
first pole of each axis in contracts.AXIS_LABELS. Models predict the four bits and the
16-type answer is their combination, so it is scored with the same 16-type metrics.
"""

from .contracts import AXIS_KEYS, AXIS_LABELS


def to_bits(label):
    poles = label.split("·")
    return [AXIS_LABELS[j].index(poles[j]) for j in range(len(AXIS_KEYS))]


def from_bits(bits):
    return "·".join(AXIS_LABELS[j][int(b)] for j, b in enumerate(bits))


class AxesLR:
    """Four binary TF-IDF+LR pipelines combined into a 16-type prediction."""

    def __init__(self, make_pipeline):
        self.models = [make_pipeline() for _ in AXIS_KEYS]
        self.classes_ = None

    def fit(self, texts, labels):
        bits = [to_bits(v) for v in labels]
        for j, m in enumerate(self.models):
            m.fit(texts, [b[j] for b in bits])
        self.classes_ = sorted({from_bits(b) for b in _all_bits()})
        return self

    def predict(self, texts):
        cols = [m.predict(texts) for m in self.models]
        return [from_bits(bits) for bits in zip(*cols, strict=True)]


def _all_bits():
    return [[(i >> (3 - j)) & 1 for j in range(4)] for i in range(16)]
