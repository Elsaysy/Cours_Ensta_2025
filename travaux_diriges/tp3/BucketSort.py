from mpi4py import MPI
import numpy as np

def bucket_sort_parallel(data, num_buckets):
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()

    if size != num_buckets:
        if rank == 0:
            print(f"Erreur : Le nombre de processus ({size}) doit correspondre au nombre de seaux ({num_buckets}).")
        return None

    if rank == 0:
        # Le processus principal génère les données aléatoires
        print("Données originales:", data)
        # Calcule la plage pour chaque seau
        min_val, max_val = min(data), max(data)
        bucket_range = (max_val - min_val) / num_buckets

        # Distribue les données dans les seaux
        buckets = [[] for _ in range(num_buckets)]
        for num in data:
            bucket_index = int((num - min_val) // bucket_range)
            if bucket_index >= num_buckets:
                bucket_index = num_buckets - 1
            buckets[bucket_index].append(num)

        # Distribue les données aux processus
        for i in range(1, size):
            comm.send(buckets[i], dest=i)
        local_bucket = buckets[0]
    else:
        # Les autres processus reçoivent leurs données
        local_bucket = comm.recv(source=0)

    # Chaque processus trie son seau
    local_bucket.sort()

    # Renvoie les données triées au processus principal
    if rank == 0:
        sorted_data = local_bucket
        for i in range(1, size):
            sorted_data.extend(comm.recv(source=i))  
        print("Données triées:", sorted_data)
    else:
        comm.send(local_bucket, dest=0)

if __name__ == "__main__":
    # Initialisation MPI
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()

    # Définit le nombre de seaux
    num_buckets = comm.Get_size()

    # Le processus principal génère les données aléatoires
    if rank == 0:
        data = np.random.randint(0, 1000, 100).tolist()  # Génère 100 nombres aléatoires entre 0 et 1000
    else:
        data = None

    # Appelle le tri par seaux parallèle
    bucket_sort_parallel(data, num_buckets)