"""Cells for the CSV downloads (the rota and the hours report). A
spreadsheet reads a cell that starts with =, +, - or @ as a formula, and a
name or a comment typed on the grid can start with one; prefixing ' makes
Excel show the text as typed instead of running it."""

import csv

TRIGGERS = ("=", "+", "-", "@")


def cell(value):
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(TRIGGERS) else text


class Writer:
    """csv.writer whose cells are made safe on the way out."""

    def __init__(self, response):
        self._out = csv.writer(response)

    def writerow(self, row):
        return self._out.writerow([cell(v) for v in row])
