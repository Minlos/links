import pdb
import argparse
import codecs
import copy
import math
import os
import pickle
import re
import urllib
import spacy
from bs4 import BeautifulSoup, element
from collections import Counter, namedtuple
from multiprocessing.dummy import Pool as DummyPool
from multiprocessing import Pool, cpu_count
from nltk.stem.snowball import RussianStemmer
from nltk import word_tokenize
import datetime as dt
import xml.etree.ElementTree as ET

FOLDER = "data"
DEFAULT_NUMBER = 140
PARAGRAPH = "\d\d?\.(\d\d?\.)?(\d\d?\.)?"

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--number", help="number of documents to process", default=DEFAULT_NUMBER, type=int)
    args = parser.parse_args()
    return args

def clean_text(text):
    stemmer = RussianStemmer()
    stemmed = [stemmer.stem(word) for word in word_tokenize(text)]
    clean = [word for word in stemmed if word.isalpha() or word.isdigit()]
    return " ".join(clean)

def normalize(text):
    return re.sub('\s+', " ", text.strip().replace("\n", " "))

def letters_only(text):
    return "".join([elem for elem in text if elem.isalpha()])

def clean_amendment(text):
    text = normalize(text.strip('•'))
    match_pattern = PARAGRAPH + "(?P<text>.*)"
    match = re.match(match_pattern, text)
    if match:
        text = match.group('text').strip()
    match = re.match("\S\)(.*)", text)
    if match:
        text = match[1].strip()
    return text.rstrip(";")


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
                self.bookmark = "no"
            elif previous[-2] == "$file":
                self.target_folder = previous[-3]
            elif ":" in previous[-2]:
                self.target_folder = previous[-2].split(":")[1]
            else:
                self.bookmark = "no"
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
    def __init__(self, a_tuple):
        html_file, folder = a_tuple
        self.html_file = html_file
        self.folder = folder
        self.soup = None
        self.__tree = None
        self.title = None
        self.clean_title = None
        self.get_soup()
        self.get_title()
        self.get_text()
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
        # self.links = list(self.all_links())
        self.soup = None # the soup object is not trivially pickled because of the recursion, so we'd better null it
       
    def __repr__(self):
        return "<Document: folder {f}; html_file: {html}; title: {t}; processed title: {ct}>".format(f=self.folder, t=self.title, ct=self.clean_title, html=self.html_file)

    def get_soup(self):
        if not self.soup:
            fullname = os.path.join(FOLDER, self.folder, self.html_file)
            doc = codecs.open(fullname).read()
            self.soup = BeautifulSoup(doc, "html.parser")


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
    def __init__(self, limit=140):
        self.dirs = []
        self.limit = limit
        for d in os.listdir(FOLDER):
            fold = os.path.join(FOLDER, d)
            if os.path.isdir(fold):
                self.dirs.append(d)

    def __iter__(self):
        i = 0
        for d in self.dirs:
            dir_path = os.path.join(FOLDER, d)
            # we are looking for the "main" html-file, ignoring its enclosures (for example, see 06D37A5F0169035CC32574110043F35D)
            fnames = [fname for fname in os.listdir(dir_path) if fname.endswith(".html")]
            #the are folders without any html-docs, such as E476185581C0B1B3C3257552002DBA1C
            if fnames:
                fname = sorted(fnames, key=len)[0]
                if i<self.limit:
                    i +=1
                    yield (fname, d)


class Indexer():
    def __init__(self, num_of_docs=100):
        self.num_of_docs=num_of_docs
        self.index = {}

    def pickle(self, name='default'):
        with open("ind_{}".format(name), "wb") as fh:
            pickle.dump(self.index, fh)

    def unpickle(self, name='default'):
        with open("ind_{}".format(name), "rb") as fh:
            self.index = pickle.load(fh)


    def maybe_doc(self, a_tuple):
        if a_tuple not in self.index:
            return Document(a_tuple)

    @timeit
    def run(self):
        docs = Docs(self.num_of_docs)
        processes = cpu_count()
        chunksize = 10
        pool = Pool(processes=processes)
        for maybe_doc in pool.map(self.maybe_doc, docs, chunksize=chunksize):
            if maybe_doc:
                self.index[(maybe_doc.html_file, maybe_doc.folder)] = maybe_doc
        pool.close()
        pool.join()
    

    @timeit
    def process_links(self):
        local_index = copy.deepcopy(self.index)
        for doc in self.index.values():
            previous = None
            for link in doc.links:
                if (previous is not None) and (previous.url == link.url) and  (previous.anchor_text != link.anchor_text) and previous.anchor_text:
                    link.anchor_text = " ".join([previous.anchor_text, link.anchor_text])
                    previous.is_redundant = True
                previous = link
                if link.target_folder == doc.folder:
                    link.type = "self-reference"
                elif link.target_file_exists:
                    # target_doc = self.index.get(link.target_folder)
                    target_doc = local_index.get((link.target_file, link.target_folder))
                    if target_doc is None:
                        target_doc = Document((link.target_file, link.target_folder))
                        local_index[(link.target_file, link.target_folder)] = target_doc
                    target_doc.incoming_links.append(doc)
                    if target_doc.is_amendment:
                            if doc.is_amendment:
                                link.type = "amendments to amendments"
                            else:
                                intersection = word_intersection(target_doc.main_doc_title.split(), doc.clean_title.split())
                                link.type = "to amendments"
                                link.intersection_len = len(intersection)
                                link.anchor_text_in_target_text = link.anchor_text in target_doc.clean_text
                    else:
                            intersection = word_intersection(link.anchor_text.split(), target_doc.clean_title.split())
                            link.type = "to document"
                            link.intersection_len = len(intersection)
        for key, value in local_index.items():
            if key not in self.index:
                self.index[key]=value


    def find_sources(self, amendment):
        """Given an amendment ("изменения и дополнения") document, which will be the target of the links,
           find the best sources of the links - that is, the documents the titles of which contain more or less
           the same bag of words. We are not trying to find only one source"""
        the_least_intersection = 10
        # the first value is for soring, two other numbers for debugging only.
        # the function returns only documents
        Source = namedtuple("Source", "sorting_key intersection_len intersection_to_source_title source_doc")
        possible_sources = []
        for doc in self.index.values():
            if not doc.is_amendment:
                intersection_len = len(word_intersection(amendment.main_doc_title.split(), doc.clean_title.split()))
                if intersection_len > the_least_intersection:
                        # we will not compare the intersection length to the length of the amendment title, because it 
                        # also contains some part as "введенную в действие приказом от ...."
                        doc_title_len = len(set(doc.clean_title.split()))
                        prop = intersection_len / doc_title_len
                        maybe_source = Source(intersection_len+prop, intersection_len, prop, doc)
                        possible_sources.append(maybe_source)
        sorted_sources = sorted(possible_sources, key=lambda x: x.sorting_key, reverse=True)
        if sorted_sources:
            # we get all documents with the same highest score
            the_best_match = sorted_sources[0].sorting_key
            sources = [elem.source_doc for elem in sorted_sources if elem.sorting_key == the_best_match]
        else:
            sources = []
        return sources


    @timeit
    def add_link_to_amendments(self):
        
        def text_to_patterns(txt):
            paragraph = "\d\d?\.\d\d?\.\d\d?\."
            for partition in re.split(paragraph, txt):
                for sentence in re.split('\.|:', partition):
                    if len(sentence)>20:
                        escaped = re.escape(sentence).replace("\ ", " ")
                        pattern_txt = ".*" + ".*".join(escaped.split())
                        yield re.compile(pattern_txt, re.DOTALL | re.MULTILINE)
        
        def gen_matches(target_doc):
           #следующего содержания
           quoted_pattern = re.compile(u"в следующей редакции:\n?\s?\n?«(.*?)»", re.MULTILINE | re.DOTALL)
           if target_doc.is_amendment:
                 sources = self.find_sources(target_doc)
                 for match in re.finditer(quoted_pattern, target.text):
                         txt = clean_amendment(match[1])
                         #if u'Банк в установленном порядке посредством Терминала' in txt:
                         #   print (txt)
                         for source in sources:
                             found = letters_only(txt) in letters_only(normalize(source.text))
                             if found:
                                for pattern in text_to_patterns(txt):
                                    #print (pattern)
                                    yield (pattern, source)
                             

        def add_link_to_element(elem, link_url):
           modified = False
           # first, I tried a simplier construction like
           # if elem.a: elem.a["href"] = link_url
           # but it modified only part of the links
           for a in elem.find_all('a'):
                a["href"] = link_url
                modified = True
           if not modified:
               txt = elem.text
               new_tag = source.soup.new_tag("a", href=link_url)
               new_tag.string = txt
               child = list(elem.children)[0]
               # a rather cruel way of modification, that does not preserve the inner structure, if present
               if isinstance(child, element.Tag):
                   child.clear()
                   child.append(new_tag)
               else:
                   print ('can not modify')


        def modify_source_html(pattern, source, target, paragraph):
            source.get_soup()
            # attention!
            # the construction source.soup.find('p', text=pattern) does not return all the matches
            for p in source.soup.find_all('p'):
                if re.search(pattern, p.text):
                    target_fname = os.path.join(target.folder, target.html_file)
                    link_url = "../{}#{}".format(target_fname, paragraph or "")
                    add_link_to_element(p, link_url)
                    #print(link_url, "\n")


        def find_target(elem, target):    
            """The target text might be not precisely in the previous paragraph, so we loop to find it"""
            while True and elem:
                previous = elem.find_previous_sibling()
                if previous and (target in previous.text):
                    name = ""
                    if previous.a:
                        name = previous.find('a').get('name')
                    else:
                        # additionally, we can shift left exactly once, in case the target paragraph does not 
                        # contain name
                        prev = previous.find_previous_sibling()
                        if prev.a:
                            name = prev.find('a').get('name')
                    return name
                else:
                    elem = previous


        def process_target_html(pattern, target, marker_text):
            """Unofortunately, we can not use construction like 
                 target.soup.find('p', text=pattern)
            becaouse it can not find text inside some structure of span's inside"""
            target.get_soup()
            for elem in target.soup.find_all('p'):
                match = re.search(pattern, elem.text)
                if match:
                    return find_target(elem, target=marker_text)


        for target in self.index.values():
            marker_text = u'в следующей редакции'
            modified = set()
            for pattern, source in gen_matches(target):
                paragraph = process_target_html(pattern, target, marker_text)
                modify_source_html(pattern, source, target, paragraph)
                modified.add(source)
            for doc in modified:
                current_fname = os.path.join(FOLDER, doc.folder, doc.html_file)
                new_fname = current_fname.replace(".html", "_new.html")
                with open(new_fname, 'w') as fh:
                    fh.write(doc.soup.prettify())
                    print (new_fname)



if __name__ == "__main__":
    args = parse_args()

    s = Indexer(args.number)
    s.run(); 
    s.pickle()
    s.unpickle()
    #s.process_links(); s.pickle('links')
    #s.unpickle('links')
    s.add_link_to_amendments()
