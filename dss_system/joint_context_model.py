"""Joint telemetry-note model for context-aware note classification.

This is a small multi-task PyTorch model:
- text branch: token embedding with masked mean pooling
- telemetry branch: normalized numeric telemetry snapshot
- joint branch: shared MLP with separate output heads

It is intended to improve fields whose meaning depends on spacecraft state,
especially urgency.
"""

from collections import Counter
from dataclasses import dataclass
import re
from typing import Iterable

import numpy as np
import pandas as pd

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, Dataset
except ModuleNotFoundError:  # pragma: no cover
    torch = None
    nn = None
    DataLoader = None
    Dataset = object


TARGET_FIELDS = ["subsystem", "concern", "urgency", "action", "expected_behaviour"]
TOKEN_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9_&+-]*|\d+(?:\.\d+)?")


@dataclass(frozen=True)
class JointContextArtifacts:
    model: "JointContextModel"
    vocab: dict[str, int]
    label_maps: dict[str, dict[str, int]]
    inverse_label_maps: dict[str, dict[int, str]]
    telemetry_mean: np.ndarray
    telemetry_std: np.ndarray
    feature_columns: list[str]


@dataclass(frozen=True)
class NoteContext:
    expected: bool | None
    subsystem: str
    concern: str
    fault_type: str
    urgency: str
    action: str
    matched_terms: tuple[str, ...] = ()
    model_confidence: float = 0.0
    parser_source: str = "joint-context-pytorch"


def require_torch() -> None:
    if torch is None:
        raise ModuleNotFoundError("PyTorch is required for the joint context model.")


def tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(str(text).lower())


def build_vocab(texts: Iterable[str], min_freq: int = 1, max_size: int = 8000) -> dict[str, int]:
    counts = Counter(token for text in texts for token in tokenize(text))
    vocab = {"<pad>": 0, "<unk>": 1}
    for token, _ in counts.most_common(max_size - len(vocab)):
        if counts[token] >= min_freq:
            vocab[token] = len(vocab)
    return vocab


def encode_text(text: str, vocab: dict[str, int], max_tokens: int = 64) -> list[int]:
    ids = [vocab.get(token, vocab["<unk>"]) for token in tokenize(text)[:max_tokens]]
    if len(ids) < max_tokens:
        ids.extend([vocab["<pad>"]] * (max_tokens - len(ids)))
    return ids


def load_joint_records(notes_path, annotations_path, telemetry_path) -> pd.DataFrame:
    notes = pd.read_csv(notes_path, parse_dates=["timestamp"])
    annotations = pd.read_csv(annotations_path)
    annotations["subsystem"] = annotations["subsystem"].fillna("System")
    annotations["concern"] = annotations["concern"].fillna("None")
    annotations["urgency"] = annotations["urgency"].fillna("Nominal")
    annotations["expected_behaviour"] = annotations["expected_behaviour"].fillna("Unknown")
    annotations["action"] = annotations["action"].fillna("None")

    telemetry = pd.read_csv(telemetry_path, parse_dates=["timestamp"])

    records = notes.merge(annotations, on="note_id", how="inner")
    records = records.merge(
        telemetry,
        on=["mission_id", "timestamp"],
        how="inner",
        suffixes=("", "_telemetry"),
    )
    return records


class JointContextDataset(Dataset):
    def __init__(
        self,
        records: pd.DataFrame,
        vocab: dict[str, int],
        label_maps: dict[str, dict[str, int]],
        feature_columns: list[str],
        telemetry_mean: np.ndarray,
        telemetry_std: np.ndarray,
        max_tokens: int = 64,
    ):
        self.text_ids = np.asarray(
            [encode_text(text, vocab, max_tokens) for text in records["operator_note"]],
            dtype=np.int64,
        )
        values = records[feature_columns].to_numpy(dtype=np.float32)
        self.telemetry = ((values - telemetry_mean) / telemetry_std).astype(np.float32)
        self.telemetry = np.clip(self.telemetry, -10.0, 10.0)
        self.targets = {
            field: np.asarray([label_maps[field][str(value)] for value in records[field]], dtype=np.int64)
            for field in TARGET_FIELDS
        }

    def __len__(self) -> int:
        return len(self.text_ids)

    def __getitem__(self, index: int):
        item = {
            "text_ids": torch.tensor(self.text_ids[index], dtype=torch.long),
            "telemetry": torch.tensor(self.telemetry[index], dtype=torch.float32),
        }
        for field, labels in self.targets.items():
            item[field] = torch.tensor(labels[index], dtype=torch.long)
        return item


if nn is not None:

    class JointContextModel(nn.Module):
        def __init__(
            self,
            vocab_size: int,
            telemetry_dim: int,
            output_sizes: dict[str, int],
            embedding_dim: int = 48,
            hidden_dim: int = 96,
        ):
            super().__init__()
            self.embedding = nn.Embedding(vocab_size, embedding_dim, padding_idx=0)
            self.telemetry_encoder = nn.Sequential(
                nn.Linear(telemetry_dim, hidden_dim),
                nn.ReLU(),
                nn.Dropout(0.15),
            )
            self.shared = nn.Sequential(
                nn.Linear(embedding_dim + hidden_dim, hidden_dim),
                nn.ReLU(),
                nn.Dropout(0.20),
            )
            self.heads = nn.ModuleDict(
                {field: nn.Linear(hidden_dim, size) for field, size in output_sizes.items()}
            )

        def forward(self, text_ids, telemetry):
            embeddings = self.embedding(text_ids)
            mask = (text_ids != 0).unsqueeze(-1)
            text_sum = (embeddings * mask).sum(dim=1)
            text_count = mask.sum(dim=1).clamp(min=1)
            text_vector = text_sum / text_count

            telemetry_vector = self.telemetry_encoder(telemetry)
            joint = self.shared(torch.cat([text_vector, telemetry_vector], dim=1))
            return {field: head(joint) for field, head in self.heads.items()}

else:

    class JointContextModel:  # type: ignore[no-redef]
        pass


def _label_maps(records: pd.DataFrame) -> tuple[dict[str, dict[str, int]], dict[str, dict[int, str]]]:
    maps = {}
    inverse = {}
    for field in TARGET_FIELDS:
        labels = sorted(str(value) for value in records[field].dropna().unique())
        maps[field] = {label: idx for idx, label in enumerate(labels)}
        inverse[field] = {idx: label for label, idx in maps[field].items()}
    return maps, inverse


def split_records(records: pd.DataFrame, train_ratio: float = 0.8, seed: int = 7):
    shuffled = records.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    split = int(len(shuffled) * train_ratio)
    return shuffled.iloc[:split].copy(), shuffled.iloc[split:].copy()


def train_joint_context_model(
    train_records: pd.DataFrame,
    feature_columns: list[str],
    epochs: int = 25,
    batch_size: int = 64,
    learning_rate: float = 1e-3,
    seed: int = 7,
) -> JointContextArtifacts:
    require_torch()
    torch.manual_seed(seed)
    np.random.seed(seed)

    vocab = build_vocab(train_records["operator_note"])
    label_maps, inverse_maps = _label_maps(train_records)
    values = train_records[feature_columns].to_numpy(dtype=np.float32)
    telemetry_mean = values.mean(axis=0)
    telemetry_std = values.std(axis=0)
    telemetry_std[telemetry_std == 0] = 1.0

    dataset = JointContextDataset(
        train_records,
        vocab,
        label_maps,
        feature_columns,
        telemetry_mean,
        telemetry_std,
    )
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    model = JointContextModel(
        vocab_size=len(vocab),
        telemetry_dim=len(feature_columns),
        output_sizes={field: len(label_maps[field]) for field in TARGET_FIELDS},
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    criterion = nn.CrossEntropyLoss()

    model.train()
    for _ in range(epochs):
        for batch in loader:
            optimizer.zero_grad()
            outputs = model(batch["text_ids"], batch["telemetry"])
            loss = sum(criterion(outputs[field], batch[field]) for field in TARGET_FIELDS)
            loss.backward()
            optimizer.step()

    return JointContextArtifacts(
        model=model,
        vocab=vocab,
        label_maps=label_maps,
        inverse_label_maps=inverse_maps,
        telemetry_mean=telemetry_mean,
        telemetry_std=telemetry_std,
        feature_columns=feature_columns,
    )


def evaluate_joint_context_model(
    train_records: pd.DataFrame,
    test_records: pd.DataFrame,
    feature_columns: list[str],
    epochs: int = 25,
) -> dict[str, float]:
    require_torch()
    artifacts = train_joint_context_model(train_records, feature_columns, epochs=epochs)
    dataset = JointContextDataset(
        test_records,
        artifacts.vocab,
        artifacts.label_maps,
        feature_columns,
        artifacts.telemetry_mean,
        artifacts.telemetry_std,
    )
    loader = DataLoader(dataset, batch_size=128, shuffle=False)

    correct = Counter()
    total = Counter()
    artifacts.model.eval()
    with torch.no_grad():
        for batch in loader:
            outputs = artifacts.model(batch["text_ids"], batch["telemetry"])
            for field in TARGET_FIELDS:
                pred = outputs[field].argmax(dim=1)
                correct[field] += int((pred == batch[field]).sum().item())
                total[field] += int(batch[field].numel())
    return {field: correct[field] / total[field] if total[field] else 0.0 for field in TARGET_FIELDS}


def save_joint_artifact(path, artifacts: JointContextArtifacts) -> None:
    from pathlib import Path
    require_torch()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "vocab": artifacts.vocab,
        "label_maps": artifacts.label_maps,
        "inverse_label_maps": artifacts.inverse_label_maps,
        "telemetry_mean": artifacts.telemetry_mean,
        "telemetry_std": artifacts.telemetry_std,
        "feature_columns": artifacts.feature_columns,
        "model_state_dict": artifacts.model.state_dict(),
        "vocab_size": len(artifacts.vocab),
        "telemetry_dim": len(artifacts.feature_columns),
        "output_sizes": {field: len(artifacts.label_maps[field]) for field in TARGET_FIELDS},
    }, path)


def load_joint_artifact(path) -> JointContextArtifacts:
    from pathlib import Path
    require_torch()
    path = Path(path)
    data = torch.load(path, map_location="cpu", weights_only=False)
    model = JointContextModel(
        vocab_size=data["vocab_size"],
        telemetry_dim=data["telemetry_dim"],
        output_sizes=data["output_sizes"],
    )
    model.load_state_dict(data["model_state_dict"])
    model.eval()
    return JointContextArtifacts(
        model=model,
        vocab=data["vocab"],
        label_maps=data["label_maps"],
        inverse_label_maps=data["inverse_label_maps"],
        telemetry_mean=data["telemetry_mean"],
        telemetry_std=data["telemetry_std"],
        feature_columns=data["feature_columns"],
    )


def predict_note_context(
    note: str,
    telemetry_row: dict[str, float],
    artifacts: JointContextArtifacts,
):
    require_torch()
    artifacts.model.eval()
    
    # 1. Encode text
    text_ids = torch.tensor([encode_text(note, artifacts.vocab)], dtype=torch.long)
    
    # 2. Extract telemetry features in correct order
    tel_values = np.array([telemetry_row[col] for col in artifacts.feature_columns], dtype=np.float32)
    # Normalize
    scaled_tel = (tel_values - artifacts.telemetry_mean) / artifacts.telemetry_std
    scaled_tel = np.clip(scaled_tel, -10.0, 10.0)
    telemetry_tensor = torch.tensor([scaled_tel], dtype=torch.float32)
    
    # 3. Model prediction
    with torch.no_grad():
        outputs = artifacts.model(text_ids, telemetry_tensor)
        
    predictions = {}
    total_prob = 0.0
    for field in TARGET_FIELDS:
        logits = outputs[field][0]
        probs = torch.softmax(logits, dim=0)
        pred_idx = torch.argmax(probs).item()
        pred_label = artifacts.inverse_label_maps[field][pred_idx]
        pred_prob = probs[pred_idx].item()
        
        predictions[field] = (pred_label, pred_prob)
        total_prob += pred_prob
        
    avg_confidence = total_prob / len(TARGET_FIELDS)
    
    expected_str = predictions["expected_behaviour"][0]
    expected = True if expected_str == "Yes" else False if expected_str == "No" else None
    
    matched_terms = tuple(
        part
        for part in (predictions["subsystem"][0], predictions["concern"][0], predictions["urgency"][0], predictions["action"][0])
        if part and part != "None"
    )
    
    return NoteContext(
        expected=expected,
        subsystem=predictions["subsystem"][0],
        concern=predictions["urgency"][0],  # map concern value
        fault_type=predictions["concern"][0], # from annotation column: concern
        urgency=predictions["urgency"][0],
        action=predictions["action"][0],
        matched_terms=matched_terms,
        model_confidence=avg_confidence,
        parser_source="joint-context-pytorch",
    )
