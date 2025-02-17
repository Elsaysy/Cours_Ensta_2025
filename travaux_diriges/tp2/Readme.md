# TD n° 2 - 27 Janvier 2025

##  1. Parallélisation ensemble de Mandelbrot
1. `Mandelbrot-parallel.py`

| nbp | Temps de calcul (s) | Speedup |
| --- | ------------------- | ------- |
| 1   | 3.5662658214569090  | 1       |
| 2   | 1.5205612182617188  | 2.345   |
| 4   | 0.9460878372192383  | 3.769   |
| 8   | 0.7325904369354248  | 4.868   |

J'ai défini une liste de différents nombres de processus `nbp_list` pour les tests. Pour chaque nombre de processus, j'utilise `multiprocessing.Pool` pour calculer les lignes de l'image en parallèle. Après le calcul, les résultats sont rassemblés dans le tableau `convergence`. J'ai mesuré le temps d'exécution pour chaque nombre de processus et calculé l'accélération, qui montre une amélioration significative.

2. `Mandelbrot-improved-parallel.py`

| nbp | Temps de calcul (s) | Speedup |
| --- | ------------------- | ------- |
| 1   | 3.5584290027618410  | 1       |
| 2   | 1.5909330844879150  | 2.237   |
| 4   | 0.9227039813995361  | 3.857   |
| 8   | 0.6993927955627441  | 5.088   |

Chaque processus reçoit un ensemble de numéros de lignes distribuées par pas, ce qui permet d'obtenir un équilibrage de charge, car la complexité de calcul de l'ensemble de Mandelbrot est uniformément répartie entre les différentes lignes. On utilise `multiprocessing.Queue` pour renvoyer les résultats de calcul de chaque processus vers le processus principal. Le calcul de l'accélération montre une légère amélioration par rapport à la première solution.

3. `Mandelbrot-maître-esclave.py`

| nbp | Temps de calcul (s) | Speedup |
| --- | ------------------- | ------- |
| 1   | 3.4113667011260986  | 1       |
| 2   | 1.5224745273590088  | 2.241   |
| 4   | 0.9361574649810791  | 3.644   |
| 8   | 0.6832985877990723  | 4.992   |

Dans le stratégie maître-esclave, le processus maître distribue dynamiquement les tâches (numéros de lignes) aux processus esclaves. Les esclaves, après avoir terminé leur tâche, continuent à récupérer de nouvelles tâches de la file d'attente jusqu'à ce que celle-ci soit vide. Le processus maître collecte tous les résultats des processus esclaves depuis la file des résultats. Les résultats sont stockés dans le tableau `convergence` selon leur numéro de ligne. Une valeur sentinelle `None` est utilisée pour notifier aux processus esclaves que la file des tâches est vide et qu'ils peuvent terminer. Ce schéma de distribution dynamique donne une meilleure accélération que les deux approches précédentes.

## 2. Produit matrice-vecteur

$N = 4800$, $N_{loc} = N / nbp$

### a - Produit parallèle matrice-vecteur par colonne

| nbp | Temps de calcul (s) | Speedup |
| --- | ------------------- | ------- |
| 1   | 9.8887              | 1       |
| 2   | 5.0610              | 1.954   |
| 3   | 3.4204              | 2.891   |
| 4   | 2.5564              | 3.868   |

### b - Produit parallèle matrice-vecteur par ligne

| nbp | Temps de calcul (s) | Speedup |
| --- | ------------------- | ------- |
| 1   | 10.8210             | 1       |
| 2   | 4.1831              | 2.587   |
| 3   | 2.8146              | 3.845   |
| 4   | 2.0940              | 5.168   |

## 3. Entraînement pour l'examen écrit

1. Calcul de l'accélération maximale selon la loi d'Amdahl:

- La partie parallèle représente 90% du temps d'exécution, donc f = 0.1 (la fraction séquentielle)
- La loi d'Amdahl nous donne: $S(n) = n/(1 + (n-1)f)$
- Quand n tend vers l'infini, $S(\infty) = 1/f = 1/0.1 = 10$

Donc l'accélération maximale théorique que pourra obtenir Alice est de 10.

2. Nombre raisonnable de nœuds:

- Pour n = 4: S(4) = 4/(1 + 3×0.1) = 4/1.3 ≈ 3.08
- Pour n = 8: S(8) = 8/(1 + 7×0.1) = 8/1.7 ≈ 4.71
- Pour n = 16: S(16) = 16/(1 + 15×0.1) = 16/2.5 = 6.4

On constate que l'efficacité diminue rapidement. À partir de 8-10 nœuds, l'augmentation de l'accélération devient faible par rapport aux ressources utilisées. Un nombre raisonnable serait donc entre 8 et 10 nœuds.

3. Accélération selon la loi de Gustafson avec double quantité de données:

La loi de Gustafson nous donne: $S(n) = n + (1-n)×t_s$

L'accélération attendue serait: $S(n) = n + (1-n)×0.1 = 0.9n + 0.1$

Pour le même nombre de nœuds qui donnait une accélération de 4 précédemment, avec le double de données, on peut espérer une accélération proche de 8, car avec plus de données, la partie parallèle devient plus importante par rapport à la partie séquentielle.
