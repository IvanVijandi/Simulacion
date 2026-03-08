import numpy as np
import matplotlib.pyplot as plt
from itertools import product


def graficar_diseno_factorial(output='resultados/diseno_doe.png'):
    fig = plt.figure(figsize=(8, 7))
    ax = fig.add_subplot(111, projection='3d')

    esquinas = np.array(list(product([-1, 1], repeat=3)))
    ax.scatter(esquinas[:, 0], esquinas[:, 1], esquinas[:, 2], color='black', s=80, zorder=5)

    ax.scatter([0], [0], [0], color='black', s=120, zorder=6)

    # Aristas del cubo
    for i in range(3):
        for combo in product([-1, 1], repeat=2):
            p = list(combo); p.insert(i, -1)
            q = list(combo); q.insert(i,  1)
            ax.plot([p[0], q[0]], [p[1], q[1]], [p[2], q[2]],
                    color='gray', linewidth=0.8, alpha=0.6)

    ax.set_xlabel('A (llegadas)',   labelpad=8)
    ax.set_ylabel('S (servicio)',   labelpad=8)
    ax.set_zlabel('R (reposición)', labelpad=8)
    ax.set_title('Diseño $2^3$ + Punto Central', fontsize=13)

    for setter in (ax.set_xticks, ax.set_yticks, ax.set_zticks):
        setter([-1, 0, 1])
    for setter in (ax.set_xticklabels, ax.set_yticklabels, ax.set_zticklabels):
        setter(['-1', '0', '+1'])

    fig.tight_layout()
    fig.savefig(output, dpi=150, bbox_inches='tight', transparent=True)
    plt.show()


if __name__ == '__main__':
    graficar_diseno_factorial()
