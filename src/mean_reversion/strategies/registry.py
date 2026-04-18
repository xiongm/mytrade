from .mean_reversion import (
    MeanReversionFastExitStrategy,
    MeanReversionStrictStrategy,
    MeanReversionV1Strategy,
)


STRATEGY_FACTORIES = {
    "mean_reversion_v1": MeanReversionV1Strategy,
    "mean_reversion_strict": MeanReversionStrictStrategy,
    "mean_reversion_fast_exit": MeanReversionFastExitStrategy,
}


def list_strategy_names() -> list[str]:
    return sorted(STRATEGY_FACTORIES)


def get_strategy(name: str):
    try:
        return STRATEGY_FACTORIES[name]()
    except KeyError as exc:
        valid = ", ".join(list_strategy_names())
        raise ValueError(f"Unknown strategy '{name}'. Valid strategies: {valid}") from exc
