
# TD1

`pandoc -s --toc README.md --css=./github-pandoc.css -o README.html`

## lscpu

*lscpu donne des infos utiles sur le processeur : nb core, taille de cache :*

```
Coller ici les infos *utiles* de lscpu.
```


## Produit matrice-matrice

### Effet de la taille de la matrice

  n            | MFlops
---------------|--------
1023           | 873.185
1024 (origine) | 212.4
1025           | 825.117

Pour mesurer le temps de calcul du produit matrice-matrice, j'ai effectué des tests avec trois dimensions différentes. Voici les résultats observés :

Pour une matrice de dimension 1023 :
- Temps d'exécution : 2,45 secondes
- Performance : 873,185 MFlops

Pour une matrice de dimension 1024 :
- Temps d'exécution : 10,11 secondes
- Performance : 212,4 MFlops

Pour une matrice de dimension 1025 :
- Temps d'exécution : 2,61 secondes
- Performance : 825,117 MFlops

L'analyse des résultats montre une anomalie significative pour la dimension 1024. Cette dimension, qui est une puissance de 2 (2¹⁰), présente un temps d'exécution environ quatre fois plus élevé que les dimensions adjacentes.

Ce phénomène s'explique par le comportement du cache :
- Lorsque la taille de la matrice est une puissance de 2 (1024), les éléments de la même colonne dans différentes lignes sont mappés aux mêmes emplacements dans le cache
- Cela provoque des conflits de cache systématiques (cache conflicts)
- Ces conflits entraînent de nombreux défauts de cache (cache misses)
- Par conséquent, le processeur doit fréquemment recharger les données depuis la mémoire principale

En revanche, les dimensions 1023 et 1025 évitent ces conflits systématiques, ce qui explique leurs meilleures performances.

Cette observation illustre l'importance de la gestion du cache dans les performances des algorithmes de calcul matriciel, comme nous l'avons vu dans le cours.

### Permutation des boucles

*Expliquer comment est compilé le code (ligne de make ou de gcc) : on aura besoin de savoir l'optim, les paramètres, etc. Par exemple :*

`make TestProduct.exe && ./TestProduct.exe 1024`


  ordre           | time    | MFlops  | MFlops(n=2048)
------------------|---------|---------|----------------
i,j,k (origine)   | 2.73764 | 782.476 |
j,i,k             |         |         |
i,k,j             |         |         |
k,i,j             |         |         |
j,k,i             |         |         |
k,j,i             |         |         |


*Discuter les résultats.*



### OMP sur la meilleure boucle

`make TestProduct.exe && OMP_NUM_THREADS=8 ./TestProduct.exe 1024`

  OMP_NUM         | MFlops  | MFlops(n=2048) | MFlops(n=512)  | MFlops(n=4096)
------------------|---------|----------------|----------------|---------------
1                 |
2                 |
3                 |
4                 |
5                 |
6                 |
7                 |
8                 |

*Tracer les courbes de speedup (pour chaque valeur de n), discuter les résultats.*



### Produit par blocs

`make TestProduct.exe && ./TestProduct.exe 1024`

  szBlock         | MFlops  | MFlops(n=2048) | MFlops(n=512)  | MFlops(n=4096)
------------------|---------|----------------|----------------|---------------
origine (=max)    |
32                |
64                |
128               |
256               |
512               |
1024              |

*Discuter les résultats.*



### Bloc + OMP


  szBlock      | OMP_NUM | MFlops  | MFlops(n=2048) | MFlops(n=512)  | MFlops(n=4096)|
---------------|---------|---------|----------------|----------------|---------------|
1024           |  1      |         |                |                |               |
1024           |  8      |         |                |                |               |
512            |  1      |         |                |                |               |
512            |  8      |         |                |                |               |

*Discuter les résultats.*


### Comparaison avec BLAS, Eigen et numpy

*Comparer les performances avec un calcul similaire utilisant les bibliothèques d'algèbre linéaire BLAS, Eigen et/ou numpy.*


# Tips

```
	env
	OMP_NUM_THREADS=4 ./produitMatriceMatrice.exe
```

```
    $ for i in $(seq 1 4); do elap=$(OMP_NUM_THREADS=$i ./TestProductOmp.exe|grep "Temps CPU"|cut -d " " -f 7); echo -e "$i\t$elap"; done > timers.out
```
