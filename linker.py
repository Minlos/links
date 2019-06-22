import argparse
import codecs
import copy
import os
import pickle
import re
import urllib
import spacy
from bs4 import BeautifulSoup
from collections import Counter
from nltk.stem.snowball import RussianStemmer
from nltk import word_tokenize
import datetime as dt
import xml.etree.ElementTree as ET

FOLDER = "data"
DEFAULT_NUMBER = 140

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--number", help="number of documents to process", default=DEFAULT_NUMBER)
    args = parser.parse_args()
    return args

def clean_text(text):
    stemmer = RussianStemmer()
    stemmed = [stemmer.stem(word) for word in word_tokenize(text)]
    clean = [word for word in stemmed if word.isalpha() or word.isdigit()]
    return " ".join(clean)

def common_subsequence(X, Y):
    return [x for x,y in zip(X, Y) if x==y]


def word_intersection(X, Y):
    return set(X).intersection(Y)


def timeit(func):
    def timed(*args, **kwargs):
        begin = dt.datetime.now()
        result = func(*args, *kwargs)
        end = dt.datetime.now()
        delta = (end - begin).seconds
        minutes = delta // 60
        seconds = delta % 60
        print ("{m} minutes, {s} seconds in {f}".format(f=func.__name__, m=minutes, s=seconds))
    return timed
        


class Link():
    def __init__(self, url, anchor_text):
        self.url = url.strip()
        self.anchor_text = clean_text(anchor_text.replace('\n', ' '))
        self.target_folder = None
        self.target_file = None
        self.__parse_url()
        self.target_folder_exists = self.if_folder_exists()
        self.target_file_exists = self.if_file_exists()
        self.is_redundant = False
        self.type = None
        self.intersecion_len = None
        self.anchor_text_in_target_text = None
        self.target = None

    def if_folder_exists(self):
        if not self.target_folder:
            return False
        fullname = os.path.join(FOLDER, self.target_folder)
        return os.path.exists(fullname)

    def if_file_exists(self):
         if not self.target_file:
             return False
         if not self.target_folder:
            return False
         fullname = os.path.join(FOLDER, self.target_folder, self.target_file)
         return os.path.exists(fullname)

    def __parse_url(self):
        spl = re.split('/?#', self.url)
        if len(spl) == 1:
            self.bookmark = "no"
        else:
            bookmark_digits = "".join([elem for elem in spl[-1] if elem.isdigit()])
            previous = spl[-2].split("/")
            if len(previous) == 1:
                print (self.url, previous)
                self.bookmark = "no"
            elif previous[-2] == "$file":
                self.target_folder = previous[-3]
            else:
                self.target_folder = previous[-2].split(":")[1]
            fname = urllib.request.unquote(previous[-1])
            self.target_file = re.sub('\.docx?', '.html', fname)
            previous_digits = "".join([elem for elem in previous[-1] if elem.isdigit()])
            isin = bookmark_digits in previous_digits
            if isin:
                self.bookmark = "trivial"
            else:
                self.bookmark = "nontrivial"

    def __str__(self):
        return "<Link; Url: {u}; Target folder: {d}; Exists? {de}; Target file: {f}; Exists? {fe}; Bookmark: {b}; Anchortext: {a}>".format(u=self.url, a=self.anchor_text, b=self.bookmark, d=self.target_folder, f=self.target_file, de=self.target_folder_exists, fe=self.target_file_exists)

class Document():
    def __init__(self, html_file, folder):
        self.html_file = html_file
        self.folder = folder
        self.__soup = None
        self.__tree = None
        self.title = None
        self.clean_title = None
        self.get_title()
        # self.get_text()
        self.is_amendment = self.clean_title.startswith(u"изменен и дополнен")
        if self.is_amendment:
            spl = re.split(u' к|во? ', self.clean_title)
            if len(spl)>1:
                self.main_doc_title = spl[1]
            else:
                self.main_doc_title = None
        else:
            self.main_doc_title = None
        self.incoming_links = []
       
    def __repr__(self):
        return "<Document: folder {f}; title: {t}; processed title: {ct}>".format(f=self.folder, t=self.title, ct=self.clean_title)

    @property
    def soup(self):
        if not self.__soup:
            fullname = os.path.join(FOLDER, self.folder, self.html_file)
            doc = codecs.open(fullname).read()
            self.__soup = BeautifulSoup(doc, "html.parser")
        return self.__soup


    @property
    def properties_tree(self):
        if not self.__tree:
            fname = os.path.join(FOLDER, self.folder, "Properties.xml")
            tree = ET.parse(fname)
            self.__tree = tree
        return self.__tree

    def get_title(self):
        root = self.properties_tree.getroot()
        self.title = root.find('Subject').text
        self.clean_title = clean_text(self.title)
    
    def get_text(self):
        self.text = self.soup.text
        self.clean_text = clean_text(self.text)

    def all_links(self):
        for a in self.soup.find_all('a', href=True):
            if a['href'].startswith("http"):
                link = Link(a['href'], a.text)
                yield link

       

class Docs():
    def __init__(self):
        self.dirs = []
        for d in os.listdir(FOLDER):
            fold = os.path.join(FOLDER, d)
            if os.path.isdir(fold):
                self.dirs.append(d)

    def __iter__(self):
        for d in self.dirs:
            dir_path = os.path.join(FOLDER, d)
            for fname in os.listdir(dir_path):
                if fname.endswith(".html"):
                    doc = Document(fname, d)
                    yield doc

class Indexer():
    def __init__(self, num_of_docs=100):
        self.num_of_docs=num_of_docs
        self.index = {}

    def pickle(self):
        with open("index_{}".format(self.num_of_docs), "wb") as fh:
            pickle.dump(self.index, fh)

    def unpickle(self):
        with open("index_{}".format(self.num_of_docs), "rb") as fh:
            self.index = pickle.load(fh)

    @timeit
    def run(self):
        docs = Docs()
        for i, doc in enumerate(docs):
            if i> self.num_of_docs:
                break
            self.index[doc.folder] = doc


    @timeit
    def process_links(self):
        local_index = copy.copy(self.index)
        for doc in self.index.values():
            previous = None
            for link in doc.all_links():
                if (previous is not None) and (previous.url == link.url) and  (previous.anchor_text != link.anchor_text) and previous.anchor_text:
                    link.anchor_text = " ".join([previous.anchor_text, link.anchor_text])
                    previous.is_redundant = True
                previous = link
                if link.target_folder == doc.folder:
                    link.type = "self-reference"
                elif link.target_file_exists:
                    # target_doc = self.index.get(link.target_folder)
                    target_doc = local_index.get(link.target_folder)
                    if target_doc is None:
                        target_doc = Document(link.target_file, link.target_folder)
                        local_index[link.target_folder] = target_doc
                    target_doc.incoming_links.append(doc)
                    if target_doc.is_amendment:
                            if doc.is_amendment:
                                link.type = "amendments to amendments"
                            else:
                                intersection = word_intersection(target_doc.main_doc_title.split(), doc.clean_title.split())
                                link.type = "to amendments"
                                link.intersection_len = len(intersection)
                                #link.anchor_text_in_target_text = link.anchor_text in target_doc.clean_text
                    else:
                            intersection = word_intersection(link.anchor_text.split(), target_doc.clean_title.split())
                            link.type = "to document"
                            link.intersection_len = len(intersection)
            #for link in doc.all_links():
            #    print (link.type, link.target_file_exists)

    @timeit
    def find_amendments(self):
         for obj in self.index.values():
            if obj.is_amendment:
                possible_sources = []
                for elem in self.index.values():
                    if not elem.is_amendment:
                        intersection = word_intersection(obj.main_doc_title.split(), elem.clean_title.split())
                        if len(intersection)>10:
                            maybe = (len(intersection), len(intersesion)/len(obj.clean_title.split()), elem)
                            possible_sources.append(maybe)
                print (obj.main_doc_title)
                sorted_sources = sorted(possible_sources, key=lambda x: -x[0])
                if sorted_sources:
                    source = sorted_sources[0]
                    print (obj in source.incoming_links)
                print ("\n")


if __name__ == "__main__":
    args = parse_args()
    s = Indexer(args.number)
    s.run(); s.pickle()
    #s.unpickle()
    #s.process_links(); s.pickle()
    #s.find_amendments(); s.pickle()
