"""klue/bert-base fine-tuning for the 16-type classifier.

Default: one 16-way softmax. axes=True: four binary outputs (one per axis), combined into the
16-type label (comparison experiment). Validation 16-type macro-F1 picks the best epoch either
way; test is never touched here (train.py evaluates once).
"""

import random
import time
from pathlib import Path

WEIGHTS = "model.safetensors"


def _device():
    import torch

    use_cuda = torch.cuda.is_available() and torch.cuda.device_count() > 0
    return torch.device("cuda" if use_cuda else "cpu")


def _batches(tokenizer, texts, max_length, batch_size):
    for i in range(0, len(texts), batch_size):
        yield tokenizer(
            texts[i : i + batch_size],
            truncation=True,
            max_length=max_length,
            padding=True,
            return_tensors="pt",
        )


def predict_axis_probs(model, tokenizer, texts, *, max_length=512, batch_size=32):
    """axes model: probability of the second pole on each of the four axes."""
    import torch

    device = next(model.parameters()).device
    model.eval()
    out = []
    with torch.no_grad(), torch.autocast(device.type, enabled=device.type == "cuda"):
        for enc in _batches(tokenizer, texts, max_length, batch_size):
            logits = model(**{k: v.to(device) for k, v in enc.items()}).logits
            out.extend(torch.sigmoid(logits.float()).tolist())
    return out


def _logits(model, tokenizer, texts, *, max_length=512, batch_size=32):
    import torch

    device = next(model.parameters()).device
    model.eval()
    out = []
    with torch.no_grad(), torch.autocast(device.type, enabled=device.type == "cuda"):
        for enc in _batches(tokenizer, texts, max_length, batch_size):
            out.append(model(**{k: v.to(device) for k, v in enc.items()}).logits.float().cpu())
    return torch.cat(out)


def predict_ids(model, tokenizer, texts, *, max_length=512, batch_size=32):
    import torch

    device = next(model.parameters()).device
    model.eval()
    out = []
    with torch.no_grad(), torch.autocast(device.type, enabled=device.type == "cuda"):
        for enc in _batches(tokenizer, texts, max_length, batch_size):
            logits = model(**{k: v.to(device) for k, v in enc.items()}).logits
            out.extend(logits.argmax(-1).tolist())
    return out


def finetune(
    x,
    y,
    labels,
    output,
    *,
    model_name,
    revision,
    epochs=12,
    lr=3e-5,
    batch_size=8,
    max_length=512,
    seed=42,
    local_files_only=True,
    axes=False,
    dropout=None,
    weight_decay=0.01,
    label_smoothing=0.0,
):
    """x/y: {"train": [...], "validation": [...]} texts and label strings. Returns run log."""
    import numpy as np
    import torch
    from sklearn.metrics import f1_score
    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
        get_linear_schedule_with_warmup,
    )

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    device = _device()
    index = {label: i for i, label in enumerate(labels)}
    load = {"revision": revision, "local_files_only": local_files_only}
    tokenizer = AutoTokenizer.from_pretrained(model_name, **load)
    if dropout is not None:  # regularization: BERT/RoBERTa config names
        load |= {"hidden_dropout_prob": dropout, "attention_probs_dropout_prob": dropout}
    from .axes import from_bits, to_bits
    from .contracts import AXIS_KEYS

    if axes:
        model = AutoModelForSequenceClassification.from_pretrained(
            model_name, num_labels=len(AXIS_KEYS), id2label=dict(enumerate(AXIS_KEYS)), **load
        ).to(device)
        model.config.lovecode_axes = True
        y_train = torch.tensor([to_bits(v) for v in y["train"]], dtype=torch.float)
        # Balanced per axis: weight the second pole by negatives/positives.
        pos = y_train.sum(0)
        bce = torch.nn.BCEWithLogitsLoss(
            pos_weight=((len(y_train) - pos) / pos.clamp(min=1)).to(device)
        )
        y_val = torch.tensor([to_bits(v) for v in y["validation"]], dtype=torch.float)

        def loss_fn(logits, target):  # training: label smoothing pulls targets toward 0.5
            return bce(logits.float(), target * (1 - label_smoothing) + 0.5 * label_smoothing)

        def eval_loss(logits, target):
            return bce(logits.float(), target)
    else:
        model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            num_labels=len(labels),
            id2label=dict(enumerate(labels)),
            label2id=index,
            **load,
        ).to(device)
        y_train = torch.tensor([index[v] for v in y["train"]])
        # Balanced class weights, same intent as class_weight="balanced" in the LR baselines.
        counts = torch.bincount(y_train, minlength=len(labels)).float()
        weight = (len(y_train) / (len(labels) * counts.clamp(min=1))).to(device)
        loss_fn = torch.nn.CrossEntropyLoss(weight=weight, label_smoothing=label_smoothing)
        eval_loss = torch.nn.CrossEntropyLoss(weight=weight)
        y_val = torch.tensor([index[v] for v in y["validation"]])
    optim = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    steps = epochs * -(-len(y_train) // batch_size)
    sched = get_linear_schedule_with_warmup(optim, int(0.1 * steps), steps)
    scaler = torch.amp.GradScaler(enabled=device.type == "cuda")
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats()

    output = Path(output)
    history, best = [], (-1.0, -1)
    start = time.perf_counter()
    for epoch in range(1, epochs + 1):
        model.train()
        order = torch.randperm(len(y_train)).tolist()
        total = 0.0
        for i in range(0, len(order), batch_size):
            idx = order[i : i + batch_size]
            enc = tokenizer(
                [x["train"][j] for j in idx],
                truncation=True,
                max_length=max_length,
                padding=True,
                return_tensors="pt",
            ).to(device)
            with torch.autocast(device.type, enabled=device.type == "cuda"):
                loss = loss_fn(model(**enc).logits, y_train[idx].to(device))
            optim.zero_grad()
            scaler.scale(loss).backward()
            scaler.unscale_(optim)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(optim)
            scaler.update()
            sched.step()
            total += loss.item() * len(idx)
        logits = _logits(model, tokenizer, x["validation"], max_length=max_length)
        with torch.no_grad():
            val_loss = eval_loss(logits.to(device), y_val.to(device)).item()
        if axes:
            pred = [from_bits([p > 0.5 for p in row]) for row in torch.sigmoid(logits).tolist()]
        else:
            pred = [labels[i] for i in logits.argmax(-1).tolist()]
        f1 = f1_score(y["validation"], pred, labels=labels, average="macro", zero_division=0)
        history.append(
            {"epoch": epoch, "train_loss": total / len(y_train), "validation_loss": val_loss,
             "validation_macro_f1": f1}
        )
        print(
            f"[{'klue_bert_axes' if axes else 'klue_bert'}] epoch {epoch}/{epochs} "
            f"loss {total / len(y_train):.4f} val_loss {val_loss:.4f} val_macro_f1 {f1:.4f}"
        )
        if f1 > best[0]:
            best = (f1, epoch)
            model.save_pretrained(output, safe_serialization=True)
            tokenizer.save_pretrained(output)
    return {
        "model": model_name,
        "revision": revision,
        "device": torch.cuda.get_device_name(0) if device.type == "cuda" else "cpu",
        "torch": torch.__version__,
        "hyperparameters": {
            "epochs": epochs,
            "lr": lr,
            "batch_size": batch_size,
            "max_length": max_length,
            "seed": seed,
            "warmup_ratio": 0.1,
            "weight_decay": weight_decay,
            "dropout": model.config.hidden_dropout_prob,
            "label_smoothing": label_smoothing,
            "class_weight": "balanced",
            "heads": "four binary axes" if axes else "16-way softmax",
            "amp": device.type == "cuda",
        },
        "best_epoch": best[1],
        "history": history,
        "train_seconds": time.perf_counter() - start,
        "peak_gpu_memory_mb": torch.cuda.max_memory_allocated() / 2**20
        if device.type == "cuda"
        else None,
    }


class BertModel:
    """Loads a fine-tuned directory written by finetune(); offline only."""

    def __init__(self, directory, max_length=512):
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(directory, local_files_only=True)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            directory, local_files_only=True
        ).to(_device())
        self.max_length = max_length
        self.axes = bool(getattr(self.model.config, "lovecode_axes", False))
        if self.axes:
            from .axes import _all_bits, from_bits

            self.classes_ = sorted(from_bits(b) for b in _all_bits())
        else:
            config = self.model.config.id2label
            self.classes_ = [config[i] for i in range(len(config))]

    def predict(self, texts):
        if self.axes:
            from .axes import from_bits

            probs = predict_axis_probs(
                self.model, self.tokenizer, list(texts), max_length=self.max_length
            )
            return [from_bits([p > 0.5 for p in row]) for row in probs]
        ids = predict_ids(self.model, self.tokenizer, list(texts), max_length=self.max_length)
        return [self.classes_[i] for i in ids]
