"""PR-000 data-feasibility spike.

This module uses read-only API calls to measure whether historical token price
data can support approximately 30-second paper fill reconstruction.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

CANDIDATE_WALLET = "86xCnPeV69n6t3DnyGvkKobf9FdN2H9oiVDdaMpo2MMY"
CANDIDATE_WALLET_RATIONALE = (
    "Public seed wallet from the Helius enhanced-transactions address endpoint "
    "documentation. It is hardcoded only to validate read-only data feasibility; "
    "it is not treated as an endorsed top trader."
)

HELIUS_TRANSACTIONS_URL = (
    "https://mainnet.helius-rpc.com/v0/addresses/{address}/transactions"
)
BIRDEYE_OHLCV_URL = "https://public-api.birdeye.so/defi/ohlcv"
HELIUS_DOCS_URL = (
    "https://www.helius.dev/docs/api-reference/enhanced-transactions/"
    "gettransactionsbyaddress"
)
BIRDEYE_DOCS_URL = "https://docs.birdeye.so/reference/get-defi-ohlcv"
REQUIRED_ENV_KEYS = ("HELIUS_API_KEY", "BIRDEYE_API_KEY")

WRAPPED_SOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDT_MINT = "Es9vMFrzaCERmJfrF4H2FYD4mKCoNkYb4KqSKLcd6x"
QUOTE_MINTS = frozenset({WRAPPED_SOL_MINT, USDC_MINT, USDT_MINT})

BIRDEYE_INTERVAL_SECONDS = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1_800,
    "1H": 3_600,
}
MAX_HELIUS_PAGES = 12
MAX_TOKENS_TO_PROBE = 5
HTTP_TIMEOUT_SECONDS = 30


class AdapterDisabledError(RuntimeError):
    """Raised when read-only API keys are absent."""


@dataclass(frozen=True)
class SwapObservation:
    signature: str
    timestamp: datetime
    token_mints: tuple[str, ...]


@dataclass(frozen=True)
class TokenOhlcvProbe:
    mint: str
    first_seen_at: datetime
    finest_interval: str | None
    candles_returned: int
    earliest_candle_at: datetime | None
    latest_candle_at: datetime | None
    status: str

    @property
    def finest_interval_seconds(self) -> int | None:
        if self.finest_interval is None:
            return None
        return BIRDEYE_INTERVAL_SECONDS[self.finest_interval]


@dataclass(frozen=True)
class FeasibilityResult:
    wallet: str
    window_start: datetime
    window_end: datetime
    swap_count: int
    token_count: int
    probes: tuple[TokenOhlcvProbe, ...]

    @property
    def finest_interval_seconds(self) -> int | None:
        intervals = [
            probe.finest_interval_seconds
            for probe in self.probes
            if probe.finest_interval_seconds is not None
        ]
        if not intervals:
            return None
        return min(intervals)

    @property
    def can_reconstruct_approximately_30s(self) -> bool:
        return can_reconstruct_approximately_30s(self.finest_interval_seconds)


def can_reconstruct_approximately_30s(interval_seconds: int | None) -> bool:
    return interval_seconds is not None and interval_seconds <= 30


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        clean_key = key.strip()
        clean_value = value.strip().strip('"').strip("'")
        if clean_key:
            values[clean_key] = clean_value
    return values


def load_runtime_env(env_path: Path = Path(".env")) -> dict[str, str]:
    file_values = load_env_file(env_path)
    return {
        key: os.environ.get(key, file_values.get(key, "")) for key in REQUIRED_ENV_KEYS
    }


def missing_required_keys(env: dict[str, str]) -> tuple[str, ...]:
    return tuple(key for key in REQUIRED_ENV_KEYS if not env.get(key))


def require_read_only_adapters_enabled(env: dict[str, str]) -> None:
    missing = missing_required_keys(env)
    if missing:
        joined = ", ".join(missing)
        raise AdapterDisabledError(
            f"adapter disabled: missing {joined}; add read-only keys to .env to run "
            "PR-000 without fabricated data"
        )


def utc_window(days: int = 90) -> tuple[datetime, datetime]:
    end = datetime.now(tz=UTC).replace(microsecond=0)
    return end - timedelta(days=days), end


def parse_swap_mints(transaction: dict[str, Any]) -> tuple[str, ...]:
    swap = transaction.get("events", {}).get("swap", {})
    mints: set[str] = set()

    for transfer in _iter_swap_token_transfers(swap):
        mint = transfer.get("mint")
        if isinstance(mint, str) and mint not in QUOTE_MINTS:
            mints.add(mint)

    return tuple(sorted(mints))


def _iter_swap_token_transfers(swap: dict[str, Any]) -> list[dict[str, Any]]:
    transfers: list[dict[str, Any]] = []
    for key in ("tokenInputs", "tokenOutputs", "tokenFees"):
        values = swap.get(key, [])
        if isinstance(values, list):
            transfers.extend(item for item in values if isinstance(item, dict))

    inner_swaps = swap.get("innerSwaps", [])
    if isinstance(inner_swaps, list):
        for inner_swap in inner_swaps:
            if not isinstance(inner_swap, dict):
                continue
            for key in ("tokenInputs", "tokenOutputs", "tokenFees"):
                values = inner_swap.get(key, [])
                if isinstance(values, list):
                    transfers.extend(item for item in values if isinstance(item, dict))

    return transfers


def fetch_swap_history(
    *,
    api_key: str,
    wallet: str,
    window_start: datetime,
    window_end: datetime,
) -> tuple[SwapObservation, ...]:
    observations: list[SwapObservation] = []
    before_signature: str | None = None

    for _ in range(MAX_HELIUS_PAGES):
        params: dict[str, str | int] = {
            "api-key": api_key,
            "type": "SWAP",
            "gte-time": int(window_start.timestamp()),
            "lte-time": int(window_end.timestamp()),
            "limit": 100,
        }
        if before_signature is not None:
            params["before-signature"] = before_signature

        transactions = _get_json_list(
            HELIUS_TRANSACTIONS_URL.format(address=wallet), params=params, headers={}
        )
        if not transactions:
            break

        for transaction in transactions:
            if not isinstance(transaction, dict):
                continue
            timestamp = _parse_unix_timestamp(transaction.get("timestamp"))
            if timestamp is None or timestamp < window_start:
                continue
            token_mints = parse_swap_mints(transaction)
            if not token_mints:
                continue
            signature = transaction.get("signature")
            if isinstance(signature, str):
                observations.append(
                    SwapObservation(
                        signature=signature,
                        timestamp=timestamp,
                        token_mints=token_mints,
                    )
                )

        last_signature = transactions[-1].get("signature")
        if not isinstance(last_signature, str):
            break
        before_signature = last_signature
        time.sleep(0.2)

    return tuple(observations)


def probe_birdeye_ohlcv(
    *,
    api_key: str,
    mint: str,
    first_seen_at: datetime,
) -> TokenOhlcvProbe:
    for interval, seconds in BIRDEYE_INTERVAL_SECONDS.items():
        window_end = first_seen_at + timedelta(seconds=seconds * 999)
        params: dict[str, str | int] = {
            "address": mint,
            "type": interval,
            "currency": "usd",
            "time_from": int(first_seen_at.timestamp()),
            "time_to": int(window_end.timestamp()),
        }
        try:
            response = _get_json_object(
                BIRDEYE_OHLCV_URL,
                params=params,
                headers={"X-API-KEY": api_key, "x-chain": "solana"},
            )
        except RuntimeError as exc:
            return TokenOhlcvProbe(
                mint=mint,
                first_seen_at=first_seen_at,
                finest_interval=None,
                candles_returned=0,
                earliest_candle_at=None,
                latest_candle_at=None,
                status=str(exc),
            )

        candles = _extract_ohlcv_items(response)
        if candles:
            candle_times = sorted(
                timestamp
                for timestamp in (
                    _parse_unix_timestamp(item.get("unixTime")) for item in candles
                )
                if timestamp is not None
            )
            earliest = candle_times[0] if candle_times else None
            latest = candle_times[-1] if candle_times else None
            return TokenOhlcvProbe(
                mint=mint,
                first_seen_at=first_seen_at,
                finest_interval=interval,
                candles_returned=len(candles),
                earliest_candle_at=earliest,
                latest_candle_at=latest,
                status="ok",
            )

        time.sleep(0.2)

    return TokenOhlcvProbe(
        mint=mint,
        first_seen_at=first_seen_at,
        finest_interval=None,
        candles_returned=0,
        earliest_candle_at=None,
        latest_candle_at=None,
        status="no OHLCV candles returned at tested intervals",
    )


def run_spike(env: dict[str, str] | None = None) -> FeasibilityResult:
    runtime_env = load_runtime_env() if env is None else env
    require_read_only_adapters_enabled(runtime_env)

    window_start, window_end = utc_window()
    swaps = fetch_swap_history(
        api_key=runtime_env["HELIUS_API_KEY"],
        wallet=CANDIDATE_WALLET,
        window_start=window_start,
        window_end=window_end,
    )
    first_seen_by_mint: dict[str, datetime] = {}
    for swap in swaps:
        for mint in swap.token_mints:
            first_seen_by_mint.setdefault(mint, swap.timestamp)

    probes = tuple(
        probe_birdeye_ohlcv(
            api_key=runtime_env["BIRDEYE_API_KEY"],
            mint=mint,
            first_seen_at=first_seen,
        )
        for mint, first_seen in sorted(first_seen_by_mint.items())[:MAX_TOKENS_TO_PROBE]
    )
    return FeasibilityResult(
        wallet=CANDIDATE_WALLET,
        window_start=window_start,
        window_end=window_end,
        swap_count=len(swaps),
        token_count=len(first_seen_by_mint),
        probes=probes,
    )


def render_findings(result: FeasibilityResult) -> str:
    answer = "YES" if result.can_reconstruct_approximately_30s else "NO"
    finest = (
        f"{result.finest_interval_seconds}s"
        if result.finest_interval_seconds is not None
        else "none observed"
    )
    lines = [
        "# PR-000 Data-Feasibility Findings",
        "",
        f"## Answer: {answer}",
        "",
        "Can we reconstruct a fill at ~30s resolution?",
        "",
        f"**{answer}.** The finest observed Birdeye OHLCV interval was {finest}.",
        "A 60-second or coarser candle cannot distinguish entry at +0s from +30s.",
        "",
        "## Candidate Wallet",
        "",
        f"- Wallet: `{result.wallet}`",
        f"- Choice: {CANDIDATE_WALLET_RATIONALE}",
        "",
        "## Run Window",
        "",
        f"- Start UTC: `{result.window_start.isoformat()}`",
        f"- End UTC: `{result.window_end.isoformat()}`",
        f"- Helius swaps observed: `{result.swap_count}`",
        f"- Distinct non-quote token mints observed: `{result.token_count}`",
        "",
        "## Reference Docs",
        "",
        f"- Helius enhanced transactions by address: {HELIUS_DOCS_URL}",
        f"- Birdeye OHLCV: {BIRDEYE_DOCS_URL}",
        "",
        "## Birdeye OHLCV Probes",
        "",
        "| Token mint | First seen UTC | Finest interval | Candles | Coverage | "
        "Status |",
        "|---|---:|---:|---:|---|---|",
    ]
    if result.probes:
        lines.extend(_render_probe_row(probe) for probe in result.probes)
    else:
        lines.append("| n/a | n/a | n/a | 0 | none | no token probes were available |")

    lines.extend(
        [
            "",
            "## Rate-Limit / Cost Reality",
            "",
            "- Helius enhanced transactions and Birdeye OHLCV both require API keys.",
            "- Birdeye OHLCV returns a maximum of 1000 records per request, so a full",
            "  90-day 1m backtest would require many paginated/windowed requests "
            "per token.",
            "- The spike limits token probes and request windows deliberately to avoid",
            "  surprising spend or rate-limit pressure.",
            "",
            "## Implication For PR-013",
            "",
            "- PR-013's 3-month backtest should remain explicitly approximate unless a",
            "  future data source provides <=30s historical executable quotes or "
            "candles.",
            "- If only 1m OHLCV is available, latency sensitivity at the target 30s",
            "  horizon is not measurable from backtest fills.",
            "- The live paper trial remains the primary evidence for real 30s latency.",
            "",
            "## Safety",
            "",
            "- The spike uses read-only HTTP GET requests only.",
            "- No private keys, transaction signing, transaction broadcasting, swaps,",
            "  or exchange write APIs are introduced.",
            "- Missing API keys disable the adapters; no data is fabricated.",
        ]
    )
    return "\n".join(lines) + "\n"


def render_disabled_findings(message: str) -> str:
    window_start, window_end = utc_window()
    return (
        "\n".join(
            [
                "# PR-000 Data-Feasibility Findings",
                "",
                "## Answer: NO",
                "",
                "Can we reconstruct a fill at ~30s resolution?",
                "",
                "**NO, not from this run.** The local adapters were disabled because",
                "read-only API keys were not present, so no historical swaps or OHLCV",
                "candles were pulled. No substitute or fabricated data was used.",
                "",
                "The documented finest Birdeye OHLCV interval to test is `1m`, "
                "which is",
                "already too coarse to distinguish a +0s fill from a +30s fill. This",
                "must be confirmed with real keyed data before treating backtest fills",
                "as anything more than approximate.",
                "",
                "## Candidate Wallet",
                "",
                f"- Wallet: `{CANDIDATE_WALLET}`",
                f"- Choice: {CANDIDATE_WALLET_RATIONALE}",
                "",
                "## Run Window",
                "",
                f"- Intended start UTC: `{window_start.isoformat()}`",
                f"- Intended end UTC: `{window_end.isoformat()}`",
                "- Helius swaps observed: `0`",
                "- Distinct non-quote token mints observed: `0`",
                "",
                "## Reference Docs",
                "",
                f"- Helius enhanced transactions by address: {HELIUS_DOCS_URL}",
                f"- Birdeye OHLCV: {BIRDEYE_DOCS_URL}",
                "",
                "## Adapter Status",
                "",
                f"- `{message}`",
                "- Required keys: `HELIUS_API_KEY`, `BIRDEYE_API_KEY`.",
                "",
                "## Real Granularity",
                "",
                "- Actual account-tier granularity was not measured because "
                "adapters were",
                "  disabled.",
                "- Birdeye's OHLCV endpoint documents `1m` as the finest listed "
                "interval.",
                "",
                "## Coverage Gaps For Fresh Tokens",
                "",
                "- Not measured in this local run because no keyed data was pulled.",
                "- The PR-013 backtest must keep missing early token candles as "
                "`unknown`,",
                "  never as inferred fills.",
                "",
                "## Rate-Limit / Cost Reality",
                "",
                "- Both data sources require read-only API keys.",
                "- Birdeye OHLCV is capped at 1000 records per request, which means a",
                "  90-day 1m analysis requires many requests per token.",
                "- This spike intentionally exits instead of using fallback data "
                "when keys",
                "  are missing.",
                "",
                "## Implication For PR-013",
                "",
                "- PR-013's 3-month backtest remains approximate.",
                "- Without <=30s historical price/quote data, the backtest cannot "
                "measure",
                "  the central latency question.",
                "- The live paper trial remains the primary evidence for real 30s "
                "latency.",
                "",
                "## Safety",
                "",
                "- No live trading path was added.",
                "- No private keys, transaction signing, transaction broadcasting, "
                "swaps,",
                "  or exchange write APIs are introduced.",
                "- Missing API keys disable the adapters; no data is fabricated.",
            ]
        )
        + "\n"
    )


def write_findings(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def main() -> int:
    output_path = Path("docs/data-feasibility-findings.md")
    try:
        result = run_spike()
    except AdapterDisabledError as exc:
        message = str(exc)
        write_findings(output_path, render_disabled_findings(message))
        print(message)
        print(f"wrote {output_path}")
        return 2

    write_findings(output_path, render_findings(result))
    print(f"wrote {output_path}")
    print(
        "30s reconstruction: "
        f"{'YES' if result.can_reconstruct_approximately_30s else 'NO'}"
    )
    return 0


def _render_probe_row(probe: TokenOhlcvProbe) -> str:
    coverage = "none"
    if probe.earliest_candle_at is not None and probe.latest_candle_at is not None:
        coverage = (
            f"{probe.earliest_candle_at.isoformat()} to "
            f"{probe.latest_candle_at.isoformat()}"
        )
    finest = probe.finest_interval if probe.finest_interval is not None else "none"
    return (
        f"| `{probe.mint}` | `{probe.first_seen_at.isoformat()}` | `{finest}` | "
        f"`{probe.candles_returned}` | {coverage} | {probe.status} |"
    )


def _extract_ohlcv_items(response: dict[str, Any]) -> list[dict[str, Any]]:
    data = response.get("data")
    if not isinstance(data, dict):
        return []
    items = data.get("items")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _parse_unix_timestamp(value: Any) -> datetime | None:
    if isinstance(value, int | float):
        return datetime.fromtimestamp(value, tz=UTC).replace(microsecond=0)
    if isinstance(value, str) and value.isdigit():
        return datetime.fromtimestamp(int(value), tz=UTC).replace(microsecond=0)
    return None


def _get_json_list(
    url: str, *, params: dict[str, str | int], headers: dict[str, str]
) -> list[Any]:
    payload = _get_json(url, params=params, headers=headers)
    if not isinstance(payload, list):
        raise RuntimeError("unexpected Helius response shape")
    return payload


def _get_json_object(
    url: str, *, params: dict[str, str | int], headers: dict[str, str]
) -> dict[str, Any]:
    payload = _get_json(url, params=params, headers=headers)
    if not isinstance(payload, dict):
        raise RuntimeError("unexpected Birdeye response shape")
    return payload


def _get_json(
    url: str, *, params: dict[str, str | int], headers: dict[str, str]
) -> Any:
    request_url = f"{url}?{urlencode(params)}"
    request = Request(request_url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        raise RuntimeError(
            f"read-only API request failed with HTTP {exc.code}"
        ) from exc
    except URLError as exc:
        raise RuntimeError("read-only API request failed") from exc
    return json.loads(body, parse_float=Decimal)


if __name__ == "__main__":
    raise SystemExit(main())
