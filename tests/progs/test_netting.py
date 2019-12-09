from apps.netting.src import netting, client
from pytest import mark
import subprocess

@mark.asyncio
async def test_end_to_end_server():
    # subprocess.Popen("python3 apps/netting/src/client.py &", shell=True)
    netting.main()

# @mark.asyncio
# async def test_end_to_end_client():
#     subprocess.Popen("python3 apps/netting/src/netting.py &", shell=True)
#     await client.run_clients()
