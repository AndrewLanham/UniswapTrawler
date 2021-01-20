import matplotlib.pyplot as plt
import numpy as np
import time
import datetime

from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport


#os.environ["PROVIDER"] = "https://mainnet.infura.io/v3/ac6c8b97894749d09f1c78f9577b56d9" # Go to Infura and copy paste "Endpoints"


def GetFirstThousandPairs(client):

    # get 1000 most liquid pairs from client
    query = gql('''
        {
         pairs(first: 1000, orderBy: txCount, orderDirection: desc) {
           id
         }
        }
    ''')
    list_of_pairs = client.execute(query)


    return list_of_pairs

# given a timestamp, generate the set of timestamps going back in time in 24hr intervals
# for num_days days. timestamps are ordered from past to future
# ordering is:
#   [now - 24h*num_days , ... , now - 24h, now]
# so length is num_days+1.
def Return24hrTimestamps(init_timestamp, num_days):

    timestamps = [None]*(num_days + 1)

    for i in range(0, num_days + 1):
        timestamps[num_days - i] = init_timestamp - (24*60*60)*(i)

    return timestamps

# convert timestamps to blocks
def ConvertTimeStampsToBlocks(timestamps):

    blocks = [None]*(len(timestamps))

    # eth block api
    sample_transport_ETH = RequestsHTTPTransport(
        url='https://api.thegraph.com/subgraphs/name/blocklytics/ethereum-blocks',
        verify=True,
        retries=5,
    )
    client_ETH = Client(
        transport=sample_transport_ETH
    )

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

        block_data = client_ETH.execute(block, variable_values=params_name)
        blocks[i] = int(block_data['blocks'][0]['number'])

    return blocks

# Get volume for the blocks contained in 'blocks'
# Return the volume as
# volume = [vol_from_block0_to_block1, vol_from_block1_to_block2, ...]
# where blocks = [block0, block1, ...]
def GetVolumeStatistics(contract, blocks, client):

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

# Calculate Vol From TotalVolume
def CalculateVolFromTotalVol(total_vol):

    dv_vol = [None]*(len(total_vol) - 1) # one shorter since we're taking differences

    for i in range(0, len(dv_vol)):
        dv_vol[i] = total_vol[i+1] - total_vol[i]

    return dv_vol

def QueryNameData(contract, client):
    params_name = {
        "id": contract
    }
    name = gql("""
        query ($id : ID!) 
          {
           pair(id: $id){
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
    """)
    name_data = client.execute(name, variable_values=params_name)

    return name_data

def main():

    LOOKBACK_PERIOD = 10 # days

    # uniswap api
    sample_transport = RequestsHTTPTransport(
        url='https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v2',
        verify=True,
        retries=5,
    )
    client = Client(
        transport=sample_transport
    )

    pairs = GetFirstThousandPairs(client)
    #print(pairs)

    contracts = [None]*1000


    # get time now
    # calculate times going back every 24hrs for 30 days
    #
    time_now = int(time.time()) - 300 # int truncates ms, which aren't important for us. Also subtract a few minutes for blocks to be updated
    # get date 30 days before this moment.
    timestamps = Return24hrTimestamps(time_now, LOOKBACK_PERIOD)
    blocks = ConvertTimeStampsToBlocks(timestamps)

    text = input("Press 1 to find coins with Max Volume in past 30 days, Press 2 for more speculative large deviation analysis. 3 for variation on 2")  # Python 3

    useToday = False

    if(text == '1'):
        for i in range(650, 1000):

            if (i % 50 == 0):
                print('Got through %d so far' % i)

            contracts[i] = pairs['pairs'][i]['id']

            # Get name data for convenience
            name_data = QueryNameData(contracts[i], client)

            # get 10-30 days worth of volume statistics for a given currency
            tv_data = GetVolumeStatistics(contracts[i], blocks, client)
            len_desired = LOOKBACK_PERIOD

            if((tv_data == None) or (len(tv_data) != LOOKBACK_PERIOD+1)):
                print('Contract %s full historical data not available. Examine it manually.' % contracts[i])
                time.sleep(0.1)
            else:
                vol = CalculateVolFromTotalVol(tv_data)

                print('Examining Volume for Pair:' + name_data['pair']['token0']['symbol'] + '/' + name_data['pair']['token1']['symbol'])
                print('Contract: %s.' % contracts[i])
                if(np.argmax(vol) == len_desired - 1 and (np.max(vol) < 2.5*float(np.max(vol[0:len_desired-2])))): # if most recent period is max, take a closer look:
                    print('24hr volume is most in 30 day period for contract %s. Plotting:' % contracts[i])

                    plt.bar(np.arange(0, len_desired), vol)
                    plt.title(name_data['pair']['token0']['symbol']+'/'+name_data['pair']['token1']['symbol'])
                    plt.show()
                    plt.clf()
                time.sleep(0.1) # so i don't get DDOS warning (idk how fast i can poll yet)

    elif(text == '2'): # large deviation stuff
        for i in range(0, 1000):

            if (i % 50 == 0):
                print('Got through %d so far' % i)

            contracts[i] = pairs['pairs'][i]['id']


            # Get name data for convenience
            name_data = QueryNameData(contracts[i], client)

            # get 10-30 days worth of volume statistics for a given currency
            tv_data = GetVolumeStatistics(contracts[i], blocks, client)
            len_desired = LOOKBACK_PERIOD

            if((tv_data == None) or (len(tv_data) != LOOKBACK_PERIOD+1)):
                print('Contract %s full historical data not available. Examine it manually.' % contracts[i])
                time.sleep(0.1)
            else:
                vol = CalculateVolFromTotalVol(tv_data)
                cheby_thresh = 0.4

                print('Examining volume for contract %s.' % contracts[i])
                print('Pair:' + name_data['pair']['token0']['symbol'] + '/' + name_data['pair']['token1']['symbol'])

                vol_mean = np.mean(vol[0:len_desired-3])
                vol_std = np.std(vol[0:len_desired-3]) # leave last two elements for examination

                yesterdays_vol_dev = vol[len_desired - 2] - vol_mean
                todays_vol_dev = vol[len_desired - 1] - vol_mean

                k_cheby_yesterday = np.abs(yesterdays_vol_dev)/vol_std
                p_cheby_yesterday = 1/(k_cheby_yesterday)**2

                k_cheby_today = np.abs(todays_vol_dev) / vol_std
                p_cheby_today = 1 / (k_cheby_today) ** 2

                if(p_cheby_yesterday < cheby_thresh):
                    if(yesterdays_vol_dev < 0):
                        print('Yesterday, volume was anomalously low for this coin. Ignoring...')
                    else:
                        print('Yesterday, volume was anomalously high for this coin. Checking todays volume...')

                        if(p_cheby_today < cheby_thresh and todays_vol_dev > 0):
                            print('Todays volume is also anomalous. Plotting...')
                            plt.bar(np.arange(0, len_desired), vol)
                            plt.show()
                            plt.clf()
                        else:
                            print('Todays volume is not anomalous, likely pumped already, ignoring...')

                if(p_cheby_today < cheby_thresh and p_cheby_yesterday >= cheby_thresh): # plot all anomalous vols that were not caputred above

                    if(todays_vol_dev < 0):
                        print('Today, volume was anomalously low for this coin. Ignoring...')
                    else:
                        print('Today, volume was anomalously high for this coin. Plotting volume chart')
                        plt.bar(np.arange(0, len_desired), vol)
                        plt.show()
                        plt.clf()

                time.sleep(0.1) # so i don't get DDOS warning (idk how fast i can poll yet)

    elif(text == '3'): # modified to filter events where today's vol is lower than yesterdays
        for i in range(0, 1000):

            if (i % 50 == 0):
                print('Got through %d so far' % i)

            contracts[i] = pairs['pairs'][i]['id']

            # Get name data for convenience
            name_data = QueryNameData(contracts[i], client)

            # get 10-30 days worth of volume statistics for a given currency
            tv_data = GetVolumeStatistics(contracts[i], blocks, client)
            len_desired = LOOKBACK_PERIOD

            if((tv_data == None) or (len(tv_data) != LOOKBACK_PERIOD+1)):
                print('Contract %s full historical data not available. Examine it manually.' % contracts[i])
                time.sleep(0.1)
            else:
                vol = CalculateVolFromTotalVol(tv_data)
                cheby_thresh = 0.5

                print('Examining volume for contract %s.' % contracts[i])
                print('Pair:' + name_data['pair']['token0']['symbol'] + '/' + name_data['pair']['token1']['symbol'])

                vol_mean = np.mean(vol[0:len_desired-3])
                vol_std = np.std(vol[0:len_desired-3]) # leave last two elements for examination

                yesterdays_vol_dev = vol[len_desired - 2] - vol_mean
                todays_vol_dev = vol[len_desired - 1] - vol_mean

                k_cheby_yesterday = np.abs(yesterdays_vol_dev)/vol_std
                p_cheby_yesterday = 1/(k_cheby_yesterday)**2

                k_cheby_today = np.abs(todays_vol_dev) / vol_std
                p_cheby_today = 1 / (k_cheby_today) ** 2

                if(p_cheby_yesterday < cheby_thresh):
                    if(yesterdays_vol_dev < 0):
                        print('Yesterday, volume was anomalously low for this coin. Ignoring...')
                    else:
                        print('Yesterday, volume was anomalously high for this coin. Checking todays volume...')

                        if(p_cheby_today < cheby_thresh and todays_vol_dev > 0):
                            if(todays_vol_dev < yesterdays_vol_dev):
                                print('Todays volume is also anomalous. Probably too late tho. Ignore.')
                            elif(p_cheby_today < cheby_thresh and todays_vol_dev > 0 and todays_vol_dev > yesterdays_vol_dev):
                                print('Today, volume was anomalously high too and maybe a chance for something.')
                                plt.bar(np.arange(0, len_desired), vol)
                                plt.show()
                                plt.clf()
                            else:
                                print('Today, volume was anomalously high too but probably too late.')
                                #plt.bar(np.arange(0, len_desired), vol)
                                #plt.show()
                                #plt.clf()

                        else:
                            print('Todays volume is not anomalous, likely pumped already, ignoring...')

                if(p_cheby_today < cheby_thresh and p_cheby_yesterday >= cheby_thresh): # plot all anomalous vols that were not caputred above

                    if(todays_vol_dev < 0):
                        print('Today, volume was anomalously low for this coin. Ignoring...')
                    else:
                        print('Today, volume was anomalously high for this coin. Plotting volume chart')
                        plt.bar(np.arange(0, len_desired), vol)
                        plt.show()
                        plt.clf()

                time.sleep(0.1) # so i don't get DDOS warning (idk how fast i can poll yet)

    else:
        print('you did not press 1 or 2 or 3')

if __name__ == "__main__":
    main()