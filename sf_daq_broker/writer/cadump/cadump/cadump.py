from bottle import route, run, request, abort
import json

import data_api
import data_api.client
import requests
import dateutil.parser
import pytz
import datetime
import time
import re

import logging
logger = logging.getLogger("logger")

# This is how the notification look like
# {
#     'range': {
#         'startPulseId': 100,
#         'endPulseId': 120
#     },
#
#     'parameters': {
#         'general/created': 'test',
#         'general/user': 'tester',
#         'general/process': 'test_process',
#         'general/instrument': 'mac',
#         'output_file': '/bla/test.h5'}    # this is usually the full path
# }

channel_list = ["S10-CPCL-VM1MGC:LOAD"]  # specified channel is only for test purposes
base_url = ""


@route('/notify', method='PUT')
def put_document():
    data = request.body.read()
    if not data:
        abort(400, 'No data received')

    try:
        download_data(json.loads(data))
    except Exception as e:
        logger.exception("Download data failed")


def download_data(config):

    logger.info("Dump data to hdf5 ...")

    start_pulse = config["range"]["startPulseId"]
    end_pulse = config["range"]["endPulseId"]

    # Overwrite the channels list if specified in the request
    channels = channel_list
    if "channels" in config:
        channels = config["channels"]

    logger.info("Retrieve data for channels: %s" % channels)

    if "retrieval_url" in config:
        new_base_url = config["retrieval_url"]
    else:
        new_base_url = base_url

    logger.info("Retrieve pulse-id / data mapping for pulse ids")
    start_date, end_date = get_pulse_id_date_mapping([start_pulse, end_pulse])

    filename = config["parameters"]["output_file"]
    if filename != "/dev/null":
        new_filename = filename
    else:
        new_filename = None

    logger.info("Retrieving data for interval start: " + str(start_date) + " end: " + str(end_date) + " . From " + new_base_url)
    data = get_data(channels, start=start_date, end=end_date, base_url=new_base_url)

    if len(data) < 1:
        logger.error("No data retrieved")
        open(new_filename+"_NO_DATA", 'a').close()

    else:
        if new_filename:
            logger.info("Persist data to hdf5 file")
            data_api.to_hdf5(data, new_filename, overwrite=True, compression=None, shuffle=False)


def read_channels(filename):
    with open(filename) as f:
        lines = f.readlines()

    channels = []
    for line in lines:
        line = re.sub(r'\w*#.*', "", line)
        line = line.strip()
        if line:  # if not empty line
            channels.append(line)  # remove all leading and trailing spaces

    return channels


def get_data(channel_list, start=None, end=None, base_url=None):
    query = {"range": {"startDate": datetime.datetime.isoformat(start),
                       "endDate": datetime.datetime.isoformat(end),
                       "startExpansion": True},
             "channels": channel_list,
             "fields": ["pulseId", "globalSeconds", "globalDate", "value", "eventCount"]}

    logger.info(query)

    response = requests.post(base_url + '/query', json=query)

    # Check for successful return of data
    if response.status_code != 200:
        logger.info("Data retrievali failed, sleep for another time and try")

        itry = 0
        while itry < 5:
            itry += 1
            time.sleep(60)
            response = requests.post(base_url + '/query', json=query)
            if response.status_code == 200:
                break
            logger.info("Data retrieval failed, post attempt %d" % itry)

    if response.status_code != 200:
        raise RuntimeError("Unable to retrieve data from server: ", response)

    logger.info("Data retieval is successful")

    data = response.json()

    return data_api.client._build_pandas_data_frame(data, index_field="globalDate")


def get_pulse_id_date_mapping(pulse_ids):

    # See https://jira.psi.ch/browse/ATEST-897 for more details ...

    try:
        dates = []
        for pulse_id in pulse_ids:

            query = {"range": {"startPulseId": 0,
                               "endPulseId": pulse_id},
                     "limit": 1,
                     "ordering": "desc",
                     "channels": ["SIN-CVME-TIFGUN-EVR0:BUNCH-1-OK"],
                     "fields": ["pulseId", "globalDate"]}

            for c in range(10):

                logger.info("Retrieve mapping for pulse_id %d" % pulse_id)
                # Query server
                response = requests.post("https://data-api.psi.ch/sf/query", json=query)

                # Check for successful return of data
                if response.status_code != 200:
                    raise RuntimeError("Unable to retrieve data from server: ", response)

                data = response.json()

                if len(data[0]["data"]) == 0 or not "pulseId" in data[0]["data"][0]:
                    raise RuntimeError("Didn't get good responce from data_api : %s " % data)

                if not pulse_id == data[0]["data"][0]["pulseId"]:
                    logger.info("retrieval failed")
                    if c == 0:
                        ref_date = data[0]["data"][0]["globalDate"]
                        ref_date = dateutil.parser.parse(ref_date)

                        now_date = datetime.datetime.now()
                        now_date = pytz.timezone('Europe/Zurich').localize(now_date)

                        check_date = ref_date+datetime.timedelta(seconds=24)  # 20 seconds should be enough
                        delta_date = check_date - now_date

                        s = delta_date.seconds
                        logger.info("retry in " + str(s) + " seconds ")
                        if not s <= 0:
                            time.sleep(s)
                        continue

                    raise RuntimeError('Unable to retrieve mapping')

                date = data[0]["data"][0]["globalDate"]
                date = dateutil.parser.parse(date)
                dates.append(date)
                break

        return dates
    except Exception:
        raise RuntimeError('Unable to retrieve mapping')


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Channel Access archiver dump to hdf5')
    parser.add_argument('--channels', dest='channel_list', default="tests/channels.txt", help='channels to dump')
    parser.add_argument('--url', dest='url', default=None, help='base url to retrieve data from')

    args = parser.parse_args()
    print(args.channel_list)

    global channel_list
    channel_list = read_channels(args.channel_list)
    logger.info("Using channel list: " + " ".join(channel_list))

    global base_url
    base_url = args.url
    logger.info("Using base url: " + str(base_url))

    run(host='localhost', port=10200)


if __name__ == '__main__':
    main()
