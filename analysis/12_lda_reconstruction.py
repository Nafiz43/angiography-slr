"""Reconstructed (back-calculated) LDA over the full texts of the included studies.
The original topic-model run was lost in a data migration; this script reruns the procedure in Methods 2.4.
Usage: python3 analysis/12_lda_reconstruction.py <fulltext_dir> analysis-results/lda_reconstruction.json   (needs gensim, nltk)
<fulltext_dir> holds <RID>.md for every included study (not redistributed for copyright).
Settings follow Methods 2.4: lowercase, strip URLs/HTML/refs, stopwords, WordNet lemmas, bigrams,
drop terms in <5% (or >50%) of docs, K=5..20 by C_v coherence, symmetric priors 1/K, 20 passes, 100 iterations, seed 42.
Each topic lists the gaps whose coding correlates with its document weight at r >= 0.2."""
import re,json,sys,math,numpy as np
from pathlib import Path
from gensim.corpora import Dictionary
from gensim.models import LdaModel, CoherenceModel, Phrases
from gensim.models.phrases import Phraser
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
SLR=Path(__file__).resolve().parents[1]
FT,OUT=Path(sys.argv[1]),Path(sys.argv[2])
ids=sorted(p.stem for p in (SLR/'extraction/out').glob('R*.json'))
G=[f'G{i}' for i in range(1,13)]
EX={r:json.load(open(SLR/f'extraction/out/{r}.json')) for r in ids}
Y=np.array([[EX[r]['gaps'][g]['status'] in('documents','both') for g in G] for r in ids],float)
END=re.compile(r'^#+.*(reference|acknowledg|bibliograph|funding|declaration|conflict|author contrib|data availab|code availab|supplement|ethic)',re.I)
def body(r):
    out=[]
    for l in (FT/f'{r}.md').read_text(errors='replace').split('\n'):
        if END.match(l): break
        out.append(l)
    return ' '.join(out)
SW=set(stopwords.words('english'))|set('et al fig figure table also may might use used using study studies method proposed paper work however would could one two well show result results based shown thus hence respectively furthermore moreover therefore'.split())
L=WordNetLemmatizer()
def prep(t):
    t=t.lower(); t=re.sub(r'https?://\S+|www\.\S+|<[^>]+>|\[[0-9,\s\-–]+\]|\*\*?|\$[^$]*\$',' ',t)
    return [L.lemmatize(w) for w in re.findall(r'[a-z][a-z\-]+',t) if w not in SW and len(w)>2]
docs=[prep(body(r)) for r in ids]
bg=Phraser(Phrases(docs,min_count=5,threshold=10)); docs=[bg[d] for d in docs]
D=Dictionary(docs); D.filter_extremes(no_below=math.ceil(.05*len(docs)),no_above=.5,keep_n=None)
bow=[D.doc2bow(d) for d in docs]
res={}
for K in range(5,21):
    m=LdaModel(bow,id2word=D,num_topics=K,alpha=[1/K]*K,eta=1/K,passes=20,iterations=100,random_state=42)
    res[K]=(CoherenceModel(model=m,texts=docs,dictionary=D,coherence="c_v",processes=1).get_coherence(),m)
    print(K,round(res[K][0],4),flush=True)
K=max(res,key=lambda k:res[k][0]); m=res[K][1]
th=np.array([[dict(m.get_document_topics(b,minimum_probability=0)).get(k,0) for k in range(K)] for b in bow])
R=np.nan_to_num(np.corrcoef(th.T,Y.T)[:K,K:]); dom=th.argmax(1)
topics=[{'k':k+1,'terms':[w for w,_ in m.show_topic(k,10)],'n_dominant':int((dom==k).sum()),
         'rep':[ids[i] for i in np.argsort(-th[:,k])[:3]],
         'gaps':{G[j]:round(float(R[k,j]),2) for j in np.argsort(-R[k]) if R[k,j]>=.2}} for k in range(K)]
json.dump({"coherence":{k:round(v[0],3) for k,v in res.items()},'bestK':K,'vocab':len(D),'docs':len(docs),
           'gap_best_r':{G[j]:round(float(R[:,j].max()),2) for j in range(12)},'topics':topics},open(OUT,'w'),indent=1)
print('best',K)
