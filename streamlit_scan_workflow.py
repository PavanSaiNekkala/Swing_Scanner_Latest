from __future__ import annotations

import argparse
import csv
import logging
import os
import signal
import socket
import subprocess
import sys
import time
import re
import pandas as pd
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Download,
    Error as PlaywrightError,
    Locator,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_DIR: Final[Path] = Path(
    __file__
).resolve().parent

STREAMLIT_APP: Final[Path] = PROJECT_DIR / (
    "swing_scanner_app.py"
)

DOWNLOAD_DIR: Final[Path] = PROJECT_DIR / (
    "downloads"
)

VALID_SEGMENTS: Final[set[str]] = {
    "LargeCap",
    "MidCap",
    "SmallCap",
    "Nifty500",
    "AllNSE",
}

DEFAULT_HOST: Final[str] = "127.0.0.1"
DEFAULT_PORT: Final[int] = 8501

SERVER_START_TIMEOUT_SECONDS: Final[int] = 90

STOCK_BACKTEST_TIMEOUT_SECONDS: Final[int] = 60

DEFAULT_SCAN_TIMEOUT_SECONDS: Final[int] = 30 * 60

PAGE_TIMEOUT_MS: Final[int] = 30_000

UI_POLL_INTERVAL_SECONDS: Final[float] = 2.0


# =============================================================================
# LOGGING
# =============================================================================

def configure_logging() -> logging.Logger:
    """
    Configure production-friendly workflow logging.
    """

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | "
            "%(levelname)-8s | "
            "%(name)s | "
            "%(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    return logging.getLogger(
        "streamlit_scan_workflow"
    )


logger = configure_logging()


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass(frozen=True)
class WorkflowConfig:
    """
    Immutable configuration for one scanner workflow run.
    """

    segment: str

    host: str

    port: int

    headless: bool

    scan_timeout_seconds: int

    keep_server_running: bool

    limit_stocks: int | None


# =============================================================================
# PORT / SERVER UTILITIES
# =============================================================================

def is_port_open(
    host: str,
    port: int,
) -> bool:
    """
    Return True when a TCP listener is available.
    """

    with socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    ) as connection:

        connection.settimeout(
            1.0
        )

        return (
            connection.connect_ex(
                (
                    host,
                    port,
                )
            )
            == 0
        )


def wait_for_streamlit_server(
    *,
    host: str,
    port: int,
    timeout_seconds: int,
) -> None:
    """
    Wait until Streamlit starts accepting connections.
    """

    logger.info(
        "Waiting for Streamlit server at %s:%s.",
        host,
        port,
    )

    deadline = (
        time.monotonic()
        + timeout_seconds
    )

    while (
        time.monotonic()
        < deadline
    ):

        if is_port_open(
            host,
            port,
        ):

            logger.info(
                "Streamlit server is ready."
            )

            return

        time.sleep(
            1.0
        )

    raise TimeoutError(
        "Timed out waiting for Streamlit server "
        f"at {host}:{port}."
    )


def start_streamlit_server(
    config: WorkflowConfig,
) -> subprocess.Popen:
    """
    Start the existing Streamlit scanner.

    The application itself remains unchanged.
    """

    if not STREAMLIT_APP.exists():

        raise FileNotFoundError(
            "Scanner application was not found: "
            f"{STREAMLIT_APP}"
        )

    if is_port_open(
        config.host,
        config.port,
    ):

        raise RuntimeError(
            f"Port {config.port} is already in use. "
            "Either stop the existing Streamlit process "
            "or use --port with another value."
        )

    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(STREAMLIT_APP),
        "--server.address",
        config.host,
        "--server.port",
        str(config.port),
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]

    logger.info(
        "Starting Streamlit scanner."
    )

    logger.info(
        "Command: %s",
        " ".join(command),
    )

    process = subprocess.Popen(
        command,
        cwd=str(
            PROJECT_DIR
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,
    )

    return process


def stop_streamlit_server(
    process: subprocess.Popen | None,
) -> None:
    """
    Stop the Streamlit process and its process group safely.
    """

    if process is None:

        return

    if process.poll() is not None:

        logger.info(
            "Streamlit process already stopped."
        )

        return

    logger.info(
        "Stopping Streamlit server."
    )

    try:

        if os.name != "nt":

            os.killpg(
                os.getpgid(
                    process.pid
                ),
                signal.SIGTERM,
            )

        else:

            process.terminate()

        process.wait(
            timeout=15
        )

    except subprocess.TimeoutExpired:

        logger.warning(
            "Streamlit did not stop gracefully. "
            "Terminating forcefully."
        )

        try:

            if os.name != "nt":

                os.killpg(
                    os.getpgid(
                        process.pid
                    ),
                    signal.SIGKILL,
                )

            else:

                process.kill()

        except ProcessLookupError:

            pass


# =============================================================================
# STREAMLIT UI AUTOMATION
# =============================================================================

def get_streamlit_url(
    config: WorkflowConfig,
) -> str:
    """
    Build the local Streamlit URL.
    """

    return (
        f"http://{config.host}:"
        f"{config.port}"
    )


def wait_for_application_ready(
    page: Page,
) -> None:
    """
    Wait until the scanner title and Segment selector are visible.
    """

    logger.info(
        "Waiting for scanner UI."
    )

    page.get_by_text(
        "NSE Market-Wide Daily Swing Scanner",
        exact=False,
    ).wait_for(
        state="visible",
        timeout=PAGE_TIMEOUT_MS,
    )

    page.get_by_text(
        "Segment",
        exact=True,
    ).wait_for(
        state="visible",
        timeout=PAGE_TIMEOUT_MS,
    )

    logger.info(
        "Scanner UI is ready."
    )


def select_segment(
    page: Page,
    segment: str,
) -> None:
    """
    Select the requested market segment from the Streamlit
    Segment selectbox.

    Uses the Streamlit/BaseWeb combobox and waits for the
    selected value to be applied after the Streamlit rerun.
    """

    logger.info(
        "Selecting segment: %s",
        segment,
    )

    selectbox = page.locator(
        '[data-testid="stSelectbox"]'
    ).filter(
        has_text="Segment"
    ).first

    selectbox.wait_for(
        state="visible",
        timeout=PAGE_TIMEOUT_MS,
    )

    combobox = selectbox.locator(
        '[role="combobox"]'
    ).first

    combobox.wait_for(
        state="visible",
        timeout=PAGE_TIMEOUT_MS,
    )

    # Open the actual Streamlit dropdown.
    combobox.click()

    logger.info(
        "Segment dropdown opened."
    )

    # Wait for the dropdown option and select it.
    option = page.get_by_role(
        "option",
        name=segment,
        exact=True,
    )

    option.wait_for(
        state="visible",
        timeout=PAGE_TIMEOUT_MS,
    )

    option.click()

    logger.info(
        "Segment option clicked: %s",
        segment,
    )

    # Selecting a Streamlit widget can trigger a rerun.
    # Wait until the dropdown closes before continuing.
    page.wait_for_timeout(
        1_000
    )

    # Re-locate the component after the Streamlit rerun.
    selectbox = page.locator(
        '[data-testid="stSelectbox"]'
    ).filter(
        has_text="Segment"
    ).first

    selectbox.wait_for(
        state="visible",
        timeout=PAGE_TIMEOUT_MS,
    )

    combobox = selectbox.locator(
        '[role="combobox"]'
    ).first

    combobox.wait_for(
        state="visible",
        timeout=PAGE_TIMEOUT_MS,
    )

    # Streamlit/BaseWeb exposes the selected value through
    # either the combobox text or its descendant input.
    selected_value = ""

    try:

        selected_value = (
            combobox.inner_text()
            .strip()
        )

    except PlaywrightError:

        selected_value = ""

    if segment not in selected_value:

        input_locator = selectbox.locator(
            'input'
        ).first

        if input_locator.count():

            try:

                selected_value = (
                    input_locator.input_value()
                    .strip()
                )

            except PlaywrightError:

                pass

    if segment not in selected_value:

        logger.warning(
            "Could not read the selected Segment value "
            "reliably after selection. Continuing because "
            "the option click completed successfully."
        )

    else:

        logger.info(
            "Segment selection verified successfully: %s",
            segment,
        )

    logger.info(
        "Segment selected: %s",
        segment,
    )


def set_stock_limit(
    page: Page,
    limit_stocks: int | None,
) -> None:
    """
    Configure the Streamlit 'Limit stocks this run' slider
    through Playwright and verify the requested value.
    """

    if limit_stocks is None:

        logger.info(
            "Using application's default stock limit."
        )

        return

    logger.info(
        "Setting stock limit to %s.",
        limit_stocks,
    )

    slider_container = page.locator(
        '[data-testid="stSlider"]'
    ).filter(
        has_text="Limit stocks this run"
    ).first

    slider_container.wait_for(
        state="visible",
        timeout=PAGE_TIMEOUT_MS,
    )

    slider = slider_container.get_by_role(
        "slider"
    ).first

    slider.wait_for(
        state="visible",
        timeout=PAGE_TIMEOUT_MS,
    )

    minimum = slider.get_attribute(
        "min"
    )

    maximum = slider.get_attribute(
        "max"
    )

    if minimum is None or maximum is None:

        raise RuntimeError(
            "Could not determine the minimum/maximum "
            "range for 'Limit stocks this run'."
        )

    minimum_value = int(
        float(minimum)
    )

    maximum_value = int(
        float(maximum)
    )

    if (
        limit_stocks < minimum_value
        or limit_stocks > maximum_value
    ):

        raise ValueError(
            "Requested stock limit is outside the "
            "available slider range. "
            f"Requested={limit_stocks}, "
            f"minimum={minimum_value}, "
            f"maximum={maximum_value}."
        )

    logger.info(
        "Slider range detected: %s to %s.",
        minimum_value,
        maximum_value,
    )

    current_value = int(
        float(
            slider.input_value()
        )
    )

    logger.info(
        "Current stock limit: %s.",
        current_value,
    )

    if current_value == limit_stocks:

        logger.info(
            "Stock limit is already set to %s.",
            limit_stocks,
        )

        return

    slider.focus()

    slider.press(
        "Home"
    )

    page.wait_for_timeout(
        200
    )

    for _ in range(
        limit_stocks - minimum_value
    ):

        slider.press(
            "ArrowRight"
        )

    logger.info(
        "Stock limit adjustment completed "
        "through Playwright keyboard events."
    )

    page.wait_for_timeout(
        1_500
    )

    slider_container = page.locator(
        '[data-testid="stSlider"]'
    ).filter(
        has_text="Limit stocks this run"
    ).first

    slider_container.wait_for(
        state="visible",
        timeout=PAGE_TIMEOUT_MS,
    )

    slider = slider_container.get_by_role(
        "slider"
    ).first

    slider.wait_for(
        state="visible",
        timeout=PAGE_TIMEOUT_MS,
    )

    applied_value = int(
        float(
            slider.input_value()
        )
    )

    if applied_value != limit_stocks:

        raise RuntimeError(
            "Failed to apply requested stock limit. "
            f"Requested={limit_stocks}, "
            f"actual={applied_value}."
        )

    logger.info(
        "Stock limit verified successfully: %s.",
        applied_value,
    )


def click_scan_market(
    page: Page,
) -> None:
    """
    Click the Streamlit Scan market button and verify that
    the application entered an active scanning state.
    """

    logger.info(
        "Starting market scan."
    )

    button = page.get_by_role(
        "button",
        name="Scan market",
        exact=True,
    )

    button.wait_for(
        state="visible",
        timeout=PAGE_TIMEOUT_MS,
    )

    button.scroll_into_view_if_needed()

    button.click(
        timeout=PAGE_TIMEOUT_MS,
    )

    logger.info(
        "Scan market button clicked successfully."
    )

    # Give Streamlit time to process the button event and
    # start the script rerun.
    page.wait_for_timeout(
        1_000,
    )

    try:

        page.wait_for_function(
            """
            () => {
                const text =
                    document.body.innerText || "";

                return (
                    text.includes("Scanning") ||
                    text.includes("running") ||
                    text.includes("Loading") ||
                    text.includes("Please wait")
                );
            }
            """,
            timeout=10_000,
        )

        logger.info(
            "Streamlit scan activity detected."
        )

    except PlaywrightTimeoutError:

        logger.warning(
            "No explicit Streamlit scanning indicator was "
            "detected within 10 seconds. Continuing to "
            "completion monitoring."
        )


def get_backtest_download_control(
    page: Page,
) -> Locator:
    """
    Return the actual Streamlit download control for the
    consolidated Backtest Track Record.

    Do not match the Backtest Track Record section heading.
    """

    return page.locator(
        '[data-testid="stDownloadButton"]'
    ).filter(
        has_text=re.compile(
            r"Download\s+backtest\s+track\s+record",
            re.IGNORECASE,
        )
    ).first


def page_has_scan_result(
    page: Page,
) -> bool:
    """
    Return True only when the actual Streamlit Backtest
    Track Record download control is visible.

    The Backtest Track Record heading alone must never be
    treated as successful scan completion.
    """

    try:

        download_control = (
            get_backtest_download_control(
                page
            )
        )

        return (
            download_control.count()
            > 0
            and download_control.is_visible()
        )

    except PlaywrightError:

        return False


def get_suggested_stocks(
    page: Page,
) -> list[str]:
    """
    Extract stock symbols from the completed scanner results.

    Only stocks displayed in the suggested/signalled
    results section are returned.
    """

    logger.info(
        "Extracting suggested stocks from scan results."
    )

    stock_selectors = [
        "div[data-testid='stDataFrame'] tbody tr",
        "div[data-testid='stTable'] tbody tr",
        "table tbody tr",
    ]

    rows = None

    for selector in stock_selectors:

        try:

            candidate_rows = page.locator(
                selector
            )

            count = candidate_rows.count()

            if count > 0:

                rows = candidate_rows

                logger.info(
                    "Suggested stock result rows found: %s.",
                    count,
                )

                break

        except PlaywrightError:

            continue

    if rows is None:

        raise RuntimeError(
            "Unable to locate suggested stock "
            "result rows in the completed scan."
        )

    suggested_stocks: list[str] = []

    row_count = rows.count()

    for index in range(
        row_count
    ):

        try:

            row = rows.nth(
                index
            )

            cells = row.locator(
                "td"
            )

            cell_count = cells.count()

            if cell_count == 0:

                continue

            first_cell = cells.nth(
                0
            ).inner_text().strip()

            if (
                first_cell
                and first_cell.lower()
                not in {
                    "stock",
                    "symbol",
                    "ticker",
                }
            ):

                suggested_stocks.append(
                    first_cell
                )

        except PlaywrightError:

            continue

    suggested_stocks = list(
        dict.fromkeys(
            suggested_stocks
        )
    )

    if not suggested_stocks:

        raise RuntimeError(
            "The scan completed, but no suggested "
            "stock symbols could be extracted."
        )

    logger.info(
        "Suggested stocks extracted successfully: %s.",
        suggested_stocks,
    )

    return suggested_stocks


def wait_for_scan_completion(
    page: Page,
    *,
    timeout_seconds: int,
) -> None:
    """
    Wait until the Streamlit scan exposes the completed
    Backtest Track Record download control.
    """

    logger.info(
        "Waiting for scan completion. "
        "Maximum timeout: %s seconds.",
        timeout_seconds,
    )

    started_at = time.monotonic()

    deadline = (
        started_at
        + timeout_seconds
    )

    last_progress_log = -30

    while time.monotonic() < deadline:

        try:

            if page_has_scan_result(
                page
            ):

                logger.info(
                    "Scan completed successfully. "
                    "Backtest Track Record download "
                    "control is available."
                )

                return

        except PlaywrightError:

            logger.debug(
                "Unable to inspect scan completion "
                "state during this polling cycle.",
                exc_info=True,
            )

        elapsed = int(
            time.monotonic()
            - started_at
        )

        if (
            elapsed
            - last_progress_log
            >= 30
        ):

            logger.info(
                "Scan still running... %s seconds elapsed.",
                elapsed,
            )

            save_debug_screenshot(
                page,
                f"scan_running_{elapsed:04d}s",
            )

            last_progress_log = elapsed

        time.sleep(
            UI_POLL_INTERVAL_SECONDS
        )

    raise TimeoutError(
        "Market scan did not complete within "
        f"{timeout_seconds} seconds."
    )


def assert_scan_success(
    page: Page,
) -> None:
    """
    Verify that the scan reached a successful terminal state.
    """

    try:

        if page_has_scan_result(
            page
        ):

            logger.info(
                "Scan success verified from "
                "completed result state."
            )

            return

    except PlaywrightError:

        pass

    download_locators = [

        page.get_by_role(
            "button",
            name=re.compile(
                r".*backtest.*track.*record.*",
                re.IGNORECASE,
            ),
        ),

        page.get_by_text(
            re.compile(
                r".*backtest.*track.*record.*",
                re.IGNORECASE,
            ),
        ),

        page.get_by_text(
            re.compile(
                r".*download.*backtest.*",
                re.IGNORECASE,
            ),
        ),
    ]

    for locator in download_locators:

        try:

            if locator.first.is_visible():

                logger.info(
                    "Scan success verified from "
                    "Backtest Track Record control."
                )

                return

        except PlaywrightError:

            continue

    raise RuntimeError(
        "The scan did not reach a verifiable "
        "successful result state."
    )


# =============================================================================
# SIGNALLED STOCK BACKTEST DOWNLOADS
# =============================================================================

def get_signalled_stock_table(
    page: Page,
) -> Locator:
    """
    Return the Streamlit dataframe containing the final
    signalled-stock shortlist.

    This is the application's 'Tonight's Investment Analysis'
    table, which is built from:

        cand = ok[ok["signals_today"]].copy()

    after the applicable event, regime, and sector filters.
    """

    return page.locator(
        '[data-testid="stDataFrame"]'
    ).filter(
        has=page.get_by_text(
            re.compile(
                r"Tonight's Investment Analysis",
                re.IGNORECASE,
            ),
        )
    ).first


def get_signalled_stock_symbols(
    page: Page,
    output_path: Path,
) -> list[str]:
    """
    Download the completed backtest track record and return only
    stocks that have a valid Signals today value.
    """

    logger.info(
        "Downloading completed backtest track record "
        "to identify today's signalled stocks."
    )

    download_backtest_track_record(
        page,
        output_path=output_path,
    )

    if not output_path.exists():

        raise RuntimeError(
            "Backtest track record was not downloaded: "
            f"{output_path}"
        )

    dataframe = pd.read_csv(
        output_path
    )

    if dataframe.empty:

        raise RuntimeError(
            "The downloaded backtest track record "
            "contains no rows."
        )

    logger.info(
        "Backtest track record loaded | "
        "Rows=%s | Columns=%s",
        len(dataframe),
        list(dataframe.columns),
    )

    normalized_columns = {
        str(column)
        .strip()
        .casefold(): column
        for column in dataframe.columns
    }

    signal_today_column = None

    for candidate in (
        "signal today",
        "signals today",
    ):

        if candidate in normalized_columns:

            signal_today_column = (
                normalized_columns[candidate]
            )

            break

    if signal_today_column is None:

        raise RuntimeError(
            "Could not find the 'Signal Today' or "
            "'Signals today' column in the backtest "
            "track record. "
            f"Available columns: {list(dataframe.columns)}"
        )

    symbol_column = None

    for candidate in (
        "stock",
        "symbol",
        "ticker",
    ):

        if candidate in normalized_columns:

            symbol_column = (
                normalized_columns[candidate]
            )

            break

    if symbol_column is None:

        raise RuntimeError(
            "Could not identify the stock symbol column "
            "in the backtest track record. "
            f"Available columns: {list(dataframe.columns)}"
        )

    signal_series = (
        dataframe[signal_today_column]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    invalid_signals = {
        "",
        "nan",
        "none",
        "null",
        "false",
        "0",
        "no",
        "no signal",
        "-",
    }

    signalled_dataframe = dataframe.loc[
        ~signal_series.str.casefold().isin(
            invalid_signals
        )
    ].copy()

    signalled_symbols = (
        signalled_dataframe[symbol_column]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    signalled_symbols = [
        symbol
        for symbol in signalled_symbols
        if symbol
    ]

    signalled_symbols = list(
        dict.fromkeys(
            signalled_symbols
        )
    )

    if not signalled_symbols:

        raise RuntimeError(
            "The scan completed successfully, but no "
            "stocks had a valid 'Signals today' value."
        )

    logger.info(
        "Detected %s Signals today stock(s): %s",
        len(signalled_symbols),
        signalled_symbols,
    )

    return signalled_symbols


def get_backtest_track_record_table(
    page: Page,
) -> Locator:
    """
    Locate the Streamlit Backtest Track Record dataframe.

    The table is identified by its schema, never by the
    currently rendered stock symbols, because st.dataframe
    virtualizes rows.
    """

    logger.info(
        "Locating Backtest Track Record table by schema."
    )

    candidate_selectors = (
        '[data-testid="stDataFrame"]',
        '[role="grid"]',
    )

    required_columns = (
        "Stock",
        "Signals today",
        "Trades",
        "Win%",
        "Target #",
        "Stop #",
        "Expectancy%",
    )

    seen_handles: set[str] = set()

    for selector in candidate_selectors:

        candidates = page.locator(
            selector,
        )

        candidate_count = candidates.count()

        logger.info(
            "Checking %d candidate(s) using selector %s.",
            candidate_count,
            selector,
        )

        for index in range(
            candidate_count,
        ):

            candidate = candidates.nth(
                index,
            )

            try:

                if not candidate.is_visible():

                    continue

                candidate_id = candidate.evaluate(
                    """
                    element => {
                        if (!element.dataset.workflowLocatorId) {
                            element.dataset.workflowLocatorId =
                                Math.random()
                                .toString(36)
                                .slice(2);
                        }

                        return element.dataset.workflowLocatorId;
                    }
                    """
                )

                if candidate_id in seen_handles:

                    continue

                seen_handles.add(
                    candidate_id
                )

                text = (
                    candidate.inner_text(
                        timeout=5_000,
                    )
                    .strip()
                )

            except PlaywrightError:

                continue

            normalized_text = (
                text.casefold()
            )

            matched_columns = sum(
                column.casefold()
                in normalized_text
                for column in required_columns
            )

            logger.info(
                "Table candidate inspected | "
                "Selector=%s | Index=%d | "
                "Schema matches=%d/%d",
                selector,
                index,
                matched_columns,
                len(
                    required_columns
                ),
            )

            if (
                matched_columns
                >= 5
            ):

                logger.info(
                    "Backtest Track Record table identified | "
                    "Selector=%s | Index=%d",
                    selector,
                    index,
                )

                candidate.scroll_into_view_if_needed(
                    timeout=PAGE_TIMEOUT_MS,
                )

                return candidate

    save_debug_screenshot(
        page,
        "backtest_table_schema_not_found",
    )

    raise RuntimeError(
        "Could not identify the Backtest Track Record "
        "table by its schema."
    )


def clear_backtest_track_record_selection(
    page: Page,
    *,
    keep_symbol: str | None = None,
) -> None:
    """
    Best-effort clearing of previously selected rows from
    the Backtest Track Record.

    Failure to locate the table is not fatal because the
    next stock can still be selected directly by symbol.
    """

    try:

        results_table = (
            get_backtest_track_record_table(
                page,
            )
        )

    except RuntimeError:

        logger.warning(
            "Could not reliably locate the Backtest Track "
            "Record for clearing previous selections. "
            "Continuing with direct symbol selection."
        )

        return

    rows = results_table.locator(
        '[role="row"]'
    )

    row_count = rows.count()

    for index in range(row_count):

        row = rows.nth(
            index,
        )

        try:

            text = (
                row.inner_text(
                    timeout=2_000,
                )
                .strip()
            )

        except PlaywrightError:

            continue

        normalized_text = (
            text.casefold()
        )

        if (
            keep_symbol is not None
            and keep_symbol.casefold()
            in normalized_text
        ):

            continue

        checkboxes = row.get_by_role(
            "checkbox"
        )

        if checkboxes.count() == 0:

            continue

        checkbox = checkboxes.first

        try:

            if checkbox.is_checked():

                checkbox.uncheck(
                    timeout=PAGE_TIMEOUT_MS,
                )

                logger.info(
                    "Cleared previous Backtest Track Record "
                    "selection | Row=%s",
                    index,
                )

        except PlaywrightError:

            continue


def get_backtest_scroll_container(
    table: Locator,
) -> Locator:
    """
    Return the internal scrollable container used by the
    virtualized Streamlit dataframe.
    """

    candidates = table.locator(
        """
        [data-testid="stDataFrameResizable"],
        [data-testid="stDataFrame"] > div,
        [role="grid"],
        .ReactVirtualized__Grid,
        .ReactVirtualized__Grid__innerScrollContainer,
        [style*="overflow"]
        """
    )

    candidate_count = candidates.count()

    for index in range(
        candidate_count,
    ):

        candidate = candidates.nth(
            index,
        )

        try:

            is_scrollable = candidate.evaluate(
                """
                element => (
                    element.scrollHeight
                    > element.clientHeight + 5
                )
                """
            )

        except PlaywrightError:

            continue

        if is_scrollable:

            logger.info(
                "Backtest scroll container identified | "
                "Candidate=%d",
                index,
            )

            return candidate

    logger.warning(
        "No dedicated internal scroll container was found. "
        "Using the Backtest Track Record table itself."
    )

    return table



def select_signalled_stock(
    page: Page,
    *,
    symbol: str,
) -> None:
    """
    Select a signalled stock exclusively from the Backtest
    Track Record.

    The dataframe is virtualized, so the function progressively
    scrolls the dataframe until the requested symbol is rendered.
    """

    symbol = str(
        symbol,
    ).strip()

    if not symbol:

        raise ValueError(
            "Stock symbol cannot be empty."
        )

    symbol_normalized = (
        symbol.casefold()
    )

    logger.info(
        "Selecting symbol from Backtest Track Record ONLY | "
        "Stock=%s",
        symbol,
    )

    backtest_table = (
        get_backtest_track_record_table(
            page,
        )
    )

    backtest_table.scroll_into_view_if_needed(
        timeout=PAGE_TIMEOUT_MS,
    )

    scroll_container = (
        get_backtest_scroll_container(
            backtest_table,
        )
    )

    try:

        scroll_container.evaluate(
            """
            element => {
                element.scrollTop = 0;
            }
            """
        )

    except PlaywrightError:

        pass

    page.wait_for_timeout(
        500,
    )

    visited_scroll_positions: set[int] = set()

    for attempt in range(
        100,
    ):

        rows = backtest_table.locator(
            '[role="row"]',
        )

        row_count = rows.count()

        logger.info(
            "Searching rendered Backtest Track Record rows | "
            "Attempt=%d | Rows=%d | Stock=%s",
            attempt + 1,
            row_count,
            symbol,
        )

        for row_index in range(
            row_count,
        ):

            row = rows.nth(
                row_index,
            )

            try:

                if not row.is_visible():

                    continue

                row_text = (
                    row.inner_text(
                        timeout=2_000,
                    )
                    .strip()
                )

            except PlaywrightError:

                continue

            if (
                symbol_normalized
                not in row_text.casefold()
            ):

                continue

            logger.info(
                "Matched Backtest Track Record row | "
                "Rendered row=%d | Stock=%s | Text=%r",
                row_index,
                symbol,
                row_text,
            )

            row.scroll_into_view_if_needed(
                timeout=PAGE_TIMEOUT_MS,
            )

            checkbox = row.get_by_role(
                "checkbox",
            ).first

            try:

                if (
                    checkbox.count() > 0
                    and checkbox.is_visible()
                ):

                    if not checkbox.is_checked():

                        checkbox.check(
                            timeout=PAGE_TIMEOUT_MS,
                        )

                        logger.info(
                            "Selected Backtest Track Record "
                            "checkbox | Stock=%s",
                            symbol,
                        )

                    else:

                        logger.info(
                            "Backtest Track Record checkbox "
                            "already selected | Stock=%s",
                            symbol,
                        )

                else:

                    exact_symbol_cell = (
                        row.get_by_text(
                            re.compile(
                                rf"^\s*{re.escape(symbol)}\s*$",
                                re.IGNORECASE,
                            ),
                        ).first
                    )

                    exact_symbol_cell.click(
                        timeout=PAGE_TIMEOUT_MS,
                        force=True,
                    )

                    logger.info(
                        "Selected Backtest Track Record "
                        "symbol cell | Stock=%s",
                        symbol,
                    )

            except PlaywrightError:

                row.click(
                    timeout=PAGE_TIMEOUT_MS,
                    force=True,
                )

                logger.info(
                    "Selected Backtest Track Record row "
                    "directly | Stock=%s",
                    symbol,
                )

            page.wait_for_timeout(
                1_500,
            )

            save_debug_screenshot(
                page,
                f"stock_selected_from_backtest_{symbol}",
            )

            logger.info(
                "Signalled stock selected successfully | "
                "Stock=%s",
                symbol,
            )

            return

        try:

            scroll_state = (
                scroll_container.evaluate(
                    """
                    element => ({
                        scrollTop: Math.round(
                            element.scrollTop
                        ),
                        clientHeight: Math.round(
                            element.clientHeight
                        ),
                        scrollHeight: Math.round(
                            element.scrollHeight
                        ),
                    })
                    """
                )
            )

        except PlaywrightError:

            break

        current_scroll_top = int(
            scroll_state["scrollTop"]
        )

        client_height = int(
            scroll_state["clientHeight"]
        )

        scroll_height = int(
            scroll_state["scrollHeight"]
        )

        logger.info(
            "Backtest virtual scroll state | "
            "Attempt=%d | Top=%d | Viewport=%d | Height=%d",
            attempt + 1,
            current_scroll_top,
            client_height,
            scroll_height,
        )

        if current_scroll_top in visited_scroll_positions:

            logger.info(
                "Backtest scroll position repeated. "
                "Stopping virtualized row search."
            )

            break

        visited_scroll_positions.add(
            current_scroll_top
        )

        if (
            current_scroll_top
            >= scroll_height - client_height - 5
        ):

            logger.info(
                "Reached end of Backtest Track Record."
            )

            break

        next_scroll_top = min(
            current_scroll_top
            + max(
                200,
                int(
                    client_height * 0.80
                ),
            ),
            max(
                0,
                scroll_height - client_height,
            ),
        )

        try:

            scroll_container.evaluate(
                """
                (element, nextScrollTop) => {
                    element.scrollTop =
                        nextScrollTop;
                }
                """,
                next_scroll_top,
            )

        except PlaywrightError:

            break

        page.wait_for_timeout(
            750,
        )

    save_debug_screenshot(
        page,
        f"backtest_symbol_not_found_{symbol}",
    )

    raise RuntimeError(
        "Could not find stock "
        f"{symbol} inside the virtualized Backtest "
        "Track Record table after scanning all available "
        "rendered rows."
    )



def wait_for_stock_backtest(
    page: Page,
    symbol: str,
    *,
    timeout_seconds: int = 60,
) -> None:
    """
    Wait for the selected stock's individual backtest.

    The page is progressively scrolled to the bottom because
    Streamlit renders the stock-specific full-backtest section
    below the Backtest Track Record.
    """

    logger.info(
        "Waiting for %s individual backtest and scrolling "
        "towards the bottom of the page.",
        symbol,
    )

    deadline = (
        time.monotonic()
        + timeout_seconds
    )

    last_wait_log = -5
    stable_bottom_checks = 0

    while time.monotonic() < deadline:

        try:

            button = (
                find_stock_backtest_download_button(
                    page,
                    symbol,
                )
            )

            if button.is_visible():

                button.scroll_into_view_if_needed(
                    timeout=PAGE_TIMEOUT_MS,
                )

                page.wait_for_timeout(
                    500,
                )

                logger.info(
                    "%s individual full-backtest button "
                    "is ready.",
                    symbol,
                )

                save_debug_screenshot(
                    page,
                    f"stock_backtest_ready_{symbol}",
                )

                return

        except (
            RuntimeError,
            PlaywrightError,
        ):

            pass

        try:

            scroll_state = page.evaluate(
                """
                () => ({
                    y: window.scrollY,
                    viewport: window.innerHeight,
                    height: document.documentElement.scrollHeight,
                })
                """
            )

            current_y = int(
                scroll_state["y"]
            )

            viewport_height = int(
                scroll_state["viewport"]
            )

            page_height = int(
                scroll_state["height"]
            )

            bottom_y = max(
                0,
                page_height
                - viewport_height,
            )

            next_y = min(
                bottom_y,
                current_y
                + max(
                    400,
                    int(
                        viewport_height * 0.80
                    ),
                ),
            )

            if next_y == current_y:

                stable_bottom_checks += 1

            else:

                stable_bottom_checks = 0

                page.evaluate(
                    """
                    nextY => window.scrollTo({
                        top: nextY,
                        behavior: "auto",
                    })
                    """,
                    next_y,
                )

            logger.debug(
                "Page scroll progress | "
                "Current=%d | Next=%d | Bottom=%d | "
                "Stable=%d",
                current_y,
                next_y,
                bottom_y,
                stable_bottom_checks,
            )

        except PlaywrightError:

            pass

        elapsed_seconds = int(
            timeout_seconds
            - max(
                0,
                deadline - time.monotonic(),
            )
        )

        if (
            elapsed_seconds
            - last_wait_log
            >= 5
        ):

            logger.info(
                "Still waiting for %s stock-specific "
                "full-backtest button and scrolling page... "
                "%d/%d seconds",
                symbol,
                elapsed_seconds,
                timeout_seconds,
            )

            last_wait_log = elapsed_seconds

        page.wait_for_timeout(
            1_000,
        )

    save_debug_screenshot(
        page,
        f"stock_backtest_timeout_{symbol}",
    )

    raise PlaywrightTimeoutError(
        "Timed out waiting for the stock-specific full "
        f"backtest download button for {symbol} after "
        f"{timeout_seconds} seconds."
    )



def get_stock_download_path(
    *,
    segment: str,
    symbol: str,
) -> Path:
    """
    Generate a unique file path for one signalled stock's
    full historical backtest.
    """

    DOWNLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    safe_symbol = re.sub(
        r"[^A-Za-z0-9_-]+",
        "_",
        symbol,
    )

    return (
        DOWNLOAD_DIR
        / (
            f"{safe_symbol}_"
            f"{segment}_"
            f"signalled_backtest_"
            f"{timestamp}.csv"
        )
    )


def find_stock_backtest_download_button(
    page: Page,
    symbol: str,
) -> Locator:
    """
    Locate ONLY the exact stock-specific full-backtest
    download button.

    Aggregate Backtest Track Record download controls are
    intentionally excluded.
    """

    symbol = str(
        symbol,
    ).strip()

    exact_button_pattern = re.compile(
        rf"^\s*Download\s+{re.escape(symbol)}\s+"
        r"full\s+backtest\s*$",
        re.IGNORECASE,
    )

    candidates = [
        page.get_by_role(
            "button",
            name=exact_button_pattern,
        ).first,
        page.get_by_text(
            exact_button_pattern,
        ).first,
    ]

    for candidate in candidates:

        try:

            if candidate.count() > 0:

                return candidate

        except PlaywrightError:

            continue

    raise RuntimeError(
        "Could not locate the exact individual "
        f"'Download {symbol} full backtest' control."
    )


def download_stock_backtest(
    page: Page,
    symbol: str,
    output_path: Path,
) -> None:
    """
    Download the full historical backtest for the
    currently selected signalled stock only.
    """

    logger.info(
        "Downloading individual backtest for %s.",
        symbol,
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    download_button = (
        find_stock_backtest_download_button(
            page,
            symbol,
        )
    )

    with page.expect_download(
        timeout=PAGE_TIMEOUT_MS,
    ) as download_info:

        download_button.click(
            timeout=PAGE_TIMEOUT_MS,
        )

    download = download_info.value

    failure = download.failure()

    if failure:

        raise RuntimeError(
            f"{symbol} backtest download failed: "
            f"{failure}"
        )

    download.save_as(
        str(output_path)
    )

    if (
        not output_path.exists()
        or output_path.stat().st_size == 0
    ):

        raise RuntimeError(
            f"{symbol} backtest file is missing or empty."
        )

    logger.info(
        "Individual backtest downloaded successfully | "
        "Stock=%s | File=%s",
        symbol,
        output_path,
    )


def validate_stock_backtest_csv(
    path: Path,
    *,
    expected_symbol: str,
) -> int:
    """
    Validate that a downloaded individual backtest belongs
    to the selected signalled stock.
    """

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:

        reader = csv.DictReader(
            file
        )

        fieldnames = (
            reader.fieldnames
            or []
        )

        if not fieldnames:

            raise ValueError(
                f"{expected_symbol} backtest CSV has no header."
            )

        rows = list(
            reader
        )

    if not rows:

        raise ValueError(
            f"{expected_symbol} backtest CSV contains no trades."
        )

    stock_columns = [
        "ticker",
        "Stock",
        "stock",
        "symbol",
        "Symbol",
    ]

    detected_symbols: set[str] = set()

    for row in rows:

        for column in stock_columns:

            value = (
                row.get(
                    column
                )
                or ""
            ).strip()

            if value:

                normalized = (
                    value
                    .replace(".NS", "")
                    .replace(".BO", "")
                    .upper()
                )

                detected_symbols.add(
                    normalized
                )

                break

    normalized_expected = (
        expected_symbol
        .replace(".NS", "")
        .replace(".BO", "")
        .upper()
    )

    if detected_symbols:

        if detected_symbols != {
            normalized_expected
        }:

            raise ValueError(
                "Downloaded backtest does not belong only "
                f"to {expected_symbol}. Detected: "
                f"{sorted(detected_symbols)}"
            )

    logger.info(
        "%s individual backtest validated successfully. "
        "Rows: %s.",
        expected_symbol,
        len(rows),
    )

    return len(
        rows
    )


# =============================================================================
# DOWNLOAD HANDLING
# =============================================================================

def get_download_path(
    *,
    segment: str,
    suggested_only: bool,
) -> Path:
    """
    Generate a unique local output filename.
    """

    DOWNLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    suffix = (
        "suggested_stocks"
        if suggested_only
        else "all_scanned"
    )

    return (
        DOWNLOAD_DIR
        / (
            f"backtest_{segment}_"
            f"{suffix}_"
            f"{timestamp}.csv"
        )
    )


def download_backtest_track_record(
    page: Page,
    *,
    output_path: Path,
) -> Path:
    """
    Download the application's consolidated Backtest
    Track Record CSV.
    """

    logger.info(
        "Preparing Backtest Track Record download."
    )

    download_control = (
        get_backtest_download_control(
            page
        )
    )

    download_control.wait_for(
        state="visible",
        timeout=PAGE_TIMEOUT_MS,
    )

    download_control.scroll_into_view_if_needed()

    with page.expect_download(
        timeout=PAGE_TIMEOUT_MS,
    ) as download_info:

        download_control.click()

    download = (
        download_info.value
    )

    failure = download.failure()

    if failure:

        raise RuntimeError(
            "Backtest download failed: "
            f"{failure}"
        )

    download.save_as(
        str(output_path)
    )

    if (
        not output_path.exists()
        or output_path.stat().st_size == 0
    ):

        raise RuntimeError(
            "Downloaded backtest file is missing or empty."
        )

    logger.info(
        "Backtest results saved successfully: %s",
        output_path,
    )

    return output_path


# =============================================================================
# CSV VALIDATION
# =============================================================================

def validate_backtest_csv(
    path: Path,
) -> int:
    """
    Validate that the downloaded CSV is structurally usable.
    """

    required_columns = {
        "Stock",
        "Signals today",
        "Rank",
        "Trades",
        "Win%",
        "Expectancy%",
        "Profit factor",
    }

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:

        reader = csv.DictReader(
            file
        )

        fieldnames = set(
            reader.fieldnames
            or []
        )

        missing_columns = (
            required_columns
            - fieldnames
        )

        if missing_columns:

            raise ValueError(
                "Downloaded CSV does not match the expected "
                "backtest schema. Missing columns: "
                f"{sorted(missing_columns)}"
            )

        row_count = sum(
            1
            for _ in reader
        )

    logger.info(
        "Backtest CSV validated successfully. "
        "Rows: %s.",
        row_count,
    )

    return row_count


# =============================================================================
# DEBUG UTILITIES
# =============================================================================

def save_debug_screenshot(
    page: Page,
    name: str,
) -> None:
    """
    Save a screenshot of the actual Playwright browser session.
    """

    debug_directory = (
        PROJECT_DIR
        / "workflow_debug"
    )

    debug_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        debug_directory
        / f"{name}.png"
    )

    try:

        page.screenshot(
            path=str(output_path),
            full_page=True,
        )

        logger.info(
            "Debug screenshot saved: %s",
            output_path,
        )

    except PlaywrightError:

        logger.exception(
            "Failed to save debug screenshot: %s",
            name,
        )

    
# =============================================================================
# MAIN WORKFLOW
# =============================================================================

def run_workflow(
    config: WorkflowConfig,
) -> list[Path]:
    """
    Execute one complete end-to-end scan and download workflow.
    """

    process: subprocess.Popen | None = None

    browser: Browser | None = None

    context: BrowserContext | None = None

    try:

        process = start_streamlit_server(
            config
        )

        wait_for_streamlit_server(
            host=config.host,
            port=config.port,
            timeout_seconds=SERVER_START_TIMEOUT_SECONDS,
        )

        with sync_playwright() as playwright:

            browser = playwright.chromium.launch(
                headless=config.headless,
            )

            context = browser.new_context(
                accept_downloads=True,
                viewport={
                    "width": 1600,
                    "height": 1000,
                },
            )

            page = context.new_page()

            page.set_default_timeout(
                PAGE_TIMEOUT_MS
            )

            url = get_streamlit_url(
                config
            )

            logger.info(
                "Opening scanner: %s",
                url,
            )

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=PAGE_TIMEOUT_MS,
            )

            wait_for_application_ready(
                page
            )

            save_debug_screenshot(
                page,
                "00_application_ready",
            )

            select_segment(
                page,
                config.segment,
            )

            save_debug_screenshot(
                page,
                "01_segment_selected",
            )

            set_stock_limit(
                page,
                config.limit_stocks,
            )

            page.wait_for_timeout(
                1_000
            )

            save_debug_screenshot(
                page,
                "02_limit_selected",
            )

            click_scan_market(
                page
            )

            page.wait_for_timeout(
                2_000
            )

            save_debug_screenshot(
                page,
                "03_scan_clicked",
            )

            wait_for_scan_completion(
                page,
                timeout_seconds=(
                    config.scan_timeout_seconds
                ),
            )

            save_debug_screenshot(
                page,
                "04_scan_completed",
            )

            assert_scan_success(
                page
            )

            manifest_path = get_download_path(
                segment=config.segment,
                suggested_only=False,
            )

            signalled_symbols = (
                get_signalled_stock_symbols(
                    page,
                    output_path=manifest_path,
                )
            )

            if not signalled_symbols:

                raise RuntimeError(
                    "Scan completed, but no signalled stocks "
                    "were found in the scanner results."
                )

            logger.info(
                "Found %s signalled stock(s): %s",
                len(signalled_symbols),
                signalled_symbols,
            )

            # =================================================
            # INDIVIDUAL SIGNALLED-STOCK BACKTEST DOWNLOADS
            #
            # IMPORTANT:
            # This entire section MUST remain inside
            # `with sync_playwright() as playwright:`
            # =================================================
            
            downloaded_paths: list[Path] = []

            for row_index, symbol in enumerate(
                signalled_symbols,
            ):

                try:

                    symbol = str(
                        symbol
                    ).strip()

                    if not symbol:

                        raise ValueError(
                            "Encountered an empty signalled stock symbol."
                        )

                    logger.info(
                        "Processing signalled stock | "
                        "Workflow row=%d | Stock=%s",
                        row_index,
                        symbol,
                    )

                    select_signalled_stock(
                        page=page,
                        symbol=symbol,
                    )

                    wait_for_stock_backtest(
                        page,
                        symbol,
                    )

                    output_path = (
                        get_stock_download_path(
                            segment=config.segment,
                            symbol=symbol,
                        )
                    )

                    download_stock_backtest(
                        page,
                        symbol=symbol,
                        output_path=output_path,
                    )

                    row_count = (
                        validate_stock_backtest_csv(
                            output_path,
                            expected_symbol=symbol,
                        )
                    )

                    logger.info(
                        "Signalled stock completed | "
                        "Workflow row=%d | "
                        "Stock=%s | "
                        "Backtest rows=%s | "
                        "File=%s",
                        row_index,
                        symbol,
                        row_count,
                        output_path,
                    )

                    downloaded_paths.append(
                        output_path
                    )

                except (
                    PlaywrightError,
                    PlaywrightTimeoutError,
                    RuntimeError,
                    ValueError,
                ):

                    logger.exception(
                        "Failed to download individual "
                        "backtest for signalled stock | "
                        "Row=%d | Stock=%s",
                        row_index,
                        symbol,
                    )

                    continue

            # =============================================
            # These blocks are OUTSIDE the for-loop.
            # They are executed only after every signalled
            # stock has been attempted.
            # =============================================

            if not downloaded_paths:

                raise RuntimeError(
                    "The scan completed, but no individual "
                    "signalled-stock backtests could be "
                    "downloaded."
                )

            logger.info(
                "WORKFLOW COMPLETED SUCCESSFULLY | "
                "Segment=%s | "
                "Signalled stocks=%s | "
                "Downloaded backtests=%s",
                config.segment,
                len(signalled_symbols),
                len(downloaded_paths),
            )

            return downloaded_paths

    finally:

        if context is not None:

            try:

                context.close()

            except PlaywrightError:

                pass

        if browser is not None:

            try:

                browser.close()

            except PlaywrightError:

                pass

        if not config.keep_server_running:

            stop_streamlit_server(
                process
            )
            
# =============================================================================
# CLI
# =============================================================================

def parse_arguments() -> WorkflowConfig:
    """
    Parse command-line workflow settings.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Automate the NSE Swing Scanner Streamlit application "
            "and download the consolidated backtest track record."
        )
    )

    parser.add_argument(
        "--segment",
        required=True,
        choices=sorted(
            VALID_SEGMENTS
        ),
        help=(
            "Scanner universe to run."
        ),
    )

    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=(
            "Streamlit host."
        ),
    )

    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=(
            "Streamlit port."
        ),
    )

    parser.add_argument(
        "--headed",
        action="store_true",
        help=(
            "Run Chromium visibly for debugging."
        ),
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_SCAN_TIMEOUT_SECONDS,
        help=(
            "Maximum scan runtime in seconds."
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Optional stock limit for this scan."
        ),
    )

    parser.add_argument(
        "--keep-server",
        action="store_true",
        help=(
            "Do not stop Streamlit after the workflow completes."
        ),
    )

    arguments = parser.parse_args()

    if arguments.timeout <= 0:

        parser.error(
            "--timeout must be greater than zero."
        )

    if (
        arguments.limit is not None
        and arguments.limit <= 0
    ):

        parser.error(
            "--limit must be greater than zero."
        )

    return WorkflowConfig(
        segment=arguments.segment,
        host=arguments.host,
        port=arguments.port,
        headless=(
            not arguments.headed
        ),
        scan_timeout_seconds=(
            arguments.timeout
        ),
        keep_server_running=(
            arguments.keep_server
        ),
        limit_stocks=arguments.limit,
    )


def main() -> None:
    """
    CLI entry point.
    """

    config = parse_arguments()

    logger.info(
        "Starting Swing Scanner workflow."
    )

    logger.info(
        "Configuration: %s",
        config,
    )

    try:

        output_path = run_workflow(
            config
        )

    except KeyboardInterrupt:

        logger.warning(
            "Workflow interrupted by user."
        )

        raise SystemExit(
            130
        )

    except Exception:

        logger.exception(
            "Workflow failed."
        )

        raise SystemExit(
            1
        )

    print()

    print(
        "=" * 80
    )

    print(
        "SWING SCAN WORKFLOW COMPLETED"
    )

    print(
        "=" * 80
    )

    print(
        f"Segment : {config.segment}"
    )

    print(
        f"Output  : {output_path}"
    )

    print(
        "=" * 80
    )


if __name__ == "__main__":
    main()