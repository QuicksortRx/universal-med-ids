# Merge Medicare NDC Crosswalk file with ASP Pricing file.
#
# Use included files in DATA_PATH directory or download the latest files from:
#  https://www.cms.gov/medicare/payment/all-fee-service-providers/medicare-part-b-drug-average-sales-price/asp-pricing-files
#
# Usage: python -m src.medicare_part_b.merge_ndc_crosswalk_asp
#        -crosswalk_file <path>
#        -asp_file <path>

import argparse
import pandas as pd

from src.common.logger_config import logger

FILE_ENCODING = "ISO-8859-1"
HEADER_ROW = 8  # 0-indexed
DATA_PATH = "src/medicare_part_b/data"
MERGED_FILE_PATH = f"{DATA_PATH}/merged.csv"
ASP_COLUMNS = [
    "HCPCS Code",
    "Payment Limit",
]
CROSSWALK_COLUMNS = [
    "_2024_CODE",
    "NDC2",
    "Short Description",
    "Drug Name",
    "PKG SIZE",
    "PKG QTY",
    "BILLUNITSPKG",
]


def calculate_asp(payment_limit, markup_percentage=0.06):
    """
    Calculate Average Sales Price (ASP) from the payment limit, adjusting for the markup
    percentage, which is 6% by default.
    """
    return payment_limit / (1 + markup_percentage)


def merge(crosswalk_file_path, asp_file_path):
    crosswalk_df = pd.read_csv(
        crosswalk_file_path,
        encoding=FILE_ENCODING,
        header=HEADER_ROW,
    )
    crosswalk_df = crosswalk_df[CROSSWALK_COLUMNS]
    crosswalk_df_renamed = crosswalk_df.rename(
        columns={
            "_2024_CODE": "HCPCS Code",
            "NDC2": "NDC",
            "Short Description": "Description",
            "PKG SIZE": "Pkg Size",
            "PKG QTY": "Pkg Qty",
            "BILLUNITSPKG": "BUPP",
        }
    )

    asp_df = pd.read_csv(
        asp_file_path,
        encoding=FILE_ENCODING,
        header=HEADER_ROW,
    )
    asp_df = asp_df[ASP_COLUMNS]

    # Merge DataFrames on HCPCS Code
    merged_df = pd.merge(crosswalk_df_renamed, asp_df, on="HCPCS Code")

    # Add Average Sales Price (ASP) column
    merged_df["ASP"] = calculate_asp(merged_df["Payment Limit"]).round(3)

    # Save the result to a CSV file
    merged_df.to_csv(MERGED_FILE_PATH, index=False)
    logger.info(f"Saved merged data to {MERGED_FILE_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Merge Medicare NDC Crosswalk file with ASP Pricing file."
    )
    parser.add_argument(
        "-crosswalk_file",
        required=True,
        help="Path to the NDC-HCPCS Crosswalk file",
    )
    parser.add_argument(
        "-asp_file",
        required=True,
        help="Path to the ASP Pricing file",
    )
    args = parser.parse_args()

    merge(args.crosswalk_file, args.asp_file)
