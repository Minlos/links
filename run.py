import argparse
from indexer import Indexer
from linker import add_links

DEFAULT_NUMBER = 140

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--number", help="number of documents to add to index", default=DEFAULT_NUMBER, type=int)
    parser.add_argument("-i", "--index", help="add documents to index", action='store_true')
    parser.add_argument("-l", "--links", help="add links", action='store_true')
    args = parser.parse_args()
    return args

if __name__ == "__main__":
    args = parse_args()

    s = Indexer(args.number)
    if args.index:
        s.run(); 
        s.pickle()
    if  args.links:
        s.unpickle()
        add_links(s.index)
