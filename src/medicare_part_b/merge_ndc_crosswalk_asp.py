# Merge Medicare NDC Crosswalk file with ASP Pricing file.
#
# Use included files or download the latest files from:
#   https://www.cms.gov/medicare/payment/all-fee-service-providers/medicare-part-b-drug-average-sales-price/asp-pricing-files
# Put files in 'data' directory and update ASP_FILE_PATH and CROSSWALK_FILE_PATH below.
#
# Usage: python -m src.medicare_part_b.merge_ndc_crosswalk_asp

import pandas as pd

from src.common.logger_config import logger  # noqa: E402

FILE_ENCODING = "ISO-8859-1"
DATA_ROW_START = 8
DATA_PATH = "src/medicare_part_b/data"
MERGED_FILE_PATH = f"{DATA_PATH}/merged.csv"
ASP_FILE_PATH = (
    f"{DATA_PATH}/section 508 version of January 2024 ASP Pricing File 121223.csv"
)
CROSSWALK_FILE_PATH = f"{DATA_PATH}/section 508 version of January 2024 ASP NDC-HCPCS Crosswalk 122023.csv"
ASP_COLUMNS = [
    "HCPCS Code",
    "Payment Limit",
]
CROSSWALK_COLUMNS = [
    "_2023_CODE",
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


def merge():
    asp_df = pd.read_csv(
        ASP_FILE_PATH,
        encoding=FILE_ENCODING,
        header=DATA_ROW_START,
    )
    asp_df = asp_df[ASP_COLUMNS]

    crosswalk_df = pd.read_csv(
        CROSSWALK_FILE_PATH,
        encoding=FILE_ENCODING,
        header=DATA_ROW_START,
    )

    crosswalk_df = crosswalk_df[CROSSWALK_COLUMNS]
    crosswalk_df_renamed = crosswalk_df.rename(
        columns={
            "_2023_CODE": "HCPCS Code",
            "NDC2": "NDC",
            "Short Description": "Description",
            "PKG SIZE": "Pkg Size",
            "PKG QTY": "Pkg Qty",
            "BILLUNITSPKG": "BUPP",
        }
    )

    # Merge DataFrames on HCPCS Code
    merged_df = pd.merge(crosswalk_df_renamed, asp_df, on="HCPCS Code")

    # Add ASP
    merged_df["ASP"] = calculate_asp(merged_df["Payment Limit"]).round(3)

    # Save the result to a CSV file
    merged_df.to_csv(MERGED_FILE_PATH, index=False)
    logger.info(f"Saved merged data to {MERGED_FILE_PATH}")


if __name__ == "__main__":
    merge()
