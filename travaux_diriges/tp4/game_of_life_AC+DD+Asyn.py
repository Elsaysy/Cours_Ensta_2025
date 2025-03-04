import pygame as pg
import numpy as np
from mpi4py import MPI
import time
import sys

# Initialisation de l'environnement MPI
global_comm = MPI.COMM_WORLD.Dup()
rank = global_comm.Get_rank()
size = global_comm.Get_size()

if size < 2:
    print("Au moins 2 processus sont nécessaires : 1 pour l'affichage, au moins 1 pour le calcul")
    global_comm.Abort()
    sys.exit(1)

# Création d'un nouveau communicateur, séparant le processus d'affichage (rank==0) et les processus de calcul (rank>0)
compute_comm = global_comm.Split(0 if rank == 0 else 1, rank)

if rank > 0:
    compute_size = compute_comm.Get_size()
    compute_rank = compute_comm.Get_rank()
    print(f"Processus de calcul : rank global = {rank}, rank dans le communicateur de calcul = {compute_rank}, nombre total de processus de calcul = {compute_size}")

class Grille:
    """
    Classe décrivant la grille du jeu. La grille locale comprend une ligne fantôme en haut et en bas.
    """
    def __init__(self, dim_glob, compute_rank=0, compute_size=1, init_pattern=None, 
                 color_life=pg.Color("black"), color_dead=pg.Color("white")):
        self.dimensions_glob = dim_glob
        if compute_size > 1:
            rows_per_proc = dim_glob[0] // compute_size
            extra_rows = dim_glob[0] % compute_size
            if compute_rank < extra_rows:
                local_rows = rows_per_proc + 1
                start_row = compute_rank * local_rows
            else:
                local_rows = rows_per_proc
                start_row = extra_rows * (rows_per_proc + 1) + (compute_rank - extra_rows) * rows_per_proc
            self.dimensions_loc = (local_rows + 2, dim_glob[1])
            self.start_row = start_row
        else:
            self.dimensions_loc = (dim_glob[0] + 2, dim_glob[1])
            self.start_row = 0
        
        self.cells = np.zeros(self.dimensions_loc, dtype=np.uint8)
        
        if init_pattern is not None:
            for i, j in init_pattern:
                if self.start_row <= i < self.start_row + self.dimensions_loc[0] - 2:
                    self.cells[i - self.start_row + 1, j] = 1
        
        self.col_life = color_life
        self.col_dead = color_dead
        
        print(f"Processus de calcul {compute_rank} : taille de la grille locale {self.dimensions_loc}, ligne de départ {self.start_row}")

    def update_ghost_cells(self, compute_comm):
        """Mettre à jour de manière non bloquante les cellules fantômes sur les bords haut et bas"""
        if compute_comm.Get_size() > 1:
            compute_rank = compute_comm.Get_rank()
            compute_size = compute_comm.Get_size()
            prev_rank = (compute_rank - 1) % compute_size
            next_rank = (compute_rank + 1) % compute_size
            
            # Réception non bloquante des données des voisins
            req_recv_top = compute_comm.Irecv(self.cells[0, :], source=prev_rank, tag=10)
            req_recv_bottom = compute_comm.Irecv(self.cells[-1, :], source=next_rank, tag=20)
            
            # Envoi des données de la frontière locale : utilisation de .copy() pour éviter toute modification pendant la transmission
            req_send_top = compute_comm.Isend(self.cells[1, :].copy(), dest=prev_rank, tag=20)
            req_send_bottom = compute_comm.Isend(self.cells[-2, :].copy(), dest=next_rank, tag=10)
            
            MPI.Request.Waitall([req_recv_top, req_recv_bottom, req_send_top, req_send_bottom])
    
    def compute_next_iteration(self):
        """Calculer l'état des cellules pour la prochaine itération"""
        working_area = self.cells[1:-1, :]
        neighbors_count = np.zeros(working_area.shape, dtype=np.uint8)
        for i in (-1, 0, 1):
            for j in (-1, 0, 1):
                if i != 0 or j != 0:
                    neighbors_count += np.roll(np.roll(self.cells, i, 0), j, 1)[1:-1, :]
        
        next_cells = np.zeros(working_area.shape, dtype=np.uint8)
        mask_alive = (working_area == 1)
        mask_survive = (neighbors_count == 2) | (neighbors_count == 3)
        next_cells[mask_alive & mask_survive] = 1
        
        mask_dead = (working_area == 0)
        mask_reproduce = (neighbors_count == 3)
        next_cells[mask_dead & mask_reproduce] = 1
        
        diff = (working_area != next_cells)
        self.cells[1:-1, :] = next_cells
        return diff

class App:
    """
    Classe d'application pygame chargée d'afficher la grille.
    """
    def __init__(self, geometry, dimensions):
        self.dimensions = dimensions
        self.size_x = geometry[1] // dimensions[1]
        self.size_y = geometry[0] // dimensions[0]
        if self.size_x > 4 and self.size_y > 4:
            self.draw_color = pg.Color('lightgrey')
        else:
            self.draw_color = None
        self.width = dimensions[1] * self.size_x
        self.height = dimensions[0] * self.size_y
        self.screen = pg.display.set_mode((self.width, self.height))
        self.colors = np.array([pg.Color("white")[:-1], pg.Color("black")[:-1]])
        self.grid_display = np.zeros(dimensions, dtype=np.uint8)
    
    def draw(self):
        surface = pg.surfarray.make_surface(self.colors[self.grid_display.T])
        surface = pg.transform.flip(surface, False, True)
        surface = pg.transform.scale(surface, (self.width, self.height))
        self.screen.blit(surface, (0, 0))
        if self.draw_color is not None:
            [pg.draw.line(self.screen, self.draw_color, (0, i * self.size_y), (self.width, i * self.size_y)) 
             for i in range(self.dimensions[0])]
            [pg.draw.line(self.screen, self.draw_color, (j * self.size_x, 0), (j * self.size_x, self.height)) 
             for j in range(self.dimensions[1])]
        pg.display.update()
    
    def update_grid(self, new_data):
        self.grid_display = new_data

if __name__ == '__main__':
    dico_patterns = {  
        'blinker': ((5, 5), [(2, 1), (2, 2), (2, 3)]),
        'toad': ((6, 6), [(2, 2), (2, 3), (2, 4), (3, 3), (3, 4), (3, 5)]),
        "acorn": ((100, 100), [(51, 52), (52, 54), (53, 51), (53, 52), (53, 55), (53, 56), (53, 57)]),
        "beacon": ((6, 6), [(1, 3), (1, 4), (2, 3), (2, 4), (3, 1), (3, 2), (4, 1), (4, 2)]),
        "boat": ((5, 5), [(1, 1), (1, 2), (2, 1), (2, 3), (3, 2)]),
        "glider": ((100, 90), [(1, 1), (2, 2), (2, 3), (3, 1), (3, 2)]),
        "glider_gun": ((200, 100), [(51, 76), (52, 74), (52, 76), (53, 64), (53, 65), (53, 72), (53, 73), 
                                     (53, 86), (53, 87), (54, 63), (54, 67), (54, 72), (54, 73), (54, 86), 
                                     (54, 87), (55, 52), (55, 53), (55, 62), (55, 68), (55, 72), (55, 73), 
                                     (56, 52), (56, 53), (56, 62), (56, 66), (56, 68), (56, 69), (56, 74), 
                                     (56, 76), (57, 62), (57, 68), (57, 76), (58, 63), (58, 67), (59, 64), (59, 65)]),
        "space_ship": ((25, 25), [(11, 13), (11, 14), (12, 11), (12, 12), (12, 14), (12, 15), 
                                  (13, 11), (13, 12), (13, 13), (13, 14), (14, 12), (14, 13)]),
        "die_hard": ((100, 100), [(51, 57), (52, 51), (52, 52), (53, 52), (53, 56), (53, 57), (53, 58)]),
        "pulsar": ((17, 17), [(2, 4), (2, 5), (2, 6), (7, 4), (7, 5), (7, 6), (9, 4), (9, 5), (9, 6), 
                              (14, 4), (14, 5), (14, 6), (2, 10), (2, 11), (2, 12), (7, 10), (7, 11), 
                              (7, 12), (9, 10), (9, 11), (9, 12), (14, 10), (14, 11), (14, 12), (4, 2), 
                              (5, 2), (6, 2), (4, 7), (5, 7), (6, 7), (4, 9), (5, 9), (6, 9), (4, 14), 
                              (5, 14), (6, 14), (10, 2), (11, 2), (12, 2), (10, 7), (11, 7), (12, 7), 
                              (10, 9), (11, 9), (12, 9), (10, 14), (11, 14), (12, 14)]),
        "floraison": ((40, 40), [(19, 18), (19, 19), (19, 20), (20, 17), (20, 19), (20, 21), (21, 18), (21, 19), (21, 20)]),
        "block_switch_engine": ((400, 400), [(201, 202), (201, 203), (202, 202), (202, 203), (211, 203), (212, 204), (212, 202), (214, 204), (214, 201), (215, 201), (215, 202), (216, 201)]),
        "u": ((200, 200), [(101, 101), (102, 102), (103, 102), (103, 101), (104, 103), (105, 103), (105, 102), (105, 101), (105, 105), (103, 105), (102, 105), (101, 105), (101, 104)]),
        "flat": ((200, 400), [(80, 200), (81, 200), (82, 200), (83, 200), (84, 200), (85, 200), (86, 200), (87, 200), 
                              (89, 200), (90, 200), (91, 200), (92, 200), (93, 200), (97, 200), (98, 200), (99, 200), 
                              (106, 200), (107, 200), (108, 200), (109, 200), (110, 200), (111, 200), (112, 200), 
                              (114, 200), (115, 200), (116, 200), (117, 200), (118, 200)])
    }
    
    choice = 'glider'
    if len(sys.argv) > 1:
        choice = sys.argv[1]
    resx = 800
    resy = 800
    if len(sys.argv) > 3:
        resx = int(sys.argv[2])
        resy = int(sys.argv[3])
    
    try:
        init_pattern = dico_patterns[choice]
    except KeyError:
        print("Le mode n'existe pas. Les modes disponibles sont :", dico_patterns.keys())
        global_comm.Abort()
        sys.exit(1)
    
    # Processus d'affichage
    if rank == 0:
        print(f"Mode initial choisi : {choice}")
        print(f"Résolution de l'écran : {(resx, resy)}")
        pg.init()
        appli = App((resx, resy), init_pattern[0])
        grid_display = np.zeros(init_pattern[0], dtype=np.uint8)
        loop = True
        iteration = 0
        
        while loop:
            # Réception asynchrone de la grille complète envoyée par le processus de calcul
            req_recv = global_comm.irecv(source=1)
            grid_display = req_recv.wait()
            
            t_display_start = time.time()
            appli.update_grid(grid_display)
            appli.draw()
            t_display_end = time.time()
            
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    loop = False
            
            # Envoi asynchrone du signal de contrôle au processus de calcul
            req_send = global_comm.isend(loop, dest=1)
            req_send.wait()
            
            iteration += 1
            print(f"Iteration {iteration}, affichage time: {t_display_end - t_display_start:2.2e} sec")
        
        pg.quit()
    
    # Processus de calcul
    else:
        grid = Grille(init_pattern[0], compute_rank, compute_size, init_pattern[1])
        grid.update_ghost_cells(compute_comm)
        
        full_grid = None
        if compute_rank == 0:
            full_grid = np.zeros(init_pattern[0], dtype=np.uint8)
        
        rows_per_proc = np.zeros(compute_size, dtype=np.int32)
        displacements = np.zeros(compute_size, dtype=np.int32)
        
        for i in range(compute_size):
            if i < init_pattern[0][0] % compute_size:
                rows_per_proc[i] = init_pattern[0][0] // compute_size + 1
            else:
                rows_per_proc[i] = init_pattern[0][0] // compute_size
            if i > 0:
                displacements[i] = displacements[i - 1] + rows_per_proc[i - 1]
        
        sendcounts = rows_per_proc * init_pattern[0][1]
        displacements = displacements * init_pattern[0][1]
        
        loop = True
        iteration = 0
        
        while loop:
            t_compute_start = time.time()
            diff = grid.compute_next_iteration()
            grid.update_ghost_cells(compute_comm)
            t_compute_end = time.time()
            
            # Collecte asynchrone des données de tous les processus de calcul (uniquement la zone non fantôme)
            req_gather = compute_comm.Igatherv(grid.cells[1:-1, :],
                                               [full_grid, sendcounts, displacements, MPI.UNSIGNED_CHAR],
                                               root=0)
            req_gather.Wait()
            
            # Le processus de calcul de rang 0 communique de manière non bloquante avec le processus d'affichage
            if compute_rank == 0:
                req_send = global_comm.isend(full_grid, dest=0)
                req_send.Wait()
                req_recv = global_comm.irecv(source=0)
                loop = req_recv.wait()
            
            # Diffusion du signal de contrôle
            loop = compute_comm.bcast(loop, root=0)
            iteration += 1
            print(f"Rank global {rank}, itération {iteration}, temps de calcul: {t_compute_end - t_compute_start:2.2e} sec")
