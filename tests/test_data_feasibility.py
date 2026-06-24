from datetime import UTC, datetime

import pytest

from memecopy_lab.spikes.data_feasibility import (
    QUOTE_MINTS,
    AdapterDisabledError,
    can_reconstruct_approximately_30s,
    missing_required_keys,
    parse_swap_mints,
    require_read_only_adapters_enabled,
)


def test_missing_keys_disable_adapters() -> None:
    env = {"HELIUS_API_KEY": "", "BIRDEYE_API_KEY": ""}

    assert missing_required_keys(env) == ("HELIUS_API_KEY", "BIRDEYE_API_KEY")
    with pytest.raises(AdapterDisabledError, match="adapter disabled"):
        require_read_only_adapters_enabled(env)


def test_can_reconstruct_approximately_30s_requires_30s_or_better() -> None:
    assert can_reconstruct_approximately_30s(30)
    assert not can_reconstruct_approximately_30s(60)
    assert not can_reconstruct_approximately_30s(None)


def test_parse_swap_mints_excludes_quote_assets() -> None:
    traded_mint = "Meme111111111111111111111111111111111111111"
    quote_mint = next(iter(QUOTE_MINTS))
    transaction = {
        "timestamp": int(datetime(2026, 1, 1, tzinfo=UTC).timestamp()),
        "events": {
            "swap": {
                "tokenInputs": [{"mint": quote_mint}],
                "tokenOutputs": [{"mint": traded_mint}],
            }
        },
    }

    assert parse_swap_mints(transaction) == (traded_mint,)
