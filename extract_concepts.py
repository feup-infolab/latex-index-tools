#!/usr/bin/env python
#
# extract_concepts.py
# José Devezas <joseluisdevezas@gmail.com>
# 2020-06-12

import argparse
import csv
import os
import re
import sys
from collections import Counter

import nltk
from RAKE import Rake
from yake import KeywordExtractor


def get_continuous_chunks(sentence):
    chunked = nltk.ne_chunk(nltk.pos_tag(nltk.word_tokenize(sentence)))
    continuous_chunk = []
    current_chunk = []

    for i in chunked:
        if type(i) is nltk.Tree:
            current_chunk.append(" ".join([token for token, pos in i.leaves()]))
        elif current_chunk:
            named_entity = " ".join(current_chunk)
            if named_entity not in continuous_chunk:
                continuous_chunk.append(named_entity)
                current_chunk = []
        else:
            continue

    if continuous_chunk:
        named_entity = " ".join(current_chunk)
        if named_entity not in continuous_chunk:
            continuous_chunk.append(named_entity)

    return continuous_chunk


def nltk_extract_concepts(text, exclude, number):
    print("==> Segmenting into sentences and extracting entities", file=sys.stderr)
    entities = []
    for sentence in nltk.sent_tokenize(text):
        entities += get_continuous_chunks(sentence)
    entities = [e for e in entities if e != '' and e not in exclude and len(e) >= args.min_length]

    print("==> Counting entities", file=sys.stderr)
    entity_count = Counter(entities)

    print("==> Identifying top %d entities" % number, file=sys.stderr)
    return entity_count.most_common(args.number)


def rake_extract_concepts(text, exclude, number):
    r = Rake('/usr/share/postgresql/10/tsearch_data/english.stop')
    concepts = r.run(text, minCharacters=2, maxWords=4, minFrequency=3)
    count = 0
    for keyword, weight in concepts:
        if weight > 1 and count < number and keyword not in exclude:
            yield keyword, weight
        count += 1


def yake_extract_concepts(text, exclude, number):
    y = KeywordExtractor(lan='en', n=5, windowsSize=1, top=number)
    concepts = y.extract_keywords(text)

    for keyword, weight in concepts:
        if keyword not in exclude:
            yield keyword, weight


parser = argparse.ArgumentParser(description="Extract concepts from your LaTeX manuscript")

parser.add_argument(
    '-i', '--input',
    type=str,
    required=True,
    help='main LaTeX file')

parser.add_argument(
    '-o', '--output',
    type=str,
    required=True,
    help='output CSV to store keywords and their weights')

parser.add_argument(
    '-f', '--from',
    type=str,
    default='Introduction',
    help='exact title of the first section (default is "Introduction")')

parser.add_argument(
    '-t', '--to',
    type=str,
    default='Appendix',
    help='exact title of the first section to ignore (default is "Appendix")')

parser.add_argument(
    '-n', '--number',
    type=int,
    default=200,
    help='number of concepts to extract (default is 200)')

parser.add_argument(
    '-e', '--exclude',
    type=str,
    default='Figure,Table,Figures,Tables,Section,Sections',
    help='number of concepts to extract (default is "Figure,Table,Figures,Tables,Section,Sections")')

parser.add_argument(
    '-ml', '--min-length',
    type=int,
    default=0,
    help='minimum number of characters of a keyword (default is 0)')

parser.add_argument(
    '-m', '--method',
    type=str,
    choices=['nltk', 'rake', 'yake'],
    default='rake',
    help='concept extraction method (default is "yake")')

parser.add_argument(
    '-s', '--select',
    action='store_true',
    default=False,
    help='interactively select or edit concepts to keep (default is false)')

args, _ = parser.parse_known_args()


nltk.download([
    'averaged_perceptron_tagger',
    'maxent_ne_chunker',
    'words'
], quiet=True)

print("==> Converting LaTeX files to plain text", file=sys.stderr)

text = ''
detex_exclude = ['table', 'figure', 'equation', 'minipage', 'multicols', 'lstlisting']
with os.popen('detex -e "%s" %s' % (','.join(detex_exclude), args.input)) as f:
    ignore = True
    for line in f:
        if line == getattr(args, 'from') + '\n':
            ignore = False

        if line == args.to + '\n':
            break

        if ignore:
            continue

        text += line

text = re.sub(r'\n{2,}', '\n\n', text)
text = re.sub(r'\[.*?\]', '', text)

exclude = set(args.exclude.split(','))

if args.method == 'nltk':
    print("==> Extracting concepts using NLTK", file=sys.stderr)
    concepts = nltk_extract_concepts(text, exclude, args.number)
elif args.method == 'rake':
    print("==> Extracting concepts using RAKE", file=sys.stderr)
    concepts = rake_extract_concepts(text, exclude, args.number)
elif args.method == 'yake':
    print("==> Extracting concepts using YAKE", file=sys.stderr)
    concepts = yake_extract_concepts(text, exclude, args.number)

concepts = list(concepts)

with open(args.output, 'w') as f:
    csv = csv.writer(f)
    csv.writerow(['concept', 'match', 'weight'])

    added = set([])
    for idx, (concept, weight) in enumerate(concepts):
        if concept in added:
            continue

        matches = [concept]

        if args.select:
            while True:
                print('\n[%4d/%d] %s -> %s ' % (idx, len(concepts), ','.join(matches), concept))
                ans = input('[k/enter=KEEP, a=KEEP ALL FOLLOWING, d=DELETE, e=RENAME INDEX ENTRY, w=EDIT MATCHES] ')

                if ans == 'a':
                    args.select = False
                    break

                if ans == 'd':
                    break

                if ans == 'e':
                    concept = input('index entry rename> ')
                    continue

                if ans == 'w':
                    matches = input('edit matches (comma-separated)> ').split(',')
                    continue

                if ans in ('k', ''):
                    if concept in added:
                        break
                    added.add(concept)
                    for match in matches:
                        csv.writerow([concept, match, weight])
                    break
        else:
            for match in matches:
                csv.writerow([concept, match, weight])
