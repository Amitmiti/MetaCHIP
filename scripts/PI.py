from __future__ import division

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
import re
import glob
import shutil
import warnings
import itertools
from time import sleep
from datetime import datetime
from string import ascii_uppercase
from Bio import SeqIO, AlignIO, Align
from Bio.Seq import Seq
from Bio.Alphabet import IUPAC, generic_dna
from Bio import SeqFeature as SF
from Bio.SeqRecord import SeqRecord
from Bio.SeqFeature import SeqFeature, FeatureLocation
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
import multiprocessing as mp


def report_and_log(message_for_report, log_file, keep_quiet):

    time_format = '[%Y-%m-%d %H:%M:%S]'
    with open(log_file, 'a') as log_handle:
        log_handle.write('%s %s\n' % ((datetime.now().strftime(time_format)), message_for_report))

    if keep_quiet is False:
        print('%s %s' % ((datetime.now().strftime(time_format)), message_for_report))


def force_create_folder(folder_to_create):
    if os.path.isdir(folder_to_create):
        shutil.rmtree(folder_to_create, ignore_errors=True)
        if os.path.isdir(folder_to_create):
            shutil.rmtree(folder_to_create, ignore_errors=True)
            if os.path.isdir(folder_to_create):
                shutil.rmtree(folder_to_create, ignore_errors=True)
                if os.path.isdir(folder_to_create):
                    shutil.rmtree(folder_to_create, ignore_errors=True)
    os.mkdir(folder_to_create)


def remove_empty_element(list_in):

    list_out = []
    for each_element in list_in:
        if each_element != '':
            list_out.append(each_element)

    return list_out


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


def get_genome_length(genome_file):
    genome_len = 0
    for each_seq in SeqIO.parse(genome_file, 'fasta'):
        genome_len += len(each_seq.seq)
    return genome_len


def get_group_index_list():

    def iter_all_strings():
        size = 1
        while True:
            for s in itertools.product(ascii_uppercase, repeat=size):
                yield "".join(s)
            size += 1

    group_index_list = []
    for s in iter_all_strings():
        group_index_list.append(s)
        if s == 'ZZ':
            break

    return group_index_list


def export_dna_record(gene_seq, gene_id, gene_description, output_handle):
    seq_object = Seq(gene_seq, IUPAC.unambiguous_dna)
    seq_record = SeqRecord(seq_object)
    seq_record.id = gene_id
    seq_record.description = gene_description
    SeqIO.write(seq_record, output_handle, 'fasta')


def export_aa_record(gene_seq, gene_id, gene_description, output_handle):
    seq_object = Seq(gene_seq, IUPAC.protein)
    seq_record = SeqRecord(seq_object)
    seq_record.id = gene_id
    seq_record.description = gene_description
    SeqIO.write(seq_record, output_handle, 'fasta')


def remove_low_cov_and_consensus_columns(alignment_file_in, minimal_cov, min_consensus, alignment_file_out):

    def list_to_segments(list_in):

        segments_out = []
        current_element = None
        current_segment = [None, None]
        for each_element in list_in:

            # for the first ellment
            if current_element == None:
                current_element = each_element
                current_segment = [each_element, each_element]

            elif each_element == current_element + 1:
                current_segment[1] = each_element
                current_element = each_element

            elif each_element != current_element + 1:

                # add segment to list
                segments_out.append(current_segment)

                # resetting segment
                current_segment = [each_element, each_element]
                current_element = each_element

        # add segment to list
        segments_out.append(current_segment)

        return segments_out

    def remove_columns_from_msa(alignment_in, cols_to_remove):

        # get 0 based index of all wanted columns
        cols_to_remove_0_base = [(i - 1) for i in cols_to_remove]
        aln_cols_index_all = list(range(alignment_in.get_alignment_length()))
        aln_cols_index_wanted = []
        for i in aln_cols_index_all:
            if i not in cols_to_remove_0_base:
                aln_cols_index_wanted.append(i)

        # get wanted alignment segments
        wanted_segments = list_to_segments(aln_cols_index_wanted)

        # create an empty Alignment object
        alignment_new = Align.MultipleSeqAlignment([])
        for sequence in alignment_in:
            new_seq_object = Seq('')
            new_seq_record = SeqRecord(new_seq_object)
            new_seq_record.id = sequence.id
            new_seq_record.description = sequence.description
            alignment_new.append(new_seq_record)

        # add wanted columns to empty Alignment object
        for segment in wanted_segments:

            # for single column segment
            if segment[0] == segment[1]:
                segment_value = alignment_in[:, segment[0]]

                m = 0
                for each_seq in alignment_new:
                    each_seq.seq = Seq(str(each_seq.seq) + segment_value[m])
                    m += 1

            # for multiple columns segment
            else:
                segment_value = alignment_in[:, (segment[0]):(segment[1] + 1)]
                alignment_new += segment_value

        return alignment_new

    def remove_low_cov_columns(alignment_in, min_cov_cutoff):

        # get columns with low coverage
        sequence_number = len(alignment_in)
        total_col_num = alignment_in.get_alignment_length()
        low_cov_columns = []
        n = 0
        while n < total_col_num:
            current_column = alignment_in[:, n]
            dash_number = current_column.count('-')
            gap_percent = (dash_number / sequence_number) * 100

            if gap_percent > min_cov_cutoff:
                low_cov_columns.append(n + 1)

            n += 1

        # remove identified columns
        alignment_new = remove_columns_from_msa(alignment_in, low_cov_columns)

        return alignment_new

    def remove_low_consensus_columns(alignment_in, min_css_cutoff):

        # get columns with low coverage
        sequence_number = len(alignment_in)
        total_col_num = alignment_in.get_alignment_length()
        low_css_columns = []
        n = 0
        while n < total_col_num:
            current_column = alignment_in[:, n]

            # get all aa in current column
            aa_list = set()
            for aa in current_column:
                aa_list.add(aa)

            # get maximum aa percent
            most_abundant_aa_percent = 0
            for each_aa in aa_list:
                each_aa_percent = (current_column.count(each_aa) / sequence_number) * 100
                if each_aa_percent > most_abundant_aa_percent:
                    most_abundant_aa_percent = each_aa_percent

            # if maximum percent lower than provided cutoff, add current column to low consensus column list
            if most_abundant_aa_percent < min_css_cutoff:
                low_css_columns.append(n + 1)

            n += 1

        # remove identified columns
        alignment_new = remove_columns_from_msa(alignment_in, low_css_columns)

        return alignment_new

    # read in alignment
    alignment = AlignIO.read(alignment_file_in, "fasta")

    # remove_low_cov_columns
    alignment_cov = remove_low_cov_columns(alignment, minimal_cov)

    # remove_low_consensus_columns
    alignment_cov_css = remove_low_consensus_columns(alignment_cov, min_consensus)

    # write filtered alignment
    alignment_file_out_handle = open(alignment_file_out, 'w')
    for each_seq in alignment_cov_css:
        alignment_file_out_handle.write('>%s\n' % str(each_seq.id))
        alignment_file_out_handle.write('%s\n' % str(each_seq.seq))
    alignment_file_out_handle.close()


def prodigal_parser(seq_file, sco_file, prefix, output_folder):

    bin_ffn_file =     '%s.ffn' % prefix
    bin_faa_file =     '%s.faa' % prefix
    bin_gbk_file =     '%s.gbk' % prefix
    pwd_bin_ffn_file = '%s/%s'  % (output_folder, bin_ffn_file)
    pwd_bin_faa_file = '%s/%s'  % (output_folder, bin_faa_file)
    pwd_bin_gbk_file = '%s/%s'  % (output_folder, bin_gbk_file)

    # get sequence id list
    id_to_sequence_dict = {}
    sequence_id_list = []
    for each_seq in SeqIO.parse(seq_file, 'fasta'):
        id_to_sequence_dict[each_seq.id] = str(each_seq.seq)
        sequence_id_list.append(each_seq.id)


    # get sequence to cds dict and sequence to transl_table dict
    current_seq_id = ''
    current_transl_table = ''
    current_seq_csd_list = []
    seq_to_cds_dict = {}
    seq_to_transl_table_dict = {}
    for each_cds in open(sco_file):
        if each_cds.startswith('# Sequence Data'):

            # add to dict
            if current_seq_id != '':
                seq_to_cds_dict[current_seq_id] = current_seq_csd_list
                seq_to_transl_table_dict[current_seq_id] = current_transl_table

            # reset value
            current_seq_id = each_cds.strip().split('=')[-1][1:-1].split(' ')[0]
            current_transl_table = ''
            current_seq_csd_list = []

        elif each_cds.startswith('# Model Data'):
            current_transl_table = each_cds.strip().split(';')[-2].split('=')[-1]

        else:
            current_seq_csd_list.append('_'.join(each_cds.strip().split('_')[1:]))

    seq_to_cds_dict[current_seq_id] = current_seq_csd_list
    seq_to_transl_table_dict[current_seq_id] = current_transl_table


    bin_gbk_file_handle = open(pwd_bin_gbk_file, 'w')
    bin_ffn_file_handle = open(pwd_bin_ffn_file, 'w')
    bin_faa_file_handle = open(pwd_bin_faa_file, 'w')
    gene_index = 1
    for seq_id in sequence_id_list:

        # create SeqRecord
        current_sequence = Seq(id_to_sequence_dict[seq_id])
        current_SeqRecord = SeqRecord(current_sequence, id=seq_id)
        current_SeqRecord.seq.alphabet = generic_dna
        transl_table = seq_to_transl_table_dict[seq_id]

        # add SeqFeature to SeqRecord
        for cds in seq_to_cds_dict[seq_id]:

            # define locus_tag id
            locus_tag_id = '%s_%s' % (prefix, "{:0>5}".format(gene_index))

            # define FeatureLocation
            cds_split = cds.split('_')
            cds_start = SF.ExactPosition(int(cds_split[0]))
            cds_end = SF.ExactPosition(int(cds_split[1]))
            cds_strand = cds_split[2]
            current_strand = None
            if cds_strand == '+':
                current_strand = 1
            if cds_strand == '-':
                current_strand = -1
            current_feature_location = FeatureLocation(cds_start, cds_end, strand=current_strand)

            # get nc sequence
            sequence_nc = ''
            if cds_strand == '+':
                sequence_nc = id_to_sequence_dict[seq_id][cds_start-1:cds_end]
            if cds_strand == '-':
                sequence_nc = str(Seq(id_to_sequence_dict[seq_id][cds_start-1:cds_end], generic_dna).reverse_complement())

            # translate to aa sequence
            sequence_aa = str(SeqRecord(Seq(sequence_nc)).seq.translate(table=transl_table))

            # remove * at the end
            sequence_aa = sequence_aa[:-1]

            # export nc and aa sequences
            export_dna_record(sequence_nc, locus_tag_id, '', bin_ffn_file_handle)
            export_aa_record(sequence_aa, locus_tag_id, '', bin_faa_file_handle)

            # Define feature type
            current_feature_type = 'CDS'

            # Define feature qualifiers
            current_qualifiers_dict = {}
            current_qualifiers_dict['locus_tag'] = locus_tag_id
            current_qualifiers_dict['transl_table'] = transl_table
            current_qualifiers_dict['translation'] = sequence_aa

            # Create a SeqFeature
            current_feature = SeqFeature(current_feature_location, type=current_feature_type, qualifiers=current_qualifiers_dict)

            # Append Feature to SeqRecord
            current_SeqRecord.features.append(current_feature)
            gene_index += 1

        # export to gbk file
        SeqIO.write(current_SeqRecord, bin_gbk_file_handle, 'genbank')

    bin_gbk_file_handle.close()
    bin_ffn_file_handle.close()
    bin_faa_file_handle.close()


def sep_combined_hmm(combined_hmm_file, hmm_profile_sep_folder, hmmfetch_exe, pwd_hmmstat_exe):

    # extract hmm profile id from phylo.hmm
    pwd_phylo_hmm_stat_txt = '%s/phylo.hmm.stat.txt' % hmm_profile_sep_folder
    hmmstat_cmd = '%s %s > %s' % (pwd_hmmstat_exe, combined_hmm_file, pwd_phylo_hmm_stat_txt)
    os.system(hmmstat_cmd)

    # get hmm profile id file
    hmm_id_list = []
    for each_profile in open(pwd_phylo_hmm_stat_txt):
        if not each_profile.startswith('#'):
            each_profile_split = each_profile.strip().split(' ')
            if each_profile_split != ['']:
                each_profile_split_no_space = []
                for each_element in each_profile_split:
                    if each_element != '':
                        each_profile_split_no_space.append(each_element)
                hmm_id_list.append(each_profile_split_no_space[2])

    for each_hmm_id in hmm_id_list:
        hmmfetch_cmd = '%s %s %s > %s/%s.hmm' % (hmmfetch_exe, combined_hmm_file, each_hmm_id, hmm_profile_sep_folder, each_hmm_id)
        os.system(hmmfetch_cmd)


def prodigal_worker(argument_list):

    input_genome = argument_list[0]
    input_genome_folder = argument_list[1]
    pwd_prodigal_exe = argument_list[2]
    nonmeta_mode = argument_list[3]
    pwd_prodigal_output_folder = argument_list[4]

    # prepare command (according to Prokka)
    input_genome_basename, input_genome_ext = os.path.splitext(input_genome)
    pwd_input_genome = '%s/%s' % (input_genome_folder, input_genome)
    pwd_output_sco = '%s/%s.sco' % (pwd_prodigal_output_folder, input_genome_basename)

    prodigal_cmd_meta = '%s -f sco -q -c -m -g 11 -p meta -i %s -o %s' % (
    pwd_prodigal_exe, pwd_input_genome, pwd_output_sco)
    prodigal_cmd_nonmeta = '%s -f sco -q -c -m -g 11 -i %s -o %s' % (
    pwd_prodigal_exe, pwd_input_genome, pwd_output_sco)

    if nonmeta_mode is True:
        prodigal_cmd = prodigal_cmd_nonmeta
    else:
        prodigal_cmd = prodigal_cmd_meta

    os.system(prodigal_cmd)

    # prepare ffn, faa and gbk files from prodigal output
    prodigal_parser(pwd_input_genome, pwd_output_sco, input_genome_basename, pwd_prodigal_output_folder)


def copy_annotaion_worker(argument_list):
    genome = argument_list[0]
    pwd_prodigal_output_folder = argument_list[1]
    pwd_ffn_folder = argument_list[2]
    pwd_faa_folder = argument_list[3]
    pwd_gbk_folder = argument_list[4]

    os.system('cp %s/%s.ffn %s' % (pwd_prodigal_output_folder, genome, pwd_ffn_folder))  # may not need
    os.system('cp %s/%s.faa %s' % (pwd_prodigal_output_folder, genome, pwd_faa_folder))  # for usearch
    os.system('cp %s/%s.gbk %s' % (pwd_prodigal_output_folder, genome, pwd_gbk_folder))  # may not need


def hmmsearch_worker(argument_list):

    faa_file_basename = argument_list[0]
    pwd_SCG_tree_wd = argument_list[1]
    pwd_hmmsearch_exe = argument_list[2]
    path_to_hmm = argument_list[3]
    pwd_faa_folder = argument_list[4]

    # run hmmsearch
    pwd_faa_file = '%s/%s.faa' % (pwd_faa_folder, faa_file_basename)
    os.system('%s -o /dev/null --domtblout %s/%s_hmmout.tbl %s %s' % (pwd_hmmsearch_exe, pwd_SCG_tree_wd, faa_file_basename, path_to_hmm, pwd_faa_file))

    # Reading the protein file in a dictionary
    proteinSequence = {}
    for seq_record in SeqIO.parse(pwd_faa_file, 'fasta'):
        proteinSequence[seq_record.id] = str(seq_record.seq)

    # Reading the hmmersearch table/extracting the protein part found beu hmmsearch out of the protein/Writing
    # each protein sequence that was extracted to a fasta file (one for each hmm in phylo.hmm
    hmm_id = ''
    hmm_name = ''
    hmm_pos1 = 0
    hmm_pos2 = 0
    hmm_score = 0
    pwd_hmmout_tbl = pwd_SCG_tree_wd + '/' + faa_file_basename + '_hmmout.tbl'
    with open(pwd_hmmout_tbl, 'r') as tbl:
        for line in tbl:
            if line[0] == "#": continue
            line = re.sub('\s+', ' ', line)
            splitLine = line.split(' ')

            if (hmm_id == ''):
                hmm_id = splitLine[4]
                hmm_name = splitLine[0]
                hmm_pos1 = int(splitLine[17]) - 1
                hmm_pos2 = int(splitLine[18])
                hmm_score = float(splitLine[13])
            elif (hmm_id == splitLine[4]):
                if (float(splitLine[13]) > hmm_score):
                    hmm_name = splitLine[0]
                    hmm_pos1 = int(splitLine[17]) - 1
                    hmm_pos2 = int(splitLine[18])
                    hmm_score = float(splitLine[13])
            else:
                file_out = open(pwd_SCG_tree_wd + '/' + hmm_id + '.fasta', 'a+')
                file_out.write('>' + faa_file_basename + '\n')
                if hmm_name != '':
                    seq = str(proteinSequence[hmm_name][hmm_pos1:hmm_pos2])
                    file_out.write(str(seq) + '\n')
                    file_out.close()
                hmm_id = splitLine[4]
                hmm_name = splitLine[0]
                hmm_pos1 = int(splitLine[17]) - 1
                hmm_pos2 = int(splitLine[18])
                hmm_score = float(splitLine[13])

        else:
            file_out = open(pwd_SCG_tree_wd + '/' + hmm_id + '.fasta', 'a+')
            file_out.write('>' + faa_file_basename + '\n')
            if hmm_name != '':
                seq = str(proteinSequence[hmm_name][hmm_pos1:hmm_pos2])
                file_out.write(str(seq) + '\n')
                file_out.close()


def convert_hmmalign_output(align_in, align_out):

    # read in alignment
    sequence_id_list = []
    sequence_seq_dict = {}
    for aligned_seq in open(align_in):
        aligned_seq_split = aligned_seq.strip().split(' ')
        aligned_seq_split = remove_empty_element(aligned_seq_split)

        if aligned_seq_split != []:
            aligned_seq_id = aligned_seq_split[0]
            aligned_seq_seq = aligned_seq_split[1]

            # add id to sequence id list
            if aligned_seq_id not in sequence_id_list:
                sequence_id_list.append(aligned_seq_id)

            # add seq to sequence seq dict
            if aligned_seq_id not in sequence_seq_dict:
                sequence_seq_dict[aligned_seq_id] = aligned_seq_seq
            else:
                sequence_seq_dict[aligned_seq_id] += aligned_seq_seq

    # write out
    align_out_handle = open(align_out, 'w')
    for sequence_id in sequence_id_list:
        sequence_seq = sequence_seq_dict[sequence_id]
        align_out_handle.write('>%s\n' % sequence_id)
        align_out_handle.write('%s\n' % sequence_seq)
    align_out_handle.close()


def hmmalign_worker(argument_list):
    fastaFile_basename = argument_list[0]
    pwd_SCG_tree_wd = argument_list[1]
    pwd_hmm_profile_folder = argument_list[2]
    pwd_hmmalign_exe = argument_list[3]

    pwd_hmm_file =    '%s/%s.hmm'               % (pwd_hmm_profile_folder, fastaFile_basename)
    pwd_seq_in =      '%s/%s.fasta'             % (pwd_SCG_tree_wd, fastaFile_basename)
    pwd_aln_out_tmp = '%s/%s_aligned_tmp.fasta' % (pwd_SCG_tree_wd, fastaFile_basename)
    pwd_aln_out =     '%s/%s_aligned.fasta'     % (pwd_SCG_tree_wd, fastaFile_basename)

    hmmalign_cmd = '%s --trim --outformat PSIBLAST %s %s > %s ; rm %s' % (pwd_hmmalign_exe, pwd_hmm_file, pwd_seq_in, pwd_aln_out_tmp, pwd_seq_in)
    os.system(hmmalign_cmd)

    # convert alignment format
    convert_hmmalign_output(pwd_aln_out_tmp, pwd_aln_out)

    # remove tmp alignment
    os.system('rm %s' % pwd_aln_out_tmp)


def get_qualified_gene_cluster(UCLUST_output, min_gene_num, seq_file_prefix, cluster_to_gene_file):

    # srote clustering results into dict
    cluster_to_gene_member_dict = {}
    for each in open(UCLUST_output):
        each_split = each.strip().split('\t')
        cluster_id = each_split[1]
        gene_member = each_split[8]
        if cluster_id not in cluster_to_gene_member_dict:
            cluster_to_gene_member_dict[cluster_id] = {gene_member}
        else:
            cluster_to_gene_member_dict[cluster_id].add(gene_member)

    # get qualified clustes
    output_file_handle = open(cluster_to_gene_file, 'w')
    for cluster in cluster_to_gene_member_dict:
        if len(cluster_to_gene_member_dict[cluster]) >= min_gene_num:
            output_file_handle.write('%s_Gene_Cluster_%s\t%s\n' % (seq_file_prefix, cluster, ','.join(cluster_to_gene_member_dict[cluster])))
    output_file_handle.close()


def parallel_blastn_worker(argument_list):
    query_file = argument_list[0]
    pwd_query_folder = argument_list[1]
    pwd_blast_db = argument_list[2]
    pwd_blast_result_folder = argument_list[3]
    blast_parameters = argument_list[4]
    pwd_blastn_exe = argument_list[5]

    pwd_blast_result_file = '%s/%s_blastn.tab' % (pwd_blast_result_folder, '.'.join(query_file.split('.')[:-1]))
    blastn_cmd = '%s -query %s/%s -db %s -out %s %s' % (pwd_blastn_exe,
                                                        pwd_query_folder,
                                                        query_file,
                                                        pwd_blast_db,
                                                        pwd_blast_result_file,
                                                        blast_parameters)
    os.system(blastn_cmd)


def create_blastn_job_script(wd_on_katana, job_script_folder, job_script_file_name, node_num, ppn_num, memory, walltime,
                             email, modules_list, cmd):
    # Prepare header
    line_1 = '#!/bin/bash'
    line_2 = '#PBS -l nodes=%s:ppn=%s' % (str(node_num), str(ppn_num))
    line_3 = '#PBS -l vmem=%sgb' % str(memory)
    line_4 = '#PBS -l walltime=%s' % walltime
    line_5 = '#PBS -j oe'
    line_6 = '#PBS -M %s' % email
    line_7 = '#PBS -m ae'
    header = '%s\n%s\n%s\n%s\n%s\n%s\n%s\n' % (line_1, line_2, line_3, line_4, line_5, line_6, line_7)

    # Prepare module lines
    module_lines = ''
    for module in modules_list:
        module_lines += 'module load %s\n' % module

    # write to qsub files
    output_file_handle = open('%s/%s' % (job_script_folder, job_script_file_name), 'w')
    output_file_handle.write(header)
    output_file_handle.write(module_lines)
    output_file_handle.write('cd %s\n' % wd_on_katana)
    output_file_handle.write('%s\n' % cmd)
    output_file_handle.close()

    current_wd = os.getcwd()
    os.chdir(job_script_folder)
    os.system('qsub %s' % job_script_file_name)
    os.chdir(current_wd)


def PI(args, config_dict):

    # read in arguments
    input_genome_folder =   args['i']
    GTDB_output_file =      args['taxon']
    output_prefix =         args['p']
    grouping_level =        args['r']
    file_extension =        args['x']
    grouping_only =         args['grouping_only']
    num_threads =           args['t']
    keep_quiet =            args['quiet']
    nonmeta_mode =          args['nonmeta']
    qsub_on =               args['qsub']
    noblast =               args['noblast']



    # read in config file
    path_to_hmm =           config_dict['path_to_hmm']
    pwd_makeblastdb_exe =   config_dict['makeblastdb']
    pwd_blastn_exe =        config_dict['blastn']
    pwd_prodigal_exe =      config_dict['prodigal']
    pwd_hmmsearch_exe =     config_dict['hmmsearch']
    pwd_hmmfetch_exe =      config_dict['hmmfetch']
    pwd_hmmalign_exe =      config_dict['hmmalign']
    pwd_hmmstat_exe =       config_dict['hmmstat']
    pwd_usearch_exe =       config_dict['usearch']
    pwd_fasttree_exe =      config_dict['fasttree']

    warnings.filterwarnings("ignore")
    minimal_cov_in_msa = 50
    min_consensus_in_msa = 25
    blast_parameters = '-evalue 1e-5 -outfmt "6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore qlen slen" -task blastn'

    wd_on_katana = os.getcwd()
    node_num = 1
    ppn_num = 3
    memory = 20
    walltime = '11:59:00'
    email = '244289990@qq.com'
    modules_list = ['blast+/2.6.0']


    #################################################### check input ###################################################

    MetaCHIP_wd =   '%s_MetaCHIP_wd'                   % (output_prefix)
    pwd_log_file =  '%s/%s_%s_PI_%s.log'  % (MetaCHIP_wd, output_prefix, grouping_level, datetime.now().strftime('%Y-%m-%d_%Hh-%Mm-%Ss_%f'))


    # check whether input genome exist
    input_genome_file_re = '%s/*.%s' % (input_genome_folder, file_extension)
    input_genome_file_name_list = [os.path.basename(file_name) for file_name in glob.glob(input_genome_file_re)]
    input_genome_basename_list = ['.'.join(i.split('.')[:-1]) for i in input_genome_file_name_list]

    if input_genome_file_name_list == []:
        report_and_log('No input genome detected, program exited!', pwd_log_file, keep_quiet)
        exit()


    # report running mode
    if grouping_only is True:
        report_and_log('running with grouping-only mode', pwd_log_file, keep_quiet)
    else:
        force_create_folder(MetaCHIP_wd)


    ############################################ read GTDB output into dict  ###########################################

    # read GTDB output into dict
    taxon_assignment_dict = {}
    for each_genome in open(GTDB_output_file):
        if not each_genome.startswith('user_genome'):
            each_split = each_genome.strip().split('\t')
            bin_name = each_split[0]

            if bin_name in input_genome_basename_list:

                assignment_full = []
                if len(each_split) == 1:
                    assignment_full = ['d__', 'p__', 'c__', 'o__', 'f__', 'g__', 's__']
                elif (len(each_split) > 1) and (';' in each_split[1]):
                    assignment = each_split[1].split(';')
                    if len(assignment) == 7:
                        assignment_full = assignment
                    if len(assignment) == 6:
                        assignment_full = assignment + ['s__']
                    if len(assignment) == 5:
                        assignment_full = assignment + ['g__', 's__']
                    if len(assignment) == 4:
                        assignment_full = assignment + ['f__', 'g__', 's__']
                    if len(assignment) == 3:
                        assignment_full = assignment + ['o__', 'f__', 'g__', 's__']
                    if len(assignment) == 2:
                        assignment_full = assignment + ['c__', 'o__', 'f__', 'g__', 's__']

                elif (len(each_split) > 1) and (';' not in each_split[1]):
                    assignment_full = [each_split[1]] + ['p__', 'c__', 'o__', 'f__', 'g__', 's__']

                # store in dict
                taxon_assignment_dict[bin_name] = assignment_full


    # get all identified taxon at defined ranks
    rank_to_position_dict = {'d': 0, 'p': 1, 'c': 2, 'o': 3, 'f': 4, 'g': 5, 's': 6}
    specified_rank_pos = rank_to_position_dict[grouping_level]
    identified_taxon_list = []
    for each_TaxonAssign in taxon_assignment_dict:
        specified_rank_id = taxon_assignment_dict[each_TaxonAssign][specified_rank_pos]
        if specified_rank_id not in identified_taxon_list:
            identified_taxon_list.append(specified_rank_id)


    # get the id of genomes assigned to each taxon at specified level
    taxon_2_genome_dict = {}
    for each_taxon in identified_taxon_list:

        genome_list = []
        for genome in taxon_assignment_dict:
            if taxon_assignment_dict[genome][specified_rank_pos] == each_taxon:
                genome_list.append(genome)
        taxon_2_genome_dict[each_taxon] = genome_list


    # get the number of ignored genome
    unclassified_symbol = '%s__' % grouping_level
    ignored_genome_num = 0
    if unclassified_symbol in taxon_2_genome_dict:
        ignored_genome_num = len(taxon_2_genome_dict[unclassified_symbol])


    rank_abbre_dict = {'d': 'domain', 'p': 'phylum', 'c': 'class', 'o': 'order', 'f': 'family', 'g': 'genus', 's': 'species'}


    ####################################################### report #####################################################

    # report group number
    group_num = 0
    if unclassified_symbol in taxon_2_genome_dict:
        group_num = len(taxon_2_genome_dict) - 1
    else:
        group_num = len(taxon_2_genome_dict)
    sleep(0.5)

    # for report and log
    report_and_log(('Input genomes clustered into %s groups' % group_num), pwd_log_file, keep_quiet)

    if group_num == 1:
        sleep(0.5)
        report_and_log('Group number is too low for HGT analysis, please provide a lower rank level', pwd_log_file, keep_quiet)
        exit()

    # report ignored genomes
    sleep(0.5)
    if ignored_genome_num > 0:
        report_and_log(('Ignored %s genome(s) with unknown classification at specified level' % ignored_genome_num), pwd_log_file, keep_quiet)


    ############################################# define file/folder names #############################################

    genome_size_file_name =              '%s_all_genome_size.txt'               % (output_prefix)
    prodigal_output_folder =             '%s_all_prodigal_output'               % (output_prefix)
    combined_ffn_file =                  '%s_all_combined_ffn.fasta'            % (output_prefix)
    blast_db_folder =                    '%s_all_blastdb'                       % (output_prefix)
    blast_results_file =                 '%s_all_all_vs_all_blastn.tab'         % (output_prefix)
    blast_result_folder =                '%s_all_blastn_results'                % (output_prefix)
    blast_cmd_file =                     '%s_all_blastn_commands.txt'           % (output_prefix)
    blast_job_scripts_folder =           '%s_all_blastn_job_scripts'            % (output_prefix)

    grouping_file_name =                 '%s_%s%s_grouping.txt'                 % (output_prefix, grouping_level, group_num)
    grouping_plot_name =                 '%s_%s%s_grouping.png'                 % (output_prefix, grouping_level, group_num)
    grouping_id_to_taxon_tmp_file_name = '%s_%s%s_group_to_taxon_tmp.txt'       % (output_prefix, grouping_level, group_num)
    grouping_id_to_taxon_file_name =     '%s_%s%s_group_to_taxon.txt'           % (output_prefix, grouping_level, group_num)
    excluded_genome_file_name =          '%s_%s%s_excluded_genomes.txt'         % (output_prefix, grouping_level, group_num)
    ffn_folder =                         '%s_%s%s_ffn_files'                    % (output_prefix, grouping_level, group_num)
    faa_folder =                         '%s_%s%s_faa_files'                    % (output_prefix, grouping_level, group_num)
    gbk_folder =                         '%s_%s%s_gbk_files'                    % (output_prefix, grouping_level, group_num)
    combined_faa_file =                  '%s_%s%s_combined_faa.fasta'           % (output_prefix, grouping_level, group_num)
    combined_faa_file_sorted =           '%s_%s%s_combined_faa_sorted.faa'      % (output_prefix, grouping_level, group_num)
    usearch_output_txt =                 '%s_%s%s_usearch_output.txt'           % (output_prefix, grouping_level, group_num)
    usearch_cluster_to_gene_file =       '%s_%s%s_gene_clusters.txt'            % (output_prefix, grouping_level, group_num)
    SCG_tree_wd =                        '%s_%s%s_get_SCG_tree_wd'              % (output_prefix, grouping_level, group_num)
    combined_alignment_file_tmp =        '%s_%s%s_species_tree_tmp.aln'         % (output_prefix, grouping_level, group_num)
    combined_alignment_file =            '%s_%s%s_species_tree_cov%s_css%s.aln' % (output_prefix, grouping_level, group_num, minimal_cov_in_msa, min_consensus_in_msa)
    newick_tree_file =                   '%s_%s%s_species_tree.newick'          % (output_prefix, grouping_level, group_num)
    hmm_profile_sep_folder =             '%s_%s%s_hmm_profile_fetched'          % (output_prefix, grouping_level, group_num)

    pwd_genome_size_file =               '%s/%s'                                % (MetaCHIP_wd, genome_size_file_name)
    pwd_grouping_file =                  '%s/%s'                                % (MetaCHIP_wd, grouping_file_name)
    pwd_grouping_plot =                  '%s/%s'                                % (MetaCHIP_wd, grouping_plot_name)
    pwd_grouping_id_to_taxon_tmp_file =  '%s/%s'                                % (MetaCHIP_wd, grouping_id_to_taxon_tmp_file_name)
    pwd_grouping_id_to_taxon_file =      '%s/%s'                                % (MetaCHIP_wd, grouping_id_to_taxon_file_name)
    pwd_excluded_genome_file =           '%s/%s'                                % (MetaCHIP_wd, excluded_genome_file_name)
    pwd_prodigal_output_folder =         '%s/%s'                                % (MetaCHIP_wd, prodigal_output_folder)
    pwd_ffn_folder =                     '%s/%s'                                % (MetaCHIP_wd, ffn_folder)
    pwd_faa_folder =                     '%s/%s'                                % (MetaCHIP_wd, faa_folder)
    pwd_gbk_folder =                     '%s/%s'                                % (MetaCHIP_wd, gbk_folder)
    pwd_combined_ffn_file =              '%s/%s'                                % (MetaCHIP_wd, combined_ffn_file)
    pwd_combined_faa_file =              '%s/%s'                                % (MetaCHIP_wd, combined_faa_file)
    pwd_combined_faa_file_sorted =       '%s/%s'                                % (MetaCHIP_wd, combined_faa_file_sorted)
    pwd_blast_db_folder =                '%s/%s'                                % (MetaCHIP_wd, blast_db_folder)
    pwd_blast_results =                  '%s/%s'                                % (MetaCHIP_wd, blast_results_file)
    pwd_usearch_output_txt =             '%s/%s'                                % (MetaCHIP_wd, usearch_output_txt)
    pwd_usearch_cluster_to_gene_file =   '%s/%s'                                % (MetaCHIP_wd, usearch_cluster_to_gene_file)
    pwd_SCG_tree_wd =                    '%s/%s'                                % (MetaCHIP_wd, SCG_tree_wd)
    pwd_combined_alignment_file_tmp =    '%s/%s/%s'                             % (MetaCHIP_wd, SCG_tree_wd, combined_alignment_file_tmp)
    pwd_combined_alignment_file =        '%s/%s/%s'                             % (MetaCHIP_wd, SCG_tree_wd, combined_alignment_file)
    pwd_hmm_profile_sep_folder =         '%s/%s/%s'                             % (MetaCHIP_wd, SCG_tree_wd, hmm_profile_sep_folder)
    pwd_newick_tree_file =               '%s/%s'                                % (MetaCHIP_wd, newick_tree_file)
    pwd_blast_result_folder =            '%s/%s'                                % (MetaCHIP_wd, blast_result_folder)
    pwd_blast_job_scripts_folder =       '%s/%s'                                % (MetaCHIP_wd, blast_job_scripts_folder)
    pwd_blast_cmd_file =                 '%s/%s'                                % (MetaCHIP_wd, blast_cmd_file)


    ################################################### get grouping ###################################################

    group_index_list = get_group_index_list()
    grouping_file_handle = open(pwd_grouping_file, 'w')
    grouping_id_to_taxon_tmp_file_handle = open(pwd_grouping_id_to_taxon_tmp_file, 'w')
    excluded_genome_file_handle = open(pwd_excluded_genome_file, 'w')
    genomes_with_clear_taxon = set()
    n = 0
    for each_taxon in taxon_2_genome_dict:
        if each_taxon != unclassified_symbol:
            group_id = group_index_list[n]
            for genome in taxon_2_genome_dict[each_taxon]:
                genomes_with_clear_taxon.add(genome)
                for_write_1 = '%s,%s\n' % (group_id, genome)
                for_write_2 = '%s,%s\n' % (group_id, each_taxon)
                grouping_file_handle.write(for_write_1)
                grouping_id_to_taxon_tmp_file_handle.write(for_write_2)
            n += 1

        # export excluded genomes
        else:
            for un_classfided_genome in taxon_2_genome_dict[each_taxon]:
                excluded_genome_file_handle.write('%s\n' % un_classfided_genome)

    grouping_file_handle.close()
    grouping_id_to_taxon_tmp_file_handle.close()
    excluded_genome_file_handle.close()

    os.system('cat %s | sort | uniq > %s' % (pwd_grouping_id_to_taxon_tmp_file, pwd_grouping_id_to_taxon_file))
    os.system('rm %s' % pwd_grouping_id_to_taxon_tmp_file)

    if ignored_genome_num == 0:
        os.system('rm %s' % pwd_excluded_genome_file)

    sleep(0.5)
    # for report and log
    report_and_log(('Grouping file exported to: %s' % grouping_file_name), pwd_log_file, keep_quiet)


    ################################################## plot grouping stats #################################################

    # plot the number of genomes in each group
    group_id_all = []
    group_id_uniq = []
    for each_group_assignment in open(pwd_grouping_file):
        group_id = each_group_assignment.strip().split(',')[0]
        if group_id not in group_id_uniq:
            group_id_uniq.append(group_id)
        group_id_all.append(group_id)
    group_id_uniq_sorted = sorted(group_id_uniq)

    # read group_2_taxon into dict
    group_2_taxon_dict = {}
    for each_group_2_taxon in open(pwd_grouping_id_to_taxon_file):
        each_group_2_taxon_split = each_group_2_taxon.strip().split(',')
        group_2_taxon_dict[each_group_2_taxon_split[0]] = each_group_2_taxon_split[1]

    group_id_with_taxon = []
    for each_group in group_id_uniq_sorted:
        each_group_new = '(%s) %s' % (each_group, group_2_taxon_dict[each_group])
        group_id_with_taxon.append(each_group_new)

    group_id_uniq_count = []
    for each_id in group_id_uniq_sorted:
        group_id_uniq_count.append(group_id_all.count(each_id))

    x_range = range(len(group_id_uniq_sorted))
    plt.bar(x_range, group_id_uniq_count, tick_label=group_id_with_taxon, align='center', alpha=0.2, linewidth=0)

    # for a,b in zip(x_range, group_id_uniq_count):
    #     plt.text(a, b, str(b), fontsize=12, horizontalalignment='center',)

    xticks_fontsize = 10
    if 25 < len(group_id_uniq_sorted) <= 50:
        xticks_fontsize = 7
    elif len(group_id_uniq_sorted) > 50:
        xticks_fontsize = 5

    plt.xticks(x_range, group_id_with_taxon, rotation=315, fontsize=xticks_fontsize,horizontalalignment='left')

    plt.title('The number of input genome in each %s' % rank_abbre_dict[grouping_level])
    plt.ylabel('The number of genome')
    plt.tight_layout()
    plt.savefig(pwd_grouping_plot, dpi=300)
    plt.close()

    # for report and log
    report_and_log(('Grouping stats exported to: %s' % grouping_plot_name), pwd_log_file, keep_quiet)


    ################################################### export genome size #################################################

    if grouping_only == False:

        report_and_log(('Calculating the size of input genomes'), pwd_log_file, keep_quiet)

        # get input genome list
        input_genome_file_re = '%s/*.%s' % (input_genome_folder, file_extension)
        input_genome_file_name_list = [os.path.basename(file_name) for file_name in glob.glob(input_genome_file_re)]

        genome_size_file_handle = open(pwd_genome_size_file, 'w')
        genome_size_file_handle.write('Genome\tSize(Mbp)\n')
        processing = 1
        for each_genome in input_genome_file_name_list:

            if (processing/100).is_integer() is True:
                report_and_log(('Calculating genome size for the %sth genome' % processing), pwd_log_file, keep_quiet)

            pwd_each_genome = '%s/%s' % (input_genome_folder, each_genome)
            current_genome_size = get_genome_length(pwd_each_genome)
            current_genome_size_Mbp = float("{0:.2f}".format(current_genome_size / (1024 * 1024)))
            for_out = '%s\t%s\n' % (each_genome, current_genome_size_Mbp)
            genome_size_file_handle.write(for_out)
            processing += 1

        genome_size_file_handle.close()

        # for report and log
        report_and_log(('The size of input genomes exported to: %s' % genome_size_file_name), pwd_log_file, keep_quiet)


    ######################################## run prodigal with multiprocessing #########################################

    if grouping_only == False:

        # for report and log
        report_and_log(('Running Prodigal with %s cores for all input genomes' % num_threads), pwd_log_file, keep_quiet)

        # create prodigal output folder
        force_create_folder(pwd_prodigal_output_folder)

        # get input genome list
        input_genome_file_re = '%s/*.%s' % (input_genome_folder, file_extension)
        input_genome_file_name_list = [os.path.basename(file_name) for file_name in glob.glob(input_genome_file_re)]

        # prepare arguments for prodigal_worker
        list_for_multiple_arguments_Prodigal = []
        for input_genome in input_genome_file_name_list:
            list_for_multiple_arguments_Prodigal.append([input_genome, input_genome_folder, pwd_prodigal_exe, nonmeta_mode, pwd_prodigal_output_folder])

        # run prodigal with multiprocessing
        pool = mp.Pool(processes=num_threads)
        pool.map(prodigal_worker, list_for_multiple_arguments_Prodigal)
        pool.close()
        pool.join()


    ################ copy annotation files (with clear taxonomic classification) into separate folders #################

    # for report and log
    report_and_log(('Copying annotation files of qualified genomes to corresponding folders'), pwd_log_file, keep_quiet)

    # create folder
    force_create_folder(pwd_ffn_folder)
    force_create_folder(pwd_faa_folder)
    force_create_folder(pwd_gbk_folder)

    # prepare arguments for copy_annotaion_worker
    list_for_multiple_arguments_copy_annotaion = []
    for genome in genomes_with_clear_taxon:
        list_for_multiple_arguments_copy_annotaion.append([genome,
                                                           pwd_prodigal_output_folder,
                                                           pwd_ffn_folder,
                                                           pwd_faa_folder,
                                                           pwd_gbk_folder])

    # copy annotaion files with multiprocessing
    pool = mp.Pool(processes=num_threads)
    pool.map(copy_annotaion_worker, list_for_multiple_arguments_copy_annotaion)
    pool.close()
    pool.join()


    ########################################### get species tree (hmmsearch) ###########################################

    # create wd
    force_create_folder(pwd_SCG_tree_wd)

    # for report and log
    report_and_log(('Running Hmmsearch with %s cores' % num_threads), pwd_log_file, keep_quiet)

    faa_file_re = '%s/*.faa' % pwd_faa_folder
    faa_file_list = [os.path.basename(file_name) for file_name in glob.glob(faa_file_re)]
    faa_file_list = sorted(faa_file_list)

    faa_file_basename_list = []
    for faa_file in faa_file_list:
        faa_file_basename, faa_file_extension = os.path.splitext(faa_file)
        faa_file_basename_list.append(faa_file_basename)

    # prepare arguments for hmmsearch_worker
    list_for_multiple_arguments_hmmsearch = []
    for faa_file_basename in faa_file_basename_list:
        list_for_multiple_arguments_hmmsearch.append([faa_file_basename, pwd_SCG_tree_wd, pwd_hmmsearch_exe, path_to_hmm, pwd_faa_folder])

    # run hmmsearch with multiprocessing
    pool = mp.Pool(processes=num_threads)
    pool.map(hmmsearch_worker, list_for_multiple_arguments_hmmsearch)
    pool.close()
    pool.join()


    ############################################# get species tree (hmmalign) #############################################

    # for report and log
    report_and_log(('Running Hmmalign with %s cores' % num_threads), pwd_log_file, keep_quiet)

    # fetch combined hmm profiles
    force_create_folder(pwd_hmm_profile_sep_folder)
    sep_combined_hmm(path_to_hmm, pwd_hmm_profile_sep_folder, pwd_hmmfetch_exe, pwd_hmmstat_exe)

    # Call hmmalign to align all single fasta files with hmms
    files = os.listdir(pwd_SCG_tree_wd)
    fastaFiles = [i for i in files if i.endswith('.fasta')]

    # prepare arguments for hmmalign_worker
    list_for_multiple_arguments_hmmalign = []
    for fastaFile in fastaFiles:

        fastaFiles_basename = '.'.join(fastaFile.split('.')[:-1])
        list_for_multiple_arguments_hmmalign.append([fastaFiles_basename, pwd_SCG_tree_wd, pwd_hmm_profile_sep_folder, pwd_hmmalign_exe])

    # run hmmalign with multiprocessing
    pool = mp.Pool(processes=num_threads)
    pool.map(hmmalign_worker, list_for_multiple_arguments_hmmalign)
    pool.close()
    pool.join()


    ################################### get species tree (Concatenating alignments) ####################################

    # for report and log
    report_and_log('Concatenating alignments', pwd_log_file, keep_quiet)

    # concatenating the single alignments
    concatAlignment = {}
    for element in faa_file_basename_list:
        concatAlignment[element] = ''

    # Reading all single alignment files and append them to the concatenated alignment
    files = os.listdir(pwd_SCG_tree_wd)
    fastaFiles = [i for i in files if i.endswith('.fasta')]
    for faa_file_basename in fastaFiles:
        fastaFile = pwd_SCG_tree_wd + '/' + faa_file_basename
        proteinSequence = {}
        alignmentLength = 0
        for seq_record_2 in SeqIO.parse(fastaFile, 'fasta'):
            proteinName = seq_record_2.id
            proteinSequence[proteinName] = str(seq_record_2.seq)
            alignmentLength = len(proteinSequence[proteinName])

        for element in faa_file_basename_list:
            if element in proteinSequence.keys():
                concatAlignment[element] += proteinSequence[element]
            else:
                concatAlignment[element] += '-' * alignmentLength

    # writing alignment to file
    file_out = open(pwd_combined_alignment_file_tmp, 'w')
    for element in faa_file_basename_list:
        file_out.write('>' + element + '\n' + concatAlignment[element] + '\n')
    file_out.close()

    # remove columns with low coverage and low consensus
    report_and_log(('Removing columns from concatenated alignment represented by <%s%s of genomes and with an amino acid consensus <%s%s' % (minimal_cov_in_msa, '%', min_consensus_in_msa, '%')), pwd_log_file, keep_quiet)
    remove_low_cov_and_consensus_columns(pwd_combined_alignment_file_tmp, minimal_cov_in_msa, min_consensus_in_msa, pwd_combined_alignment_file)


    ########################################### get species tree (fasttree) ############################################

    # for report and log
    report_and_log('Running FastTree', pwd_log_file, keep_quiet)

    # calling fasttree for tree calculation
    fasttree_cmd = '%s -quiet %s > %s' % (pwd_fasttree_exe, pwd_combined_alignment_file, pwd_newick_tree_file)
    os.system(fasttree_cmd)

    # for report and log
    report_and_log(('Species tree exported to: %s' % newick_tree_file), pwd_log_file, keep_quiet)


    ################################################### run Usearch ####################################################

    # combine faa files
    os.system('cat %s/*.faa > %s' % (pwd_faa_folder, pwd_combined_faa_file))

    # report_and_log('Running Usearch to get gene clusters', pwd_log_file, keep_quiet)
    #
    # # sorted combined.faa
    # usearch_cmd_sortbylength = '%s -sortbylength %s -fastaout %s -minseqlength 10 -quiet' % (pwd_usearch_exe, pwd_combined_faa_file, pwd_combined_faa_file_sorted)
    # os.system(usearch_cmd_sortbylength)
    #
    # # run cluster_fast
    # usearch_cluster_parameters = '-id 0.3 -sort length -query_cov 0.7 -target_cov 0.7 -minqt 0.7 -maxqt 1.43 -quiet'
    # usearch_cmd_cluster_fast = '%s -cluster_fast %s -uc %s %s' % (pwd_usearch_exe, pwd_combined_faa_file_sorted, pwd_usearch_output_txt, usearch_cluster_parameters)
    # os.system(usearch_cmd_cluster_fast)
    #
    # # remove tmp file
    # os.system('rm %s' % pwd_combined_faa_file_sorted)
    #
    # # get qualified gene clusters
    # min_gene_number_in_cluster = 3
    # get_qualified_gene_cluster(pwd_usearch_output_txt, min_gene_number_in_cluster, output_prefix, pwd_usearch_cluster_to_gene_file)
    #
    # report_and_log(('Gene clusters exported to %s' % usearch_cluster_to_gene_file), pwd_log_file, keep_quiet)


    ############################################### run all vs all blastn ##############################################

    if grouping_only == False:

        # make blast db and run all vs all blastn
        force_create_folder(pwd_blast_db_folder)
        force_create_folder(pwd_blast_result_folder)

        # run makeblastdb
        os.system('cat %s/*.ffn > %s' % (pwd_prodigal_output_folder, pwd_combined_ffn_file))
        os.system('cp %s %s' % (pwd_combined_ffn_file, pwd_blast_db_folder))
        makeblastdb_cmd = '%s -in %s/%s -dbtype nucl -parse_seqids -logfile /dev/null' % (pwd_makeblastdb_exe, pwd_blast_db_folder, combined_ffn_file)
        os.system(makeblastdb_cmd)

        # prepare arguments list for parallel_blastn_worker
        ffn_file_re = '%s/*.ffn' % pwd_prodigal_output_folder
        ffn_file_list = [os.path.basename(file_name) for file_name in glob.glob(ffn_file_re)]
        pwd_blast_db = '%s/%s' % (pwd_blast_db_folder, combined_ffn_file)

        pwd_blast_cmd_file_handle = open(pwd_blast_cmd_file, 'w')
        list_for_multiple_arguments_blastn = []
        for ffn_file in ffn_file_list:

            list_for_multiple_arguments_blastn.append([ffn_file, pwd_prodigal_output_folder, pwd_blast_db, pwd_blast_result_folder, blast_parameters, pwd_blastn_exe])
            blastn_cmd = '%s -query %s/%s -db %s -out %s/%s %s' % (pwd_blastn_exe, pwd_prodigal_output_folder, ffn_file, pwd_blast_db, pwd_blast_result_folder, '%s_blastn.tab' % '.'.join(ffn_file.split('.')[:-1]), blast_parameters)
            pwd_blast_cmd_file_handle.write('%s\n' % blastn_cmd)

        pwd_blast_cmd_file_handle.close()

        report_and_log(('Commands for running blastn exported to: %s' % blast_cmd_file), pwd_log_file, keep_quiet)

        if noblast is True:
            report_and_log(('All-vs-all blastn disabled, please run blastn with commands provided in: %s' % blast_cmd_file), pwd_log_file, keep_quiet)
        else:
            if qsub_on is True:

                # create job scripts folder
                force_create_folder(pwd_blast_job_scripts_folder)

                for ffn_file in ffn_file_list:
                    ffn_file_basename = '.'.join(ffn_file.split('.')[:-1])
                    job_script_file_name = 'qsub_blastn_%s.sh' % ffn_file_basename
                    blastn_cmd = '%s -query %s/%s -db %s -out %s/%s %s' % (pwd_blastn_exe, pwd_prodigal_output_folder, ffn_file, pwd_blast_db, pwd_blast_result_folder, '%s_blastn.tab' % ffn_file_basename, blast_parameters)
                    create_blastn_job_script(wd_on_katana, pwd_blast_job_scripts_folder, job_script_file_name, node_num, ppn_num, memory, walltime, email, modules_list, blastn_cmd)

            else:
                report_and_log(('Running blastn for all input genomes with %s cores, blast results exported to: %s' % (num_threads, pwd_blast_result_folder)), pwd_log_file, keep_quiet)

                # run blastn with multiprocessing
                pool = mp.Pool(processes=num_threads)
                pool.map(parallel_blastn_worker, list_for_multiple_arguments_blastn)
                pool.close()
                pool.join()


    ############################################### for report and log file ##############################################

    report_and_log('PrepIn done!', pwd_log_file, keep_quiet)

