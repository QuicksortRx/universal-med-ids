# Imports:
import argparse
import logging
import numpy as np
import pandas as pd
import re

# Checks if the filename is valid
def valid_filename(s):
    s = str(s)
    if not s.endswith('.csv'):
        raise argparse.ArgumentTypeError("Filename must end with .csv")
    if not re.match(r'^[\w\-. ]+$', s):
        raise argparse.ArgumentTypeError("Filename contains invalid characters")
    return s

# Converts NDC values to the 11-digit format
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

# Processes the description to separate out useful information on the unit dosage
def process_description(desc):
        pattern = r"(?:.*\/)?\s*(\d+(\.\d+)?)\s*([^\d\(\)]*)\s*in\s*(\d+)\s*([^\d\(\)]*)"
        match = re.search(pattern, desc)
        if match:
            unit_num, _, unit, form_num, form = match.groups()
            return unit_num.strip(), unit.strip(), form_num.strip(), form.strip()
        else:
            return np.nan, np.nan, np.nan, np.nan

# Assigns each of the separated unit dosage parts from the description to new columns
def unit_dosage(df, column='PACKAGEDESCRIPTION'):
    assert column in df.columns, f"{column} not in DataFrame"
    new_desc = df[column].map(process_description)
    df['DOSE_UNIT_VALUE'], df['DOSE_UNIT'], df['DOSE_QUANTITY'], df['DOSE'] = zip(*new_desc)
    return df

# Adjusts the processed data from the description to only utilize data that can be used to calculate unit dosages
def adjust_units(df):
    viable_units=["mL", "L", "g", "mg"]
    mask = ~df['DOSE_UNIT'].isin(viable_units)
    df.loc[mask, ['DOSE', 'DOSE_QUANTITY']] = df.loc[mask, ['DOSE_UNIT', 'DOSE_UNIT_VALUE']].values
    df.loc[mask, ['DOSE_UNIT', 'DOSE_UNIT_VALUE']] = np.nan
    return df

# Rounds the furthest value to the right that is not zero, but only if it is 9
def round_nine(n):
    result = n
    n = str(n)
    index = n.rfind('9')
    if index > 0:
        to_round = n[: index + 1]
        check_zero = n[index + 1 :]
        if check_zero == '' or check_zero.find('e') != -1 or float(check_zero) == 0:
            rounding_decimal_index = to_round.find('.')
            rounded = float(to_round)
            if rounding_decimal_index == -1:
                rounded /= 10
                rounded = str(round(rounded) * 10) + check_zero
            else:
                rounding_place = (len(to_round) - 1) - rounding_decimal_index
                rounded = str(round(rounded, rounding_place - 1))
            result = float(rounded)
    return result

# Accounts for discrepancies in values due to the number of significant figures taken in measurements
def weight_sig_figs(std_name, n, part):
    v_dict = {
        "BUPIVACAINE HYDROCHLORIDE; EPINEPHRINE BITARTRATE": {0.0091: 0.005},
        "CASPOFUNGIN ACETATE": {5: 50/10.8, 7: 70/10.8},
        "CEFAZOLIN SODIUM": {225: 500/2.2},
        "DEXTROSE MONOHYDRATE; POTASSIUM CHLORIDE; SODIUM CHLORIDE": {2.98: 3, .745: .75, 2.25: 2},
        "GEMCITABINE HYDROCHLORIDE": {38: 2000/52.6, 1: 50/52.6},
        "NEOSTIGMINE METHYLSULFATE": {1.02: 1},
        "POTASSIUM CHLORIDE": {7.46: 7.45}
    }
    an_dict = {"GEMCITABINE HYDROCHLORIDE": {26.3: (50/52.6)*26.3}}
    wc_dict = {
        "CASPOFUNGIN ACETATE": {10: 10.8},
        "DEFEROXAMINE MESYLATE": {21.1: 21.053, 5.3: 500/95},
        "TOBRAMYCIN SULFATE": {50: 30}
    }
    part_dict = {"v": v_dict, "an": an_dict, "wc": wc_dict}
    new_value_dict = part_dict[part]
    if std_name in new_value_dict:
        if n in new_value_dict[std_name]:
            n = new_value_dict[std_name][n]
    return n

# Carries out moles and other substance dependent unit conversions
def mole_converter(std_name, before_unit):
    meq_dict = {"POTASSIUM CHLORIDE": 74.5, "SODIUM CHLORIDE": 58.5}
    iu_dict = {"BLEOMYCIN SULFATE": [1/1000, "[USP'U]"]}
    divider = 1
    if before_unit == "meq" and std_name in meq_dict:
        divider = meq_dict[std_name]
        before_unit = "mg"
    elif before_unit == "[iU]" and std_name in iu_dict:
        divider = iu_dict[std_name][0]
        before_unit = iu_dict[std_name][1]
    return divider, before_unit

# Processes all unit dosage related data to result in a standardized API (active pharmaceutical ingredient) amount
def process_unit(unit, value, unit_compare, unit_num, std_name):
    units = unit.split(';')
    values = [float(x) for x in value.split(';')]
    new_units = []
    new_values = []
    pattern = r"(\d*\.?\d*)?([^/]*)/(\d*\.?\d*)?([^/]*)"
    for u, v in zip(units, values):
        match = re.match(pattern, u.strip())
        if match:
            before_num, before_unit, after_num, after_unit = match.groups()
            v = weight_sig_figs(std_name, v, "v")
            divider = 1
            weight_converter = 1
            if before_unit == "g":
                divider = 1000
                before_unit = "mg"
            elif before_unit == "ug":
                divider = 1/1000
                before_unit = "mg"
            elif before_unit == "meq" or before_unit == "[iU]":
                divider, before_unit = mole_converter(std_name, before_unit)
            if unit_compare == after_unit:
                if float(unit_num) != 0:
                    weight_converter = weight_sig_figs(std_name, float(unit_num), "wc")
                    after_unit = ""
            new_unit = before_unit + "/" + after_unit
            before_num_divider = float(before_num) if before_num else 1
            after_num_divider = (1/weight_sig_figs(std_name, float(after_num), "an")) if after_num else 1
            divider *= before_num_divider * after_num_divider
            new_units.append(new_unit)
            new_values.append(round_nine(round(v * divider * weight_converter, 1)))
        else:
            new_units.append(u)
            new_values.append(v)
    return "; ".join(new_units), "; ".join([str(x) for x in new_values])

# Carries out process_unit
def convert_units(df, strength_col='ACTIVE_NUMERATOR_STRENGTH', unit_col='ACTIVE_INGRED_UNIT', 
                  dose_unit_col='DOSE_UNIT', dose_unit_val_col='DOSE_UNIT_VALUE', 
                  generic_name_col='SUBSTANCENAME'):  
    new_units_values = df.apply(lambda row: process_unit(row[unit_col], row[strength_col], row[dose_unit_col],
                                                         row[dose_unit_val_col], row[generic_name_col]), axis=1)
    df[unit_col], df[strength_col] = zip(*new_units_values)
    return df

# Removes the straggling decimal from when the RXCUI column converted from float to string
def rxcui_std(rxcui):
    index = rxcui.find('.')
    if index > -1:
        rxcui = rxcui[:index]
    return rxcui

# Simplifying dosage forms
def dosage_form(name):
    if name.find("INJECT") != -1:
        name = "INJECTABLE"
    return name

# Simplifying routes
def route(name):
    route_list = ["INTRAMUSCULAR", "EPIDURAL", "INTRAVENOUS", "INFILTRATION"]
    for item in route_list:
        if name.find(item) > -1:
            return item
    return name

# Simplifying the actual dosage forms
def dose_simplified(dose):
    index = dose.find(',')
    if index != -1:
        dose = dose[:index]
    return dose

# Uses the simplifying route to normalize the dosage route
def route_to_dosage(row):
    injection_routes = ['EPIDURAL', 'INFILTRATION','INTRACAVERNOUS', 'INTRADERMAL', 'INTRAMUSCULAR', 'INTRATHECAL',
                        'INTRAVENOUS', 'INTRAVENTRICULAR', 'INTRAVESICAL', 'INTRAVITREAL', 'PARENTERAL', 
                        'PERINEURAL', 'SUBCUTANEOUS']
    drops_routes = {"AURICULAR (OTIC)": "OTIC", "OPHTHALMIC": "OPHTHALMIC", "IRRIGATION": "IRRIGATION"}
    if (row['DOSAGEFORMNAME2'] == "INJECTION" or (row['ROUTENAME2'] in injection_routes) or 
        row['DOSE'] == "INJECTION"):
        return "INJECTABLE"
    elif "INHALATION" in row['ROUTENAME2']:
        return "INHALANT"
    elif row["ROUTENAME2"] in drops_routes:
        return drops_routes[row["ROUTENAME2"]]
    else:
        return row['DOSAGEFORMNAME2']

# Strategically eliminates duplicate NDC rows with different RXCUI
def rxcui_chooser(df, col):
    col_counts = df[col].value_counts().to_dict()
    count_name = col + '_Counts'
    df[count_name] = df[col].apply(lambda x: col_counts[x])
    df = df.sort_values(['NDC', count_name], ascending = [True, False])
    df = df.drop_duplicates(subset = 'NDC', keep = 'first')
    return df

# Helps fix RXCUI ambiguity and fill in missing data
def fix_ambiguity(df, name):
    rxcui_two_counts = df['RXCUI2'].value_counts().to_dict()
    rxcui_two_counts["nan"] = 0
    df['RXCUI2_Counts'] = df['RXCUI2'].apply(lambda x: rxcui_two_counts[x])
    if name != 'SUBSTANCENAME':
        df[name] = df[name].apply(lambda x: x.lower())
    df_unique = df.sort_values('RXCUI2_Counts', ascending=False).drop_duplicates(subset=['Code Dosage', name])
    df = df.drop('RXCUI2', axis=1)
    df = df.drop('RXCUI2_Counts', axis=1)
    df = pd.merge(df, df_unique[['Code Dosage', name, 'RXCUI2', 'RXCUI2_Counts']], on=['Code Dosage', name], 
                  how='left')
    return df

# Ensures end case ambiguous RXCUI with a last digit of 9 are properly adjusted
def rxcui_nine(row):
    if row['RXCUI'][-1] == "9" and (int(row['RXCUI'][:-1]) + 1) != int(row['RXCUI2'][:-1]):
        return row['RXCUI']
    return row['RXCUI2']

# Ensures ambiguous RXCUI within a range of 10 can be accounted for
def rxcui_two(rxcui):
    if rxcui != "nan":
        rxcui = rxcui[:-1]
    return rxcui

# Standardizes the formatting of the 'DFG' column
def dfg_std(dfg):
    if dfg.find(" Product") > -1:
        dfg = dfg[:-8]
    if dfg != "nan":
        dfg = dfg.upper()
    return dfg

# Standardizees the formatting for the 'Dosage Form' column
def dosage_form_std(row):
    df_list = ["Injectable Solution", "Injectable Suspension", "Injection"]
    if row['DF'] in df_list or row['DF'] == "nan":
        return row['DOSE'].title()
    return row['DF']

# Helps specifies the descriptions given by RxNorm further by replacing the attribute found in the 'DF' column
def replace_df(row):
    result = row['Description']
    if result == "nan":
        return "nan"
    elif row['DF'] != row['Dosage Form']:
        result = result.replace(row['DF'], row['Dosage Form'])
    return result

# Enforces that the Dosage Routes are viable classes
def use_dfg(row):
    dfg_list = ['BUCCAL', 'CHEWABLE', 'DENTAL', 'DISINTEGRATING ORAL', 'DRUG IMPLANT', 'GRANULE', 'INHALANT', 
                'INJECTABLE', 'INTRAPERITONEAL', 'INTRATRACHEAL', 'IRRIGATION', 'LOZENGE', 'MEDICATED PAD OR TAPE',
                'MOUTHWASH', 'MUCOSAL', 'NASAL', 'OPHTHALMIC', 'ORAL', 'ORAL CREAM', 'ORAL FILM', 'ORAL FOAM', 
                'ORAL GEL', 'ORAL LIQUID', 'ORAL OINTMENT', 'ORAL PASTE', 'ORAL POWDER', 'ORAL SPRAY', 'OTIC', 
                'PASTE', 'PELLET', 'PILL', 'PYELOCALYCEAL', 'RECTAL', 'SHAMPOO', 'SOAP', 'SUBLINGUAL', 
                'TOOTHPASTE', 'TOPICAL', 'TRANSDERMAL', 'URETHRAL', 'VAGINAL']
    if row['DFG'] != "nan" and row['Dosage Route'] not in dfg_list:
        row['Dosage Route'] = row['DFG']
    return row['Dosage Route']

# Inputs code specifiers to prevent clashing codes due to lack of precision
def use_df(row):
    specifier = ""
    dose_list = ["AMPULE", "SYRINGE"]
    dosage_form_list = ["Auto-Injector"]
    if row['DOSE'] in dose_list:
        specifier = row['DOSE']
    if row['Dosage Form'] in dosage_form_list:
        specifier += row['Dosage Form']
    return row['RXCUI2'] + row['Dosage Route'] + row['ACTIVE_NUMERATOR_STRENGTH'] + specifier

# Standardizes the formatting of the 'API Measure' column
def api_measure_std(unit):
    unit = unit.upper()
    unit = unit.replace("/;", ";")
    if unit[-1] == '/':
        unit = unit[:-1]
    return unit

# Makes descriptions for NDCs not found in RxNorm
def make_desc(row):
    np_name = row['NONPROPRIETARYNAME'].lower()
    num = row['ACTIVE_NUMERATOR_STRENGTH']
    unit = row['API Measure']
    d_f = row['Dosage Form']
    p_name = row['PROPRIETARYNAME'].title()
    if p_name.lower() == np_name:
        p_name = ""
    else:
        p_name = " [" + p_name + "]"
    return np_name + " " + num + " " + unit + " " + str(d_f) + p_name

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
        fda_package = pd.read_csv('data/package.csv')
    except:
        logging.error("'package.csv' not found, ensure it is in the data subdirectory and named the same")
        raise
    logging.debug("Done")
    logging.debug("Retrieving 'product.csv'...")
    try: 
        fda_product = pd.read_csv('data/product.csv')
    except:
        logging.error("'product.csv' not found, ensure it is in the data subdirectory and named the same")
        raise
    logging.debug("Done")
    logging.debug("Retrieving the NDC table from rxnorm.db...")
    try:
        rxnorm_rxcui = pd.read_sql_table('NDC', 'sqlite:///data/rxnorm.db')
    except:
        logging.error("'rxnorm.db' not found, ensure it is in the data subdirectory and named the same")
        raise
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

    # Unifying the NDC-inclusive data
    logging.info("Unifying the NDC-inclusive data...")
    ndc_data = pd.merge(rxnorm_rxcui, fda, on='NDC', how='right')
    ndc_data = ndc_data.astype(str) 
    logging.info("Merging complete")

    # Processing all unit dosage related data
    logging.info("Processing all unit dosage related data...")
    ndc_data = unit_dosage(ndc_data)
    ndc_data = adjust_units(ndc_data)
    ndc_data = convert_units(ndc_data)
    logging.info("Processing complete")

    # Cleaning up the remaining data to be utilizable for creating the codes
    logging.info("Cleaning up the remaining data to be utilizable for creating the codes...")
    ndc_data['RXCUI'] = ndc_data['RXCUI'].apply(rxcui_std)
    ndc_data['DOSAGEFORMNAME2'] = ndc_data['DOSAGEFORMNAME'].apply(dosage_form)
    ndc_data['ROUTENAME2'] = ndc_data['ROUTENAME'].apply(route)
    ndc_data['DOSE'] = ndc_data['DOSE'].apply(dose_simplified)
    ndc_data['DOSAGEFORMNAME2'] = ndc_data.apply(route_to_dosage, axis=1)
    ndc_data = ndc_data.astype(str)
    ndc_data['RXCUI2'] = ndc_data['RXCUI']
    ndc_data['Code Dosage'] = ndc_data['DOSAGEFORMNAME2'] + ndc_data['ACTIVE_NUMERATOR_STRENGTH']
    logging.info("Clean up complete")

    # Handling RXCUI ambiguity
    logging.info("Handling RXCUI ambiguity...")
    ndc_data['New Code'] = ndc_data['RXCUI2'] + ndc_data['Code Dosage']
    ndc_data = ndc_data.drop_duplicates(keep='first')
    ndc_data = rxcui_chooser(ndc_data, 'New Code')
    ndc_data_update = fix_ambiguity(ndc_data, 'PROPRIETARYNAME')
    ndc_data_update = fix_ambiguity(ndc_data_update, 'SUBSTANCENAME')
    ndc_data.reset_index(drop=True, inplace=True)
    ndc_data_update.reset_index(drop=True, inplace=True)
    fix_mask = (ndc_data['RXCUI'].str[-1] == '9') | (ndc_data['RXCUI'] == "nan")
    ndc_data.loc[fix_mask] = ndc_data_update.loc[fix_mask]
    ndc_data['RXCUI2'] = ndc_data.apply(rxcui_nine, axis=1)
    ndc_data['RXCUI2'] = ndc_data['RXCUI2'].apply(rxcui_two)
    ndc_data['New Code'] = ndc_data['RXCUI2'] + ndc_data['Code Dosage']
    logging.info("Handling complete")

    # Querying other data from RxNorm to refine the codes and displayed information
    logging.info("Querying refinenment data from RxNorm...")
    logging.debug("Querying the RXNREL and RXNCONSO tables from RxNorm...")
    try:
        query_d = "SELECT RXCUI1, RXCUI2 FROM RXNREL WHERE SAB = 'RXNORM' AND RELA = 'dose_form_of'"
        rxnrel_d = pd.read_sql_query(query_d, 'sqlite:///data/rxnorm.db')
        rxnrel_d = rxnrel_d.rename(columns={'RXCUI1': 'RXCUI'})
        query_df = "SELECT RXCUI, STR FROM RXNCONSO WHERE SAB = 'RXNORM' AND TTY = 'DF'"
        rxnconso_df = pd.read_sql_query(query_df, 'sqlite:///data/rxnorm.db')
        rxnconso_df = rxnconso_df.rename(columns={'RXCUI': 'RXCUI2', 'STR': 'DF'})
        query_i = "SELECT RXCUI1, RXCUI2 FROM RXNREL WHERE SAB = 'RXNORM' AND RELA = 'inverse_isa'"
        rxnrel_i = pd.read_sql_query(query_i, 'sqlite:///data/rxnorm.db')
        query_dfg = "SELECT RXCUI, STR FROM RXNCONSO WHERE SAB = 'RXNORM' AND TTY = 'DFG'"
        rxnconso_dfg = pd.read_sql_query(query_dfg, 'sqlite:///data/rxnorm.db')
        rxnconso_dfg = rxnconso_dfg.rename(columns={'RXCUI': 'RXCUI2', 'STR': 'DFG'})
        query_t = "SELECT RXCUI1, RXCUI2 FROM RXNREL WHERE SAB = 'RXNORM' AND RELA = 'tradename_of'"
        rxnrel_t = pd.read_sql_query(query_t, 'sqlite:///data/rxnorm.db')
        rxnrel_t = rxnrel_t.rename(columns={'RXCUI1': 'RXCUI'})
        query_sbd = "SELECT RXCUI, STR FROM RXNCONSO WHERE SAB = 'RXNORM' AND TTY = 'SBD'"
        rxnconso_sbd = pd.read_sql_query(query_sbd, 'sqlite:///data/rxnorm.db')
        rxnconso_sbd = rxnconso_sbd.rename(columns={'RXCUI': 'RXCUI2', 'STR': 'Description'})
        query_sbd = "SELECT RXCUI, STR FROM RXNCONSO WHERE SAB = 'RXNORM' AND TTY = 'SBD'"
        rxnconso_sbd = pd.read_sql_query(query_sbd, 'sqlite:///data/rxnorm.db')
        rxnconso_sbd = rxnconso_sbd.rename(columns={'RXCUI': 'RXCUI2', 'STR': 'Description'})
        query_scd = "SELECT RXCUI, STR FROM RXNCONSO WHERE SAB = 'RXNORM' AND TTY = 'SCD'"
        rxnconso_scd = pd.read_sql_query(query_scd, 'sqlite:///rxnorm.db')
        rxnconso_scd = rxnconso_scd.rename(columns={'STR': 'Description'})
    except:
        logging.error("Querying unsuccessful, ensure the full 'rxnorm.db' is still in the data subdirectory")
        raise
    logging.debug("Done")
    logging.info("Querying complete")

    # Merging the refinement data from RxNorm together
    logging.info("Merging the refinement data from RxNorm together...")
    logging.debug("Gather all useful columns...")
    rxnorm_ndc = ndc_data[['NDC', 'RXCUI', 'DOSE']].copy()
    rxnorm_ndc = pd.merge(rxnorm_ndc, rxnrel_d, on='RXCUI', how='left')
    rxnorm_ndc = pd.merge(rxnorm_ndc, rxnconso_df, on='RXCUI2', how='left')
    rxnorm_ndc = rxnorm_ndc.rename(columns={'RXCUI2': 'RXCUI1'})
    rxnorm_ndc = pd.merge(rxnorm_ndc, rxnrel_i, on='RXCUI1', how='left')
    rxnorm_ndc = pd.merge(rxnorm_ndc, rxnconso_dfg, on='RXCUI2', how='left')
    rxnorm_ndc = rxnorm_ndc.astype(str)
    rxnorm_ndc['DFG'] = rxnorm_ndc['DFG'].apply(dfg_std)
    rxnorm_ndc = rxnorm_ndc[['NDC', 'RXCUI', 'DOSE', 'DF', 'DFG']]
    rxnorm_ndc = rxnorm_ndc.drop_duplicates(subset='NDC', keep='first')
    rxnorm_ndc = pd.merge(rxnorm_ndc, rxnrel_t, on='RXCUI', how='left')
    rxnorm_ndc = pd.merge(rxnorm_ndc, rxnconso_sbd, on='RXCUI2', how='left')
    rxnorm_ndc = rxnorm_ndc[['NDC', 'RXCUI', 'DOSE', 'DF', 'DFG', 'Description']]
    rxnorm_ndc = rxnorm_ndc.drop_duplicates(subset='NDC', keep='first')
    logging.debug("Done")
    logging.debug("Retrieving the description for SBD RXCUI...")
    rxnconso_sbd = rxnconso_sbd.rename(columns={'RXCUI2': 'RXCUI'})
    rxnorm_sbd = pd.merge(rxnorm_ndc[['NDC', 'RXCUI', 'DOSE', 'DF', 'DFG']].copy(), rxnconso_sbd, on='RXCUI', how='left')
    rxnorm_sbd = rxnorm_sbd.drop_duplicates(subset='NDC', keep='first')
    rxnorm_ndc.reset_index(drop=True, inplace=True)
    rxnorm_sbd.reset_index(drop=True, inplace=True)
    nan_mask = rxnorm_ndc['Description'].isna()
    rxnorm_ndc.loc[nan_mask] = rxnorm_sbd.loc[nan_mask]
    logging.debug("Done")
    logging.debug("Retrieving the description for true SCD RXCUI...")
    rxnorm_scd = pd.merge(rxnorm_ndc[['NDC', 'RXCUI', 'DOSE', 'DF', 'DFG']].copy(), rxnconso_scd, on='RXCUI', how='left')
    rxnorm_scd = rxnorm_scd.drop_duplicates(subset='NDC', keep='first')
    rxnorm_ndc.reset_index(drop=True, inplace=True)
    rxnorm_scd.reset_index(drop=True, inplace=True)
    nan_mask = rxnorm_ndc['Description'].isna()
    rxnorm_ndc.loc[nan_mask] = rxnorm_scd.loc[nan_mask]
    logging.debug("Done")
    logging.debug("Finalizing formatting...")
    rxnorm_ndc = rxnorm_ndc.astype(str)
    rxnorm_ndc['Dosage Form'] = rxnorm_ndc.apply(dosage_form_std, axis = 1)
    rxnorm_ndc['Description'] = rxnorm_ndc.apply(replace_df, axis = 1)
    rxnorm_ndc = rxnorm_ndc[['NDC', 'DF', 'DFG', 'Description', 'Dosage Form']]
    logging.debug("Done")
    logging.info("Merging complete")

    # Merging the refinement data with the NDC data
    logging.info("Merging the refinement data with the NDC data...")
    ndc_data = pd.merge(ndc_data, rxnorm_ndc, on='NDC', how='left')
    ndc_data['Dosage Route'] = ndc_data['DOSAGEFORMNAME2']
    ndc_data['Dosage Route'] = ndc_data.apply(use_dfg, axis=1)
    ndc_data['New Code'] = ndc_data.apply(use_df, axis=1)
    ndc_data['API Measure'] = ndc_data['ACTIVE_INGRED_UNIT'].apply(api_measure_std)
    ndc_data_desc = ndc_data.copy()
    ndc_data_desc['Description'] = ndc_data_desc.apply(make_desc, axis=1) 
    ndc_data.reset_index(drop=True, inplace=True)
    ndc_data_desc.reset_index(drop=True, inplace=True)
    no_desc_mask = (ndc_data['Description'] == "nan")
    ndc_data.loc[no_desc_mask] = ndc_data_desc.loc[no_desc_mask]
    logging.info("Merging complete")

    # Creating the output CSV
    logging.info("Creating the output CSV")
    qsrx_data = ndc_data[['NDC', 'New Code', 'LABELERNAME', 'Description', 'Dosage Form', 'Dosage Route', 'ACTIVE_NUMERATOR_STRENGTH', 'API Measure', 'APPLICATIONNUMBER', 'SUBSTANCENAME', 'DEASCHEDULE']]
    qsrx_data = qsrx_data.sort_values(by=['Dosage Route','New Code'])
    qsrx_data = qsrx_data.loc(qsrx_data['Dosage Route'] == "INJECTABLE")
    qsrx_data.to_csv(filename)
    logging.info('{filename} has been successfully created')

# Parse command-line arguments and run main
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="This script generates Open QSRX Codes")
    parser.add_argument('-generate', type=valid_filename, help="The name of the CSV file to generate", required=True)
    parser.add_argument("-level", help="Set logging level", type=str, choices=['debug', 'info', 'error', 'warning', 'critical'], 
                        default='info')
    args = parser.parse_args()
    main(args.generate, args.level)