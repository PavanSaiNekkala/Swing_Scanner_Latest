from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from institutional_metrics.config import (
    InstitutionalMetricsConfig,
)
from institutional_metrics.deduplicator import (
    StockDeduplicator,
)
from institutional_metrics.governance import (
    GovernanceEngine,
)
from institutional_metrics.loader import (
    HistoryLoader,
)
from institutional_metrics.metrics import (
    DerivedMetricsCalculator,
)
from institutional_metrics.ranker import (
    InstitutionalRanker,
)
from institutional_metrics.scoring import (
    InstitutionalScorer,
)
from institutional_metrics.exceptions import (
    NoSourceDataError,
)
from institutional_metrics.schemas import (
    REQUIRED_COLUMNS,
)


# ============================================================
# TEST DATA FACTORIES
# ============================================================


def make_raw_dataframe(
    stocks: list[str] | None = None,
) -> pd.DataFrame:
    """
    Create a deterministic scanner dataframe containing
    the complete required schema.
    """

    stocks = stocks or [
        "AAA",
        "BBB",
        "CCC",
    ]

    rows = []

    for index, stock in enumerate(stocks):

        rows.append(
            {
                "Stock": stock,
                "Signals today": True,
                "Rank": index + 1,
                "Exp/DAY%": 2.0 + index,
                "RS%": 10.0 + index,
                "Trades": 100 + index * 10,
                "Win%": 60.0 + index,
                "Target #": 20,
                "Target %": 20.0,
                "Trail #": 15,
                "Trail %": 15.0,
                "Stop #": 10,
                "Stop %": 10.0,
                "Time #": 5,
                "Time %": 5.0,
                "Time-win": 10,
                "Time-loss": 5,
                "MomExit #": 4,
                "MomExit %": 4.0,
                "Decay #": 3,
                "Decay %": 3.0,
                "Staircase #": 2,
                "Expectancy%": 1.5 + index,
                "Avg win%": 4.0 + index,
                "Avg loss%": -2.0,
                "R:R": 2.0 + index * 0.1,
                "Avg days": 5.0 - index * 0.2,
                "Total return (sum)%": 100.0 + index * 10,
                "CAGR%": 15.0 + index,
                "Max DD%": -10.0 - index,
                "Profit factor": 1.5 + index * 0.1,
                "Recovery factor": 2.0 + index * 0.2,
                "Max consec. losses": 4 - min(index, 2),
                "Seq. trades": 90 + index * 10,
                "BT from": "2020-01-01",
                "BT to": "2026-08-01",
                "Years": 6.5,
                "Remark": "TEST",
            }
        )

    return pd.DataFrame(rows)


def make_governance_dataframe() -> pd.DataFrame:

    dataframe = make_raw_dataframe(
        ["ELIGIBLE", "REJECTED"]
    )

    dataframe.loc[
        dataframe["Stock"] == "REJECTED",
        "Trades",
    ] = 10

    dataframe.loc[
        dataframe["Stock"] == "REJECTED",
        "Expectancy%",
    ] = -1.0

    dataframe.loc[
        dataframe["Stock"] == "REJECTED",
        "CAGR%",
    ] = -5.0

    dataframe.loc[
        dataframe["Stock"] == "REJECTED",
        "Profit factor",
    ] = 0.5

    dataframe.loc[
        dataframe["Stock"] == "REJECTED",
        "Recovery factor",
    ] = -1.0

    dataframe.loc[
        dataframe["Stock"] == "REJECTED",
        "R:R",
    ] = 0.5

    return dataframe


# ============================================================
# SCHEMA TESTS
# ============================================================


def test_required_schema_is_complete() -> None:
    dataframe = make_raw_dataframe()

    missing = [
        column
        for column in REQUIRED_COLUMNS
        if column not in dataframe.columns
    ]

    assert not missing


# ============================================================
# LOADER TESTS
# ============================================================


def test_loader_normalizes_latest_scan_names() -> None:

    loader = HistoryLoader(
        Path("downloads/history")
    )

    assert (
        loader.normalize_sheet_name(
            "Latest Scan"
        )
        == "latestscan"
    )

    assert (
        loader.normalize_sheet_name(
            "latest_scan"
        )
        == "latestscan"
    )

    assert (
        loader.normalize_sheet_name(
            "LATEST-SCAN"
        )
        == "latestscan"
    )

    assert (
        loader.normalize_sheet_name(
            " Latest Scan "
        )
        == "latestscan"
    )


def test_loader_raises_when_history_directory_missing(
    tmp_path: Path,
) -> None:

    missing_directory = (
        tmp_path / "does_not_exist"
    )

    loader = HistoryLoader(
        missing_directory
    )

    with pytest.raises(
        NoSourceDataError
    ):
        loader.load()


def test_loader_discovers_xlsx_files(
    tmp_path: Path,
) -> None:

    workbook = (
        tmp_path
        / "history.xlsx"
    )

    dataframe = make_raw_dataframe(
        ["AAA"]
    )

    with pd.ExcelWriter(
        workbook,
        engine="openpyxl",
    ) as writer:

        dataframe.to_excel(
            writer,
            sheet_name="Latest Scan",
            index=False,
        )

    loader = HistoryLoader(
        tmp_path
    )

    workbooks = (
        loader.discover_workbooks()
    )

    assert workbooks == [workbook]


def test_loader_reads_latest_scan_sheet(
    tmp_path: Path,
) -> None:

    workbook = (
        tmp_path
        / "history.xlsx"
    )

    dataframe = make_raw_dataframe(
        ["AAA", "BBB"]
    )

    with pd.ExcelWriter(
        workbook,
        engine="openpyxl",
    ) as writer:

        dataframe.to_excel(
            writer,
            sheet_name="Latest Scan",
            index=False,
        )

    loader = HistoryLoader(
        tmp_path
    )

    loaded = loader.load()

    assert len(loaded) == 1

    assert (
        loaded[0].sheet_name
        == "Latest Scan"
    )

    assert (
        loaded[0].workbook
        == workbook
    )

    assert len(
        loaded[0].dataframe
    ) == 2

    assert (
        "Source Workbook"
        in loaded[0].dataframe.columns
    )

    assert (
        "Source Sheet"
        in loaded[0].dataframe.columns
    )

    assert (
        "Source Modified"
        in loaded[0].dataframe.columns
    )


def test_loader_ignores_invalid_schema(
    tmp_path: Path,
) -> None:

    workbook = (
        tmp_path
        / "invalid.xlsx"
    )

    dataframe = pd.DataFrame(
        {
            "Stock": ["AAA"],
            "Signals today": [True],
        }
    )

    with pd.ExcelWriter(
        workbook,
        engine="openpyxl",
    ) as writer:

        dataframe.to_excel(
            writer,
            sheet_name="Latest Scan",
            index=False,
        )

    loader = HistoryLoader(
        tmp_path
    )

    with pytest.raises(
        NoSourceDataError
    ):
        loader.load()


# ============================================================
# DEDUPLICATION TESTS
# ============================================================


def test_deduplicator_normalizes_stock_symbols() -> None:

    dataframe = make_raw_dataframe(
        [" aaa ", "BBB"]
    )

    dataframe.loc[
        0,
        "BT to",
    ] = "2026-08-01"

    deduplicator = (
        StockDeduplicator()
    )

    result, duplicates = (
        deduplicator.deduplicate(
            dataframe
        )
    )

    assert "AAA" in set(
        result["Stock"]
    )

    assert "BBB" in set(
        result["Stock"]
    )

    assert duplicates.empty


def test_deduplicator_removes_duplicate_stocks() -> None:

    first = make_raw_dataframe(
        ["AAA"]
    )

    second = make_raw_dataframe(
        ["AAA"]
    )

    first.loc[
        0,
        "BT to",
    ] = "2025-01-01"

    second.loc[
        0,
        "BT to",
    ] = "2026-08-01"

    dataframe = pd.concat(
        [first, second],
        ignore_index=True,
    )

    deduplicator = (
        StockDeduplicator()
    )

    result, duplicates = (
        deduplicator.deduplicate(
            dataframe
        )
    )

    assert len(result) == 1

    assert len(duplicates) == 2

    assert (
        result.iloc[0]["Stock"]
        == "AAA"
    )

    assert (
        pd.Timestamp(
            result.iloc[0]["BT to"]
        )
        == pd.Timestamp(
            "2026-08-01"
        )
    )


def test_deduplicator_removes_triplicates() -> None:

    dataframe = pd.concat(
        [
            make_raw_dataframe(["AAA"]),
            make_raw_dataframe(["AAA"]),
            make_raw_dataframe(["AAA"]),
        ],
        ignore_index=True,
    )

    dataframe.loc[
        0,
        "BT to",
    ] = "2024-01-01"

    dataframe.loc[
        1,
        "BT to",
    ] = "2025-01-01"

    dataframe.loc[
        2,
        "BT to",
    ] = "2026-01-01"

    deduplicator = (
        StockDeduplicator()
    )

    result, duplicates = (
        deduplicator.deduplicate(
            dataframe
        )
    )

    assert len(result) == 1

    assert len(duplicates) == 3

    assert (
        pd.Timestamp(
            result.iloc[0]["BT to"]
        )
        == pd.Timestamp(
            "2026-01-01"
        )
    )


# ============================================================
# DERIVED METRIC TESTS
# ============================================================


def test_derived_metrics_calculate_expected_values() -> None:

    dataframe = make_raw_dataframe(
        ["AAA"]
    )

    calculator = (
        DerivedMetricsCalculator()
    )

    result = calculator.calculate(
        dataframe
    )

    row = result.iloc[0]

    assert row["Loss %"] == pytest.approx(
        40.0
    )

    assert row["Trade Density"] == pytest.approx(
        100 / 6.5
    )

    assert row[
        "Sequential Trade Density"
    ] == pytest.approx(
        90 / 6.5
    )

    expected_return = (
        0.60 * 4.0
        + 0.40 * -2.0
    )

    assert row[
        "Expected Return / Trade %"
    ] == pytest.approx(
        expected_return
    )

    assert row[
        "CAGR / Max DD"
    ] == pytest.approx(
        15.0 / 10.0
    )

    assert row[
        "Expectancy / Day"
    ] == pytest.approx(
        1.5 / 5.0
    )

    assert row[
        "Expectancy × Profit Factor"
    ] == pytest.approx(
        1.5 * 1.5
    )

    assert row[
        "Max DD Magnitude %"
    ] == pytest.approx(
        10.0
    )

    assert (
        row[
            "Backtest Duration Valid"
        ]
        is True
    )


def test_derived_metrics_handle_zero_years() -> None:

    dataframe = make_raw_dataframe(
        ["AAA"]
    )

    dataframe.loc[
        0,
        "Years",
    ] = 0

    calculator = (
        DerivedMetricsCalculator()
    )

    result = calculator.calculate(
        dataframe
    )

    assert pd.isna(
        result.iloc[0][
            "Trade Density"
        ]
    )

    assert pd.isna(
        result.iloc[0][
            "Sequential Trade Density"
        ]
    )


def test_invalid_backtest_dates_are_detected() -> None:

    dataframe = make_raw_dataframe(
        ["AAA"]
    )

    dataframe.loc[
        0,
        "BT from",
    ] = "2026-08-01"

    dataframe.loc[
        0,
        "BT to",
    ] = "2020-01-01"

    calculator = (
        DerivedMetricsCalculator()
    )

    result = calculator.calculate(
        dataframe
    )

    assert (
        result.iloc[0][
            "Backtest Duration Valid"
        ]
        is False
    )


# ============================================================
# SCORING TESTS
# ============================================================


def test_percentile_scores_are_between_zero_and_hundred() -> None:

    dataframe = make_raw_dataframe()

    config = (
        InstitutionalMetricsConfig()
    )

    scorer = (
        InstitutionalScorer(
            config
        )
    )

    result = scorer.calculate(
        DerivedMetricsCalculator().calculate(
            dataframe
        )
    )

    score_columns = [
        column
        for column in result.columns
        if column.endswith(
            "Score"
        )
        or column == "Institutional Score"
    ]

    for column in score_columns:

        values = result[column].dropna()

        assert (
            (values >= 0)
            & (values <= 100)
        ).all()


def test_percentile_single_value_is_neutral() -> None:

    config = (
        InstitutionalMetricsConfig()
    )

    scorer = (
        InstitutionalScorer(
            config
        )
    )

    series = pd.Series(
        [10.0]
    )

    result = scorer.percentile(
        series
    )

    assert result.iloc[0] == pytest.approx(
        config.neutral_percentile
    )


def test_percentile_reverse_changes_order() -> None:

    config = (
        InstitutionalMetricsConfig()
    )

    scorer = (
        InstitutionalScorer(
            config
        )
    )

    series = pd.Series(
        [1.0, 2.0, 3.0]
    )

    normal = scorer.percentile(
        series
    )

    reverse = scorer.percentile(
        series,
        reverse=True,
    )

    assert normal.iloc[0] < normal.iloc[-1]

    assert reverse.iloc[0] > reverse.iloc[-1]


def test_institutional_score_is_weighted_composite() -> None:

    dataframe = make_raw_dataframe()

    metrics = (
        DerivedMetricsCalculator().calculate(
            dataframe
        )
    )

    config = (
        InstitutionalMetricsConfig()
    )

    scorer = (
        InstitutionalScorer(
            config
        )
    )

    result = scorer.calculate(
        metrics
    )

    expected = (
        result["Alpha Score"]
        * config.alpha_weight
        + result[
            "Profitability Score"
        ]
        * config.profitability_weight
        + result["Risk Score"]
        * config.risk_weight
        + result["Robustness Score"]
        * config.robustness_weight
        + result["Efficiency Score"]
        * config.efficiency_weight
    )

    pd.testing.assert_series_equal(
        result[
            "Institutional Score"
        ],
        expected,
        check_names=False,
    )


# ============================================================
# GOVERNANCE TESTS
# ============================================================


def test_governance_accepts_eligible_stock() -> None:

    dataframe = make_governance_dataframe()

    dataframe = (
        DerivedMetricsCalculator().calculate(
            dataframe
        )
    )

    config = (
        InstitutionalMetricsConfig()
    )

    result = (
        GovernanceEngine(
            config
        ).apply(
            dataframe
        )
    )

    eligible = result.loc[
        result["Stock"] == "ELIGIBLE"
    ].iloc[0]

    assert (
        eligible[
            "Institutional Eligible"
        ]
        is True
    )

    assert (
        eligible[
            "Governance Flags"
        ]
        == "NONE"
    )


def test_governance_rejects_invalid_stock() -> None:

    dataframe = make_governance_dataframe()

    dataframe = (
        DerivedMetricsCalculator().calculate(
            dataframe
        )
    )

    config = (
        InstitutionalMetricsConfig()
    )

    result = (
        GovernanceEngine(
            config
        ).apply(
            dataframe
        )
    )

    rejected = result.loc[
        result["Stock"] == "REJECTED"
    ].iloc[0]

    assert (
        rejected[
            "Institutional Eligible"
        ]
        is False
    )

    flags = rejected[
        "Governance Flags"
    ]

    assert (
        "LOW_TRADE_COUNT"
        in flags
    )

    assert (
        "NON_POSITIVE_EXPECTANCY"
        in flags
    )

    assert (
        "NON_POSITIVE_CAGR"
        in flags
    )

    assert (
        "PROFIT_FACTOR_BELOW_1"
        in flags
    )

    assert (
        "NON_POSITIVE_RECOVERY"
        in flags
    )

    assert (
        "LOW_RISK_REWARD"
        in flags
    )


def test_governance_creates_all_gate_columns() -> None:

    dataframe = make_raw_dataframe(
        ["AAA"]
    )

    dataframe = (
        DerivedMetricsCalculator().calculate(
            dataframe
        )
    )

    config = (
        InstitutionalMetricsConfig()
    )

    result = (
        GovernanceEngine(
            config
        ).apply(
            dataframe
        )
    )

    expected_gates = [
        "Minimum Trades",
        "Minimum History",
        "Positive Expectancy",
        "Positive CAGR",
        "Profit Factor",
        "Recovery Factor",
        "Risk Reward",
        "Valid Backtest",
    ]

    for gate in expected_gates:

        assert (
            f"Gate - {gate}"
            in result.columns
        )


# ============================================================
# RANKING TESTS
# ============================================================


def test_ranker_ranks_only_active_signals() -> None:

    dataframe = pd.DataFrame(
        {
            "Stock": [
                "AAA",
                "BBB",
                "CCC",
            ],
            "Signals today": [
                True,
                True,
                False,
            ],
            "Institutional Eligible": [
                True,
                True,
                True,
            ],
            "Institutional Score": [
                80.0,
                90.0,
                100.0,
            ],
        }
    )

    ranker = (
        InstitutionalRanker()
    )

    result = ranker.rank(
        dataframe
    )

    assert (
        result.loc[
            result["Stock"] == "BBB",
            "Institutional Rank",
        ].iloc[0]
        == 1
    )

    assert (
        result.loc[
            result["Stock"] == "AAA",
            "Institutional Rank",
        ].iloc[0]
        == 2
    )

    assert pd.isna(
        result.loc[
            result["Stock"] == "CCC",
            "Institutional Rank",
        ].iloc[0]
    )


def test_ranker_prioritizes_eligible_signals() -> None:

    dataframe = pd.DataFrame(
        {
            "Stock": [
                "REJECTED_HIGH_SCORE",
                "ELIGIBLE_LOWER_SCORE",
            ],
            "Signals today": [
                True,
                True,
            ],
            "Institutional Eligible": [
                False,
                True,
            ],
            "Institutional Score": [
                99.0,
                70.0,
            ],
        }
    )

    result = (
        InstitutionalRanker()
        .rank(dataframe)
    )

    assert (
        result.loc[
            result["Stock"]
            == "ELIGIBLE_LOWER_SCORE",
            "Institutional Rank",
        ].iloc[0]
        == 1
    )

    assert (
        result.loc[
            result["Stock"]
            == "REJECTED_HIGH_SCORE",
            "Institutional Rank",
        ].iloc[0]
        == 2
    )


def test_ranker_is_deterministic_on_score_tie() -> None:

    dataframe = pd.DataFrame(
        {
            "Stock": [
                "ZZZ",
                "AAA",
            ],
            "Signals today": [
                True,
                True,
            ],
            "Institutional Eligible": [
                True,
                True,
            ],
            "Institutional Score": [
                80.0,
                80.0,
            ],
        }
    )

    result = (
        InstitutionalRanker()
        .rank(dataframe)
    )

    assert (
        result.loc[
            result["Stock"] == "AAA",
            "Institutional Rank",
        ].iloc[0]
        == 1
    )

    assert (
        result.loc[
            result["Stock"] == "ZZZ",
            "Institutional Rank",
        ].iloc[0]
        == 2
    )


# ============================================================
# CLASSIFICATION TESTS
# ============================================================


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (95.0, "A+"),
        (85.0, "A"),
        (75.0, "B+"),
        (65.0, "B"),
        (55.0, "C"),
        (45.0, "D"),
        (25.0, "F"),
    ],
)
def test_rating_boundaries(
    score: float,
    expected: str,
) -> None:

    assert (
        InstitutionalRanker._rating(
            score
        )
        == expected
    )


def test_classification_decisions() -> None:

    dataframe = pd.DataFrame(
        {
            "Stock": [
                "STRONG",
                "BUY",
                "WATCH",
                "WEAK",
                "REJECT",
                "NONE",
            ],
            "Signals today": [
                True,
                True,
                True,
                True,
                True,
                False,
            ],
            "Institutional Eligible": [
                True,
                True,
                True,
                True,
                False,
                True,
            ],
            "Institutional Score": [
                85.0,
                75.0,
                65.0,
                55.0,
                90.0,
                90.0,
            ],
        }
    )

    result = (
        InstitutionalRanker()
        .classify(dataframe)
    )

    decisions = dict(
        zip(
            result["Stock"],
            result[
                "Institutional Decision"
            ],
        )
    )

    assert (
        decisions["STRONG"]
        == "STRONG_BUY"
    )

    assert (
        decisions["BUY"]
        == "BUY"
    )

    assert (
        decisions["WATCH"]
        == "WATCH"
    )

    assert (
        decisions["WEAK"]
        == "WEAK_WATCH"
    )

    assert (
        decisions["REJECT"]
        == "REJECT"
    )

    assert (
        decisions["NONE"]
        == "NO_SIGNAL"
    )


# ============================================================
# END-TO-END MODULE TEST
# ============================================================


def test_core_pipeline_stages_work_together() -> None:

    dataframe = make_raw_dataframe(
        [
            "AAA",
            "BBB",
            "CCC",
            "DDD",
        ]
    )

    metrics = (
        DerivedMetricsCalculator()
        .calculate(dataframe)
    )

    config = (
        InstitutionalMetricsConfig()
    )

    scored = (
        InstitutionalScorer(
            config
        ).calculate(
            metrics
        )
    )

    governed = (
        GovernanceEngine(
            config
        ).apply(
            scored
        )
    )

    ranked = (
        InstitutionalRanker()
        .rank(governed)
    )

    classified = (
        InstitutionalRanker()
        .classify(ranked)
    )

    assert len(classified) == 4

    assert (
        "Institutional Score"
        in classified.columns
    )

    assert (
        "Institutional Eligible"
        in classified.columns
    )

    assert (
        "Institutional Rank"
        in classified.columns
    )

    assert (
        "Institutional Rating"
        in classified.columns
    )

    assert (
        "Institutional Decision"
        in classified.columns
    )

    active_ranks = (
        classified.loc[
            classified["Signals today"],
            "Institutional Rank",
        ]
        .dropna()
        .astype(int)
        .tolist()
    )

    assert active_ranks == [
        1,
        2,
        3,
        4,
    ]
