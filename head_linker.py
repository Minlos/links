import os
import re
from utils import timeit, clean_text

"""Текущие проблемы:
1) Находит документ "Дополнительное соглашение к Договору банковского счета" по тексту "Заключает договоры и дополнительные соглашения к договорам банковских счетов клиентов дополнительных офисов московского региона".Требовать единственное число? То есть все-таки честно разбирать морфологию?
"""

def str_to_pattern_text(s):
    return "(\w*[\s\n\W]*)".join([re.escape(elem) for elem in s.split()])

@timeit
def collect_titles(index):
    return {doc.clean_title : doc for doc in index.values() if doc.clean_title}

@timeit
def compile_title_pattern(list_of_pattern_texts):
    total_pattern_text = "|".join(map(str_to_pattern_text, list_of_pattern_texts))
    return re.compile(total_pattern_text, re.MULTILINE | re.DOTALL | re.IGNORECASE)

@timeit
def add_head_links(index):
    title_to_doc = collect_titles(index)
    total_pattern = compile_title_pattern(title_to_doc.keys())
    for doc in index.values():
        add_links_to_doc(doc, total_pattern, title_to_doc)

@timeit
def add_links_to_doc(doc, pattern, title_to_doc):
    for match in re.finditer(pattern, doc.text):
        clean_title = clean_text(match[0])
        target_doc = title_to_doc.get(clean_title)
        #there are cases where target_doc is None, and it is worth investigating
        if target_doc and target_doc != doc:
             target_fname = os.path.join(target_doc.folder, target_doc.html_file)
             link_url = "../{}".format(target_fname)
             pattern = str_to_pattern_text(match[0])
             doc.get_soup()
             html_text = str(doc.soup)
             m = re.search(pattern, html_text)
             if m:
                found_text = html_text[m.start(): m.end()]
                replacement = "<a href={link}>{txt}</a>".format(link=link_url, txt=found_text) 
                html_text = html_text.replace(found_text, replacement)
                print (doc)
                print (replacement)
                


