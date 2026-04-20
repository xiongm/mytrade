from .mean_reversion import STRATEGY_TYPES


STRATEGY_FACTORIES = {strategy_type.name: strategy_type for strategy_type in STRATEGY_TYPES}


def list_strategy_names() -> list[str]:
    return sorted(STRATEGY_FACTORIES)


def get_strategy(name: str):
    try:
        return STRATEGY_FACTORIES[name]()
    except KeyError as exc:
        valid = ", ".join(list_strategy_names())
        raise ValueError(f"Unknown strategy '{name}'. Valid strategies: {valid}") from exc
