"""Vercel entrypoint: CPU BERT and OpenAI explanation, with no result database."""
import os
from pathlib import Path

os.environ["LC_MODELS_DIR"] = str(Path(__file__).parent / "model")
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from lovecode.api import app  # noqa: F401
