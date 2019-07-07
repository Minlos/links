import os
import re
from bs4 import element
from collections import namedtuple

from utils import normalize, letters_only, clean_amendment, word_intersection
from documents import FOLDER

MARKER_TEXT = u'в следующей редакции'

"""Единственная функция, которую мы отсюда импортирируем, это add_links. Она обрабатывает все документы в индексе.

В функции add_links итеририруемся по всем документам и для каждого документа, который является "изменением и дополнением", генерируем гипотезы - пары (регулярное выражение, документ).
Гипотезы документов генерирует функция gen_matches следующим образом: если документ является "изменениями и дополнениями", она ищет возможные основные документы к этим изменениям и дополнениям  (проходит по всем заголовкам и находит относительно похожие).
Регулярные выражения в этих гипотезах порождаются так: находим в "изменениях и дополнениях" текст "в следующей редакции" и выделяем то, что стоит в кавычках после него. Кусок текста в кавычках разбиваем на фрагменты по разделителю параграфов (что-то вроде "2.3.14") и строим регулярку из содержимого параграфа. Разбивку на фрагменты и порождение регулярки осуществляет функция text_to_patterns. При этом мы работаем не с html, а с относительно чистым текстом (который возвращает атрибут .text у BeautifulSoup). Однако этот текст недостаточно чистый, все равно понадобились какие-то ухищрения для его нормализации. В основном работали функции clean_amendment (в частности, убирает нумерацию параграфов) и normalize, однако в результате и их оказалось недостаточно для некоторых случаев, поэтому я начал нормализовывать, просто оставляя строки только из букв.
Далее, когда мы породили гипотезы, основываясь на нормализованном тексте, нужно применить эти гипотезы к реальным html-документам.
process_target_html извлекает имя параграфа "изменений и дополнений", на который нужно сослаться (если в текущем html нет подходящего имени параграфа, будем ссылаться на документ в целом). 
modify_source_html модифицирует html-дерево (в формате BeutifulSoup) основного документа, в который нужно вставить ссылки. В последнем цикле сохраняем документы под новыми именами.
"""

def add_links(index):
    # folder, fname = ("D138D5D36436D0CA442579E900265CF8", "201_2012Н.html")
    # target = index.get((fname, folder))
    # if target:
    for target in index.values():
        modified = set()
        marker_text = MARKER_TEXT
        for pattern, source in gen_matches(index, target, marker_text):
            paragraph = process_target_html(pattern, target, marker_text)
            modify_source_html(pattern, source, target, paragraph)
            modified.add(source)
        for doc in modified:
            current_fname = os.path.join(FOLDER, doc.folder, doc.html_file)
            new_fname = current_fname.replace(".html", "_new.html")
            with open(new_fname, 'w') as fh:
                fh.write(doc.soup.prettify())
                print (new_fname)

def gen_matches(index, target_doc, marker_text):
       def text_to_patterns(txt):
            paragraph = "\d\d?\.\d\d?\.\d\d?\."
            for partition in re.split(paragraph, txt):
                for sentence in re.split('\.|:', partition):
                    if len(sentence)>20:
                        escaped = re.escape(sentence).replace("\ ", " ")
                        pattern_txt = "[\n\s]*" + "[\n\s]*".join(escaped.split())
                        yield re.compile(pattern_txt, re.DOTALL | re.MULTILINE)
        
       #следующего содержания
       marker_text = "[\n\s]*".join(marker_text.split())
       quoted_pattern = re.compile(u"{}:[\n\s]*«(.*?)»".format(marker_text), re.MULTILINE | re.DOTALL)
       if target_doc.is_amendment:
             sources = find_sources(index, target_doc)
             for match in re.finditer(quoted_pattern, target_doc.text):
                     txt = clean_amendment(match[1])
                     for source in sources:
                         found = letters_only(txt) in letters_only(normalize(source.text))
                         if found:
                            for pattern in text_to_patterns(txt):
                                yield (pattern, source)

def find_sources(index, amendment):
    """Given an amendment ("изменения и дополнения") document, which will be the target of the links,
       find the best sources of the links - that is, the documents the titles of which contain more or less
       the same bag of words. We are not trying to find only one source"""
    the_least_intersection = 10
    # the first value is for soring, two other numbers for debugging only.
    # the function returns only documents
    Source = namedtuple("Source", "sorting_key intersection_len intersection_to_source_title source_doc")
    possible_sources = []
    for doc in index.values():
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


def modify_source_html(pattern, source, target, paragraph):
    def add_link_to_element(elem, link_url):
       modified = False
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
               elem.clear()
               elem.append(new_tag)

    source.get_soup()
    for p in source.soup.find_all('p'):
        if re.search(pattern, p.text):
            target_fname = os.path.join(target.folder, target.html_file)
            link_url = "../{}#{}".format(target_fname, paragraph or "")
            add_link_to_element(p, link_url)


def process_target_html(pattern, target, marker_text):
    """Unofortunately, we can not use construction like 
         target.soup.find('p', text=pattern)
    because it can not find text inside some structure of span's inside"""
    
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
                    if prev and prev.a:
                        name = prev.find('a').get('name')
                return name
            else:
                elem = previous
    
    target.get_soup()
    for elem in target.soup.find_all('p'):
        match = re.search(pattern, elem.text)
        if match:
            return find_target(elem, target=marker_text)



