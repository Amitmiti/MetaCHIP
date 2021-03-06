#!/usr/bin/env python

# Copyright (C) 2017, Weizhi Song, Torsten Thomas.
# songwz03@gmail.com or t.thomas@unsw.edu.au

# MetaCHIP is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# MetaCHIP is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import os
import sys
import argparse
from scripts.PI import PI
from scripts.BM import BM
from scripts.PG import PG

to_do = '''

All:
add option -force
report progress for every 100 processes (if n/100 is int)
replace all-vs-all blastn with usearch

-r option only accept p c o f g s

PI:
if there is a Usearch error, break the pipeline
provide qsub option for running blast  
combine grouping and group_to_taxon file

BM:
not print if disabled: [2018-12-09 21:54:32] Plotting flanking regions with 16 cores

PG:
change text direction for circos plot
report the number of low cov and low css columns in alignment
run mafft in fast mode if sequence number higher than 200 
error ocurred during plot if no HGT validated by PG
steps move to PG.py: uclust, get species tree
faa subset file to PG_wd
removed %s columns from the concatenated msa with low coverage 
removed %s columns from the concatenated msa with consensus
make a tmp folder 

'''


def get_program_path_dict(pwd_cfg_file):
    program_path_dict = {}
    for each in open(pwd_cfg_file):
        each_split = each.strip().split('=')
        program_name = each_split[0]
        program_path = each_split[1]

        # remove space if there are
        if program_name[-1] == ' ':
            program_name = program_name[:-1]
        if program_path[0] == ' ':
            program_path = program_path[1:]
        program_path_dict[program_name] = program_path

    return program_path_dict


def print_main_help():

    help_message = ''' 
             ...::: MetaCHIP :::...
        
    HGT detection modules:
       PI               -> Prepare Input files 
       BM               -> Best-Match approach 
       PG               -> PhyloGenetic approach
    
    Plot modules:
       plot_tree        -> Plot newick tree
       plot_taxon       -> show taxon correlations with sankey plot
      
    Other modules:
       parallel_blastn  -> run all-vs-all blastn in parallel
       get_gene_cluster -> get gene clusters with Usearch
    

    # for command specific help
    MetaCHIP <command> -h
    '''

    print(help_message)


if __name__ == '__main__':

    # initialize the options parser
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help="--", dest='subparser_name')

    # arguments for PI
    PI_parser = subparsers.add_parser('PI',  description='Prepare input files', epilog='Example: MetaCHIP PI -h')
    PI_parser.add_argument('-i',             required=True,  help='input genome folder')
    PI_parser.add_argument('-taxon',         required=False,  help='taxonomic classification')
    PI_parser.add_argument('-p',             required=True,  help='output prefix')
    PI_parser.add_argument('-r',             required=False, default=None, help='grouping rank')
    PI_parser.add_argument('-g',             required=False, default=None, help='grouping file')
    PI_parser.add_argument('-x',             required=False, default='fasta', help='file extension')
    PI_parser.add_argument('-grouping_only', required=False, action="store_true", help='run grouping only, deactivate gene calling and phylogenetic tree building')
    PI_parser.add_argument('-nonmeta',       required=False, action="store_true", help='annotate Non-metagenome-assembled genomes (Non-MAGs)')
    PI_parser.add_argument('-noblast',       required=False, action="store_true", help='not run all-vs-all blastn')
    PI_parser.add_argument('-t',             required=False, type=int, default=1, help='number of threads')
    PI_parser.add_argument('-qsub',          required=False, action="store_true", help='run blastn with job scripts, only for HPC users')
    PI_parser.add_argument('-force',         required=False, action="store_true", help='overwrite previous results')
    PI_parser.add_argument('-quiet',         required=False, action="store_true", help='not report progress')

    # arguments for BM approach
    BM_parser = subparsers.add_parser('BM',  description='Best-match approach', epilog='Example: MetaCHIP BM -h')
    BM_parser.add_argument('-p',             required=True,  help='output prefix')
    BM_parser.add_argument('-r',             required=False, default=None, help='grouping rank')
    BM_parser.add_argument('-g',             required=False, default=None, help='grouping file')
    BM_parser.add_argument('-cov',           required=False, type=int, default=75, help='coverage cutoff, deafult: 75')
    BM_parser.add_argument('-al',            required=False, type=int, default=200, help='alignment length cutoff, deafult: 200')
    BM_parser.add_argument('-flk',           required=False, type=int, default=10, help='the length of flanking sequences to plot (Kbp), deafult: 10')
    BM_parser.add_argument('-ip',            required=False, type=int, default=90, help='identity percentile cutoff, deafult: 90')
    BM_parser.add_argument('-ei',            required=False, type=float, default=90, help='end match identity cutoff, deafult: 95')
    BM_parser.add_argument('-t',             required=False, type=int, default=1, help='number of threads, deafult: 1')
    BM_parser.add_argument('-plot_iden',     required=False, action="store_true", help='plot identity distribution')
    BM_parser.add_argument('-NoEbCheck',     required=False, action="store_true", help='disable end break and contig match check for fast processing, not recommend for metagenome-assembled genomes (MAGs))')
    BM_parser.add_argument('-force',         required=False, action="store_true", help='overwrite previous results')
    BM_parser.add_argument('-quiet',         required=False, action="store_true", help='Do not report progress')
    BM_parser.add_argument('-tmp',           required=False, action="store_true", help='keep temporary files')

    # arguments for PG approach
    PG_parser = subparsers.add_parser('PG',  description='Phylogenetic approach', epilog='Example: MetaCHIP PG -h')
    PG_parser.add_argument('-p',             required=True,  help='output prefix')
    PG_parser.add_argument('-r',             required=False, default=None, help='grouping rank')
    PG_parser.add_argument('-g',             required=False, help='grouping file')
    PG_parser.add_argument('-cov',           required=False, type=int, default=75, help='coverage cutoff, deafult: 75')
    PG_parser.add_argument('-al',            required=False, type=int, default=200, help='alignment length cutoff, deafult: 200')
    PG_parser.add_argument('-flk',           required=False, type=int, default=10, help='the length of flanking sequences to plot (Kbp), deafult: 10')
    PG_parser.add_argument('-ip',            required=False, type=int, default=90, help='identity percentile, deafult: 90')
    PG_parser.add_argument('-ei',            required=False, type=float, default=90, help='end match identity cutoff, deafult: 95')
    PG_parser.add_argument('-t',             required=False, type=int, default=1, help='number of threads, deafult: 1')
    PG_parser.add_argument('-force',         required=False, action="store_true", help='overwrite previous results')
    PG_parser.add_argument('-quiet',         required=False, action="store_true", help='Do not report progress')


    # get and check options
    args = None
    if (len(sys.argv) == 1) or (sys.argv[1] == '-h') or (sys.argv == '--help'):
        print_main_help()
        sys.exit(0)
    else:
        args = vars(parser.parse_args())

    # read in config file
    pwd_MetaCHIP_script = sys.argv[0]
    MetaCHIP_script_path, file_name = os.path.split(pwd_MetaCHIP_script)
    pwd_cfg_file = '%s/config.txt' % MetaCHIP_script_path
    config_dict = get_program_path_dict(pwd_cfg_file)
    config_dict['path_to_hmm'] = '%s/phylo.hmm' % MetaCHIP_script_path
    config_dict['circos_HGT_R'] = '%s/circos_HGT.R' % MetaCHIP_script_path

    # run corresponding module
    if args['subparser_name'] == 'PI':
        PI(args, config_dict)
    if args['subparser_name'] == 'BM':
        BM(args, config_dict)
    if args['subparser_name'] == 'PG':
        PG(args, config_dict)

