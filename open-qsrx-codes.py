#Imports:
import argparse
import logging
import numpy as np
import pandas as pd
import re

def main(filename):

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="This script generates Open QSRX Codes")
    parser.add_argument('-generate', type=str, help="The name of the CSV file to generate")
    parser.add_argument("-level", help="Set logging level", type=str, choices=['debug', 'info', 'warning', 'critical'])
    args = parser.parse_args()
    main(args.generate)