import pandas as pd
import numpy as np
from planarity import is_planar

def pmfg(df):
    n = len(df)
    A = np.zeros([n,n])
    rho = df.as_matrix()

    rholist = []
    for i in range(0, n):
        for j in range(i+1, n):
            rholist.append([rho[i][j], i, j])
    rholist = np.array(rholist)
    rholist = rholist[rholist[:,0].argsort()].tolist()
    rholist = [rholist[len(rholist)-i-1] for i in range(len(rholist))]

    control = 0
    edgelist = []
    for t in range(0, len(rholist)):
        if control <= 3*(n-2)-1:
            i, j = rholist[t][1], rholist[t][2]
            A[i][j], A[j][i] = 1, 1
            edgelist.append((str(i),str(j)))

            if is_planar(edgelist) == False:
                A[i][j], A[j][i] = 0, 0
                edgelist = edgelist[:-1]
            else:
                control += 1
    return pd.DataFrame(data=A, columns=df.columns, index=df.index)