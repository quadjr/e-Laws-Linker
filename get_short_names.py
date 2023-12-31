#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
import pandas as pd
import io

dfs = pd.read_html(io.StringIO(requests.get('https://elaws.e-gov.go.jp/abb/').text))
assert(len(dfs) == 1)
dfs[0].to_csv('short_law_names.csv', index = False)