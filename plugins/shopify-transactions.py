"""
Plugin for handling Shopify Payment Transactions Export

This plugin handles one of the two spreadsheets Shopify provides for financial
data (the other being payouts).  This one covers the full details of each
transaction including payment fee, and refunds and the associated fee
adjustment.
"""

import logging
from bank2ynab import B2YBank, CrossversionCsvReader, configparser

class ShopifyTransactionsPlugin(B2YBank):
    def __init__(self, config_object, is_py2):
        super(ShopifyTransactionsPlugin, self).__init__(config_object, is_py2)
        self.name = "Shopify Transactions"

    def read_data(self, file_path):

        # Read in our own config (may as well make use of the confiparser
        # module setup from bank2ynab) and merge it into the class config as a
        # dict.
        config = configparser.SafeConfigParser()
        config.read("shopify.ini")
        self.config = dict(self.config)
        self.config.update(dict(config.items("shopify")))

        delim = self.config["input_delimiter"]
        output_columns = self.config["output_columns"]
        # we know it should have headers, but we respect the setting
        header_rows = self.config["header_rows"]
        output_data = []

        with CrossversionCsvReader(file_path,
                                   self._is_py2,
                                   delimiter=delim) as reader:
            for index, row in enumerate(reader):
                # skip first row if headers
                if index == 0 and header_rows != 0:
                    keys = row
                    continue
                row = {key: row[i] for i, key in enumerate(keys)}
                tmp_gross = {}
                tmp_fee = {}
                order = row["Order"].strip("#")
                date = shopify_date_to_ynab(row["Transaction Date"])
                if row["Type"] == "charge":
                    # Most common event for an ordinary charge:
                    # gross: inflow mount
                    # fee: payment fee amount
                    tmp_gross["Date"]     = date
                    tmp_gross["Memo"]     = "order # %s" % order
                    tmp_gross["Inflow"]   = row["Amount"]
                    tmp_gross["Payee"]    = self.config["payee_you"]
                    tmp_gross["Category"] = self.config["category_income"]
                    tmp_fee["Date"]     = date
                    tmp_fee["Memo"]     = "order # %s" % order
                    tmp_fee["Inflow"]   = ""
                    tmp_fee["Outflow"]  = row["Fee"]
                    tmp_fee["Payee"]    = self.config["payee_fees"]
                    tmp_fee["Category"] = self.config["category_fees"]
                elif row["Type"] == "refund":
                    # Simple refund event:
                    # gross: negative inflow for amount refunded
                    # (fee adjustment is handled in a separate row)
                    tmp_gross["Date"]     = date
                    tmp_gross["Memo"]     = "order # %s refund" % order
                    tmp_gross["Inflow"]   = row["Amount"]
                    tmp_gross["Payee"]    = self.config["payee_refunds"]
                    tmp_gross["Category"] = self.config["category_refunds"]
                elif row["Type"] == "adjustment":
                    # A fee adjustment matching a refund:
                    # fee: reverse of a previous payment fee
                    tmp_fee["Date"]     = date
                    tmp_fee["Memo"]     = "order # %s refund fee adjustment" % order
                    tmp_fee["Inflow"]   = row["Amount"]
                    tmp_fee["Payee"]    = self.config["payee_fees_adjustment"]
                    tmp_fee["Category"] = self.config["category_fees"]
                elif row["Type"] == "chargeback":
                    # Initial chargeback event:
                    # gross: negative inflow for amount reversed for chargeback
                    # fee: additional fee for the chargeback itself
                    tmp_gross["Date"]     = date
                    tmp_gross["Memo"]     = "order # %s chargeback" % order
                    tmp_gross["Inflow"]   = row["Amount"]
                    tmp_gross["Payee"]    = self.config["payee_chargebacks"]
                    tmp_gross["Category"] = self.config["category_chargebacks"]
                    tmp_fee = {}
                    tmp_fee["Date"]     = date
                    tmp_fee["Memo"]     = "order # %s chargeback fee" % order
                    tmp_fee["Inflow"]   = ""
                    tmp_fee["Outflow"]  = row["Fee"]
                    tmp_fee["Payee"]    = self.config["payee_fees_chargebacks"]
                    tmp_fee["Category"] = self.config["category_fees"]
                elif row["Type"] == "chargeback won":
                    # Reverse for previous chargeback:
                    # gross: inflow to return original inflow reversed earlier
                    # fee: return of previous chargeback fee
                    tmp_gross["Date"]     = date
                    tmp_gross["Memo"]     = "order # %s chargeback won" % order
                    tmp_gross["Inflow"]   = row["Amount"]
                    tmp_gross["Payee"]    = self.config["payee_chargebacks_won"]
                    tmp_gross["Category"] = self.config["category_chargebacks"]
                    tmp_fee["Date"]     = date
                    tmp_fee["Memo"]     = "order # %s chargeback won fee refund" % order
                    tmp_fee["Inflow"]   = row["Fee"].lstrip("-")
                    tmp_fee["Outflow"]  = ""
                    tmp_fee["Payee"]    = self.config["payee_fees_adjustment"]
                    tmp_fee["Category"] = self.config["category_fees"]
                else:
                    logging.error("Category \"%s\" not recognized", row["Type"])
                # respect Output Columns option
                out_row_gross = [""] * len(output_columns)
                out_row_fee = [""] * len(output_columns)
                for index, key in enumerate(output_columns):
                    out_row_gross[index] = tmp_gross.get(key, "")
                    out_row_fee[index] = tmp_fee.get(key, "")
                if tmp_gross:
                    output_data.append(out_row_gross)
                if tmp_fee:
                    output_data.append(out_row_fee)
        output_data.insert(0, output_columns)
        return output_data


def build_bank(config, is_py2):
    return ShopifyTransactionsPlugin(config, is_py2)

def shopify_date_to_ynab(text):
    date = text.split()[0]
    yyyy = date.split("-")[0]
    mm = date.split("-")[1]
    dd = date.split("-")[2]
    return "%s/%s/%s" % (mm, dd, yyyy)
