from dataclasses import asdict, dataclass
from datetime import date, timedelta

FEATURES = (
    "lag_1",
    "lag_7",
    "lag_28",
    "rolling_mean_7",
    "rolling_mean_28",
    "day_of_week",
    "item_id",
)
FEATURES_VERSION = "1.0"
BASELINE = "weekday_mean_4"
CANDIDATE = "hist_gradient_boosting_poisson"
METHODS = (BASELINE, CANDIDATE)
MODEL_CONFIG = {
    "loss": "poisson",
    "max_iter": 100,
    "learning_rate": 0.1,
    "max_leaf_nodes": 15,
    "min_samples_leaf": 50,
    "random_state": 42,
    "early_stopping": False,
    "categorical_features": ["item_id"],
}
CPU_THREADS = 2
CONTEXT_DAYS = 28


@dataclass(frozen=True)
class Protocol:
    version: str = "1.0"
    source: str = "m5"
    store_id: str = "CA_1"
    department_id: str = "FOODS_1"
    start: date = date(2015, 1, 1)
    end: date = date(2016, 5, 22)
    expected_skus: int = 216
    horizon: int = 14
    cutoffs: tuple[date, ...] = (
        date(2016, 2, 14),
        date(2016, 2, 28),
        date(2016, 3, 13),
        date(2016, 3, 27),
        date(2016, 4, 10),
        date(2016, 4, 24),
    )
    test_cutoff: date = date(2016, 5, 8)

    def stages(self):
        return (
            *((f"fold_{i}", c) for i, c in enumerate(self.cutoffs, 1)),
            ("test", self.test_cutoff),
        )

    def manifest(self) -> dict:
        result = asdict(self)
        result.update(
            features=list(FEATURES),
            features_version=FEATURES_VERSION,
            model_config=dict(MODEL_CONFIG),
            cpu_threads=CPU_THREADS,
            baseline={"method": BASELINE, "same_weekday_observations": 4},
            stages=[
                {
                    "stage": name,
                    "cutoff": str(c),
                    "start": str(c + timedelta(days=1)),
                    "end": str(c + timedelta(days=self.horizon)),
                }
                for name, c in self.stages()
            ],
            segmentation="training-only equal-count tertiles; stable item_id tie-break",
            selection_rule="lower pooled RMSE14 AND wins >= 4/6 AND abs bias no worse",
        )
        return result


V1 = Protocol()


class ForecastError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}
