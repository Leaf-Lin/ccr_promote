# ccr promote

This script takes Elasticsearch support diagnostics to generate a sequence of APIs to be executed to promote CCR followers to regular indices.

If your ccr cluster contains follower from several different leader cluster, you can add the flag `-l|--leader <leader_cluster>` to specify which leader cluster you wish to stop following.
   
1. Get autofollow patterns from `_ccr/auto_follow` 
2. Get CCR follower indices from `_ccr/stats` 
3. Find CCR follower data streams from 2.
4. Print instruction:
- Step1. Pause auto_follow patterns
- Step2. Promote data streams
- Step3. Promote indices (pause, close, unfollow, open)
- Additionally, it prints all indices promotes (for reference)

## Prerequisites
- Python3 (tested with Python version 3.x):
  - how to check Python version: `python3 --version`
- [packaging](https://pypi.org/project/packaging/)
  - Install dependices via `pip3 install packaging`
- Elasticsearch support diagnostics generated for your cluster. See https://github.com/elastic/support-diagnostics for more details.


## Script usage
```
usage: ccr_promote.py [-h] (-d diagnostics | -f FOLLOWER) [-l LEADER] [--execute]

Build required APIs to promote ccr followers.

optional arguments:
  -h, --help      show this help message and exit
  -d diagnostics  path to the unzipped Elasticsearch support diagnostics bundle
  -f FOLLOWER     specify follower cluster endpoint, ie https://es_endpoint:9200
  -l LEADER       specify name of the remote cluster (leader) currently experience downtime. If not specified, it will operate on follower indices from all remote clusters.
  --execute       Without this flag, instructions will be printed to a file. You need to specify this flag to execute commands directly to the follower cluster when -f is used.
```

## Running the script

- To get script usage:
```
python3 ccr_promote.py -h
```

- To Run with a remote cluster:
```
python3 ccr_promote.py -f [https://es_endpoint:9200]
python3 ccr_promote.py -f [https://es_endpoint:9200] --execute
python3 ccr_promote.py -f [https://es_endpoint:9200] -l [leader_cluster]
python3 ccr_promote.py -f [https://es_endpoint:9200] -l [leader_cluster] --execute
```

-   To Run with a diagnostics bundle:
```
python3 ccr_promote.py [path_to_diag/api-diagnostics-ccr_promote_test0]
python3 ccr_promote.py [path_to_diag/api-diagnostics-ccr_promote_test0] -l [leader_cluster]
```

- Diagnostics (Input) can be generated from https://github.com/elastic/support-diagnostics
  - Several input files are available in the examples folder.
- Output files are written to the diganostics folder "promote-<cluster_id>.txt"
- Logging files are written to "promote_api_builder.log"
