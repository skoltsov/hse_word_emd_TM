# -*- coding: utf-8 -*-

# ----------------------------------------------------------------------------------------------------------------------------------
# Функция для вычисления Most Similar Words
#
# Парметры:
#   tmlda_filename: файл в формате TMLDA, из словаря которого берутся слова для поиска ближайших
#   emb_filename: путь и имя файла с эмбеддингами 
#   s_words_need: кол-во ближайших слов
# 
# Date: 28/02/2022. Vladimir Filippov.
#
# ----------------------------------------------------------------------------------------------------------------------------------

import sys
import os
import re
import csv
import math
import struct
#import numpy as np
#import pandas as pd
import binascii
from gensim.models import keyedvectors as kd
import tmlda
               


# Функция преобразования слова в crc32
def _word2crc32(s_word):
    return (binascii.crc32(s_word.encode('cp1251'), 0xFFFFFFFF) ^ 0xFFFFFFFF) & 0xFFFFFFFF


def getsimilarwords(tmlda_filename, ebm_filename, s_words_need):

    print('Calculating the Most Similar Words')

    # загружаем ембеддинги из входного файла
    embs = kd.Word2VecKeyedVectors.load_word2vec_format(ebm_filename, no_header=True, encoding='cp1251')

    bindoc = tmlda.CBinaryDoc(tmlda_filename, False)
    wafsize = bindoc.GetLDAWordmapBinarySize()
    waf_dict = bindoc.GetLDAWordmapBinary(wafsize)

    d_wrdcnt = len(waf_dict)

    if wafsize==0:
        return []

    #print('Word count = '+str(d_wrdcnt))
    #print('Len WAF dict = '+str(len(waf_dict)))

    miss_cnt = 0
    progress_prev = 0

    result_simwords = []

    for wrd_idx in range(d_wrdcnt):
        s_word = waf_dict[wrd_idx][2] # слово из словаря входного файла
        wordlist = []
        try:
            msim = embs.most_similar(s_word, topn=s_words_need)
            # слова надо представить в виде индексов из словаря входного файла (от 0 до N-1), а не в виде crc32
            # в словаре файла может не оказаться таких слов, поэтому вместо запрошенного кол-ва близких слов их может оказаться меньше            
            for r in msim:
                currw = _word2crc32(r[0])
                for dr in range(len(waf_dict)):
                    if waf_dict[dr][0] == currw:
                        wordlist += [dr]
                        break
        except Exception:
            miss_cnt+=1

        for i in range(s_words_need-len(wordlist)):
            wordlist += [-1]
        
        result_simwords.append(wordlist)
               
        progress = int((wrd_idx+1)*100/d_wrdcnt)
        if progress>progress_prev:
            progress_prev = progress
            pr2clnt = 'Progress '+str(progress)+'%'
            print(pr2clnt, end='\r')
    
    del bindoc
    #
    print('Done. Words misses = ', miss_cnt, "/", d_wrdcnt)

    return result_simwords

# Получение similar words для готового словаря
def getsimilarwords2(dictionary, ebm_filename, s_words_need):

    print('Calculating the Most Similar Words')

    # загружаем ембеддинги из входного файла
    embs = kd.Word2VecKeyedVectors.load_word2vec_format(ebm_filename, no_header=True, encoding='cp1251')

    waf_dict = dictionary

    d_wrdcnt = len(waf_dict)

    if d_wrdcnt==0:
        return []

    #print('Word count = '+str(d_wrdcnt))
    #print('Len WAF dict = '+str(len(waf_dict)))

    miss_cnt = 0
    progress_prev = 0

    result_simwords = []

    for wrd_idx in range(d_wrdcnt):
        s_word = waf_dict[wrd_idx] # слово из словаря входного файла
        wordlist = []
        try:
            msim = embs.most_similar(s_word, topn=s_words_need)
            # слова надо представить в виде индексов из словаря входного файла (от 0 до N-1), а не в виде crc32
            # в словаре файла может не оказаться таких слов, поэтому вместо запрошенного кол-ва близких слов их может оказаться меньше            
            for r in msim:
                currw = r[0]
                try:
                    dr = waf_dict.token2id[currw]
                    wordlist += [dr]
                    #print("sim", s_word, currw)
                except Exception:
                    #print("Exception =", currw)
                    pass
        except Exception:
            miss_cnt+=1

        for i in range(s_words_need-len(wordlist)):
            wordlist += [-1]
        
        result_simwords.append(wordlist)
               
        progress = int((wrd_idx+1)*100/d_wrdcnt)
        if progress>progress_prev:
            progress_prev = progress
            pr2clnt = 'Progress '+str(progress)+'%'
            print(pr2clnt, end='\r')
    
    #
    print('Done. Words misses = ', miss_cnt, "/", d_wrdcnt)

    return result_simwords

