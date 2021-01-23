# Graphql

import matplotlib.pyplot as plt
# from matplotlib.pyplot import figure
import numpy as np

import time
import datetime
import pytz
import json

import requests

from graphqlstuff import GetFirstThousandPairs, ConvertTimeStampsToBlocks, GetVolumeStatistics

# Constants
LOOKBACK_PERIOD = 10  # days
USE_TODAY = False
TIMEZONE_DALLAS = pytz.timezone('America/Chicago')
MAX_DATA_LENGTH = 5  # how many recent objects should be in data.json

HOW_MANY_TO_SEARCH = 1000

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/801724295751139328/aLNTXeNdZcAahKA2r02wSxt-YIzEGlYtcvO0TPObPHoCFb9Puk_wu-WXs9uZ8xxZ4ecu"


def getCurrentTime():
    return datetime.datetime.now(TIMEZONE_DALLAS).strftime("%m/%d/%Y %H:%M:%S"),


def main():
    while(1):

        scan = {
            'start_time': getCurrentTime(),
            'end_time': None,
            'num_searched': HOW_MANY_TO_SEARCH,
            'pairs': [],
        }

        # Get 1000 pairs
        pairs = GetFirstThousandPairs()

        # get time now.
        # calculate times going back every 24hrs for 30 days
        # int truncates ms, which aren't important for us.
        # Also subtract a few minutes for blocks to be updated
        time_now = int(time.time()) - 300

        # get date 30 days before this moment.
        timestamps = Return24hrTimestamps(time_now, LOOKBACK_PERIOD)
        blocks = ConvertTimeStampsToBlocks(timestamps)

        for i in range(0, HOW_MANY_TO_SEARCH):
            if (i % 50 == 0):
                print('Got through %d so far' % i)

            # Pair data
            pair = pairs[i]
            token0 = pair['token0']
            token1 = pair['token1']
            pair_string = token0['symbol'] + '-' + token1['symbol']
            pair_address = pair['id']

            # get 10-30 days worth of volume statistics for a given currency
            tv_data = GetVolumeStatistics(pair_address, blocks)
            len_desired = LOOKBACK_PERIOD

            if ((tv_data == None) or (len(tv_data) != LOOKBACK_PERIOD + 1)):
                print('Pair %s full historical data not available. Examine it manually.' % pair_string)
                time.sleep(0.1)
            else:
                vol = CalculateVolFromTotalVol(tv_data)

                print('Examining Volume for Pair:' + pair_string)
                print('Contract: %s.' % pair_address)

                if (np.argmax(vol) == len_desired - 1 and (np.max(vol) < 2.5 * float(np.max(vol[0:len_desired - 2])))):
                    # if most recent period is max, take a closer look:
                    print('24hr volume is most in 10 day period for pair %s. Plotting:' % pair_string)

                    plt.bar(np.arange(0, len_desired), vol)

                    # Append find to data for this scan
                    pair_object = {
                        'name': pair_string,
                        'address': pair['id'],
                        # 'volumes': vol,
                        'time': getCurrentTime(),
                    }
                    scan['pairs'].append(pair_object)

                    # Save img and plot
                    fileStr = pair_string
                    plt.title(fileStr)
                    plt.savefig('./images/' + fileStr)
                    plt.clf()

                time.sleep(0.1)  # so i don't get DDOS warning (idk how fast i can poll yet)

        # Finalize the scan object
        scan['end_time'] = getCurrentTime();

        # Get new pairs we should be notified about
        new_pairs = compare_old_and_new(scan)

        # Write current scan to file
        write_to_json(scan)

        # Tell discord about the new pairs / current scan
        discord_string = formatDiscordString(scan, new_pairs)
        if(discord_string != None):

            len_string = len(discord_string)

            if len_string < 2000:
                pingDiscord({'content': discord_string})
            else:
                len_msg_i = [0]
                i = 0
                while i < len_string:  # figure out how long each message is such that each new message starts with '-'
                    i = i + 2000
                    if i > len_string:
                        len_msg_i.append(len_string - 1)  # can send the whole remaining message
                    else:
                        while (not(discord_string[i] == '-' and discord_string[i+1] == ' ')):
                            i = i - 1
                        len_msg_i.append(i)

                for i in range(0, len(len_msg_i) - 1):
                    pingDiscord({'content': discord_string[len_msg_i[i]:len_msg_i[i + 1]]})

        print('final new pairs', new_pairs)

        time.sleep(600)

def formatDiscordString(scan, new_pairs):
    strs = []

    strs.append('~~~ \n Scanned {0} pairs from ({1} - {2}).'.format(HOW_MANY_TO_SEARCH, scan['end_time'][0],
                                                                    scan['end_time'][0]))

    if len(new_pairs) > 0:
        strs.append('24hr volume is most in 10 day period:')
        for pair in scan['pairs']:
            name = pair['name']
            addr = pair['address']
            pair_time = pair['time'][0]
            uniswap_url = 'https://info.uniswap.org/pair/' + addr
            dextools_url = 'https://www.dextools.io/app/uniswap/pair-explorer/' + addr

            # shorten_url(dextools_url)

            if name in new_pairs:
                name = '**NEW** ' + name

            formattedString = ' - {0}: [dextools]({1})'.format(name, dextools_url, uniswap_url)

            # Comment this in and the other one out if we're getting char limit issues and just want the name
            # formattedString = ' - {0}: ({1})'.format(name,)

            strs.append(formattedString)

        joined_string = "\n".join(strs)
        # print('JOINED STRING', joined_string)

        return joined_string

    # If no new pairs dont return anything
    print("NADA")
    return None


def compare_old_and_new(current_scan):
    # Open database
    with open('./data.json', 'r') as r:
        try:
            data = json.load(r)
        except:
            print('EXCEPTION LOADING DATA')
            return []

        # Get last known found token pairs
        last_known_snapshot = data[-1]

        # Get the pairs for old snap and current snap
        old_pairs = list(map((lambda x: x['name']), last_known_snapshot['pairs']))
        current_pairs = list(map((lambda x: x['name']), current_scan['pairs']))

        # Figure out which pairs are "new" by comparing
        new_pairs = list(set(current_pairs) - set(old_pairs))
        return new_pairs


def write_to_json(scan_obj):
    with open('./data.json', 'r') as r:
        try:
            data = json.load(r)
        except:
            data = []

    with open('data.json', 'w') as f:

        # print('data', data, type(data), len(data))
        # print('scan_obj', scan_obj)

        if len(data) >= MAX_DATA_LENGTH:
            data.pop(0)

        data.append(scan_obj)
        # print('output', data)

        json.dump(data, f, indent=4)
        print('Wrote to file.')

    return


# given a timestamp, generate the set of timestamps going back in time in 24hr intervals
# for num_days days. timestamps are ordered from past to future
# ordering is:
#   [now - 24h*num_days , ... , now - 24h, now]
# so length is num_days+1.
def Return24hrTimestamps(init_timestamp, num_days):
    timestamps = [None] * (num_days + 1)

    for i in range(0, num_days + 1):
        timestamps[num_days - i] = init_timestamp - (24 * 60 * 60) * (i)

    return timestamps


# Calculate Vol From TotalVolume
def CalculateVolFromTotalVol(total_vol):
    dv_vol = [None] * (len(total_vol) - 1)  # one shorter since we're taking differences

    for i in range(0, len(dv_vol)):
        dv_vol[i] = total_vol[i + 1] - total_vol[i]

    return dv_vol


def pingDiscord(data):
    headers = {
        'Content-Type': 'application/json'
    }

    url = DISCORD_WEBHOOK_URL

    json_data = json.dumps(data)

    try:
        requests.post(url, json=data, headers=headers)
    except:
        print('could not send to discord.')


def shorten_url(longURL):
    endpoint = "http://ow.ly/api/1.1/url/shorten?apiKey={0}&longUrl={1}".format(apiKey, longURL)
    try:
        data = requests.get(endpoint)
        print('res', data, data.results.shortUrl)
    except:
        print('could not send to discord.')


if __name__ == "__main__":
    main()
    print('Done')