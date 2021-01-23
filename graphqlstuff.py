from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport

# uniswap api
uni_transport = RequestsHTTPTransport(
    url='https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v2',
    verify=True,
    retries=5,
)

client = Client(
    transport=uni_transport
)

# eth block api
eth_block_transport = RequestsHTTPTransport(
    url='https://api.thegraph.com/subgraphs/name/blocklytics/ethereum-blocks',
    verify=True,
    retries=5,
)
eth_block_client = Client(
    transport=eth_block_transport
)

def GetFirstThousandPairs():

    # get 1000 most liquid pairs from client
    query = gql('''
        {
         pairs(first: 1000, orderBy: txCount, orderDirection: desc) {
           id
           token0 {
            id
            symbol
            name
          }
          token1 {
            id
            symbol
            name
          }
         }
        }
    ''')
    list_of_pairs = client.execute(query)
    return list_of_pairs['pairs']



# convert timestamps to blocks
def ConvertTimeStampsToBlocks(timestamps):

    blocks = [None]*(len(timestamps))

    for i in range(0 , len(timestamps)):
        params_name = {
            "timestamp_gt": timestamps[i]
        }

        block = gql("""
        query($timestamp_gt: BigInt! )
        {
            blocks(first: 1, orderBy: timestamp, orderDirection: asc,
            where: {timestamp_gt: $timestamp_gt})
        {
            id
        number
        timestamp
        }
        }""")

        block_data = eth_block_client.execute(block, variable_values=params_name)
        blocks[i] = int(block_data['blocks'][0]['number'])

    return blocks

# Get volume for the blocks contained in 'blocks'
# Return the volume as
# volume = [vol_from_block0_to_block1, vol_from_block1_to_block2, ...]
# where blocks = [block0, block1, ...]
def GetVolumeStatistics(contract, blocks):

    tv_volume = [None]*len(blocks)
    for i in range(0, len(blocks)):
        params = {
            "id": contract,
            "number": blocks[i]
        }
        query = gql("""
            query ($id : ID!, $number : Int!) 
              {
               pair(id: $id, block: {number: $number}){
                   volumeUSD
               }
              }        
        """)

        vol_data = client.execute(query, variable_values=params)
        if(vol_data['pair'] == None):
            return None
        else:
            tv_volume[i] = int(float(vol_data['pair']['volumeUSD'])) # round the fractional stuff

    return tv_volume