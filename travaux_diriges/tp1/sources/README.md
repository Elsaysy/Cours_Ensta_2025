
# TD1

`pandoc -s --toc README.md --css=./github-pandoc.css -o README.html`

## lscpu

*lscpu donne des infos utiles sur le processeur : nb core, taille de cache :*

```
Architecture:                        x86_64
CPU op-mode(s):                      32-bit, 64-bit
Byte Order:                          Little Endian
Address sizes:                       39 bits physical, 48 bits virtual
CPU(s):                              4
On-line CPU(s) list:                 0-3
Thread(s) per core:                  1
Core(s) per socket:                  4
Socket(s):                           1
NUMA node(s):                        1
Vendor ID:                           GenuineIntel
CPU family:                          6
Model:                               183
Model name:                          13th Gen Intel(R) Core(TM) i9-13900HX
Stepping:                            1
CPU MHz:                             2419.200
BogoMIPS:                            4838.40
Hypervisor vendor:                   KVM
Virtualization type:                 full
L1d cache:                           192 KiB
L1i cache:                           128 KiB
L2 cache:                            8 MiB
L3 cache:                            144 MiB
NUMA node0 CPU(s):                   0-3
```


## Produit matrice-matrice

### Effet de la taille de la matrice

  n            | MFlops
---------------|--------
1023           | 873.185
1024 (origine) | 212.4
1025           | 825.117

L'analyse des résultats montre une anomalie significative pour la dimension 1024. Cette dimension, qui est une puissance de 2 (2¹⁰), présente un temps d'exécution environ quatre fois plus élevé que les dimensions adjacentes.

Ce phénomène s'explique par le comportement du cache :
- Lorsque la taille de la matrice est une puissance de 2 (1024), les éléments de la même colonne dans différentes lignes sont mappés aux mêmes emplacements dans le cache
- Cela provoque des conflits de cache systématiques (cache conflicts)
- Ces conflits entraînent de nombreux défauts de cache (cache misses)
- Par conséquent, le processeur doit fréquemment recharger les données depuis la mémoire principale

En revanche, les dimensions 1023 et 1025 évitent ces conflits systématiques, ce qui explique leurs meilleures performances.

### Permutation des boucles

`g++ -O3 -march=native -fopenmp -o TestProductMatrix.exe TestProductMatrix.cpp ProdMatMat.cpp Matrix.cpp;./TestProductMatrix.exe 1024`


  ordre           | time    | MFlops  | MFlops(n=2048)
------------------|---------|---------|----------------
i,j,k (origine)   | 4.12097 | 521.112 |   459.897
j,i,k             | 4.22567 | 508.199 |   302.221
i,k,j             | 8.13349 | 264.030 |   137.175
k,i,j             | 8.14009 | 263.816 |   151.489
j,k,i             | 0.21903 | 9804.60 |   6359.45
k,j,i             | 0.30090 | 7136.81 |   4602.32


Pour l'ordre des boucles (j,k,i) dans la multiplication matricielle :

La meilleure performance s'explique par l'accès optimal à la mémoire cache :

La boucle interne sur i :
- Accède aux éléments de C[i][j] en colonne
- Accède aux éléments de A[i][k] en colonne
- B[k][j] reste constant et peut être gardé en registre

La boucle du milieu sur k :
- Permet de réutiliser B[k][j] qui est déjà en cache
- Change la colonne de A à chaque itération

La boucle externe sur j :
- Change la colonne de B et C
- Maximise la réutilisation du cache

Cette organisation minimise les défauts de cache et optimise l'utilisation des registres du processeur.



### OMP sur la meilleure boucle

`g++ -O3 -march=native -fopenmp -o TestProductMatrix.exe TestProductMatrix.cpp ProdMatMat.cpp Matrix.cpp; $env:OMP_NUM_THREADS=8; ./TestProductMatrix.exe 4096`

  OMP_NUM   | MFlops  | MFlops(n=2048) | MFlops(n=512)  | MFlops(n=4096)
------------|---------|----------------|----------------|---------------
1           | 517.824 |    416.504     |    1371.24     |   325.653
2           | 1114.01 |    1052.23     |    3505.73     |   646.478
3           | 1619.95 |    1614.19     |    3642.85     |   1106.15
4           | 2218.43 |    1872.89     |    6390.79     |   1158.46
5           | 3073.63 |    2680.15     |    8439.35     |   1769.36
6           | 3660.71 |    3138.76     |    9405.82     |   1783.31
7           | 3811.11 |    3593.81     |    10574.3     |   2118.57
8           | 4531.77 |    3604.24     |    11008.4     |   1773.54    

![](TP1.png)

Effets de l'accélération parallèle :
- Une amélioration significative des performances avec l'augmentation du nombre de threads
- Pour n=1024, nous observons une accélération superlinéaire (8.75x avec 8 threads)
- L'efficacité du parallélisme est démontrée sur toutes les tailles de matrices

Performance selon la taille des matrices :
- Meilleure performance pour n=512 :
  - 11008.4 MFlops avec 8 threads
  - Excellent ratio cache/calcul
- Performance décroissante avec l'augmentation de n :
  - n=4096 montre les performances les plus faibles
  - Seulement 1773.54 MFlops avec 8 threads
  - Cette baisse est due aux limitations de la mémoire cache

La plus petite matrice (n=512) offre les meilleures performances en raison d'une meilleure utilisation du cache, tandis que les grandes matrices souffrent des limitations de la bande passante mémoire.

### Produit par blocs

  szBlock      | MFlops  | MFlops(n=2048) | MFlops(n=512)  | MFlops(n=4096)
---------------|---------|----------------|----------------|---------------
origine(=max)  | 7646.32 |    5666.75     |    14140.9     |    4476.68
32             | 8012.98 |    7262.19     |    9622.31     |    7626.21
64             | 11963.1 |    8596.14     |    12932.1     |    9353.76
128            | 14432.1 |    11767.9     |    13364.4     |    10903.7
256            | 11560.0 |    14124.8     |    8909.06     |    12784.5
512            | 9443.52 |    11462.4     |    14140.9     |    11876.3
1024           | 7646.32 |    7952.49     |    14133.7     |    8251.09

Performance optimale :
- Pour n=1024 : meilleure performance avec szBlock=128 (14432.1 MFlops)
- Pour n=2048 : meilleure performance avec szBlock=256 (14124.8 MFlops)
- Pour n=512 : meilleures performances avec szBlock=512 (14140.9 MFlops)
- Pour n=4096 : meilleure performance avec szBlock=256 (12784.5 MFlops)

Tendances observées :
- Les petites tailles de blocs (32, 64) sont généralement moins performantes
- Les très grandes tailles de blocs (1024) montrent aussi des performances réduites
- La taille optimale des blocs varie selon la dimension de la matrice
- Les blocs de taille intermédiaire (128-256) donnent généralement les meilleures performances

Explications :
- Les petits blocs : trop d'overhead de gestion des blocs
- Les grands blocs : moins bonne utilisation du cache
- Les blocs intermédiaires : bon compromis entre utilisation du cache et overhead de gestion



### Bloc + OMP

  szBlock      | OMP_NUM | MFlops  | MFlops(n=2048) | MFlops(n=512)  | MFlops(n=4096)|
---------------|---------|---------|----------------|----------------|---------------|
1024           |  1      | 8646.28 |    10153.7     |    13526.3     |    8985.32    |
1024           |  8      | 9220.77 |    38511.2     |    11874.8     |    39077.4    |
512            |  1      | 13080.3 |    11645.6     |    15207.5     |    13433.5    |
512            |  8      | 29683.8 |    79526.7     |    14669.9     |    95307.6    |

Impact de la Taille des Blocs :
- En mode mono-thread :
  - Les blocs de taille 512 sont plus performants que ceux de 1024
  - Pour n=1024 : 13080.3 MFlops (bloc 512) contre 8646.28 MFlops (bloc 1024)
  - Meilleure utilisation du cache avec des blocs plus petits

Parallélisation :
- Avec 8 threads :
  - Meilleures performances sur grandes matrices (n=2048, 4096)
  - Pour n=4096 : accélération ~7.1x avec blocs de 512
  - Accélération non linéaire due aux limitations de bande passante mémoire

Impact de la Taille des Matrices :
- Petites matrices (n=512) : accélération parallèle limitée
- Grandes matrices (n≥2048) : meilleure mise à l'échelle
- Meilleure amortissement des coûts de parallélisation

Configuration Optimale :
- Taille de bloc : 512
- Nombre de threads : 8
- Grandes matrices (n≥2048)


### Comparaison avec BLAS, Eigen et numpy

*Comparer les performances avec un calcul similaire utilisant les bibliothèques d'algèbre linéaire BLAS, Eigen et/ou numpy.*

| OMP_NUM | MFlops  | MFlops(n=2048) | MFlops(n=512)  | MFlops(n=4096)|
|---------|---------|----------------|----------------|---------------|
|  1      | 11816.9 |    14710.3     |    11392.7     |    12331.6    |
|  8      | 57160.4 |    63741.1     |    48544.7     |    66754.8    |

La bibliothèque BLAS offre de meilleures performances. Avec la stratégie Bloc + OMP, les performances fluctuent considérablement et sont plus sensibles à la taille des matrices. Pour les petites matrices comme n=512, l'accélération multi-thread n'est pas très significative. La bibliothèque BLAS, quant à elle, présente des performances relativement stables et maintient de bonnes performances pour différentes tailles de matrices.
