###############################################################################
#
#   This script takes Elasticsearch support diagnostics to generate a sequence
#   of APIs to be executed to promote CCR followers to regular indices.
#   
#   Refer to README.md for detailed instructions
#   
###############################################################################

import argparse
import json
import logging
import os
import sys
import getpass

from packaging.version import Version, parse

# configuration
LOG_LEVEL = logging.INFO
LOG_FILE = 'promote_api_builder.log'
ES_CCR_VERSION = "6.5.0"
MAX_HTTP_LINE_LENGTH = 3500
INDENT_LEVEL = 2

# JSON files
VERSION_JSON = "version.json"
CCR_STATS_JSON = "ccr_stats.json"
CCR_AUTOFOLLOW_PATTERNS_JSON = "ccr_autofollow_patterns.json"
DATA_STREAM_JSON = "data_stream.json"

class DiagnosticsData:
    def __init__(self, version=None, ccr_autofollow_patterns=None, instructions=None, is_loaded=None):
        self.version = version
        self.data_stream = []
        self.ccr_stats = []
        self.ccr_autofollow_patterns = []
        self.instructions = []
        self.is_loaded = False

    def add_comment(self, comment):
        self.instructions.append({'type': 'comment', 'text': comment})

    def add_api(self, api):
        self.instructions.append({'type': 'api', 'text': api})


def load_diagnostics(path,subdir):
    diagnostics = DiagnosticsData()


    try:
        path_file = os.sep.join([path, VERSION_JSON])
        with open(path_file) as f:
            diagnostics.version = json.load(f)
            if 'version' in diagnostics.version:
                cluster_version = parse(diagnostics.version['version']['number'].split("-",1)[0])
                if cluster_version >= Version(ES_CCR_VERSION):
                    path_file = os.sep.join([path, subdir, DATA_STREAM_JSON])
                    with open(path_file) as f:
                        diagnostics.data_stream = json.load(f)

                    path_file = os.sep.join([path, subdir, CCR_STATS_JSON])
                    with open(path_file) as f:
                        diagnostics.ccr_stats = json.load(f)

                    path_file = os.sep.join([path, subdir, CCR_AUTOFOLLOW_PATTERNS_JSON])
                    with open(path_file) as f:
                        diagnostics.ccr_autofollow_patterns = json.load(f)

                    diagnostics.is_loaded = True
                
            else:
                diagnostics.is_loaded = False




    except FileNotFoundError as e:
        diagnostics.is_loaded = False
        logging.exception(f'Exception occurred')

    return diagnostics


def parse_arguments():
    parser = argparse.ArgumentParser(prog='ccr_promote.py', description='Build required APIs to promote ccr followers.')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-d', dest='diag', metavar='diagnostics',
                        help='path to the unzipped Elasticsearch support diagnostics bundle')
    group.add_argument('-f', dest='follower', 
                        help='specify follower cluster endpoint, ie https://es_endpoint:9200')
    parser.add_argument('-l', dest='leader', default='all',
                        help='specify name of the remote cluster (leader) currently experience downtime. If not specified, it will operate on follower indices from all remote clusters.')
    parser.add_argument('--execute', action='store_true', help='Without this flag, instructions will be printed to a file. You need to specify this flag to execute commands directly to the follower cluster when -f is used.')
    args = parser.parse_args()
    return args.leader, args.follower, args.diag, args.execute

def get_cred():

    user = input ("Enter username for follower:")
    password = getpass.getpass(prompt = 'Enter password for follower:')

    return user, password

def exec_curl(user, password, follower, method, api, output):

    if output:
        os.system("curl -s -X" + method + " -u " + user + ":" + password + " -o " + output + " " + follower + api + "?pretty")
    else:
        print ('Running ' + method + ' ' + api)
        os.system("curl -s -X" + method + " -u " + user + ":" + password + " " + follower + api )
        print ('')

    return 

def get_diagnostics(user,password,follower):
    method = "GET"

    exec_curl(user, password, follower, method, "/", VERSION_JSON)
    exec_curl(user, password, follower, method, "/_ccr/stats", CCR_STATS_JSON)
    exec_curl(user, password, follower, method, "/_data_stream", DATA_STREAM_JSON)
    exec_curl(user, password, follower, method, "/_ccr/auto_follow", CCR_AUTOFOLLOW_PATTERNS_JSON)


def get_ccr_autofollow_patterns(diagnostics):

    if not diagnostics.ccr_autofollow_patterns['patterns']:
        logging.info(f'No CCR autofollow patterns defined')
        return

    logging.info(f'Found {len(diagnostics.ccr_autofollow_patterns["patterns"])} CCR autofollow_patterns:')
    is_ccr_autofollow_patterns_found = False
    ccr_autofollow_patterns={}
        
    for pattern in diagnostics.ccr_autofollow_patterns['patterns']:
        is_ccr_autofollow_patterns_found = True
        if pattern['pattern']['remote_cluster'] not in ccr_autofollow_patterns.keys():
            ccr_autofollow_patterns[pattern['pattern']['remote_cluster']]=[]

    for pattern in diagnostics.ccr_autofollow_patterns['patterns']:
        logging.info(f' - autofollow pattern [{pattern["name"]}] from remote cluster [{pattern["pattern"]["remote_cluster"]}]')
        ccr_autofollow_patterns[pattern['pattern']['remote_cluster']].append(pattern['name'])
            

    if not is_ccr_autofollow_patterns_found:
        logging.info(f'CCR autofollow patterns cannot be found, unable to retrieve CCR autofollow patterns information')

    return (ccr_autofollow_patterns)


def get_ccr_follow_indices(diagnostics):
    if not diagnostics.ccr_stats['follow_stats']['indices']:
        logging.info(f'No CCR follower found in CCR stats')
        return 

    is_ccr_follow = False
    ccr_follow_indices={}
    for i in diagnostics.ccr_stats['follow_stats']['indices']:
        if i['shards'][0]['remote_cluster'] not in ccr_follow_indices.keys():
            ccr_follow_indices[i['shards'][0]['remote_cluster']]=[]

    for i in diagnostics.ccr_stats['follow_stats']['indices']:
        ccr_follow_indices[i['shards'][0]['remote_cluster']].append(i['index'])
        is_ccr_follow = True

    return (ccr_follow_indices)

def get_ccr_follower(diagnostics,ccr_follow_indices):

    is_data_stream = False
    ccr_data_streams={}
    ccr_indices={}
    index_to_data_stream_dict = {}

    for dss in diagnostics.data_stream['data_streams']:
        for index in dss['indices']:
            index_to_data_stream_dict[index['index_name']] = dss['name']
            is_data_stream = True

    logging.info(f'Found {len(ccr_follow_indices)} remote cluster in CCR stats:')

    if len(ccr_follow_indices)>0:
        for remote_cluster in ccr_follow_indices:
            ccr_data_streams[remote_cluster]=[]
            ccr_indices[remote_cluster]=[]


        for remote_cluster in ccr_follow_indices:
            logging.info(f'  From remote_cluster [{remote_cluster}]:')
            for index in ccr_follow_indices[remote_cluster]:
                if index in index_to_data_stream_dict.keys():
                    if index_to_data_stream_dict[index] not in ccr_data_streams:
                        ccr_data_streams[remote_cluster].append(index_to_data_stream_dict[index])
                else:
                    ccr_indices[remote_cluster].append(index)
                   


            logging.info(f'   - {len(ccr_data_streams[remote_cluster])} data_stream followers')
            logging.info(f'   - {len(ccr_indices[remote_cluster])} index followers')



    logging.info('\n\n')
    return (ccr_data_streams, ccr_indices)






def build_instructions(diagnostics, ccr_follow_indices, ccr_autofollow_patterns, ccr_data_streams, ccr_indices, leader, user, password, follower, execute):



    instruction = ' The following instructions are used for promoting CCR followers to regular data stream or indices so that they can be written.'
    diagnostics.add_comment(instruction)
    method = 'POST'



    if len(ccr_autofollow_patterns)>0:
        instruction = '#  Step1. Pause auto_follow patterns'
        diagnostics.add_comment(instruction)
        for remote_cluster in ccr_autofollow_patterns:
            if remote_cluster == leader or leader=='all':
                if len(ccr_autofollow_patterns[remote_cluster])>0:
                    instruction = '## Pause follow remote cluster [' + remote_cluster + ']'
                    diagnostics.add_comment(instruction)
                    for pattern in ccr_autofollow_patterns[remote_cluster]:
                        api_auto_follow_pause = '/_ccr/auto_follow/' + pattern + '/pause'
                        diagnostics.add_api(method + ' ' + api_auto_follow_pause)
                        if execute:
                            exec_curl(user, password, follower, method, api_auto_follow_pause, None)

                        

    if len(ccr_data_streams)>0:
        instruction = '#  Step2. Promote data streams'
        diagnostics.add_comment(instruction)
        for remote_cluster in ccr_data_streams:
            if remote_cluster == leader or leader=='all':
                if len(ccr_data_streams[remote_cluster])>0:
                    instruction = '## Stop follow remote cluster [' + remote_cluster + ']'
                    diagnostics.add_comment(instruction)
                    for data_stream in ccr_data_streams[remote_cluster]:
                        api_promote = '/_data_stream/_promote/' + data_stream 
                        # This currently doesn't work. See https://github.com/elastic/elasticsearch/issues/91947
                        # Because data stream promote is still waiting on leader index to complete indexing 
                        diagnostics.add_api(method + ' ' + api_promote)
                        if execute:
                            exec_curl(user, password, follower, method, api_promote, None)

    if len(ccr_indices)>0:
        instruction = '#  Step3. Promote indices (pause, close, unfollow, open)'
        diagnostics.add_comment(instruction)
        for remote_cluster in ccr_indices:
            if remote_cluster == leader or leader=='all':
                if len(ccr_indices[remote_cluster])>0:
                    instruction = '## Stop follow remote cluster [' + remote_cluster + ']'
                    diagnostics.add_comment(instruction)
                    for index in ccr_indices[remote_cluster]:
                        api_pause = index + '/_ccr/pause_follow/'
                        api_close = index + '/_close/'
                        api_unfollow = index + '/_ccr/unfollow/'
                        api_open = index + '/_open/'
                        diagnostics.add_api(method + ' ' + api_pause)
                        diagnostics.add_api(method + ' ' + api_close)
                        diagnostics.add_api(method + ' ' + api_unfollow)
                        diagnostics.add_api(method + ' ' + api_open)
                        if execute:
                            exec_curl(user, password, follower, method, api_pause, None)
                            exec_curl(user, password, follower, method, api_close, None)
                            exec_curl(user, password, follower, method, api_unfollow, None)
                            exec_curl(user, password, follower, method, api_open, None)


    if len(ccr_follow_indices)>0:
        instruction = '###############################################################################\n'
        instruction += '##  Listing all indices promoted'
        diagnostics.add_comment(instruction)
        for remote_cluster in ccr_follow_indices:
            if remote_cluster == leader or leader=='all':
                if len(ccr_follow_indices[remote_cluster])>0:
                    instruction = '## From remote cluster [' + remote_cluster + ']'
                    diagnostics.add_comment(instruction)
                    for index in ccr_follow_indices[remote_cluster]:
                        instruction = index 
                        diagnostics.add_api(instruction)



def write_instructions_to_file(diagnostics, diagnostic_bundle_root, file_name):
    path_file = os.sep.join([diagnostic_bundle_root, file_name])
    with open(path_file, 'w') as outfile:
        logging.info('\n\n')
        logging.info(f'Instructions / APIs are written in {path_file}')
        for instruction in diagnostics.instructions:
            if instruction['type'] == 'comment':
                outfile.write("#" + instruction['text'])
            elif instruction['type'] == 'api':
                outfile.write(instruction['text'])
            else:
                # unknown instruction type
                continue
            outfile.write('\n')



def main():
    # Change root logger level from WARNING (default) to NOTSET in order for all messages to be delegated.
    logging.getLogger().setLevel(logging.NOTSET)

    # Add stdout handler, with level INFO
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    logging.getLogger().addHandler(console)

    # Add file handler, with configurable log level
    file_handler = logging.FileHandler(filename=LOG_FILE, mode='w')
    file_handler.setLevel(LOG_LEVEL)
    logging.getLogger().addHandler(file_handler)

    (leader, follower, diagnostic_bundle_root, execute) = parse_arguments()
    if not diagnostic_bundle_root:
        logging.info(f"Diagnostics data was not loaded. Will be talking to follower interactively\n")
        user,password = get_cred()
        diagnostics = get_diagnostics(user,password,follower)
        diagnostic_bundle_root = "./"
        subdir = ""
    else:
        subdir = "commercial"

    diagnostics = load_diagnostics(diagnostic_bundle_root, subdir)

    if not diagnostics.is_loaded:
        if follower:
            return logging.error(f'Failed to authenticate with provided username and password to follower')
        else:
            return logging.error(f"Diagnostics data from {diagnostic_bundle_root} cannot be loaded")

    cluster_version = diagnostics.version['version']['number']
    logging.info(f'Cluster version: {cluster_version}')

    ccr_autofollow_patterns=get_ccr_autofollow_patterns(diagnostics)
    ccr_follow_indices=get_ccr_follow_indices(diagnostics)

    if ccr_follow_indices:
        (ccr_data_streams, ccr_indices)=get_ccr_follower(diagnostics,ccr_follow_indices)
        if follower:
            build_instructions(diagnostics, ccr_follow_indices, ccr_autofollow_patterns, ccr_data_streams, ccr_indices, leader, user, password, follower, execute)
        else:
            build_instructions(diagnostics, ccr_follow_indices, ccr_autofollow_patterns, ccr_data_streams, ccr_indices, leader, None, None, None, False)

        file_name = "promote-" + diagnostics.version['cluster_name'] + (".txt")
        write_instructions_to_file(diagnostics, diagnostic_bundle_root, file_name)
    else:
        logging.info(f'No promote instruction written for this cluster')



if __name__ == "__main__":
    main()


