import json
import base64
from pickle import dumps
from honeybadgermpc.protocols.crypto.boldyreva import dealer as thresh_dealer

t = 16
n = 50
k = 10
instances = n  # For dealer
base_port = 7000
command = "python -Om honeybadgermpc.hbavss_batch"

class MPCConfig(object):
    def __init__(self, command, t, k, port, num_triples, n, num_faulty_nodes):
        self.COMMAND = command
        self.T = t
        self.PORT = port
        self.NUM_TRIPLES = num_triples
        self.K = k
        self.N = n
        self.NUM_FAULTY_NODES = num_faulty_nodes

def get_configs():
    instance_configs = [None] * instances
    public_key, private_keys = thresh_dealer(n, t+1, seed=0)
    for my_id in range(instances):
        config = {
            "N": n,
            "t": t,
            "my_id": my_id,
            "peers": [f"localhost:{base_port+i}" for i in range(instances)],
            "reconstruction": {"induce_faults": False},
            "skip_preprocessing": True,
            "extra": {
                "k": k,
                "public_key": base64.b64encode(dumps(public_key)).decode(),
                "private_key": base64.b64encode(dumps(private_keys[my_id])).decode()
            }
        }
        instance_configs[my_id] = (my_id, json.dumps(config, indent=4))

    return instance_configs

# TODO: clean this up
if __name__ == '__main__':
    confs = get_configs()
    for my_id, conf in enumerate(confs):
        with open(f"conf/avss/n{n}-local/local.{my_id}.json","w") as f:
            f.write(conf[1])
