import os
import codecs
import re
from collections import Counter
from collections import namedtuple

FOLDER = "data"
pattern = re.compile('<Links_DocUNID>(.*)</Links_DocUNID>')
from soup import make_soup, get_hrefs, get_headings

class Document():
    def __init__(self, html_file, folder):
        self.html_file = html_file
        self.folder = folder

    @property
    def xml_tree(self):
        if not self.tree:
            fname = os.path.join("data", dirname, "Properties.xml")
            tree = ET.parse(fname)
            self.tree = tree
        return self.tree

    @property
    def title(self):
        root = tree.getroot()
        return root.find('Subject').text

def make_dirlist():
    DirList = []
    for d in os.listdir(FOLDER):
        directory = os.path.join(FOLDER, d)
        if os.path.isdir(directory):
            DirList.append(d)
    return DirList


def find_links(DirList):
    LinkList = []
    Links = []
    for d in DirList:
            fname = os.path.join(FOLDER, d, "links.xml")
            for line in codecs.open(fname, encoding='utf8').readlines():
                match = re.match(pattern, line.strip())
                if match:
                    link= match.groups()[0]
                    LinkList.append(link)
                    #if link in DirList:
                #    print link
    print (len(LinkList))

def make_fnames(dir_list, limit = 1000*1000):
    htmls = []
    def gen_fnames(dir_list):
        for d in dir_list:
            dir_path = os.path.join(FOLDER, d)
            for fname in os.listdir(dir_path):
                if fname.endswith(".html"):
                    full_fname = os.path.join(dir_path, fname)
                    yield full_fname

    for i, fname in enumerate(gen_fnames(dir_list)):
            if i == limit:
                break
            else:
                htmls.append(fname)
    return htmls

def collect_headings(fnames, num=100):
    headings = []
    href_links = []
    for i, fname in enumerate(fnames):
            if not i%num:
                soup = make_soup(fname)
                for link in get_hrefs(soup):
                    href_links.append(link)
                for heading in get_headings(soup):
                    headings.append(heading)
                    #print (fname)
                    #print (heading)
    return href_links

def process():
    DirList = make_dirlist()
    print (len(DirList))
    fnames = make_fnames(DirList)
    print (len(fnames))
    results = []
    res = []
    for i, f in enumerate(fnames):
        if i> 100:
            break
        soup = make_soup(f)
        for href in get_hrefs(soup):
            spl = href[0].split('/')
            if '$file' in spl:
                name = spl[spl.index('$file')-1]
                result = name in DirList
                results.append(result)
                if result:
                    fname = spl[spl.index('$file')+1]
                    fname = re.sub('\.docx?', '.html', fname)
                    fullname = os.path.join(FOLDER, name, fname)
                    processed = process_one_url(href[0])
                    print ("Source:", f)
                    print ("source title:", parse_xml(
                    print ("Target:", fullname)
                    print ("Anchertext:", href[1])                    
                    print ("correspondence:", processed[0])
                    print ("full link:", processed[1])
                    exists = os.path.exists(fullname)
                    print ("Exists:", exists) 
                    if exists:
                       print ("title:", parse_xml(name))
                    print ("\n")
            else:
                elems = [elem for elem in spl if ":" in elem]
                if elems:
                    name = elems[-1].split(":")[-1]
                    result = name in DirList
                    results.append(result)
                    if result:
                        r = (name, href[1], process_one_url(href[0]))
                        # print (r)
                    else:
                        pass
                        #print (process_one_url(href[0]))
                        #print (href[0], name)
                        #print ("\n")
                else:
                    results.append(None)
    print (Counter(results))


def process_one_url(url):
    url = url.strip()
    spl = url.split('/')
    spl0 = re.split('/?#', url.strip())
    if len(spl0) == 1:
        if len(spl) < 5:
            return ("short", url)
        else:
            return ("simple", url)
    else:
            last = "".join([elem for elem in spl0[-1] if elem.isdigit()])
            previous = "".join([elem for elem in spl0[-2] if elem.isdigit()])
            isin = last in previous
            if isin:
                return ("coincide", url)
            if not isin:
                last_list = last.split("_")
                previous_list = previous.split("_")
                inter = set(last_list).intersection(set(previous_list))
                if inter:
                    return ("intersect", url)
                else:
                    return ("empty intersection", url)

def process_td():
    short_urls = []; simple_urls = []; empty_urls = []; coincide = []; intersects = []; empty_intersection = []
    with open('td', encoding="utf8") as fh:
        for l in fh.readlines():
            url = l.strip()
            result = process_one_url(url)

    print ("short urls", len(short_urls), "\n",
         "simple urls", len(simple_urls), "\n",
         "coincide", len(coincide), "\n",
         "intersects", len(intersects), "\n",
         "empty intesection", len(empty_intersection))

if __name__ == "__main__":
    process()
