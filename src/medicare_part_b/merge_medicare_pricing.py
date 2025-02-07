# Merge Medicare pricing files:
#   - NDC Crosswalk
#   - ASP
#   - Addendum B
#
# Use included files in DATA_PATH directory or download the latest files from:
#   - https://www.cms.gov/medicare/payment/all-fee-service-providers/medicare-part-b-drug-average-sales-price/asp-pricing-files
#   - https://www.cms.gov/medicare/medicare-fee-service-payment/hospitaloutpatientpps/addendum-and-addendum-b-updates/addendum-b
#
# Usage: python -m src.medicare_part_b.merge_medicare_pricing
#        -crosswalk_file <path>
#        -asp_file <path>
#        -addendum_b_file <path>

import argparse
import pandas as pd

from src.common.logger_config import logger

DATA_PATH = "src/medicare_part_b/data"
MERGED_FILE_PATH = f"{DATA_PATH}/medicare-pricing-merged.csv"
FILE_ENCODING = "ISO-8859-1"
ASP_HEADER_ROW = 8  # 0-indexed
CROSSWALK_HEADER_ROW = 8  # 0-indexed
ADDENDUM_B_HEADER_ROW = 4  # 0-indexed
ASP_COLUMNS = [
    "HCPCS Code",
    "Payment Limit",
]
CROSSWALK_COLUMNS = [
    "_2025_CODE",
    "NDC2",
    "Short Description",
    "Drug Name",
    "PKG SIZE",
    "PKG QTY",
    "BILLUNITSPKG",
]
ADDENDUM_B_COLUMNS = [
    "HCPCS Code",
    "SI",
]


def calculate_asp(payment_limit, markup_percentage=0.06):
    """
    Calculate Average Sales Price (ASP) from the payment limit, adjusting for the markup
    percentage, which is 6% by default.
    """
    return payment_limit / (1 + markup_percentage)


def merge(crosswalk_file_path, asp_file_path, addendum_b_file_path):
    crosswalk_df = pd.read_csv(
        crosswalk_file_path,
        encoding=FILE_ENCODING,
        header=CROSSWALK_HEADER_ROW,
        usecols=CROSSWALK_COLUMNS,
    )
    crosswalk_df_renamed = crosswalk_df.rename(
        columns={
            "_2025_CODE": "HCPCS Code",
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
        header=ASP_HEADER_ROW,
        usecols=ASP_COLUMNS,
    )

    addendum_b_df = pd.read_csv(
        addendum_b_file_path,
        encoding=FILE_ENCODING,
        header=ADDENDUM_B_HEADER_ROW,
        usecols=ADDENDUM_B_COLUMNS,
    )

    # Merge crosswalk with ASP DataFrames on HCPCS Code
    merged_df = pd.merge(crosswalk_df_renamed, asp_df, on="HCPCS Code")

    # Add Average Sales Price (ASP) column
    merged_df["ASP"] = calculate_asp(merged_df["Payment Limit"]).round(3)

    # Merge Addendum B DataFrame on HCPCS Code using left join
    merged_df = pd.merge(merged_df, addendum_b_df, on="HCPCS Code", how="left")

    # Save the result to a CSV file
    merged_df.to_csv(MERGED_FILE_PATH, index=False)
    logger.info(f"Saved merged data to {MERGED_FILE_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge Medicare Pricing files.")
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
    parser.add_argument(
        "-addendum_b_file",
        required=True,
        help="Path to the Addendum B file",
    )
    args = parser.parse_args()

    merge(args.crosswalk_file, args.asp_file, args.addendum_b_file)
