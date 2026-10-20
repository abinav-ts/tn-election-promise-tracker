"""Fixed English stopword list for the BM25 tokeniser (spec 04 §4.4). Part of the run fingerprint."""

STOPWORDS: frozenset[str] = frozenset("""
a about above after again against all also am an and any are as at be because been before being below
between both but by can could did do does doing done down during each either etc few for from further
had has have having he her here hers herself him himself his how however i if in into is it its itself
just may me might more most must my myself no nor not now of off on once only or other our ours
ourselves out over own per same shall she should so some such than that the their theirs them
themselves then there these they this those through thus to too under until up upon us very via was
we were what when where whether which while who whom whose why will with within without would yet you
your yours yourself yourselves
""".split())
