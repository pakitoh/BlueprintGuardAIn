from typing import Any

from litellm import Router  # type: ignore[attr-defined]


def build_router(configs: list[tuple[str, str]], **router_kwargs: Any) -> Router:
    names = [f"config-{i}" for i in range(len(configs))]
    model_list = [
        {
            "model_name": name,
            "litellm_params": {"model": model, "api_key": api_key},
        }
        for name, (model, api_key) in zip(names, configs, strict=True)
    ]
    fallbacks: list[Any] = [{names[0]: names[1:]}] if len(names) > 1 else []
    return Router(model_list=model_list, fallbacks=fallbacks, **router_kwargs)
