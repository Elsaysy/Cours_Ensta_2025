"""
Le jeu de la vie
################
Le jeu de la vie est un automate cellulaire inventé par Conway se basant normalement sur une grille infinie
de cellules en deux dimensions. Ces cellules peuvent prendre deux états :
    - un état vivant
    - un état mort
A l'initialisation, certaines cellules sont vivantes, d'autres mortes.
Le principe du jeu est alors d'itérer de telle sorte qu'à chaque itération, une cellule va devoir interagir avec
les huit cellules voisines (gauche, droite, bas, haut et les quatre en diagonales.) L'interaction se fait selon les
règles suivantes pour calculer l'irération suivante :
    - Une cellule vivante avec moins de deux cellules voisines vivantes meurt ( sous-population )
    - Une cellule vivante avec deux ou trois cellules voisines vivantes reste vivante
    - Une cellule vivante avec plus de trois cellules voisines vivantes meurt ( sur-population )
    - Une cellule morte avec exactement trois cellules voisines vivantes devient vivante ( reproduction )

Pour ce projet, on change légèrement les règles en transformant la grille infinie en un tore contenant un
nombre fini de cellules. Les cellules les plus à gauche ont pour voisines les cellules les plus à droite
et inversement, et de même les cellules les plus en haut ont pour voisines les cellules les plus en bas
et inversement.

On itère ensuite pour étudier la façon dont évolue la population des cellules sur la grille.
"""
import pygame as pg
import numpy as np
from mpi4py import MPI
import time
import sys

# Initialisation de l'environnement MPI
global_comm = MPI.COMM_WORLD.Dup()
rank = global_comm.Get_rank()
size = global_comm.Get_size()

# S'assurer qu'il y a au moins 2 processus
if size < 2:
    print("Au moins 2 processus sont nécessaires : 1 pour l'affichage, au moins 1 pour le calcul")
    global_comm.Abort()
    sys.exit(1)

# Créer un nouveau communicateur qui divise les processus en processus d'affichage (rank=0) et processus de calcul (rank>0)
compute_comm = global_comm.Split(0 if rank == 0 else 1, rank)

# Obtenir le nombre de processus et le rang dans le communicateur de calcul
if rank > 0:
    compute_size = compute_comm.Get_size()
    compute_rank = compute_comm.Get_rank()
    print(f"Processus de calcul : rank global={rank}, rank du communicateur de calcul={compute_rank}, nombre total de processus de calcul={compute_size}")


class Grille:
    """
    Grille torique décrivant l'automate cellulaire.
    En entrée lors de la création de la grille :
        - dimensions est un tuple contenant le nombre de cellules dans les deux directions (nombre lignes, nombre colonnes)
        - init_pattern est une liste de cellules initialement vivantes sur cette grille (les autres sont considérées comme mortes)
        - color_life est la couleur dans laquelle on affiche une cellule vivante
        - color_dead est la couleur dans laquelle on affiche une cellule morte
    Si aucun pattern n'est donné, on tire au hasard quels sont les cellules vivantes et les cellules mortes
    """
    def __init__(self, dim_glob, compute_rank=0, compute_size=1, init_pattern=None, 
                 color_life=pg.Color("black"), color_dead=pg.Color("white")):
        # Stocker les dimensions globales
        self.dimensions_glob = dim_glob
        
        # Calculer les dimensions de la grille locale (y compris les cellules fantômes)
        if compute_size > 1:
            # Calculer le nombre de lignes par processus (assurer l'équilibrage de charge)
            rows_per_proc = dim_glob[0] // compute_size
            extra_rows = dim_glob[0] % compute_size
            
            # Calculer le nombre de lignes traitées par le processus actuel
            if compute_rank < extra_rows:
                local_rows = rows_per_proc + 1
                start_row = compute_rank * local_rows
            else:
                local_rows = rows_per_proc
                start_row = extra_rows * (rows_per_proc + 1) + (compute_rank - extra_rows) * rows_per_proc
            
            # Calculer les dimensions locales (ajouter une ligne fantôme en haut et en bas)
            self.dimensions_loc = (local_rows + 2, dim_glob[1])
            self.start_row = start_row
        else:
            # Si un seul processus de calcul, traiter toute la grille
            self.dimensions_loc = (dim_glob[0] + 2, dim_glob[1])
            self.start_row = 0
        
        # Initialiser la grille locale (y compris les cellules fantômes)
        self.cells = np.zeros(self.dimensions_loc, dtype=np.uint8)
        
        # Configurer le motif initial (si fourni)
        if init_pattern is not None:
            # Filtrer les cellules appartenant à la région locale
            for i, j in init_pattern:
                if self.start_row <= i < self.start_row + self.dimensions_loc[0] - 2:
                    # Convertir en coordonnées locales (en tenant compte des cellules fantômes)
                    self.cells[i - self.start_row + 1, j] = 1
        
        self.col_life = color_life
        self.col_dead = color_dead
        
        # Afficher les informations de la grille initiale
        print(f"Rang {compute_rank}: taille de la grille locale {self.dimensions_loc}, ligne de départ {self.start_row}")

    def update_ghost_cells(self, compute_comm):
        """Mettre à jour les cellules fantômes (échange aux limites pour la décomposition de domaine)"""
        if compute_comm.Get_size() > 1:
            # Obtenir les rangs des voisins supérieur et inférieur
            compute_rank = compute_comm.Get_rank()
            compute_size = compute_comm.Get_size()
            prev_rank = (compute_rank - 1) % compute_size
            next_rank = (compute_rank + 1) % compute_size
            
            # Utiliser la communication non bloquante, d'abord poster les demandes de réception
            req1 = compute_comm.Irecv(self.cells[0, :], source=prev_rank, tag=10)
            req2 = compute_comm.Irecv(self.cells[-1, :], source=next_rank, tag=20)
            
            # Envoyer la première et dernière ligne locale aux voisins
            compute_comm.Send(self.cells[1, :], dest=prev_rank, tag=20)
            compute_comm.Send(self.cells[-2, :], dest=next_rank, tag=10)
            
            # Attendre que les réceptions soient terminées
            req1.Wait()
            req2.Wait()

    def compute_next_iteration(self):
        """Calculer l'état des cellules de la génération suivante"""
        # Ne traiter que la zone réelle (sans les cellules fantômes)
        working_area = self.cells[1:-1, :]
        
        # Calculer le nombre de cellules vivantes autour de chaque cellule
        neighbors_count = np.zeros(working_area.shape, dtype=np.uint8)
        
        # Calculer la somme des voisins dans les 8 directions
        for i in (-1, 0, 1):
            for j in (-1, 0, 1):
                if i != 0 or j != 0:  # Ne pas compter la cellule elle-même
                    neighbors_count += np.roll(np.roll(self.cells, i, 0), j, 1)[1:-1, :]
        
        # Appliquer les règles du jeu de la vie
        next_cells = np.zeros(working_area.shape, dtype=np.uint8)
        # Règle 1 : Toute cellule vivante avec 2 ou 3 voisins vivants survit
        mask_alive = (working_area == 1)
        mask_survive = (neighbors_count == 2) | (neighbors_count == 3)
        next_cells[mask_alive & mask_survive] = 1
        
        # Règle 2 : Toute cellule morte avec exactement 3 voisins vivants devient vivante
        mask_dead = (working_area == 0)
        mask_reproduce = (neighbors_count == 3)
        next_cells[mask_dead & mask_reproduce] = 1
        
        # Mettre à jour l'état des cellules (uniquement dans la zone non fantôme)
        diff = (working_area != next_cells)
        self.cells[1:-1, :] = next_cells
        
        return diff


class App:
    """
    Cette classe décrit la fenêtre affichant la grille à l'écran
        - geometry est un tuple de deux entiers donnant le nombre de pixels verticaux et horizontaux (dans cet ordre)
        - grid est la grille décrivant l'automate cellulaire (voir plus haut)
    """
    def __init__(self, geometry, dimensions):
        # Sauvegarder les dimensions globales
        self.dimensions = dimensions
        
        # Calculer la taille en pixels de chaque cellule
        self.size_x = geometry[1] // dimensions[1]
        self.size_y = geometry[0] // dimensions[0]
        
        # Déterminer s'il faut dessiner les lignes de la grille
        if self.size_x > 4 and self.size_y > 4:
            self.draw_color = pg.Color('lightgrey')
        else:
            self.draw_color = None
            
        # Ajuster la taille de la fenêtre pour s'adapter à la grille
        self.width = dimensions[1] * self.size_x
        self.height = dimensions[0] * self.size_y
        
        # Créer la fenêtre d'affichage
        self.screen = pg.display.set_mode((self.width, self.height))
        
        # Définir les couleurs
        self.colors = np.array([pg.Color("white")[:-1], pg.Color("black")[:-1]])
        
        # Initialiser la grille pour l'affichage
        self.grid_display = np.zeros(dimensions, dtype=np.uint8)

    def draw(self):
        # Créer une surface à partir des données de la grille
        surface = pg.surfarray.make_surface(self.colors[self.grid_display.T])
        surface = pg.transform.flip(surface, False, True)
        surface = pg.transform.scale(surface, (self.width, self.height))
        
        # Afficher la surface
        self.screen.blit(surface, (0, 0))
        
        # Si nécessaire, dessiner les lignes de la grille
        if self.draw_color is not None:
            [pg.draw.line(self.screen, self.draw_color, (0, i*self.size_y), (self.width, i*self.size_y)) 
             for i in range(self.dimensions[0])]
            [pg.draw.line(self.screen, self.draw_color, (j*self.size_x, 0), (j*self.size_x, self.height)) 
             for j in range(self.dimensions[1])]
        
        # Mettre à jour l'affichage
        pg.display.update()

    def update_grid(self, new_data):
        """Mettre à jour les données de la grille d'affichage"""
        self.grid_display = new_data


if __name__ == '__main__':
    dico_patterns = {  # Dimension et pattern dans un tuple
        'blinker': ((5, 5), [(2, 1), (2, 2), (2, 3)]),
        'toad': ((6, 6), [(2, 2), (2, 3), (2, 4), (3, 3), (3, 4), (3, 5)]),
        "acorn": ((100, 100), [(51, 52), (52, 54), (53, 51), (53, 52), (53, 55), (53, 56), (53, 57)]),
        "beacon": ((6, 6), [(1, 3), (1, 4), (2, 3), (2, 4), (3, 1), (3, 2), (4, 1), (4, 2)]),
        "boat": ((5, 5), [(1, 1), (1, 2), (2, 1), (2, 3), (3, 2)]),
        "glider": ((100, 90), [(1, 1), (2, 2), (2, 3), (3, 1), (3, 2)]),
        "glider_gun": ((200, 100), [(51, 76), (52, 74), (52, 76), (53, 64), (53, 65), (53, 72), (53, 73), (53, 86), (53, 87), (54, 63), (54, 67), (54, 72), (54, 73), (54, 86), (54, 87), (55, 52), (55, 53), (55, 62), (55, 68), (55, 72), (55, 73), (56, 52), (56, 53), (56, 62), (56, 66), (56, 68), (56, 69), (56, 74), (56, 76), (57, 62), (57, 68), (57, 76), (58, 63), (58, 67), (59, 64), (59, 65)]),
        "space_ship": ((25, 25), [(11, 13), (11, 14), (12, 11), (12, 12), (12, 14), (12, 15), (13, 11), (13, 12), (13, 13), (13, 14), (14, 12), (14, 13)]),
        "die_hard": ((100, 100), [(51, 57), (52, 51), (52, 52), (53, 52), (53, 56), (53, 57), (53, 58)]),
        "pulsar": ((17, 17), [(2, 4), (2, 5), (2, 6), (7, 4), (7, 5), (7, 6), (9, 4), (9, 5), (9, 6), (14, 4), (14, 5), (14, 6), (2, 10), (2, 11), (2, 12), (7, 10), (7, 11), (7, 12), (9, 10), (9, 11), (9, 12), (14, 10), (14, 11), (14, 12), (4, 2), (5, 2), (6, 2), (4, 7), (5, 7), (6, 7), (4, 9), (5, 9), (6, 9), (4, 14), (5, 14), (6, 14), (10, 2), (11, 2), (12, 2), (10, 7), (11, 7), (12, 7), (10, 9), (11, 9), (12, 9), (10, 14), (11, 14), (12, 14)]),
        "floraison": ((40, 40), [(19, 18), (19, 19), (19, 20), (20, 17), (20, 19), (20, 21), (21, 18), (21, 19), (21, 20)]),
        "block_switch_engine": ((400, 400), [(201, 202), (201, 203), (202, 202), (202, 203), (211, 203), (212, 204), (212, 202), (214, 204), (214, 201), (215, 201), (215, 202), (216, 201)]),
        "u": ((200, 200), [(101, 101), (102, 102), (103, 102), (103, 101), (104, 103), (105, 103), (105, 102), (105, 101), (105, 105), (103, 105), (102, 105), (101, 105), (101, 104)]),
        "flat": ((200, 400), [(80, 200), (81, 200), (82, 200), (83, 200), (84, 200), (85, 200), (86, 200), (87, 200), (89, 200), (90, 200), (91, 200), (92, 200), (93, 200), (97, 200), (98, 200), (99, 200), (106, 200), (107, 200), (108, 200), (109, 200), (110, 200), (111, 200), (112, 200), (114, 200), (115, 200), (116, 200), (117, 200), (118, 200)])
    }

    # Analyser les arguments de ligne de commande
    choice = 'glider'
    if len(sys.argv) > 1:
        choice = sys.argv[1]
    resx = 800
    resy = 800
    if len(sys.argv) > 3:
        resx = int(sys.argv[2])
        resy = int(sys.argv[3])

    # Sélectionner le motif initial
    try:
        init_pattern = dico_patterns[choice]
    except KeyError:
        print("No such pattern. Available ones are:", dico_patterns.keys())
        global_comm.Abort()
        sys.exit(1)

    # Processus d'affichage
    if rank == 0:
        print(f"Pattern initial choisi: {choice}")
        print(f"Resolution ecran: {resx,resy}")

        # Initialiser pygame
        pg.init()
        
        # Créer l'application d'affichage
        appli = App((resx, resy), init_pattern[0])
        
        # Créer une grille vide pour l'affichage
        grid_display = np.zeros(init_pattern[0], dtype=np.uint8)
        
        loop = True
        iteration = 0
        
        while loop:
            # Recevoir les données de grille consolidées du processus de calcul
            grid_display = global_comm.recv(source=1)
            
            # Mettre à jour la grille d'affichage et mesurer le temps d'affichage
            t_display_start = time.time()
            appli.update_grid(grid_display)
            appli.draw()
            t_display_end = time.time()
            
            # Gérer les événements
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    loop = False
            
            # Envoyer un signal de contrôle au processus principal de calcul
            global_comm.send(loop, dest=1)
            
            iteration += 1
            print(f"Iteration {iteration}, temps affichage: {t_display_end-t_display_start:2.2e} secondes")
        
        pg.quit()
    
    # Processus de calcul
    else:
        # Créer la grille locale (avec cellules fantômes)
        grid = Grille(init_pattern[0], compute_rank, compute_size, init_pattern[1])
        
        # Mettre à jour les cellules fantômes avant le premier calcul
        grid.update_ghost_cells(compute_comm)
        
        # Créer un tableau pour collecter les données complètes de la grille - pour tous les processus de calcul
        full_grid = None
        if compute_rank == 0:
            # Seul le processus compute_rank=0 utilise réellement ce tableau
            full_grid = np.zeros(init_pattern[0], dtype=np.uint8)
        
        # Calculer le nombre et le décalage des données envoyées par chaque processus (pour Gatherv)
        # Résoudre le problème np.int en utilisant np.int32 à la place
        rows_per_proc = np.zeros(compute_size, dtype=np.int32)
        displacements = np.zeros(compute_size, dtype=np.int32)
        
        for i in range(compute_size):
            if i < init_pattern[0][0] % compute_size:
                rows_per_proc[i] = init_pattern[0][0] // compute_size + 1
            else:
                rows_per_proc[i] = init_pattern[0][0] // compute_size
                
            if i > 0:
                displacements[i] = displacements[i-1] + rows_per_proc[i-1]
        
        # Calculer la taille des données à envoyer (nombre de lignes * nombre de colonnes)
        sendcounts = rows_per_proc * init_pattern[0][1]
        displacements = displacements * init_pattern[0][1]
        
        loop = True
        iteration = 0
        
        while loop:
            # Mesurer le temps de calcul
            t_compute_start = time.time()
            
            # Calculer la génération suivante
            diff = grid.compute_next_iteration()
            
            # Mettre à jour les cellules fantômes
            grid.update_ghost_cells(compute_comm)
            
            t_compute_end = time.time()
            
            # Collecter les données de grille de tous les processus (en excluant les cellules fantômes)
            # Corriger l'erreur : même les processus non racines doivent fournir le paramètre full_grid
            compute_comm.Gatherv(grid.cells[1:-1, :], [full_grid, sendcounts, displacements, MPI.UNSIGNED_CHAR], root=0)
            
            # Le processus de calcul 0 est responsable de la communication avec le processus d'affichage
            if compute_rank == 0:
                # Envoyer les données complètes de la grille au processus d'affichage
                global_comm.send(full_grid, dest=0)
                
                # Recevoir le signal de contrôle
                loop = global_comm.recv(source=0)
                
            # Diffuser le signal de contrôle à tous les processus de calcul
            loop = compute_comm.bcast(loop, root=0)
            
            iteration += 1
            print(f"Rang {rank}, iteration {iteration}, temps calcul: {t_compute_end-t_compute_start:2.2e} secondes")