# TD n°3 - parallélisation du Bucket Sort

**Commande utilisée :**
```
mpiexec -n 4 python .\BucketSort.py
```
- `mpiexec` : Commande pour exécuter un programme en parallèle avec MPI
- `-n 4` : Utilisation de 4 processus (donc 4 buckets)

**Description de l'algorithme :**
1. Le processus principal (rang 0) :
   - Génère 100 nombres aléatoires entre 0 et 1000
   - Divise ces nombres en 4 seaux selon leur valeur
   - Distribue les données aux autres processus
2. Tous les processus :
   - Reçoivent leur portion de données
   - Trient localement leurs données
3. Enfin :
   - Les données triées sont renvoyées au processus principal
   - Le processus principal rassemble et affiche le résultat final
