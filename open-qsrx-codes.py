# Imports:
import argparse
import logging
import numpy as np
import pandas as pd
import re

# Check if the filename is valid
def valid_filename(s):
    s = str(s)
    if not s.endswith('.csv'):
        raise argparse.ArgumentTypeError("Filename must end with .csv")
    if not re.match(r'^[\w\-. ]+$', s):
        raise argparse.ArgumentTypeError("Filename contains invalid characters")
    return s

# Uniformly converts NDC values to the 11-digit format
def ndc_eleven_digits(ndc):
    if ndc.find('-') == -1:
        if len(ndc) == 12:
            ndc = ndc[1:]
        ndc = ndc[:5] + '-' + ndc[5:9] + '-' + ndc[9:]
    elif len(ndc) != 13:
        if ndc[5] != '-':
            ndc = '0' + ndc
        elif ndc[9] == '-':
            ndc = ndc[:6] + '0' + ndc[6:]
        else:
            ndc = ndc[:11] + '0' + ndc[11:]
    return ndc

def main(filename, log_level):
    # Set up logging level
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {log_level}')
    logging.basicConfig(format='%(asctime)s %(name)s:%(levelname)s: %(message)s', level=numeric_level)

    # Converting the NDC-inclusive data to pandas DataFrames
    logging.info("Converting the NDC-inclusive data to pandas DataFrames...")
    logging.debug("Retrieving 'package.csv'...")
    try:
        fda_package = pd.read_csv('package.csv')
    except:
        logging.error("'package.csv' not found, ensure it is in the directory and named the same")
        raise
    logging.debug("Done")
    logging.debug("Retrieving 'product.csv'...")
    try: 
        fda_product = pd.read_csv('product.csv')
    except:
        logging.error("'product.csv' not found, ensure it is in the directory and named the same")
    logging.debug("Done")
    logging.debug("Retrieivng the NDC table from rxnorm.db...")
    try:
        rxnorm_rxcui = pd.read_sql_table('NDC', 'sqlite:///rxnorm.db')
    except:
        logging.error("'rxnorm.db' not found, ensure it is in the directory and named the same")
    logging.debug("Done")
    logging.info("Data retrieval successful")

    # Making the datasets uniformly formatted
    logging.info("Making these datasets uniformly formatted...")
    logging.debug("Formatting the RxNorm NDC data...")
    rxnorm_rxcui['NDC'] = rxnorm_rxcui['NDC'].apply(ndc_eleven_digits)
    logging.debug("Done")
    logging.debug("Formatting the FDA data...")
    fda = pd.merge(fda_package, fda_product, on='PRODUCTNDC')
    fda = fda.rename(columns={'NDCPACKAGECODE': 'NDC'})
    fda['NDC'] = fda['NDC'].apply(ndc_eleven_digits)
    fda = fda.drop_duplicates(subset='NDC', keep='first')
    fda['PACKAGEDESCRIPTION'] = fda['PACKAGEDESCRIPTION'].apply(lambda x: x.replace("*", "/"))
    fda['ACTIVE_NUMERATOR_STRENGTH'] = fda['ACTIVE_NUMERATOR_STRENGTH'].fillna(1)
    fda['ACTIVE_INGRED_UNIT'] = fda['ACTIVE_INGRED_UNIT'].fillna("mL/mL")
    logging.debug("Done")
    logging.info("Formatting complete")

    #Unifying the NDC-inclusive data
    logging.info("Unifying the NDC-inclusive data...")
    ndc_data = pd.merge(rxnorm_rxcui, fda, on='NDC', how='right')
    ndc_data = ndc_data.astype(str) 
    logging.info("Merging complete")

# Parse command-line arguments and run main
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="This script generates Open QSRX Codes")
    parser.add_argument('-generate', type=valid_filename, help="The name of the CSV file to generate", required=True)
    parser.add_argument("-level", help="Set logging level", type=str, choices=['debug', 'info', 'error', 'warning', 'critical'], 
                        default='info')
    args = parser.parse_args()
    main(args.generate, args.level)