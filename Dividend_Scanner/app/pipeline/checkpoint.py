"""
Checkpoint Manager

Supports resumable scans.
"""

from __future__ import annotations

from pathlib import Path


class Checkpoint:

    def __init__(

        self,

        path="checkpoint.txt",

    ):

        self.path = Path(path)

    def load(self):

        if self.path.exists():

            return self.path.read_text().strip()

        return None

    def save(

        self,

        symbol,

    ):

        self.path.write_text(symbol)

    def clear(self):

        if self.path.exists():

            self.path.unlink()