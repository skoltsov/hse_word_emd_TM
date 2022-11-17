# -*- coding: utf-8 -*-
#
# Класс для работы с файлами TMLDA
# 28/01/2018

import struct
import multiprocessing

class CBinaryDoc(object):
    def __init__(self, fname_bin, bwrite):
        self._BINFileSign = b'\x54\x4D\x69\x6E\x65\x72\x76\x33'
        self._BINFileSign_len = len(self._BINFileSign)
        self._fname = fname_bin
        self._bwrite = bwrite
        self._binfile = None
        self._lockbinfile = multiprocessing.Lock()
        self._DocIdx = []
        self._docid = 0
        self._bFirstLDA = False
        self._LDAOffs = 0
        self._LDACount = 0
        if bwrite:
            self._binfile = open(fname_bin, "wb")
            self._binfile.write(self._BINFileSign)
            self._binfile.write(struct.pack('<q', 0))
        else:
            self._binfile = open(fname_bin, "rb+")
            self._signature = self._binfile.read(self._BINFileSign_len)
            # читаем смещение заголовка
            hdr_offs, = struct.unpack('q', self._binfile.read(8))
            self._binfile.seek(hdr_offs, 0)
            # читаем размер структуры данных в заголовке
            hdr_size, = struct.unpack('i', self._binfile.read(4))
            # читаем заголовок
            bindocIdxFile = '=iiqiqiq'
            idxs = struct.calcsize(bindocIdxFile)
            for i in range(hdr_size//idxs):
                sdocidx = self._binfile.read(idxs)
                docid, origsize, origoffs, docsize, docoffs, datasize, dataoffs = struct.unpack(bindocIdxFile, sdocidx)
                docidx = [docid, origsize, origoffs, docsize, docoffs, datasize, dataoffs]
                self._DocIdx.append(docidx)
            self._LDAOffs = hdr_offs + hdr_size + 4
            self._bFirstLDA = True


    def __del__(self):
        if self._binfile != None:
            self._lockbinfile.acquire()
            #print("CBinaryDoc.__del__: "+str(len(self._DocIdx)))
            if self._bwrite and len(self._DocIdx)>0:
                self._binfile.seek(0, 2)
                hdr_offs = self._binfile.tell()
                self._binfile.seek(self._BINFileSign_len, 0)
                self._binfile.write(struct.pack('q', hdr_offs))

                bindocIdxFile = '=iiqiqiq'
                hdr_size = len(self._DocIdx)*struct.calcsize(bindocIdxFile)
                self._binfile.seek(hdr_offs, 0)
                self._binfile.write(struct.pack('i', hdr_size))

                for docidx in self._DocIdx:
                    self._binfile.write(struct.pack(bindocIdxFile, *docidx)) #[0], docidx[1], docidx[2], docidx[3], docidx[4], docidx[5], docidx[6]))
            self._binfile.close()
            self._binfile = None
            self._DocIdx = []
            self._lockbinfile.release()

    def AddDocuments(self, orig, doc, metadata):
        '''
        Функция добавляет в файл исходный и лематизированный документы. Для этого экземпляр класса
        должен быть создан с параметром bwrite = True. Индекс документа функция присваивает и
        наращивает автоматически. Функция потоко/процессно-безопасна
        :param orig: Исходный документ
        :param doc: Лематизированный документ
        :param metadata: Метаданные как список, максимум 21 поле
        :return: True в случае успеха и False при ошибке записи
        '''
        r = False
        if self._binfile == None:
            return r
        self._lockbinfile.acquire()
        try:
            docid = self._docid
            origsize = len(orig)
            self._binfile.seek(0, 2)
            origoffs = self._binfile.tell()
            if origsize>0: self._binfile.write(bytes(orig, 'cp1251'))  # в файл TMLDA документы пишутся в кодировке 1251
            docsize = len(doc)
            docoffs = self._binfile.tell()
            if docsize>0: self._binfile.write(bytes(doc, 'cp1251'))  # в файл TMLDA документы пишутся в кодировке 1251
            # преобразуем метаданные в байтовый поток
            lens = []
            for i in range(21):
                if i > len(metadata) - 1:
                    lens.append(0)
                else:
                    lens.append(len(metadata[i]))
            rawdata = struct.pack('21i', *lens)
            for i in range(21):
                if i <= len(metadata) - 1:
                    rawdata += struct.pack(str(len(metadata[i])) + 's', metadata[i].encode('cp1251'))
            datasize = len(rawdata) # ?
            dataoffs = self._binfile.tell()
            if datasize>0: self._binfile.write(rawdata)
            docidx = [docid, origsize, origoffs, docsize, docoffs, datasize, dataoffs]
            self._DocIdx.append(docidx)
            self._docid += 1
            r = True
        except Exception:
            r = False
        finally:
            self._lockbinfile.release()
        return r

    def GetDocumentCount(self):
        return len(self._DocIdx);

    def GetOrigDocument(self, docid):
        '''
        Возвращает исходный документ и метаданные
        :param docid: идентификатор документа
        :return: Список [документ, [метаданные]]
        '''
        doc = ''
        meta = []
        if self._binfile == None:
            return []
        for docidx in self._DocIdx:
            if docidx[0] == docid:
                docsize = docidx[1]
                docoffs = docidx[2]
                try:
                    self._lockbinfile.acquire()
                    self._binfile.seek(docoffs, 0)
                    doc = self._binfile.read(docsize).decode('cp1251')
                    pdatalen = docidx[5]
                    dataoffs = docidx[6]
                    if pdatalen > 0:
                        self._binfile.seek(dataoffs, 0)
                        metalens = struct.unpack('21i', self._binfile.read(21 * 4))
                        for ml in metalens:
                            if ml > 0 and ml <= 4096:
                                mi = self._binfile.read(ml).decode('cp1251')
                            else:
                                mi = ''
                            meta.append(mi)
                except Exception:
                    doc = ''
                    meta = []
                finally:
                    self._lockbinfile.release()
                break
        if doc == '': return []
        return [doc, meta]

    def GetDocument(self, docid):
        '''
        Функция для чтения лематизированного текстового документа
        :param docid: идентификатор документа
        :return: документ
        '''
        r = ''
        if self._binfile == None:
            return r
        for docidx in self._DocIdx:
            if docidx[0] == docid:
                docsize = docidx[3]
                docoffs = docidx[4]
                try:
                    self._lockbinfile.acquire()
                    self._binfile.seek(docoffs, 0)
                    r = self._binfile.read(docsize).decode('cp1251')
                except Exception:
                    r = ''
                finally:
                    self._lockbinfile.release()
                break
        return r

    def AddLDADocumentBinary(self, plda, docid):
        '''
        Добавляет LDA документ в виде массива целых чисел (по 4 байта)
        при первом добавлении после открытия файла (создания экземпляра объекта)
        файл будет усечён и начнётся добавление данных. после этого можно добавлять словарь уникальных слов
        словарь должен быть последним
        :param plda: документ в виде списка целых чисел
        :param docid: идентификатор документа (от 0)
        :return: True если всё ОК
        '''
        if self._bwrite: return False
        r = False
        try:
            self._lockbinfile.acquire()
            need_seek = True
            if self._bFirstLDA:
                # усекаем размер файла
                self._binfile.truncate(self._LDAOffs)
                # пишем признак того, что  в файле  LDA  хранятся  в бинарном виде
                self._binfile.write(struct.pack('=i', 0))
                # пишем кол - во LDA документов(этот размер будет обновляться после записи каждого нового документа)
                self._LDACount = 0
                self._binfile.write(struct.pack('=i', self._LDACount))
                # обновляем сигнатуру до актуальной версии - 200716
                self._binfile.seek(0, 0)
                self._binfile.write(self._BINFileSign)
                self._bFirstLDA = False
                need_seek = False # добавлено 28.07.18: установка на конец файла не нужна только при записи первого документа. из-за установки
                # на конец файла при записи первого документа почему-то добавляются 8 нулевых байт и файл получается повреждённым
            # пишем кол - во LDA документов(этот размер будет обновляться после записи каждого нового документа)
            self._LDACount += 1
            self._binfile.seek(self._LDAOffs + 4, 0)
            self._binfile.write(struct.pack('=i', self._LDACount))
            # пишем ID документа
            if need_seek: self._binfile.seek(0, 2) # для первого документа мы и так стоим в нужном месте и лишний seek() не нужен (см. выше)
            self._binfile.write(struct.pack('=i', docid))
            # пишем кол - во слов в данном документе
            slda = len(plda)
            self._binfile.write(struct.pack('i', slda))
            self._binfile.write(struct.pack(str(slda)+'I', *plda));
            #for dw in plda:
            #   self._binfile.write(struct.pack('I', dw));
            r = True
        except Exception:
            pass
        finally:
            self._lockbinfile.release()
        return r

    # добавляет словарь уникальных слов с идентификаторами
    def AddLDAWordmapBinary(self, pwm, swm):
        if self._bwrite: return False
        sWordFreq = '=Ii64pdqq' # под слово выделено 64 байта, из которых первый - реальный размер слова (для совместимости с Topic Miner на Delphi)
        r = False
        try:
            self._lockbinfile.acquire()
            self._binfile.seek(0, 2)
            # пишем размер словаря (кол-во слов, а не байт)
            self._binfile.write(struct.pack('i', swm))
            # пишем сам словарь
            for di in pwm:
                self._binfile.write(struct.pack(sWordFreq, di[0], di[1], di[2].encode('cp1251'), di[3], 0, 0))
            r = True
        except Exception:
            pass
        finally:
            self._lockbinfile.release()
        return r

    # добавляет словарь уникальных слов с идентификаторами
    # pwm - словарь: ключ - это код слова, далее идёт всё как обычно кол-во, слово, TF-IDF, 0.0
    def AddLDAWordmapBinary2(self, pwm):
        if self._bwrite: return False
        sWordFreq = '=Ii64pdqq'  # под слово выделено 64 байта, из которых первый - реальный размер слова (для совместимости с Topic Miner на Delphi)
        r = False
        try:
            self._lockbinfile.acquire()
            self._binfile.seek(0, 2)
            # пишем размер словаря (кол-во слов, а не байт)
            swm = len(pwm)
            self._binfile.write(struct.pack('i', swm))
            # пишем сам словарь
            for di in pwm:
                self._binfile.write(struct.pack(sWordFreq, di, pwm[di][0], pwm[di][1].encode('cp1251'), pwm[di][2], 0, 0))
            r = True
        except Exception:
            pass
        finally:
            self._lockbinfile.release()
        return r

    def GetLDADocumentsBinaryCount(self):
        if self._bwrite: return 0
        r = 0
        try:
            self._lockbinfile.acquire()
            self._binfile.seek(self._LDAOffs, 0)
            s, = struct.unpack('i', self._binfile.read(4))
            if s == 0:
                r, = struct.unpack('i', self._binfile.read(4))
        except Exception:
            pass
        finally:
            self._lockbinfile.release()
        return r

    def GetLDADocumentBinaryFirst(self):
        '''
        Получение информации о первом оцифрованном LDA-документе в виде кортежа:
        ID документа, размер документа в количестве слов (в байтах будет size*4)
        В случае неудачи возвращает -1,0
        '''
        docid = -1
        size = 0
        if self._bwrite: return docid, size
        try:
            self._lockbinfile.acquire()
            self._binfile.seek(self._LDAOffs + 4 + 4, 0)
            docid, = struct.unpack('i', self._binfile.read(4))
            size, = struct.unpack('i', self._binfile.read(4))
        except Exception:
            docid = -1
            size = 0
        finally:
            self._lockbinfile.release()
        return docid, size

    def GetLDADocumentBinaryNext(self):
        docid = -1
        size = 0
        if self._bwrite: return docid, size
        try:
            self._lockbinfile.acquire()
            docid, = struct.unpack('i', self._binfile.read(4))
            size, = struct.unpack('i', self._binfile.read(4))
        except Exception:
            docid = -1
            size = 0
        finally:
            self._lockbinfile.release()
        return docid, size

    def GetLDADocumentBinary(self, docsize):
        '''
        Возвращает оцифрованный LDA-документ
        :param docsize: размер документа в количестве слов (не байт)
        :return: оцифрованный LDA-документ в виде списка
        '''
        plda = []
        if self._bwrite: return plda
        try:
            self._lockbinfile.acquire()
            plda = list(struct.unpack(str(docsize) + 'I', self._binfile.read(docsize * 4)))
        except Exception:
            plda = []
        finally:
            self._lockbinfile.release()
        return plda

    def GetLDADocumentBinaryRaw(self, docsize):
        '''
        Возвращает оцифрованный LDA-документ
        :param docsize: размер документа в количестве слов (не байт)
        :return: оцифрованный LDA-документ в виде байтовой последовательности
        '''
        plda = None
        if self._bwrite: return plda
        try:
            self._lockbinfile.acquire()
            plda = self._binfile.read(docsize * 4)
        except Exception:
            plda = None
        finally:
            self._lockbinfile.release()
        return plda

    def GetLDAWordmapBinarySize(self):
        '''
        Определяет размер словаря в количестве слов (записей)
        :return:
        '''
        r = 0
        if self._bwrite: return 0
        try:
            self._lockbinfile.acquire()
            self._binfile.seek(self._LDAOffs, 0)
            s, = struct.unpack('i', self._binfile.read(4))
            if s == 0:
                doccnt, = struct.unpack('i', self._binfile.read(4))
                for i in range(doccnt):
                    self._binfile.seek(4, 1)
                    s, = struct.unpack('i', self._binfile.read(4))
                    self._binfile.seek(s * 4, 1)
                r, = struct.unpack('i', self._binfile.read(4))
        except Exception:
            r = 0
        finally:
            self._lockbinfile.release()
        return r

    def GetLDAWordmapBinary(self, swm):
        '''
        Загружает словарь из файла
        :param swm: размер словаря в количестве слов
        :return: словарь (список) в виде [код_слова, частота, слово, TF-IDF, 0, 0]
        '''
        r = []
        if self._bwrite: return r
        try:
            self._lockbinfile.acquire()
            if self._signature != self._BINFileSign: raise Exception
            sWordFreq = '=Ii64pdqq'
            for i in range(swm):
                waf = list(struct.unpack(sWordFreq, self._binfile.read(struct.calcsize(sWordFreq))))
                waf[2] = waf[2].decode('cp1251')
                r.append(waf)
        except Exception:
            r = 0
        finally:
            self._lockbinfile.release()
        return r

    def GetLDAWordmapBinary2(self, swm):
        '''
        Загружает словарь из файла
        :param swm: размер словаря в количестве слов
        :return: словарь (dict) в виде {key: код_слова}: [частота, слово, TF-IDF, 0, 0]
        '''
        r = {}
        if self._bwrite: return r
        try:
            self._lockbinfile.acquire()
            if self._signature != self._BINFileSign: raise Exception
            sWordFreq = '=Ii64pdqq'
            for i in range(swm):
                waf = list(struct.unpack(sWordFreq, self._binfile.read(struct.calcsize(sWordFreq))))
                waf[2] = waf[2].decode('cp1251')
                waf2 = [waf[1], waf[2], waf[3], waf[4], waf[5]]
                r[waf[0]] = waf2
        except Exception:
            r = 0
        finally:
            self._lockbinfile.release()
        return r
