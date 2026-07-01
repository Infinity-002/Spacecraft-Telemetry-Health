"""GRU autoencoder training and anomaly inference."""

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except ModuleNotFoundError:  # pragma: no cover - exercised only on minimal runtimes.
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None


@dataclass(frozen=True)
class TelemetryScaler:
    mean: np.ndarray
    std: np.ndarray

    @classmethod
    def fit(cls, values: np.ndarray) -> "TelemetryScaler":
        mean = values.mean(axis=0)
        std = values.std(axis=0)
        std[std < 1e-4] = 1.0
        return cls(mean=mean, std=std)

    def transform(self, values: np.ndarray) -> np.ndarray:
        return (values - self.mean) / self.std


if nn is not None:

    class GRUAutoencoder(nn.Module):
        def __init__(self, feature_count: int, hidden_size: int = 48, latent_size: int = 24):
            super().__init__()
            self.encoder = nn.GRU(feature_count, hidden_size, batch_first=True)
            self.to_latent = nn.Linear(hidden_size, latent_size)
            self.from_latent = nn.Linear(latent_size, hidden_size)
            self.decoder = nn.GRU(feature_count, hidden_size, batch_first=True)
            self.output = nn.Linear(hidden_size, feature_count)

        def forward(self, sequence):
            _, hidden = self.encoder(sequence)
            latent = torch.tanh(self.to_latent(hidden[-1]))
            decoder_hidden = torch.tanh(self.from_latent(latent)).unsqueeze(0)
            decoder_input = torch.zeros_like(sequence)
            decoded, _ = self.decoder(decoder_input, decoder_hidden)
            return self.output(decoded)

else:

    class GRUAutoencoder:  # type: ignore[no-redef]
        def __init__(self, *_, **__):
            raise ModuleNotFoundError("PyTorch is required for GRUAutoencoder.")


def require_torch() -> None:
    if torch is None:
        raise ModuleNotFoundError(
            "PyTorch is required for GRU training. Run uv sync, then uv run dss-run."
        )


def make_sequences(values: np.ndarray, sequence_length: int = 10) -> np.ndarray:
    if len(values) < sequence_length:
        raise ValueError(f"Need at least {sequence_length} rows to create sequences.")
    return np.stack(
        [values[start : start + sequence_length] for start in range(len(values) - sequence_length + 1)]
    ).astype(np.float32)


def train_gru_autoencoder(
    train_values: np.ndarray,
    sequence_length: int = 10,
    epochs: int = 30,
    batch_size: int = 64,
    learning_rate: float = 1e-3,
    seed: int = 7,
) -> tuple[GRUAutoencoder, TelemetryScaler, list[float], list[float]]:
    require_torch()
    torch.manual_seed(seed)
    np.random.seed(seed)

    scaler = TelemetryScaler.fit(train_values.astype(np.float32))
    sequences = make_sequences(scaler.transform(train_values), sequence_length)

    split_idx = int(len(sequences) * 0.8)
    train_sequences = sequences[:split_idx]
    val_sequences = sequences[split_idx:]

    train_dataset = TensorDataset(torch.from_numpy(train_sequences))
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)

    val_dataset = TensorDataset(torch.from_numpy(val_sequences))
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

    model = GRUAutoencoder(feature_count=train_values.shape[1])
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    criterion = nn.MSELoss()
    losses: list[float] = []
    val_losses: list[float] = []

    best_val_loss = float("inf")
    patience = 5
    patience_counter = 0
    best_model_state = None

    for _ in range(epochs):
        model.train()
        epoch_losses = []
        for (batch,) in train_loader:
            optimizer.zero_grad()
            reconstruction = model(batch)
            loss = criterion(reconstruction, batch)
            loss.backward()
            optimizer.step()
            epoch_losses.append(float(loss.item()))
        
        train_loss = float(np.mean(epoch_losses)) if epoch_losses else 0.0
        losses.append(train_loss)

        model.eval()
        epoch_val_losses = []
        with torch.no_grad():
            for (batch,) in val_loader:
                reconstruction = model(batch)
                val_loss = criterion(reconstruction, batch)
                epoch_val_losses.append(float(val_loss.item()))
        
        val_loss = float(np.mean(epoch_val_losses)) if epoch_val_losses else 0.0
        val_losses.append(val_loss)

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            best_model_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
        else:
            patience_counter += 1
            if patience_counter >= patience:
                if best_model_state is not None:
                    model.load_state_dict(best_model_state)
                break

    return model, scaler, losses, val_losses


def reconstruction_errors(
    model: GRUAutoencoder,
    scaler: TelemetryScaler,
    values: np.ndarray,
    sequence_length: int = 10,
) -> np.ndarray:
    require_torch()
    model.eval()

    scaled = scaler.transform(values.astype(np.float32))
    scaled = np.clip(scaled, -10.0, 10.0)
    sequences = make_sequences(scaled, sequence_length)

    with torch.no_grad():
        batch = torch.from_numpy(sequences.astype(np.float32))
        reconstruction = model(batch).numpy()

    squared_errors = (reconstruction - sequences) ** 2
    mean_sequence_error = squared_errors.mean(axis=(1, 2))
    max_feature_error = squared_errors.mean(axis=1).max(axis=1)

    errors = 0.65 * mean_sequence_error + 0.35 * max_feature_error
    return np.nan_to_num(errors, nan=1e6, posinf=1e6, neginf=1e6)


def normalize_errors(errors: np.ndarray, reference_errors: Iterable[float]) -> np.ndarray:
    reference = np.asarray(list(reference_errors), dtype=float)
    low = float(np.percentile(reference, 50))
    high = float(np.percentile(reference, 99))
    if high <= low:
        high = low + 1e-6
    return np.clip((errors - low) / (high - low), 0.0, 1.0)


def compute_anomaly_pvalue(errors: np.ndarray, reference_errors: np.ndarray) -> np.ndarray:
    errs = np.asarray(errors)
    ref = np.asarray(reference_errors)
    if len(ref) == 0:
        return np.ones_like(errs, dtype=float)
    sorted_ref = np.sort(ref)
    p_values = (len(sorted_ref) - np.searchsorted(sorted_ref, errs, side="left")) / len(sorted_ref)
    return p_values


def save_gru_artifact(
    path: str | Path,
    model: GRUAutoencoder,
    scaler: TelemetryScaler,
    reference_errors: np.ndarray,
    losses: list[float],
    feature_columns: list[str],
    sequence_length: int = 10,
    val_losses: list[float] = None,
) -> None:
    require_torch()
    artifact_path = Path(path)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)

    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "feature_count": len(feature_columns),
            "feature_columns": feature_columns,
            "scaler_mean": scaler.mean,
            "scaler_std": scaler.std,
            "reference_errors": reference_errors,
            "losses": losses,
            "val_losses": val_losses if val_losses is not None else [],
            "sequence_length": sequence_length,
        },
        artifact_path,
    )


def load_gru_artifact(path: str | Path) -> tuple[GRUAutoencoder, TelemetryScaler, np.ndarray, list[float], dict]:
    require_torch()
    artifact_path = Path(path)
    artifact = torch.load(artifact_path, map_location="cpu", weights_only=False)

    model = GRUAutoencoder(feature_count=int(artifact["feature_count"]))
    model.load_state_dict(artifact["model_state_dict"])
    model.eval()

    scaler = TelemetryScaler(
        mean=np.asarray(artifact["scaler_mean"], dtype=np.float32),
        std=np.asarray(artifact["scaler_std"], dtype=np.float32),
    )

    reference_errors = np.asarray(artifact["reference_errors"], dtype=np.float32)
    losses = [float(value) for value in artifact.get("losses", [])]

    metadata = {
        "feature_columns": artifact["feature_columns"],
        "sequence_length": int(artifact.get("sequence_length", 10)),
        "val_losses": [float(val) for val in artifact.get("val_losses", [])],
    }

    return model, scaler, reference_errors, losses, metadata