# Number of transactions
NUMTX = 500

# Number of parties
NUM_CLIENTS = 8

# Number of serves
n = 4

# Number of corruptions
t = 1

# Average payment amount
mu_tx = 10000.00
mu_bal = 10000.00

# Standard deviation
sigma_tx = 100.00
sigma_bal = 100.00

# File name info
tx_file_prefix = "party_"
tx_file_suffix = "_tx_data.csv"

bal_file_prefix = "party_"
bal_file_suffix = "_bal_data.csv"

rand_share_file_prefix = "rand_"
rand_share_file_suffix = "_share.txt"

tx_mask_input_prefix = "mask_tx"
tx_mask_input_suffix = "_input.txt"

bal_mask_input_prefix = "mask_bal"
bal_mask_input_suffix = "_input.txt"

NETTING_BASE_DIR = "/usr/src/HoneyBadgerMPC/apps/netting/"
