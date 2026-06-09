import src.infrastructure.llm.router_factory as rf


def test_single_config_has_no_fallbacks(mocker):
    router_cls = mocker.patch.object(rf, "Router")

    rf.build_router([("gemini/x", "key")])

    kwargs = router_cls.call_args.kwargs
    assert kwargs["fallbacks"] == []
    assert kwargs["model_list"] == [
        {
            "model_name": "config-0",
            "litellm_params": {"model": "gemini/x", "api_key": "key"},
        }
    ]


def test_multiple_configs_build_ordered_fallbacks(mocker):
    router_cls = mocker.patch.object(rf, "Router")

    rf.build_router([("m0", "k0"), ("m1", "k1"), ("m2", "k2")])

    kwargs = router_cls.call_args.kwargs
    assert kwargs["fallbacks"] == [{"config-0": ["config-1", "config-2"]}]
    assert [m["model_name"] for m in kwargs["model_list"]] == [
        "config-0",
        "config-1",
        "config-2",
    ]


def test_extra_router_kwargs_are_forwarded(mocker):
    router_cls = mocker.patch.object(rf, "Router")

    rf.build_router([("m0", "k0")], num_retries=2)

    assert router_cls.call_args.kwargs["num_retries"] == 2
