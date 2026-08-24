"""
trading_suite.py — UNIFIED NSE swing trading dashboard
======================================================
One Streamlit app, two "layers" (modes) selectable from the sidebar:

  🔍 Daily Scanner   — the after-market scan for NEW setups
                       (was: swing_scanner_app.py)

  📊 Position Monitor — analyze what you ALREADY OWN and get
                       hold / exit / reduce / add / raise-stop advice
                       (was: monitor_app.py)

Both share the same engine, universe loader, news scorer, event fetcher.
Session state is preserved across mode switches so a completed scan doesn't
get lost if you toggle over to the monitor and back.

Run with:  streamlit run trading_suite.py

Standalone apps still work exactly as before:
  streamlit run swing_scanner_app.py
  streamlit run monitor_app.py
"""
import os
import sys
import importlib.util
import streamlit as st

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)


def _load(module_name: str, filename: str):
    """Load a sibling module by file path (avoids side effects of running main())."""
    path = os.path.join(_HERE, filename)
    if not os.path.exists(path):
        st.error(f"Required module missing: {path}")
        st.stop()
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------------
# PAGE CONFIG — MUST be the first Streamlit call in the app.
# ------------------------------------------------------------------
st.set_page_config(page_title="NSE Trading Suite",
                    page_icon="📈",
                    layout="wide",
                    initial_sidebar_state="expanded")

# ------------------------------------------------------------------
# Lazy-import the two apps AFTER set_page_config
# (module load doesn't call their main() since imports guard __main__)
# ------------------------------------------------------------------
scanner   = _load("_ts_scanner",   "swing_scanner_app.py")
monitor   = _load("_ts_monitor",   "monitor_app.py")
wishlist  = _load("_ts_wishlist",  "wishlist_app.py")
validator = _load("_ts_validator", "forward_validate_app.py")

# Sanity check — all four must expose body() (added in the split refactor)
for name, mod in (("swing_scanner_app",    scanner),
                   ("monitor_app",         monitor),
                   ("wishlist_app",        wishlist),
                   ("forward_validate_app", validator)):
    if not hasattr(mod, "body"):
        st.error(f"{name}.py is missing the required `body()` function. "
                 f"Update the file so main() calls body() (see docstring).")
        st.stop()


MODES = {
    "🔍 Daily Scanner":      ("Scan the market for new setups.  "
                               "Runs after market close on a chosen universe."),
    "📊 Position Monitor":   ("Analyze positions you already hold.  "
                               "Reads positions.csv and recommends hold / exit / add."),
    "🔮 Wishlist Tracker":   ("Track scanner predictions vs actual behaviour.  "
                               "Reads wishlist.csv, logs one observation per stock per run."),
    "🧪 Forward Validator":  ("Walk-forward test the algorithm at any historical cutoff.  "
                               "Compares predicted vs realized outcomes; surfaces failure clusters."),
}


def main():
    # -------------- Top-level mode selector (sidebar) --------------
    with st.sidebar:
        st.markdown("## 📈 NSE Trading Suite")
        mode = st.radio(
            "MODE",
            list(MODES.keys()),
            key="_suite_mode",
            help="Switch between finding new setups, managing existing holdings, "
                 "and back-testing the algorithm on past dates.",
        )
        st.caption(MODES[mode])
        st.divider()

    # -------------- Render the selected mode's body --------------
    #  Each body() manages its own sidebar section and main area.
    if mode.startswith("🔍"):
        scanner.body()
    elif mode.startswith("📊"):
        monitor.body()
    elif mode.startswith("🔮"):
        wishlist.body()
    else:
        validator.body()


if __name__ == "__main__":
    main()
