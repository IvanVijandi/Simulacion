import numpy as np
import matplotlib.pyplot as plt


##Z=(A,R)
def wq(A, R):
    return 1438.68 - 135.92 * A + 1.75 * R


def graficar_superficie(A_range=(10.6, 16.1), R_range=(583, 1193), n=80, output='resultados/superficie_respuesta.png'):
    A_vals = np.linspace(*A_range, n)
    R_vals = np.linspace(*R_range, n)
    A_grid, R_grid = np.meshgrid(A_vals, R_vals)
    Wq_grid = wq(A_grid, R_grid)

    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection='3d')

    surf = ax.plot_surface(A_grid, R_grid, Wq_grid, cmap='viridis', alpha=0.85)
    fig.colorbar(surf, ax=ax, shrink=0.5, label='$W_q$ (seg)')

    ax.set_xlabel('A — Tiempo entre llegadas (seg)', labelpad=8)
    ax.set_ylabel('R — Tiempo de reposición (seg)', labelpad=8)
    ax.set_zlabel('$W_q$ (seg)', labelpad=8)
    ax.set_title('$W_q = 1438.68 - 135.92A + 1.75R$')

    fig.tight_layout()
    fig.savefig(output, dpi=150, bbox_inches='tight', transparent=True)
    plt.show()


if __name__ == '__main__':
    graficar_superficie()
