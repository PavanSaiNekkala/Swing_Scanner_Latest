# NEWS Daily Report

A production-ready Python application that scans the NSE universe, downloads daily OHLCV data from Yahoo Finance, calculates 1-day returns, ranks the top gainers and losers, fetches recent news, and generates a formatted Excel report.

---

## Features

- Load NSE symbols from CSV
- Download daily OHLCV data using Yahoo Finance
- Calculate 1-Day Return %
- Identify Top 20 Gainers
- Identify Top 20 Losers
- Fetch latest news (past 7 days)
- Export formatted Excel report
- Logging
- Retry mechanism
- Unit Tests
- Modular architecture

---

## Project Structure

```
NSE_Daily_Report/
│
├── config.py
├── main.py
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── README.md
│
├── data/
│   ├── nse_universe.csv
│   ├── cache/
│   └── archive/
│
├── logs/
│
├── output/
│   ├── excel/
│   └── reports/
│
├── modules/
│   ├── constants.py
│   ├── exceptions.py
│   ├── loader.py
│   ├── logger.py
│   ├── market_data.py
│   ├── news.py
│   ├── ranking.py
│   ├── retry.py
│   ├── returns.py
│   ├── types.py
│   ├── utils.py
│   ├── validators.py
│   └── excel_writer.py
│
└── tests/
```

---

## Installation

Clone the repository.

```bash
git clone https://github.com/<your-username>/NSE_Daily_Report.git

cd NSE_Daily_Report
```

Create a virtual environment.

```bash
python -m venv .venv
```

Activate it.

### Linux/macOS

```bash
source .venv/bin/activate
```

### Windows

```powershell
.venv\Scripts\activate
```

Install dependencies.

```bash
pip install -r requirements.txt
```

Install development dependencies.

```bash
pip install -r requirements-dev.txt
```

---

## Input

Place your NSE universe CSV here:

```
data/nse_universe.csv
```

Example:

| Symbol |
|---------|
| RELIANCE |
| INFY |
| TCS |
| HDFCBANK |

---

## Running

```bash
python main.py
```

or

```bash
make run
```

---

## Output

Generated Excel report:

```
output/excel/
```

Workbook contains:

- Gainers
- Losers

Each sheet includes:

- Rank
- Symbol
- Company
- Open
- High
- Low
- Close
- Previous Close
- Return %
- Top Headline
- News 1
- News 2
- News 3
- News 4
- News 5

---

## Running Tests

```bash
pytest
```

Coverage

```bash
pytest --cov=modules
```

---

## Code Quality

Lint

```bash
ruff check .
```

Formatting

```bash
black .
```

Type Checking

```bash
mypy .
```

---

## Workflow

```
Load CSV
      │
      ▼
Fetch OHLCV
      │
      ▼
Calculate Returns
      │
      ▼
Rank Stocks
      │
      ▼
Fetch News
      │
      ▼
Generate Excel
```

---

## Technologies

- Python 3.11+
- pandas
- yfinance
- openpyxl
- pytest
- numpy

---

## License

MIT License
