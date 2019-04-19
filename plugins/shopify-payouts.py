"""
Plugin for handling Shopify Payouts Export

This plugin handles one of the two spreadsheets Shopify provides for financial
data (the other being transactions).  This one is essentially just transfers to
another account.
"""

from bank2ynab import B2YBank, CrossversionCsvReader, configparser

class ShopifyPayoutsPlugin(B2YBank):
    def __init__(self, config_object, is_py2):
        super(ShopifyPayoutsPlugin, self).__init__(config_object, is_py2)
        self.name = "Shopify Payouts"

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
                tmp = {}
                tmp["Category"] = ""
                tmp["Memo"] = ""
                tmp["Date"] = shopify_date_to_ynab(row["Payout Date"])
                tmp["Payee"] = "Transfer: " + self.config["payee_payouts"]
                tmp["Outflow"] = row["Total"] # net outbound transfer amount
                # respect Output Columns option
                out_row = [""] * len(output_columns)
                for index, key in enumerate(output_columns):
                    out_row[index] = tmp.get(key, "")
                output_data.append(out_row)
        output_data.insert(0, output_columns)
        return output_data


def build_bank(config, is_py2):
    return ShopifyPayoutsPlugin(config, is_py2)

def shopify_date_to_ynab(text):
    date = text.split()[0]
    yyyy = date.split("-")[0]
    mm = date.split("-")[1]
    dd = date.split("-")[2]
    return "%s/%s/%s" % (mm, dd, yyyy)
