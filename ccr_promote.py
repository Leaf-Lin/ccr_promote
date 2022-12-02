###############################################################################
#
#   This script takes Elasticsearch support diagnostics to generate a sequence
#   of APIs to be executed to promote CCR followers to regular indices.
#   
#   
#   1. Get autofollow patterns from _ccr/auto_follow 
#   2. Get CCR follower indices from _ccr/stats 
#   3. Find CCR follower data streams from 2.
#   4. Print instruction:
#     - Step1. Pause auto_follow patterns
#     - Step2. Promote data streams
#     - Step3. Promote indices (pause, close, unfollow, open)
#   
#   To Run: python3 ccr_promote.py -h
#   To Run: python3 ccr_promote.py [path_to_diag]/api-diagnostics-ccr_promote_test0
#   To Run: python3 ccr_promote.py [path_to_diag]/api-diagnostics-ccr_promote_test0 -l [leader_cluster]
#
#   Diagnostics (Input) can be generated from https://github.com/elastic/support-diagnostics
#
###############################################################################
#
# usage: ccr_promote.py [-h] [-l LEADER] path_to_diagnostics
#
# Build required APIs to promote ccr followers
#
# positional arguments:
#   path_to_diagnostics   path to the unzipped Elasticsearch support diagnostics bundle
#
# optional arguments:
#   -h, --help            show this help message and exit
#   -l LEADER, --leader LEADER
#                         Specify specific leader cluster for promoting.
#
###############################################################################

import argparse
import json
import logging
import os
import sys

import pandas as pd
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


def load_diagnostics(path):
    diagnostics = DiagnosticsData()

    try:
        path_file = os.sep.join([path, VERSION_JSON])
        with open(path_file) as f:
            diagnostics.version = json.load(f)
        cluster_version = parse(diagnostics.version['version']['number'])

        if cluster_version >= Version(ES_CCR_VERSION):

            path_file = os.sep.join([path, "commercial", DATA_STREAM_JSON])
            with open(path_file) as f:
                diagnostics.data_stream = json.load(f)

            path_file = os.sep.join([path, "commercial", CCR_STATS_JSON])
            with open(path_file) as f:
                diagnostics.ccr_stats = json.load(f)

            path_file = os.sep.join([path, "commercial", CCR_AUTOFOLLOW_PATTERNS_JSON])
            with open(path_file) as f:
                diagnostics.ccr_autofollow_patterns = json.load(f)

        diagnostics.is_loaded = True

    except FileNotFoundError as e:
        diagnostics.is_loaded = False
        logging.exception(f'Exception occurred')

    return diagnostics


def parse_arguments():
    parser = argparse.ArgumentParser(description='Build required APIs to promote ccr followers')
    parser.add_argument("path", metavar='path_to_diagnostics',
                        help="path to the unzipped Elasticsearch support diagnostics bundle")
    parser.add_argument("-l", "--leader", default='all',
                        help="Specify follower from specific leader cluster")
    args = parser.parse_args()
    return args.path, args.leader

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


    return (ccr_data_streams, ccr_indices)






def build_instructions(diagnostics, ccr_follow_indices, ccr_autofollow_patterns, ccr_data_streams, ccr_indices, leader):



    instruction = ' The following instructions are used for promoting CCR followers to regular data stream or indices so that they can be written.'
    diagnostics.add_comment(instruction)



    if len(ccr_autofollow_patterns)>0:
        instruction = '#  Step1. Pause auto_follow patterns'
        diagnostics.add_comment(instruction)
        for remote_cluster in ccr_autofollow_patterns:
            if remote_cluster == leader or leader=='all':
                if len(ccr_autofollow_patterns[remote_cluster])>0:
                    instruction = '## Pause follow remote cluster [' + remote_cluster + ']'
                    diagnostics.add_comment(instruction)
                    for pattern in ccr_autofollow_patterns[remote_cluster]:
                        api_auto_follow_pause = 'POST /_ccr/auto_follow/' + pattern + '/pause'
                        diagnostics.add_api(api_auto_follow_pause)
                        

    if len(ccr_data_streams)>0:
        instruction = '#  Step2. Promote data streams'
        diagnostics.add_comment(instruction)
        for remote_cluster in ccr_data_streams:
            if remote_cluster == leader or leader=='all':
                if len(ccr_data_streams[remote_cluster])>0:
                    instruction = '## Stop follow remote cluster [' + remote_cluster + ']'
                    diagnostics.add_comment(instruction)
                    for data_stream in ccr_data_streams[remote_cluster]:
                        api_promote = 'POST /_data_stream/_promote/' + data_stream 
                        # This currently doesn't work. See https://github.com/elastic/elasticsearch/issues/91947
                        # Because data stream promote is still waiting on leader index to complete indexing 
                        diagnostics.add_api(api_promote)

    if len(ccr_indices)>0:
        instruction = '#  Step3. Promote indices (pause, close, unfollow, open)'
        diagnostics.add_comment(instruction)
        for remote_cluster in ccr_indices:
            if remote_cluster == leader or leader=='all':
                if len(ccr_indices[remote_cluster])>0:
                    instruction = '## Stop follow remote cluster [' + remote_cluster + ']'
                    diagnostics.add_comment(instruction)
                    for index in ccr_indices[remote_cluster]:
                        api_pause = 'POST /' + index + '/_ccr/pause_follow/'
                        api_close = 'POST /' + index + '/_close/'
                        api_unfollow = 'POST /' + index + '/_ccr/unfollow/'
                        api_open = 'POST /' + index + '/_open/'
                        diagnostics.add_api(api_pause)
                        diagnostics.add_api(api_close)
                        diagnostics.add_api(api_unfollow)
                        diagnostics.add_api(api_open)


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

    (diagnostic_bundle_root, leader) = parse_arguments()
    diagnostics = load_diagnostics(diagnostic_bundle_root)
    if not diagnostics.is_loaded:
        return logging.error(f"Diagnostics data from {diagnostic_bundle_root} cannot be loaded")

    cluster_version = diagnostics.version['version']['number']
    logging.info(f'Cluster version: {cluster_version}')

    ccr_autofollow_patterns=get_ccr_autofollow_patterns(diagnostics)
    ccr_follow_indices=get_ccr_follow_indices(diagnostics)

    if ccr_follow_indices:
        (ccr_data_streams, ccr_indices)=get_ccr_follower(diagnostics,ccr_follow_indices)
        build_instructions(diagnostics, ccr_follow_indices, ccr_autofollow_patterns,ccr_data_streams, ccr_indices, leader)
        file_name = "promote-" + diagnostics.version['cluster_name'] + (".txt")
        write_instructions_to_file(diagnostics, diagnostic_bundle_root, file_name)
    else:
        logging.info(f'No promote instruction written for this cluster')



if __name__ == "__main__":
    main()


