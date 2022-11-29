############################################################################### 
#   This script takes Elasticsearch support diagnostics to generate a sequence
#   of APIs to be executed to promote CCR followers to regular indices.
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
#   Output files are written to the diganostics folder "promote-<cluster_id>.txt"
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
#                         Specify follower from specific leader cluster
#
###############################################################################
