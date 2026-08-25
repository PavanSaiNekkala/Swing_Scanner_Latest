# Dividend Scanner

A production-ready Python application for scanning upcoming dividend events
for Indian equities.

## Features

- Yahoo Finance integration
- Dividend history
- OHLC window analytics
- Relative return calculations
- Volume analytics
- Dividend scoring engine
- Google News RSS integration
- Excel report generation
- SQLite caching
- Disk caching
- Modular architecture
- Production logging
- Resume/checkpoint support

## Project Structure

```
app/
    analytics/
    cache/
    database/
    exporters/
    models/
    pipeline/
    providers/
    services/
    storage/
    utils/

config/
data/
docs/
tests/
```

## Installation

```bash
python -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt
```

## Run

```bash
python -m main
```

## Output

Generated Excel reports are written to

```
data/output/
```

## License

MIT