"""
Workflow

Complete scan pipeline.
"""

from __future__ import annotations

from app.pipeline.checkpoint import Checkpoint
from app.pipeline.csv_reader import CSVReader
from app.pipeline.scanner import Scanner


class Workflow:

    def __init__(

        self,

        input_file,

    ):

        self.reader = CSVReader()

        self.scanner = Scanner()

        self.checkpoint = Checkpoint()

        self.input_file = input_file

    def execute(self):

        dataframe = self.reader.read(

            self.input_file

        )

        results = []

        resume = self.checkpoint.load()

        started = resume is None

        for row in dataframe.itertuples():

            symbol = row.Symbol

            if not started:

                if symbol == resume:

                    started = True

                else:

                    continue

            result = self.scanner.scan(

                symbol

            )

            if result:

                results.append(

                    result

                )

            self.checkpoint.save(

                symbol

            )

        self.checkpoint.clear()

        return results