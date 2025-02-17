import numpy as np
from dataclasses import dataclass
from PIL import Image
from math import log
from time import time
import matplotlib.cm
from multiprocessing import Pool, cpu_count

@dataclass
class MandelbrotSet:
    max_iterations: int
    escape_radius:  float = 2.0

    def contains(self, c: complex) -> bool:
        return self.stability(c) == 1

    def convergence(self, c: complex, smooth=False, clamp=True) -> float:
        value = self.count_iterations(c, smooth)/self.max_iterations
        return max(0.0, min(value, 1.0)) if clamp else value

    def count_iterations(self, c: complex,  smooth=False) -> int | float:
        z:    complex
        iter: int

        # On vérifie dans un premier temps si le complexe
        # n'appartient pas à une zone de convergence connue :
        #   1. Appartenance aux disques  C0{(0,0),1/4} et C1{(-1,0),1/4}
        if c.real*c.real+c.imag*c.imag < 0.0625:
            return self.max_iterations
        if (c.real+1)*(c.real+1)+c.imag*c.imag < 0.0625:
            return self.max_iterations
        #  2.  Appartenance à la cardioïde {(1/4,0),1/2(1-cos(theta))}
        if (c.real > -0.75) and (c.real < 0.5):
            ct = c.real-0.25 + 1.j * c.imag
            ctnrm2 = abs(ct)
            if ctnrm2 < 0.5*(1-ct.real/max(ctnrm2, 1.E-14)):
                return self.max_iterations
        # Sinon on itère
        z = 0
        for iter in range(self.max_iterations):
            z = z*z + c
            if abs(z) > self.escape_radius:
                if smooth:
                    return iter + 1 - log(log(abs(z)))/log(2)
                return iter
        return self.max_iterations

def compute_row(y, width, scaleX, scaleY, mandelbrot_set):
    row = np.empty(width, dtype=np.double)
    for x in range(width):
        c = complex(-2. + scaleX*x, -1.125 + scaleY * y)
        row[x] = mandelbrot_set.convergence(c, smooth=True)
    return y, row

def main():
    mandelbrot_set = MandelbrotSet(max_iterations=50, escape_radius=10)
    width, height = 1024, 1024

    scaleX = 3./width
    scaleY = 2.25/height
    convergence = np.empty((width, height), dtype=np.double)

    nbp_list = [1, 2, 4, 8]  # Different numbers of processes to test
    for nbp in nbp_list:
        deb = time()
        with Pool(processes=nbp) as pool:
            results = pool.starmap(compute_row, [(y, width, scaleX, scaleY, mandelbrot_set) for y in range(height)])
        for y, row in results:
            convergence[:, y] = row
        fin = time()
        print(f"Temps du calcul de l'ensemble de Mandelbrot avec {nbp} processus : {fin-deb}")

        if nbp == 1:
            time_1 = fin - deb
        else:
            speedup = time_1 / (fin - deb)
            print(f"Accélération avec {nbp} processus : {speedup}")

if __name__ == "__main__":
    main()
