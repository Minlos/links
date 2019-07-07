import re
from nltk.stem.snowball import RussianStemmer
from nltk import word_tokenize
import datetime as dt

PARAGRAPH = "\d\d?\.(\d\d?\.)?(\d\d?\.)?"

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
        

