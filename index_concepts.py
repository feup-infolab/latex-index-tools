#!/usr/bin/env python
#
# index_concepts.py
# José Devezas <joseluisdevezas@gmail.com>
# 2020-06-12

import argparse
import csv
import glob
import operator
import os
import re
import sys
import tempfile
from collections import defaultdict
from itertools import chain
from shutil import copy2, copytree

import ahocorasick

# ******************************************************+**********************
# * Constants (you can change these)
# ******************************************************+**********************

# Number of distance lines (resets per chapter)
DISTANCE = 200

# Stopwords based on a cutoff at frequency 100 for the top concepts
THESIS_STOPWORDS = set([
    'entity',
    'information',
    'document',
    'model',
    'hypergraph-of-entity',
    'node',
    'entity-oriented search',
    'hypergraph',
    'ranking',
    'term'
])

# ******************************************************+**********************
# * Functions
# ******************************************************+**********************


def check_begin(line, count_env, allowed_env):
    m = re.match(r'.*\\begin{(.*?)}.*', line)
    if m and m.group(1) not in allowed_env:
        count_env[m.group(1)] += 1


def check_end(line, count_env, allowed_env):
    m = re.match(r'.*\\end{(.*?)}.*', line)
    if m and m.group(1) not in allowed_env:
        count_env[m.group(1)] -= 1


def is_inside_env(count_env):
    for _, v in count_env.items():
        if v > 0:
            return True
    return False


def is_inside_command(line, start_index, end_index, open_char='{', close_char='}'):
    before_match = line[:start_index]
    after_match = line[end_index+1:]

    before_count = before_match.count(open_char) - before_match.count(close_char)
    after_count = after_match.count(open_char) - after_match.count(close_char)

    return before_count > 0 and after_count < 0


def is_part_of_command(line, end_index):
    rev_line = ''.join(reversed(line))
    m = re.match(r'^[a-zA-Z]*?\\.*', rev_line[-end_index:])
    return m is not None


def is_invalid_concept(concept):
    return '/' in concept or 'et al' in concept


def can_annotate(methods, last_line_nr, current_line_nr, concept):
    cond = True

    if methods is not None:
        if 'dist' in methods:
            cond = cond and (last_line_nr == -1 or current_line_nr > last_line_nr + DISTANCE)

        if 'stop' in methods:
            cond = cond and concept not in THESIS_STOPWORDS

    return cond


# ******************************************************+**********************
# * Command line arguments
# ******************************************************+**********************

parser = argparse.ArgumentParser(description="Index concepts in your LaTeX manuscript")

parser.add_argument(
    '-i', '--input',
    type=str,
    required=True,
    help='main LaTeX file')

parser.add_argument(
    '-c', '--concepts',
    type=str,
    required=True,
    help='concepts CSV (generated by extract_concepts.py')

parser.add_argument(
    '-o', '--output',
    type=str,
    required=True,
    help='output directory (a copy of the project with \\index{...} entries)')

parser.add_argument(
    '-e', '--exclude',
    type=str,
    action='append',
    help='exclude LaTeX files (path from main LaTeX directory; can be defined multiple times)')

parser.add_argument(
    '-a', '--allowed-env',
    type=str,
    action='append',
    default=['sloppypar'],
    help='allowed environments for indexing concepts (text inside other environments will be skipped)')

parser.add_argument(
    '-m', '--method',
    type=str,
    action='append',
    choices=['dist', 'stop'],
    help='optionally choose multiple methods to reduce the number of page entries per concept')

args, _ = parser.parse_known_args()


# ******************************************************+**********************
# * LaTeX project copy
# ******************************************************+**********************

print("==> Copying files from main LaTeX directory to output directory", file=sys.stderr)

source_dir = os.path.dirname(os.path.abspath(args.input))
target_dir = os.path.join(args.output, os.path.basename(source_dir))
if os.path.exists(target_dir):
    print("Target directory already exists: %s" % target_dir, file=sys.stderr)
    sys.exit(1)
copytree(source_dir, target_dir)

# ******************************************************+**********************
# * Detect LaTeX files to edit
# ******************************************************+**********************

print("==> Identifying LaTeX files to edit", file=sys.stderr)

relative_paths = glob.iglob('%s/**/*.tex' % target_dir, recursive=True)
relative_paths = set([path.replace(target_dir, '').lstrip('/')
                      for path in relative_paths])

ignore_paths = [glob.glob(path) for path in args.exclude]
ignore_paths = set(chain.from_iterable(ignore_paths))

stats = defaultdict(lambda: 0)


# ******************************************************+**********************
# * Build Aho-Corasick tree
# ******************************************************+**********************

print("==> Preparing Aho-Corasick concept matcher", file=sys.stderr)
matcher = ahocorasick.Automaton()
with open(args.concepts) as con_f:
    reader = csv.DictReader(con_f)
    for idx, row in enumerate(reader):
        matcher.add_word(row['match'], (row['match'], row['concept']))
        stats['index terms'] += 1
matcher.make_automaton()


# ******************************************************+**********************
# * Annotate index entries
# ******************************************************+**********************

print("==> Inserting \\index{...} entries", file=sys.stderr)

stats['annotation distribution'] = defaultdict(lambda: 0)

for path in sorted(relative_paths.difference(ignore_paths)):
    abs_path = os.path.join(target_dir, path)
    print("    %s" % path)
    stats['edited files'] += 1

    last_line = defaultdict(lambda: -1)

    with open(abs_path, 'r') as tex_f, tempfile.NamedTemporaryFile('w', delete=False) as tmp_f:
        count_env = defaultdict(lambda: 0)

        for line_nr, line in enumerate(tex_f):
            check_begin(line, count_env, args.allowed_env)
            check_end(line, count_env, args.allowed_env)

            if is_inside_env(count_env):
                tmp_f.write(line)
                stats['environment blocks skipped'] += 1
                continue

            total_annotation_length = 0
            for end_index, (match, concept) in matcher.iter_long(line):
                end_index += total_annotation_length
                start_index = end_index - len(match) + 1

                if is_invalid_concept(concept) \
                        or is_inside_command(line, start_index, end_index, '{', '}') \
                        or is_inside_command(line, start_index, end_index, '[', ']') \
                        or is_part_of_command(line, end_index):
                    stats['invalid matches'] += 1
                    continue

                concept_freq = stats['annotation distribution'][concept]

                if re.match(r'\W', line[end_index+1]) and re.match(r'\W', line[end_index-len(match)]) \
                        and can_annotate(args.method, last_line[concept], line_nr, concept):
                    annotation = '\\index{' + concept + '}'
                    line = line[0:end_index+1] + annotation + line[end_index+1:]

                    stats['indexed matches'] += 1
                    stats['annotation distribution'][concept] += 1

                    total_annotation_length += len(annotation)
                    last_line[concept] = line_nr

            tmp_f.write(line)

        tmp_filename = tmp_f.name

    copy2(tmp_filename, abs_path)
    os.unlink(tmp_filename)


# ******************************************************+**********************
# * Show statistics
# ******************************************************+**********************

print('==> A new indexed version of your document is available in %s' % target_dir, file=sys.stderr)

for name in sorted(stats.keys()):
    if type(stats[name]) is int:
        print('    %s: %d' % (name, stats[name]))

top_n = 50

for name in sorted(stats.keys()):
    if type(stats[name]) is defaultdict:
        print('\n    %s (top %d)\n' % (name.upper(), top_n))
        for idx, (concept, freq) in enumerate(sorted(stats[name].items(), key=operator.itemgetter(1), reverse=True)):
            if idx >= top_n:
                break

            print('    %3d %s' % (freq, concept))
