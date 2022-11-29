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

## Prerequisites
- Python3 (tested with Python version 3.x):
  - how to check Python version: `python3 --version`
- [packaging](https://pypi.org/project/packaging/)
  - Install dependices via `pip3 install packaging`
- Elasticsearch support diagnostics generated for your cluster. See https://github.com/elastic/support-diagnostics for more details.


## Script usage
```
usage: ccr_promote.py [-h] [-l LEADER] path_to_diagnostics

Build required APIs to promote ccr followers

positional arguments:
  path_to_diagnostics   path to the unzipped Elasticsearch support diagnostics bundle

optional arguments:
  -h, --help            show this help message and exit
  -l LEADER, --leader LEADER
                        Specify specific leader cluster for promoting.
```

## Running the script

- To Run: `python3 ccr_promote.py -h`
- To Run: `python3 ccr_promote.py [path_to_diag]/api-diagnostics-ccr_promote_test`
- To Run: `python3 ccr_promote.py [path_to_diag]/api-diagnostics-ccr_promote_test -l [leader_cluster]`

- Diagnostics (Input) can be generated from https://github.com/elastic/support-diagnostics
- Output files are written to the diganostics folder "promote-<cluster_id>.txt"
- Logging files are written to "promote_api_builder.log"
