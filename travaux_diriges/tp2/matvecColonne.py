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

# Calculate local size
N_loc = dim // size

# Initialize local part of matrix A and vector u
if rank == 0:
    # Initialize the complete matrix and vector on rank 0
    A = np.array([[(i+j) % dim + 1. for i in range(dim)] for j in range(dim)])
    u = np.array([i+1. for i in range(dim)])
    start_time = time.time()
else:
    A = None
    u = None

# Broadcast vector u to all processes
u = comm.bcast(u, root=0)

# Scatter matrix A by columns
# Each process will receive N_loc columns
local_A = np.zeros((dim, N_loc))
for i in range(dim):
    row = None
    if rank == 0:
        row = A[i]
    row = comm.bcast(row, root=0)
    local_A[i] = row[rank*N_loc:(rank+1)*N_loc]

# Compute local product
local_v = np.zeros(dim)
for i in range(dim):
    for j in range(N_loc):
        local_v[i] += local_A[i,j] * u[rank*N_loc + j]

# Reduce all local results to get final vector
v = comm.reduce(local_v, op=MPI.SUM, root=0)

if rank == 0:
    end_time = time.time()
    execution_time = end_time - start_time
    print(f"Execution time: {execution_time:.4f} seconds")