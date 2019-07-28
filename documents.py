import codecs
import os
import re
import dateparser
from bs4 import BeautifulSoup, element
import xml.etree.ElementTree as ET
from utils import clean_text

FOLDER = "data"

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



class Document():
    def __init__(self, a_tuple):
        html_file, folder = a_tuple
        self.html_file = html_file
        self.folder = folder
        self.soup = None
        self.__tree = None
        self.title = None
        self.clean_title = None
        self.order_titles = []
        self.get_soup()
        self.get_title()
        self.get_text()
        self.is_amendment = self.clean_title.startswith(u"изменен и дополнен")
        self.is_order = self.clean_title.startswith(u'приказ')
        if self.is_amendment:
            spl = re.split(u' к|во? ', self.clean_title)
            if len(spl)>1:
                self.main_doc_title = spl[1]
            else:
                self.main_doc_title = None
        else:
            self.main_doc_title = None
        if self.is_order:
            self.get_order_titles()
        self.incoming_links = []
        # self.links = list(self.all_links())
        self.soup = None # the soup object is not trivially pickled because of the recursion, so we'd better null it

       
    def __repr__(self):
        return "<Document: path: {path}; folder {f}; html_file: {html}; title: {t}; processed title: {ct}>".format(f=self.folder, t=self.title, ct=self.clean_title, html=self.html_file, path=os.path.join(self.folder, self.html_file))


    def get_order_titles(self):
        self.order_titles = []
        num, date = self.extract_params()
        if num and date:
            for bank in (u"Банка", u"ОАО Банк ВТБ", ""):
                title = u"Приказ {bank} от {date} № {num}".format(bank=bank, date=date, num=num)
                self.order_titles.append(title)

    def extract_params(self):
        """extract date and number"""
        order_num = None
        formatted_date = None
        spl = self.title.split("№")
        if len(spl)==2:
            order_num = spl[1]
        if order_num:
            for elem in self.soup.find_all('p'):
                if order_num in elem.text:
                    date= re.split(order_num, elem.text)[0]
                    parsed_date = dateparser.parse(date.strip())
                    if parsed_date is not None:
                        formatted_date = parsed_date.date().isoformat()
        return (order_num, formatted_date)

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


