# -*- coding: utf-8 -*-

import gibbslda
import pandas as pd

# Загрузка исходных текстов
f = 'student_test2.csv'
df = pd.read_csv(f, delimiter=';',decimal='.', encoding='ANSI')
texts = [[text for text in doc.split()] for doc in df['original data']]

# Здесь должна быть очистка текста, в данном примере не показана
# ...

gibbs = gibbslda.CGibbsLDA()

# Загрузка исходных текстов из файла TMLDA...
#gibbs.SetInputTMLDA("ru_test_2.tmlda")

# ...или из массива докуметов, приготовленного выше
gibbs.SetInputDocs(texts)


print("Calculations...")

# Возможные значения параметра ldamethod:
# "lda"
# "islda" - пока не реализован
# "granulate" - в этом случае надо указать параметр granwnd
# "embeddings"

gibbs.SetParameters(alpha=0.5, beta=0.1, topics=40, niters=100, nitersave=10, ldamethod="embeddings", fixtopics = 0, granwnd = 0, out_dir="outcsv")
# Если параметр ldamethod="embeddings", то надо вызвать SetEmbeddings() и указать путь к файлу эмбеддингов и требуемое количество слов
gibbs.SetEmbeddings("300_wiki_embeddings.txt", 30)
gibbs.StartCalculation()

print("OK")
