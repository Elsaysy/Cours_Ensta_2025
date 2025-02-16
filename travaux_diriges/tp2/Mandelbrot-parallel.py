import numpy as np
from dataclasses import dataclass
from PIL import Image
from math import log
from time import time
import matplotlib.cm
from multiprocessing import Process, Queue
import matplotlib.pyplot as plt  # For plotting

@dataclass
class MandelbrotSet:
    max_iterations: int
    escape_radius: float = 2.0

    def __contains__(self, c: complex) -> bool:
        return self.stability(c) == 1

    def convergence(self, c: complex, smooth=False, clamp=True) -> float:
        value = self.count_iterations(c, smooth) / self.max_iterations
        return max(0.0, min(value, 1.0)) if clamp else value

    def count_iterations(self, c: complex, smooth=False) -> int | float:
        z: complex
        iter: int

        # Check if the point is in known convergence regions
        if c.real * c.real + c.imag * c.imag < 0.0625:
            return self.max_iterations
        if (c.real + 1) * (c.real + 1) + c.imag * c.imag < 0.0625:
            return self.max_iterations
        if (c.real > -0.75) and (c.real < 0.5):
            ct = c.real - 0.25 + 1.j * c.imag
            ctnrm2 = abs(ct)
            if ctnrm2 < 0.5 * (1 - ct.real / max(ctnrm2, 1.E-14)):
                return self.max_iterations

        # Iterate to check divergence
        z = 0
        for iter in range(self.max_iterations):
            z = z * z + c
            if abs(z) > self.escape_radius:
                if smooth:
                    return iter + 1 - log(log(abs(z))) / log(2)
                return iter
        return self.max_iterations


def worker(task_queue, result_queue, mandelbrot_set, width, scaleX, scaleY):
    while True:
        # Get a row to process
        y = task_queue.get()
        if y is None:  # Sentinel value to indicate no more tasks
            break

        # Compute the convergence for this row
        row = np.empty(width, dtype=np.double)
        for x in range(width):
            c = complex(-2. + scaleX * x, -1.125 + scaleY * y)
            row[x] = mandelbrot_set.convergence(c, smooth=True)
        result_queue.put((y, row))


def main(nbp):
    mandelbrot_set = MandelbrotSet(max_iterations=50, escape_radius=10)
    width, height = 1024, 1024

    scaleX = 3. / width
    scaleY = 2.25 / height
    convergence = np.empty((width, height), dtype=np.double)

    # Create task and result queues
    task_queue = Queue()
    result_queue = Queue()

    # Fill the task queue with row indices
    for y in range(height):
        task_queue.put(y)

    # Add sentinel values to signal the end of tasks
    for _ in range(nbp):
        task_queue.put(None)

    # Start worker processes
    processes = []
    for _ in range(nbp):
        p = Process(target=worker, args=(task_queue, result_queue, mandelbrot_set, width, scaleX, scaleY))
        p.start()
        processes.append(p)

    # Collect results
    deb = time()
    for _ in range(height):
        y, row = result_queue.get()
        convergence[:, y] = row
    fin = time()
    execution_time = fin - deb
    print(f"Temps du calcul de l'ensemble de Mandelbrot avec {nbp} processus : {execution_time}")

    # Wait for all processes to finish
    for p in processes:
        p.join()

    # Save the image
    image = Image.fromarray(np.uint8(matplotlib.cm.plasma(convergence.T) * 255))
    image.save(f"mandelbrot_{nbp}.png")

    return execution_time


if __name__ == "__main__":
    # Test with different numbers of processes
    nbp_list = [1, 2, 3, 4, 5, 6, 7, 8]  # Number of processes to test
    execution_times = []
    for nbp in nbp_list:
        print(f"Running with {nbp} processes...")
        execution_time = main(nbp)
        execution_times.append(execution_time)

    # Calculate speedup
    speedup = [execution_times[0] / t for t in execution_times]

    # Plot results
    plt.figure(figsize=(10, 5))
    plt.plot(nbp_list, speedup, marker='o', linestyle='-', color='b', label="Speedup")
    plt.xlabel("Number of Processes")
    plt.ylabel("Speedup")
    plt.title("Speedup vs Number of Processes")
    plt.grid(True)
    plt.legend()
    plt.savefig("speedup_curve.png")
    plt.show()

    # Print results
    print("\nExecution Times:")
    for nbp, time in zip(nbp_list, execution_times):
        print(f"{nbp} processes: {time:.2f} seconds")

    print("\nSpeedup:")
    for nbp, sp in zip(nbp_list, speedup):
        print(f"{nbp} processes: {sp:.2f}")