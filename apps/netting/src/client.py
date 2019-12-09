"""
Netting Client
"""
from apps.netting.config.config import (
    NUM_CLIENTS,
    NUMTX,
    NETTING_BASE_DIR,
    tx_file_prefix,
    tx_file_suffix,
    bal_file_prefix,
    bal_file_suffix,
    rand_share_file_prefix,
    rand_share_file_suffix,
    tx_mask_input_prefix,
    tx_mask_input_suffix,
    bal_mask_input_prefix,
    bal_mask_input_suffix,
    n,
)
from honeybadgermpc.polynomial import EvalPoint, polynomials_over
from honeybadgermpc.field import GF, GFElement
from honeybadgermpc.elliptic_curve import Subgroup
import logging
import subprocess
import asyncio
import os


# Declare the group we are using
gf = GF(Subgroup.BLS12_381)

class Transaction:

    """
    Initalize the transaction from CSV file line. Currently this is the only
    way we take inputs.
    """

    def __init__(self, csv_string, encoded = False):
            params = csv_string.split(",")
            assert len(params) == 4, "File transaction format incorrect"
            self.id = int(params[0])
            if encoded:
                self.amount = deser_gf(params[3])
            else:
                self.amount = int(float(params[3]) * 100)
            self.sender = int(params[1])
            self.reciever = int(params[2])

"""
Serialize field element
"""
def ser_gf(gf):
    gf = str(gf)
    return gf[1:len(gf)-1]

class MaskedTransaction:

    """
    Initalize the masked transaction from transaction
    """
    def __init__(self, tx, mask):
        self.id = tx.id
        self.amount = tx.amount + mask #masking occurs here
        assert type(self.amount) is GFElement
        self.sender = tx.sender
        self.reciever = tx.reciever

    def __str__(self):
        ser_open = ser_gf(self.amount)
        return f"{self.id},{self.sender},{self.reciever},{ser_open}\n"

def read_balance(id):
    ret = ""
    with open(
        NETTING_BASE_DIR + "data/" + bal_file_prefix + str(id) + bal_file_suffix, "r"
    ) as f:
        for line in f.readlines():
            ret = int(float(line) * 100)
    return ret


def read_txs(id):
    in_tx = {}
    out_tx = {}
    with open(
        NETTING_BASE_DIR + "data/" + tx_file_prefix + str(id) + tx_file_suffix
    ) as f:
        for line in f.readlines():
            tx = Transaction(line)
            if tx.sender == id:
                out_tx[tx.id] = tx
            elif tx.reciever == id:
                in_tx[tx.id] = tx
            else:
                logging.execption(
                    "Incorrect reading of file \
                    either or reicever must be the same as file id"
                )
                raise
    return (in_tx, out_tx)

def count_file_lines(file_path):
    """
    Counts the number of lines in a file as a check for the number of elements 
    processed till now
    """
    try:
        with open(file_path) as f:
            lines = len(f.readlines())
            return lines
    except:
        return 0
"""
Deserailize share
"""
def deser_gf(share):

    gf_elem = GFElement(int(share), gf)
    return gf_elem

class Client:
    def __init__(self, id):
        self.id = id
        self.balance = read_balance(id)
        self.out_tx, self.in_tx = read_txs(id)

    """
    Collecting client inputs. 
    Clients submit input to the servers through an input masking technique [COPS15]. 
    The servers start with a secret sharing of a random mask [r]. 
    A client retrieves shares of this mask from the servers and reconstructs r, 
    and then publishes their masked message (m+r). 
    The servers obtain their share of the input as [m] := (m+r)-[r].

    This function repeated pools to see if there are suffient masks available 
    from the server
    """
    async def wait_for_input_masks(self):

        # Check all the files whether they have suffient masks
        num_required_masks = NUM_CLIENTS + NUMTX
        while True:
            masks_avail = True

            # Check whether all servers have submitted random shares
            for i in range(0, n):
                path = NETTING_BASE_DIR + "data/rand_shares/" + rand_share_file_prefix + str(i) + rand_share_file_suffix
                num_masks = count_file_lines(path)
                masks_avail = masks_avail and (num_masks >= num_required_masks)
                # print(masks_avail)

            if masks_avail:
                break
            await asyncio.sleep(5)

    """
    Step 2 of Phase 1: Read all random shares posted by the server
    """
    async def read_rand_shares(self):
        
        gather_ser_shares = {}
        for id in range(0, n):
            with open(NETTING_BASE_DIR + "data/rand_shares/" + rand_share_file_prefix + str(id) + rand_share_file_suffix, "r") as f:
                tx_id = 0
                for share in f.readlines():
                    # Check whether this client is either the sender or reciever of this tx_id.
                    if tx_id in self.out_tx:
                        if tx_id in gather_ser_shares:
                            gather_ser_shares[tx_id].append(share)
                        else:
                            gather_ser_shares[tx_id] = []
                            gather_ser_shares[tx_id].append(share)

                    # Get one more mask for hidhing balance values
                    # after hiding all transactions
                    if tx_id == self.id + NUMTX:
                        if tx_id in gather_ser_shares:
                            gather_ser_shares[tx_id].append(share)
                        else:
                            gather_ser_shares[tx_id] = []
                            gather_ser_shares[tx_id].append(share)
                    tx_id = tx_id + 1

        for ser_shares in gather_ser_shares:
            # print(len(gather_ser_shares[ser_shares]), ser_shares)
            assert len(gather_ser_shares[ser_shares]) == n
        return gather_ser_shares
    
    """
    This takes in input all the combined shares in serialized form and computes 
    the secret and stores it in a file.

    This function is reposible for collecting and reconstructing the `r` part of 
    the input. For simplicity, we hae file communication as a way for reliable 
    broadcast. In an actual application, something like a blockchain or other 
    reliable broadcast primitives should be used. 
    """
    def recombine_shares(self, ser_batch_shares):

        poly = polynomials_over(gf)
        eval_point = EvalPoint(gf, n, use_omega_powers=False)
        masks = []        
        for ser_shares_iter in ser_batch_shares:
            #container for collecting deser shares
            shares = []
            # print("ser_shares ", ser_shares)
            for i, share in enumerate(ser_batch_shares[ser_shares_iter]):
                
                elem = deser_gf(share)
                shares.append(elem)

            shares = [(eval_point(i), share) for i, share in enumerate(shares)]
            # print(shares)
            masks.append(poly.interpolate_at(shares, 0))

        return masks

    def mask_inputs(self, masks):
        mask_iter = 0
        masked_inputs = []
        for tx in self.out_tx:
            masked_inputs.append(MaskedTransaction(self.out_tx[tx], masks[mask_iter]))
            mask_iter = mask_iter + 1

        masked_bal = masks[mask_iter] + self.balance 
        return masked_inputs, masked_bal

    """
    write the masked values onto a file with tx_id
    """
    def write_tx_masked_inputs(self, masked_inputs):

        with open(NETTING_BASE_DIR + "data/masked_inputs/" + tx_mask_input_prefix + str(self.id) + tx_mask_input_suffix, "w") as f:
            for tx in masked_inputs:
                f.write(str(tx))
        return

    """
    write the masked balance into a file
    """
    def write_bal_masked_input(self, bal_mask):

        with open(NETTING_BASE_DIR + "data/masked_inputs/" + bal_mask_input_prefix + str(self.id) + bal_mask_input_suffix
            , "w") as f:
            f.write(str(self.id) + "," + ser_gf(bal_mask))
        return
"""
create data directory for random shares if it does not exist
"""
def create_data_dir():
    dir = os.path.join(NETTING_BASE_DIR, "data/masked_inputs/")
    if not os.path.exists(dir):
        os.mkdir(dir)


def init_clients():
    clients = []
    for i in range(0, NUM_CLIENTS):
        clients.append(Client(i))
    return clients

async def run_clients(clients):
    create_data_dir()
    clients = init_clients()

    for cli in clients:
        await cli.wait_for_input_masks()
        ser_batch_shares = await cli.read_rand_shares()
        print(cli.id, "done reading shares")
        masks = cli.recombine_shares(ser_batch_shares)
        masked_tx_inputs, masked_bal = cli.mask_inputs(masks)
        print(cli.id, "done masking inputs")
        cli.write_tx_masked_inputs(masked_tx_inputs)
        cli.write_bal_masked_input(masked_bal)

def main():
    asyncio.set_event_loop(asyncio.new_event_loop())
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run_clients(clients))

if __name__ == "__main__":
    main()
