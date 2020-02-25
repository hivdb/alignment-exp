#! /usr/bin/env python

import ssw
from collections import defaultdict, Counter

from samutils import iter_paired_reads, iter_posnas


def sam2fasta(initrefnas, refnas, refalnprofile, sampath):
    nafreqs = defaultdict(Counter)
    all_paired_reads = iter_paired_reads(sampath)
    for _, posnas in iter_posnas(all_paired_reads):
        for refpos, nas, _ in posnas:
            for i, na in enumerate(nas):
                nafreqs[(refpos, i)][na] += 1

    resultseq = []
    alnprofile = []
    for refpos0, (refna, refp) in enumerate(zip(refnas, refalnprofile)):
        refpos = refpos0 + 1
        if (refpos, 0) in nafreqs:
            counter = nafreqs[(refpos, 0)]
            total = sum(counter.values())
            (na, _), = counter.most_common(1)
            resultseq.append(refna if na == '-' else na)
            alnprofile.append(
                '+' if refp == '+' else '-' if na == '-' else '.')
            i = 1
            while (refpos, i) in nafreqs:
                counter = nafreqs[(refpos, i)]
                i += 1
                (na, count), = counter.most_common(1)
                if count * 2 >= total:
                    resultseq.append(na)
                    alnprofile.append('+')
                else:
                    break
        else:
            resultseq.append(refna)
            alnprofile.append('.')
    return realign2(initrefnas, ''.join(resultseq), ''.join(alnprofile))


def str_index_all(text, char):
    start = 0
    indices = []
    while True:
        try:
            idx = text.index(char, start)
            indices.append(idx)
            start = idx + 1
        except ValueError:
            break
    return indices


def realign2(initref, lastref, lastref_profile):
    """
    Realign lastref to initref

    The purpose is to generate a better alignment for restoring
    initref position numbers in multi-alignment results.
    """
    # compatible consideration; different versions of
    # iterative alignment represent deletion slightly varied
    cons_delpos = set(
        str_index_all(lastref, '-') +
        str_index_all(lastref_profile, '-')
    )
    lastref = ''.join('' if p in cons_delpos else n
                      for p, n in enumerate(lastref))
    aligner = ssw.Aligner()
    aln = aligner.align(reference=initref, query=lastref)
    if aln.query_begin > 0 or \
            aln.reference_begin > 0 or \
            aln.query_end + 1 < len(lastref) or \
            aln.reference_end + 1 < len(initref):
        # this should never have since lastref is constructed
        # from initref but just in case
        raise NotImplementedError(
            'Partial alignment not supported yet')
    initref, _, lastref = aln.alignment
    resultseq = []
    alnprofile = []
    for refna, consna in zip(initref, lastref):
        if refna == '-':
            resultseq.append(consna)
            alnprofile.append('+')
        elif consna == '-':
            resultseq.append(refna)
            alnprofile.append('-')
        else:
            resultseq.append(consna)
            alnprofile.append('.')
    return ''.join(resultseq), ''.join(alnprofile)


def realign(initref, lastref, lastref_profile):
    """
    Realign lastref to initref

    The purpose is to generate a better alignment for restoring
    initref position numbers in multi-alignment results.
    """
    # compatible consideration; different versions of
    # iterative alignment represent deletion slightly varied
    cons_delpos = set(
        str_index_all(lastref, '-') +
        str_index_all(lastref_profile, '-')
    )
    lastref = ''.join('' if p in cons_delpos else n
                      for p, n in enumerate(lastref))
    aligner = ssw.Aligner()
    aln = aligner.align(reference=initref, query=lastref)
    if aln.query_begin > 0 or aln.reference_begin > 0:
        # Why?
        raise RuntimeError('Consensus misaligned')
    initref, _, lastref = aln.alignment
    ref_pos0 = -1
    alnprofile = []
    for refna, consna in zip(initref, lastref):
        if refna != '-':
            ref_pos0 += 1

        # The re-alignment could place deletions in slightly different
        # place comparing to the original alignment. Four cases need
        # to be considered:
        #   - +n+o: deletion presents in both alignments:
        #           no extra handling needed
        #   - +n-o: deletion only presents in new alignment:
        #           new deletion should be added to the multi-alignment
        #   - -n+o: deletion only presents in old alignment:
        #           multi-alignment NAs mapped to the old deletion
        #           should be removed to previous refpos (as insertion)
        #   - -n-o: no deletion:
        #           no extra handling needed
        newdel = consna == '-'
        olddel = len(alnprofile) in cons_delpos
        while not newdel and olddel:  # -n+o
            # mismatched old deletions
            prev_refpos0, _ = alnprofile[-1]
            alnprofile.append((prev_refpos0, -1))
            olddel = len(alnprofile) in cons_delpos
        else:
            if newdel:  # +n+o/+n-o
                # new deletions
                prev_refpos0, count = alnprofile[-1]
                alnprofile[-1] = (prev_refpos0, count + 1)
            else:  # -n-o
                # agree, non deletion
                alnprofile.append((ref_pos0, 0))
    return alnprofile
