import os
import pygsheets
import pandas as pd
from itertools import groupby
#authorization

# If modifying these scopes, delete the file token.json.
SCOPES = []

# The ID and range of a sample spreadsheet.
SAMPLE_SPREADSHEET_ID = '1IIEpImU9MtWxG7N5s96p4h1ypCYsdtj-'
SAMPLE_RANGE_NAME = 'PRICES!A1:V40'

AUTHORIZED_USER_FILE = os.environ.get("GOOGLE_API_JSON")


# def split_alpha_num(s):
#     for k, g in groupby(s, str.isalpha):
#         yield ''.join(g)


# def _split_range(range_string):
#     if ':' in range_string:
#             start, [split_alpha_num(pair)[-1] for pair in range_string.split(":")]



class GoogleSheets:

    def __init__(self, sheet_key, sheet_name, service_file=None):
        self.gc = pygsheets.authorize(service_file=AUTHORIZED_USER_FILE if not service_file else service_file) 
        self.s = self.gc.open_by_key(sheet_key)
        self.w = self.s.worksheet_by_title(sheet_name)
        
    def get_urls(self, cell_range):
        cell_range = ":".join([cell_range]*2) if ':' not in cell_range else cell_range 
        return [_c.hyperlink for c in self.w.range(cell_range) for _c in c]



if __name__ == '__main__':
    gs = GoogleSheets(sheet_key='1M8FT1qtKr5VgUAk-7IvQdX8Hp2Sn13uZLL3tq2o7YOU', sheet_name='PRICES')
    url1 = gs.get_urls('H3')

    url2 = gs.get_urls('I3:I30')

    print(urls2)