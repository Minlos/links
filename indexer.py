import pickle
from multiprocessing import Pool, cpu_count
from utils import timeit
from documents import Docs, Document

class Indexer():
    def __init__(self, num_of_docs=100):
        self.num_of_docs=num_of_docs
        self.index = {}
        self.pickle_name = "index"

    def pickle(self, name='default'):
        with open("{}_{}".format(self.pickle_name, name), "wb") as fh:
            pickle.dump(self.index, fh)

    def unpickle(self, name='default'):
        with open("{}_{}".format(self.pickle_name, name), "rb") as fh:
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

