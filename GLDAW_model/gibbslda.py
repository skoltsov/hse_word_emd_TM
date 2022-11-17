# -*- coding: utf-8 -*-
#
# Класс для работы с файлами TMLDA
# 28/01/2018

import ctypes
from ctypes.wintypes import BOOL, DWORD
import struct
import multiprocessing
import tmlda
import win32api, win32con, win32gui
from threading import Thread
import numpy as np
import csv
import similarwords2
import os
from gensim import corpora

class GibbsLDAWindow:
    def __init__(self, bindoc, texts, topics, doccnt, waf, out_dir):
        self._bindoc = bindoc
        self._texts = texts
        self._topics = topics
        self._doccnt = doccnt
        self._out_dir = out_dir
        self._waf = waf
        WM_LDA_DATAREADY = win32con.WM_USER + 410;
        win32gui.InitCommonControls()
        self.hinst = win32api.GetModuleHandle(None)
        self._className = 'GibbsLDAWndClass'
        message_map = {
            win32con.WM_DESTROY: self.OnDestroy,
            WM_LDA_DATAREADY: self.OnDataReady,
        }
        wc = win32gui.WNDCLASS()
        wc.style = win32con.CS_HREDRAW | win32con.CS_VREDRAW
        wc.lpfnWndProc = message_map
        wc.lpszClassName = self._className
        win32gui.RegisterClass(wc)
        style = win32con.WS_OVERLAPPEDWINDOW
        self.hwnd = win32gui.CreateWindow(
            self._className,
            'Gibbs LDA',
            style,
            win32con.CW_USEDEFAULT,
            win32con.CW_USEDEFAULT,
            300,
            200,
            0,
            0,
            self.hinst,
            None
        )
        win32gui.UpdateWindow(self.hwnd)
        win32gui.ShowWindow(self.hwnd, win32con.SW_HIDE)
        self._created = True
    def OnDestroy(self, hwnd, message, wparam, lparam):
        if self._created:
            self._created = False
            win32gui.PostQuitMessage(0)
            win32gui.DestroyWindow(self.hwnd)
            win32gui.UnregisterClass(self._className, self.hinst)
        return True
    def OnDataReady(self, hwnd, message, wparam, lparam):
        LDA_THETA = 1
        LDA_PHI   = 2
        LDA_NW = 8
        LDA_NWSUM = 9
        datatype = wparam & 0xFF
        niter = wparam >> 8
        if datatype==LDA_THETA:
            print("Iterations done: ", niter)
            ArrayType = ctypes.c_void_p*self._doccnt 
            dbl_ar = np.frombuffer(ArrayType.from_address(lparam), dtype=ctypes.c_void_p)
            self.saveTheta(dbl_ar, niter)

        if datatype==LDA_PHI:
            ArrayType = ctypes.c_void_p*self._topics
            dbl_ar = np.frombuffer(ArrayType.from_address(lparam), dtype=ctypes.c_void_p)
            self.savePhi(dbl_ar, niter)
            
        if datatype==LDA_NW:
            print("Save LDA_NW")

        if datatype==LDA_NWSUM:
            print("Save LDA_NWSUM")
        return True

    # Сохранение матрицы Theta
    def saveTheta(self, dbl_ar, niter):
        ArrayType2 = ctypes.c_double*self._topics

        outcsvfn = self._out_dir+"/theta"+str(niter)+".csv"
        ugof = open(outcsvfn, 'w', newline='')#, encoding='utf_8_sig')
        writer = csv.writer(ugof, delimiter=';', quoting=csv.QUOTE_ALL, doublequote=True, quotechar='"')

        sum_prob = 0
        doc_prob = 1/self._topics
        for docid in range(self._doccnt): # первый индекс массива - по кол-ву документов
            csvrow = []
            csvrow.append(docid+1)
            origdoc = []
            if self._bindoc != None: origdoc = self._bindoc.GetOrigDocument(docid)
            if self._texts != None: 
                origtxt=""
                for w in self._texts[docid]: origtxt += w + " "
                origdoc = [origtxt, ""]
            csvrow.append(origdoc[0][:50]) # ограничиваем текст 50 символами
            meta = origdoc[1]
            #csvrow.append('nick')
            for md in meta:
                csvrow.append(md)
            sng_ar = np.frombuffer(ArrayType2.from_address(int(dbl_ar[docid])), dtype=ctypes.c_double)
            for t in range(self._topics):                
                csvrow.append("%.5f" % sng_ar[t])
                # calc perplexity
                if sng_ar[t]>doc_prob: sum_prob += 1
            writer.writerow(csvrow)

        ugof.close()
        # calc perplexity of doc
        docssratio = int(100*(sum_prob/(self._topics*self._doccnt)))
        print("    Documents ratio (Theta) = ", docssratio)

    # Сохранение матрицы Phi
    def savePhi(self, dbl_ar, niter):
        ArrayType2 = ctypes.c_double*len(self._waf)

        outcsvfn = self._out_dir+"/phi"+str(niter)+".csv"
        ugof = open(outcsvfn, 'w', newline='')#, encoding='utf_8_sig')
        writer = csv.writer(ugof, delimiter=';', quoting=csv.QUOTE_ALL, doublequote=True, quotechar='"')

        sum_prob = 0
        cur_prob = 1/len(self._waf)
        for wrdid in range(len(self._waf)): # первый индекс массива - по кол-ву слов
            wrd = ""
            if self._bindoc != None: wrd = self._waf[wrdid][2]
            if self._texts != None: wrd = self._waf[wrdid]
            csvrow = [wrd]
            for t in range(self._topics):
                sng_ar = np.frombuffer(ArrayType2.from_address(int(dbl_ar[t])), dtype=ctypes.c_double)        
                csvrow.append("%.5f" % sng_ar[wrdid])
                # calc perplexity
                if sng_ar[wrdid]>cur_prob: sum_prob += 1
            writer.writerow(csvrow)

        ugof.close()
        # calc perplexity
        wordsratio = int(100*(sum_prob/(self._topics*len(self._waf))))
        print("    Words ratio (Phi) = ", wordsratio)

#def threadloop(owner):
#    w = GibbsLDAWindow()
#    owner.hmsgwnd = w.hwnd
#    win32gui.PumpMessages()



class CGibbsLDA(object):
    def __init__(self):
        self._alpha = 0.5
        self._beta = 0.1
        self._topics = 40
        self._iterations = 100
        self._savestep = 10
        self._fname = ""
        self._bindoc = None   # исходные тексты в TMLDA
        self._texts = None    # исходные тексты в явном виде
        # загружаем библиотеку kernel32.dll и создаём event
        self._kernel32 = ctypes.windll.LoadLibrary('kernel32')
        self._createstopevent()              

    def __del__(self):
        self._closestopevent()
        if self._bindoc != None:
            del self._bindoc
            self._bindoc = None

    def SetInputTMLDA(self, fname_bin):
        # загрузка данных из файла
        self._fname = fname_bin        
        self._bindoc = tmlda.CBinaryDoc(fname_bin, False)
        self._V = self._bindoc.GetLDAWordmapBinarySize()
        self._waf = self._bindoc.GetLDAWordmapBinary(self._V)
        self._ldadoccnt = self._bindoc.GetLDADocumentsBinaryCount()
        print("Documents count: ", self._ldadoccnt)
        doccnt_artype = ctypes.c_int*self._ldadoccnt
        self.docs_cnt = doccnt_artype()
        artype = ctypes.POINTER(ctypes.c_int)*self._ldadoccnt
        self.docsArray = artype()
        self._wafItems=[]
        for docnum in range(self._ldadoccnt):
            if docnum == 0:
                docid, docsize = self._bindoc.GetLDADocumentBinaryFirst()
            else:
                docid, docsize = self._bindoc.GetLDADocumentBinaryNext()            
            ldadoc = self._bindoc.GetLDADocumentBinary(docsize)
            artype2 = ctypes.c_int*docsize
            wafItem = artype2()
            self._wafItems.append(wafItem)
            for i in range(len(ldadoc)):
                wafItem[i] = ldadoc[i]
                if ldadoc[i] != -1:
                    for k in range(len(self._waf)):
                        if ldadoc[i]==self._waf[k][0]:
                            wafItem[i] = k
                            break
            self.docs_cnt[docid] = docsize
            self.docsArray[docid] = ctypes.cast(ctypes.pointer(wafItem), ctypes.POINTER(ctypes.c_int))
            print("Loading ", int((docnum+1)*100/self._ldadoccnt), "%", end='\r')
        print("Loading OK     ") 

    # входные документы как массив списков слов
    def SetInputDocs(self, texts):
        self._texts = texts
        self._ldadoccnt = len(texts)
        print("Documents count: ", self._ldadoccnt)
        doccnt_artype = ctypes.c_int*self._ldadoccnt
        self.docs_cnt = doccnt_artype()
        artype = ctypes.POINTER(ctypes.c_int)*self._ldadoccnt        
        self.docsArray = artype()
        self._wafItems=[]
        dictionary = corpora.Dictionary(texts)
        self._waf = dictionary
        self._V = len(dictionary)
        self._wafItems=[]
        for docnum in range(self._ldadoccnt):
            docsize = len(texts[docnum])
            artype2 = ctypes.c_int*docsize
            wafItem = artype2()
            for wrd in range(len(texts[docnum])):
                wafItem[wrd] = dictionary.token2id[texts[docnum][wrd]]
            self._wafItems.append(wafItem)
            self.docs_cnt[docnum] = docsize
            self.docsArray[docnum] = ctypes.cast(ctypes.pointer(wafItem), ctypes.POINTER(ctypes.c_int))
            print("Loading ", int((docnum+1)*100/self._ldadoccnt), "%", end='\r')
        print("Loading OK     ")

    def _createstopevent(self):        
        CreateEvent = self._kernel32.CreateEventW
        CreateEvent.argtypes = (ctypes.c_void_p, BOOL, BOOL, ctypes.c_void_p)
        CreateEvent.restype = ctypes.c_void_p
        self._hStopEvent = CreateEvent(0, False, False, 0)

    def _setstopevent(self):
        SetEvent = self._kernel32.SetEvent
        SetEvent.argtypes = (ctypes.c_void_p,)
        SetEvent.restype = BOOL
        SetEvent(self._hStopEvent)

    def _closestopevent(self):
        CloseHandle = self._kernel32.CloseHandle
        CloseHandle.argtypes = (ctypes.c_void_p,)
        CloseHandle.restype = BOOL
        CloseHandle(self._hStopEvent)

    def SetParameters(self, alpha, beta, topics, niters, nitersave, ldamethod, fixtopics, granwnd, out_dir):
        self._alpha = alpha
        self._beta = beta
        self._topics = topics
        self._iterations = niters
        self._savestep = nitersave
        self._ldamethod = ldamethod
        self._granwnd = granwnd
        self._out_dir = out_dir
        if not (os.path.exists(out_dir)):
            os.mkdir(out_dir)

    def SetEmbeddings(self, emb_file, emb_similars):        
        embeddings = []
        if self._fname != "": embeddings = similarwords2.getsimilarwords(self._fname, emb_file, emb_similars)
        if self._texts != None: embeddings = similarwords2.getsimilarwords2(self._waf, emb_file, emb_similars)
        artype = ctypes.POINTER(ctypes.c_int)*len(embeddings)
        self._simwords_array = artype()
        self._emb_words = len(embeddings)
        self._emb_similars = emb_similars
        artype2 = ctypes.c_int*emb_similars        
        wrdid = 0
        for emb in embeddings:
            emb_item = artype2()
            for k in range(len(emb)): emb_item[k] = emb[k]
            self._simwords_array[wrdid] = ctypes.cast(ctypes.pointer(emb_item), ctypes.POINTER(ctypes.c_int))
            wrdid += 1

    def StartCalculation(self):
        gibbsldadll = ctypes.windll.LoadLibrary(r"gibbsldacore.dll")
        gibbsldaCalc = gibbsldadll.gibbsldaCalc
        gibbsldaCalc.argtypes = (ctypes.c_void_p, ctypes.c_void_p, # HANDLE hWnd, HANDLE hStopEvent
                                ctypes.c_int, ctypes.c_double, ctypes.c_double,   #int ompthrds, double alpha, double beta
                                ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, # int ntopics, niters, savestep, twords
                                ctypes.c_int, ctypes.c_int, # M, V
                                ctypes.c_void_p, ctypes.c_void_p,  # int *docs_cnt, int **docs_ptr
                                ctypes.c_int, ctypes.c_void_p,    # int ft_size, FIXED_TOPICS *ft_data,
                                ctypes.c_int, ctypes.c_int,      # int granulate, int gran_wnd
                                ctypes.c_int,                    # int save_nw_nwsum
                                ctypes.c_void_p, ctypes.c_int, ctypes.c_int)  # int **emb_msimwords, int emb_words, int emb_simcnt
        gibbsldaCalc.restype = ctypes.c_int

        #self.hmsgwnd = 0
        #t = Thread(target=threadloop, args=(self,))
        #t.daemon=True
        #t.start()
        w = GibbsLDAWindow(self._bindoc, self._texts, self._topics, self._ldadoccnt, self._waf, self._out_dir)
        self.hmsgwnd = w.hwnd

        self.doc_cnt_ptr = ctypes.cast(ctypes.pointer(self.docs_cnt), ctypes.POINTER(ctypes.c_int))
        simwords_array = 0
        emb_words = 0
        emb_similars = 0
        granlda = 0
        gran_wnd = 0
        if self._ldamethod == "granulate":
            granlda = 1
            gran_wnd = self._granwnd
        if self._ldamethod == "embeddings":
            simwords_array = self._simwords_array
            emb_words = self._emb_words
            emb_similars = self._emb_similars

        gibbsldaCalc(self.hmsgwnd, self._hStopEvent,
                     multiprocessing.cpu_count(), self._alpha, self._beta,
                     self._topics, self._iterations, self._savestep, 100,
                     self._ldadoccnt, self._V,
                     self.doc_cnt_ptr, self.docsArray,
                     0, 0,
                     granlda, gran_wnd,
                     0,
                     simwords_array, emb_words, emb_similars)

        win32gui.SendMessage(w.hwnd, win32con.WM_DESTROY, 0, 0)
        del w

    # Досрочная остановка вычислений (пока ею не воспользоваться)
    def StopCalculation(self):
        self._setstopevent()
