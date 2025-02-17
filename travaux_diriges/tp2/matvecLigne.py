#!/usr/bin/env python3
import numpy as np
from mpi4py import MPI
import time

# Initialize MPI
comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

# Dimension of the problem
dim = 4800

# Calculate number of local rows (N_loc)
N_loc = dim // size

# Initialize matrices and vectors
if rank == 0:
    # Initialize the complete matrix and vector on rank 0
    A = np.array([[(i+j) % dim + 1. for i in range(dim)] for j in range(dim)])
    u = np.array([i+1. for i in range(dim)])
    start_time = time.time()
else:
    A = None
    u = None

# Broadcast vector u to all processes since all processes need it
u = comm.bcast(u, root=0)

# Distribute matrix rows among processes
local_A = np.zeros((N_loc, dim))
if rank == 0:
    for i in range(size):
        if i == 0:
            local_A = A[0:N_loc]
        else:
            comm.Send(A[i*N_loc:(i+1)*N_loc], dest=i)
else:
    comm.Recv(local_A, source=0)

# Compute local product
local_v = np.zeros(N_loc, dtype=np.float64)
for i in range(N_loc):
    for j in range(dim):
        local_v[i] += local_A[i,j] * u[j]

# Gather all partial results
if rank == 0:
    v = np.zeros(dim, dtype=np.float64)
    # Copy rank 0's results
    v[0:N_loc] = local_v
    # Receive results from other processes
    for i in range(1, size):
        comm.Recv(v[i*N_loc:(i+1)*N_loc], source=i)
else:
    comm.Send(local_v, dest=0)

if rank == 0:
    end_time = time.time()
    execution_time = end_time - start_time
    print(f"Execution time: {execution_time:.4f} seconds")
