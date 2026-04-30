#!/usr/bin/env python3

import csv
import os
import re
import sys
import argparse

# Allow very large CSV fields
csv.field_size_limit(sys.maxsize)

parser = argparse.ArgumentParser(description="Extract sentences from CSV fields.")
parser.add_argument("input", nargs="?", default="data.csv", help="Input CSV file (default: data.csv)")

args = parser.parse_args()

pattern = re.compile(r'[A-ZÆØÅ].*?(?:(?<! [0-9a-zæøå])\.|[!?])')

output = "sentences-" + os.path.basename(args.input)

with open(args.input, newline='', encoding="utf-8") as infile, \
     open(output, "a", encoding="utf-8") as outfile:

    reader = csv.reader(infile)

    for row in reader:
        for field in row:
            for match in pattern.finditer(field):
                sentence = match.group().strip()

                if 10 <= len(sentence) <= 125:
                    outfile.write(sentence + "\n")
