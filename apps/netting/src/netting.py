"""
The primary porpose of this 
"""
import asyncio
import os
import shutil
from honeybadgermpc.mpc import TaskProgramRunner
from honeybadgermpc.progs.mixins.dataflow import Share
from honeybadgermpc.field import GF, GFElement
from honeybadgermpc.elliptic_curve import Subgroup
from honeybadgermpc.preprocessing import (
    PreProcessedElements as FakePreProcessedElements,
)
from honeybadgermpc.utils.typecheck import TypeCheck
from honeybadgermpc.progs.mixins.share_arithmetic import (
    MixinConstants,
    BeaverMultiply,
    BeaverMultiplyArrays,
)

config = {
    MixinConstants.MultiplyShareArray: BeaverMultiplyArrays(),
    MixinConstants.MultiplyShare: BeaverMultiply(),
}

from apps.netting.config.config import (
    NUM_CLIENTS,
    NETTING_BASE_DIR,
    rand_share_file_prefix,
    rand_share_file_suffix,
    NUMTX,
    NUM_CLIENTS,
    n,
    t
)
from apps.netting.src.client import Transaction, deser_gf

# Declare the group we are using
gf = GF(Subgroup.BLS12_381)

def write_rand_shares_to_file(ctx):
    
    #Total number of shares required with 100 extra just in case :)
    total_rand_shares = NUMTX + NUM_CLIENTS + 100
    share_array = []
    
    # Step 1: write share to a file
    with open(NETTING_BASE_DIR + "/data/rand_shares/" + rand_share_file_prefix + str(ctx.myid) + rand_share_file_suffix, "w") as f:
        for i in range(0, total_rand_shares):
            r = ctx.preproc.get_rand(ctx)
            ser_share  = str(r.v)[1:len(str(r.v)) -1]
            f.write(ser_share + "\n")
            share_array.append(r)

    return share_array

def check_client_done():

    #read all the line count in all the files
    dir = NETTING_BASE_DIR + "data/masked_inputs/"
    
    count_masked_inputs = 0
    try:
        for file in os.listdir(dir):
            with open(dir + file,"r") as f:
                count_masked_inputs = count_masked_inputs + len(f.readlines())
    except:
        return False
    return count_masked_inputs >= (NUMTX + NUM_CLIENTS)

def read_masked_inputs():
    dir = NETTING_BASE_DIR + "data/masked_inputs/"
    
    count_masked_inputs = 0
    txs = []
    balance = {}
    for file in os.listdir(dir):
        if "mask_tx" in file:
            with open(dir + file,"r") as f:
                for line in f.readlines():
                    txs.append(Transaction(line, encoded = True))
        else:
            with open(dir + file,"r") as f:
                lines = f.readlines()
                assert len(lines) == 1
                client_id , bal = lines[0].split(",")
                bal = deser_gf(bal)
                client_id = int(client_id)
                balance[client_id] = bal

    assert len(txs) == NUMTX and len(balance) == NUM_CLIENTS

    return txs, balance

async def prog(ctx):

    # Step 1: write share to a file
    share_array = write_rand_shares_to_file(ctx)

    print(ctx.myid, "phase 1 complete")
    # Step 2: Now wait for clients to recombine the shares and post the masted value
    while True:
        if check_client_done():
            break
        await asyncio.sleep(5)

    print(ctx.myid, "phase 2 complete")
    # Step 3: After client has posted Get the shares for the inputs from clients.

    masked_txs, masked_bal = read_masked_inputs()
    type(masked_bal)
    # Convert the masks into shares by substracting shares of r
    for masked_tx in masked_txs:
        masked_tx.amount = masked_tx.amount - share_array[masked_tx.id]

    for client_id in masked_bal:
        masked_bal[client_id] = masked_bal[client_id] - share_array[NUMTX + client_id]

    print(ctx.myid, "phase 3 complete")

    """
        Complete the values for 
    """
    # r_final = await r.open()
    # print(ctx.myid, r_final)
    # print(s)

async def run_servers():
    print("here")
    create_data_dir("data/rand_shares/")
    create_data_dir("data/masked_inputs/")
    # Create a test network of 4 nodes (no sockets, just asyncio tasks)
    pp = FakePreProcessedElements()
    # total masks required, add 100 just in case
    total_rand_shares = NUMTX + NUM_CLIENTS + 100
    
    pp.generate_rands(total_rand_shares, n, t)
    program_runner = TaskProgramRunner(n, t, config)
    program_runner.add(prog)
    results = await program_runner.join()
    return results

"""
create data directory for random shares if it does not exist
"""
def create_data_dir(path):
    dir = os.path.join(NETTING_BASE_DIR, path)
    if not os.path.exists(dir):
        os.mkdir(dir)
    else:
        shutil.rmtree(dir)
        os.mkdir(dir)

def main():
    # Run the tutorials

    asyncio.set_event_loop(asyncio.new_event_loop())
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run_servers())
    # loop.run_until_complete(tutorial_2())

if __name__ == "__main__":
    main()
    print("Server generated random numbers successfully")
