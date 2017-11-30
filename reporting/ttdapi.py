import requests
import logging
import json
import sys
import pandas as pd
from io import StringIO

configfile = 'Config/ttdconfig.json'


url = 'https://api.thetradedesk.com/v3'
configpath = 'Config/'


class TtdApi(object):
    def __init__(self):
        self.df = pd.DataFrame()
        self.configfile = None
        self.config = None
        self.config_list = None
        self.login = None
        self.password = None
        self.ad_id = None
        self.report_name = None
        self.auth_token = None
        self.headers = None

    def input_config(self, config):
        logging.info('Loading TTD config file: ' + str(config))
        self.configfile = configpath + config
        self.load_config()
        self.check_config()

    def load_config(self):
        try:
            with open(self.configfile, 'r') as f:
                self.config = json.load(f)
        except IOError:
            logging.error(self.configfile + ' not found.  Aborting.')
            sys.exit(0)
        self.login = self.config['LOGIN']
        self.password = self.config['PASS']
        self.ad_id = self.config['ADID']
        self.report_name = self.config['Report Name']
        self.config_list = [self.login, self.password]

    def check_config(self):
        for item in self.config_list:
            if item == '':
                logging.warning(item + ' not in TTD config file.  Aborting.')
                sys.exit(0)

    def authenticate(self):
        auth_url = "{0}/authentication".format(url)
        userpass = {'Login': self.login, 'Password': self.password}
        self.headers = {'Content-Type': 'application/json'}
        r = requests.post(auth_url, headers=self.headers, json=userpass)
        if r.status_code != 200:
            logging.error('Failed to authenticate with error code: '
                          + str(r.status_code) + ' Error: ' + str(r.content))
            sys.exit(0)
        auth_token = json.loads(r.text)['Token']
        return auth_token

    def get_download_url(self):
        auth_token = self.authenticate()
        rep_url = '{0}/myreports/reportexecution/query/advertisers'.format(url)
        self.headers = {'Content-Type': 'application/json',
                        'TTD-Auth': auth_token}
        data = []
        i = 0
        error_response_count = 0
        result_data = [1]
        while len(result_data) != 0 and error_response_count < 100:
            payload = {
                'AdvertiserIds': [self.ad_id],
                'PageStartIndex': i * 99,
                'PageSize': 100
            }
            r = requests.post(rep_url, headers=self.headers, json=payload)
            raw_data = json.loads(r.content)
            if 'Result' in raw_data:
                result_data = raw_data['Result']
                match_data = [x for x in result_data if
                              x['ReportScheduleName'] == self.report_name and
                              x['ReportExecutionState'] == 'Complete']
                data.extend(match_data)
                i += 1
            else:
                logging.warning('Retrying.  Unknown response :' + raw_data)
                error_response_count += 1
                if error_response_count >= 100:
                    logging.error('Error count exceeded 100.  Aborting.')
                    sys.exit(0)
        last_completed = max(data, key=lambda x: x['ReportEndDateExclusive'])
        dl_url = last_completed['ReportDeliveries'][0]['DownloadURL']
        return dl_url

    def get_data(self, sd=None, ed=None, fields=None):
        logging.info('Getting TTD data for report: ' + str(self.report_name))
        dl_url = self.get_download_url()
        r = requests.get(dl_url, headers=self.headers)
        self.df = pd.read_csv(StringIO(r.content.decode('utf-8')))
        return self.df
