"""
CSV Universe Reader
"""

from __future__ import annotations

import pandas as pd


class CSVReader:

    def read(

        self,

        path,

    ):

        return pd.read_csv(path)