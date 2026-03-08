import simpy
import numpy as np
from scipy import stats
import pandas as pd
import os
from itertools import product
from datetime import datetime


# -- Distribuciones -----------------------------------------------------------

def burr_rv(k, alpha, beta, gamma=0):
    u = np.random.uniform(0, 1)
    return gamma + beta * (((1 - u) ** (-1 / k) - 1) ** (1 / alpha))


def wakeby_rv(alpha, beta, gamma, delta, xi):
    u = np.random.uniform(np.finfo(float).eps, 1 - np.finfo(float).eps)
    if beta != 0 and delta != 0:
        x = xi + alpha / beta * (1 - (1-u)**beta) - gamma / delta * (1 - (1-u)**(-delta))
    elif beta == 0 and delta != 0:
        x = xi + alpha * np.log(1/(1-u)) - gamma / delta * (1 - (1-u)**(-delta))
    elif beta != 0 and delta == 0:
        x = xi + alpha / beta * (1 - (1-u)**beta) + gamma * np.log(1-u)
    else:
        x = xi + (alpha + gamma) * np.log(1/(1-u))
    return max(x, 0)


def gamma_3p_rv(alpha, beta, gamma):
    u = np.random.uniform(np.finfo(float).eps, 1 - np.finfo(float).eps)
    return max(gamma + stats.gamma.ppf(u, a=alpha, scale=beta), 0)


# -- Configuracion ------------------------------------------------------------

LLEGADAS_PARAMS   = {'k': 1.1786, 'alpha': 2.9348, 'beta': 12.183, 'gamma': 0}
SERVICIO_PARAMS   = {'alpha': 156.3, 'beta': 8.5432, 'gamma': 65.464, 'delta': -0.66427, 'xi': 247.21}
REPOSICION_PARAMS = {'alpha': 1.8741, 'beta': 303.21, 'gamma': 313.7}

CAPACIDAD_MICRO   = 55
TIEMPO_SIMULACION = 3600 * 2
NUM_REPLICAS      = 3

DOE_NIVELES = {
    'arribos':    {'bajo': 15.2, 'alto': 10.1},
    'servicio':   {'bajo': 1.20, 'alto': 0.80},
    'reposicion': {'bajo': 1.20, 'alto': 0.80},
}


# -- Modelo de simulacion -----------------------------------------------------

class TerminalMicros:
    def __init__(self, env):
        self.env = env
        self.cola                   = []
        self.micro_cargando         = False
        self.total_llegadas         = 0
        self.pasajeros_atendidos    = 0
        self.micros_despachados     = 0
        self.tiempos_entre_llegadas = []
        self.tiempos_espera         = []
        self.tiempos_servicio       = []
        self.tiempos_reposicion     = []


def _proceso_llegadas(env, terminal, params):
    n = 0
    while True:
        t = burr_rv(**params)
        terminal.tiempos_entre_llegadas.append(t)
        yield env.timeout(t)
        n += 1
        terminal.total_llegadas += 1
        terminal.cola.append({'id': n, 't_llegada': env.now})
        print(f"  [t={env.now:.1f}s] Pasajero #{n} llego | Cola: {len(terminal.cola)}")


def _proceso_despacho(env, terminal, params_serv, params_repos, f_serv, f_repos):
    while True:
        t_repos = gamma_3p_rv(**params_repos) * f_repos
        terminal.tiempos_reposicion.append(t_repos)
        yield env.timeout(t_repos)

        terminal.micros_despachados += 1

        if not terminal.cola:
            continue

        t_serv = wakeby_rv(**params_serv) * f_serv
        terminal.micro_cargando = True
        print(f"  [t={env.now:.1f}s] Micro #{terminal.micros_despachados} cargando ({t_serv:.1f}s) | Cola: {len(terminal.cola)}")
        yield env.timeout(t_serv)
        terminal.micro_cargando = False

        # Embarque FIFO hasta capacidad
        n_suben  = min(len(terminal.cola), CAPACIDAD_MICRO)
        subiendo = terminal.cola[:n_suben]
        terminal.cola = terminal.cola[n_suben:]

        for p in subiendo:
            terminal.tiempos_espera.append(env.now - p['t_llegada'])

        terminal.pasajeros_atendidos += n_suben
        terminal.tiempos_servicio.append(t_serv)
        ids = [p['id'] for p in subiendo]
        print(f"  [t={env.now:.1f}s] Micro #{terminal.micros_despachados} partio | Subieron {n_suben}: {ids} | Cola: {len(terminal.cola)}")


def ejecutar_replica(llegadas_params, servicio_params, reposicion_params, f_serv=1.0, f_repos=1.0):
    env      = simpy.Environment()
    terminal = TerminalMicros(env)

    env.process(_proceso_llegadas(env, terminal, llegadas_params))
    env.process(_proceso_despacho(env, terminal, servicio_params, reposicion_params, f_serv, f_repos))

    # Avanza hasta TIEMPO_SIMULACION; si hay un micro cargando, lo deja terminar
    while True:
        proximo = env.peek()
        if proximo == float('inf'):
            break
        if not terminal.micro_cargando and proximo > TIEMPO_SIMULACION:
            break
        env.step()

    serv_validos = [t for t in terminal.tiempos_servicio if t > 0]
    return {
        'A':  np.mean(terminal.tiempos_entre_llegadas) if terminal.tiempos_entre_llegadas else 0,
        'S':  np.mean(serv_validos)                    if serv_validos                     else 0,
        'R':  np.mean(terminal.tiempos_reposicion)     if terminal.tiempos_reposicion      else 0,
        'Wq': np.mean(terminal.tiempos_espera)         if terminal.tiempos_espera          else 0,
    }


# -- DoE 2^3 + punto central --------------------------------------------------

def _nivel_codificado(nivel):
    return 1 if nivel == 'bajo' else (-1 if nivel == 'alto' else 0)


def ejecutar_doe():
    escenarios = list(product(['bajo', 'alto'], repeat=3)) + [('centro', 'centro', 'centro')]
    filas = []

    for idx, (nA, nS, nR) in enumerate(escenarios, start=1):
        print(f"\n=== Nueva corrida {idx} ===")

        llegadas_params = {**LLEGADAS_PARAMS}
        if nA != 'centro':
            llegadas_params['beta'] = DOE_NIVELES['arribos'][nA]
        f_serv  = DOE_NIVELES['servicio'][nS]   if nS != 'centro' else 1.0
        f_repos = DOE_NIVELES['reposicion'][nR] if nR != 'centro' else 1.0

        for rep in range(1, NUM_REPLICAS + 1):
            print(f"  Replica {rep}/{NUM_REPLICAS}")
            metrics = ejecutar_replica(llegadas_params, SERVICIO_PARAMS, REPOSICION_PARAMS, f_serv, f_repos)
            filas.append({
                'corrida': idx, 'replica': rep,
                'A_nivel': _nivel_codificado(nA),
                'S_nivel': _nivel_codificado(nS),
                'R_nivel': _nivel_codificado(nR),
                **metrics,
            })

    df = pd.DataFrame(filas)[['corrida', 'replica', 'A_nivel', 'S_nivel', 'R_nivel', 'A', 'S', 'R', 'Wq']]
    _guardar_excel(df)


def _guardar_excel(df):
    resultados_dir = os.path.join(os.path.dirname(__file__), 'resultados')
    os.makedirs(resultados_dir, exist_ok=True)

    path = os.path.join(resultados_dir, f'doe_r{NUM_REPLICAS}.xlsx')
    try:
        df.to_excel(path, index=False)
    except PermissionError:
        ts   = datetime.now().strftime('%Y%m%d_%H%M%S')
        path = os.path.join(resultados_dir, f'doe_r{NUM_REPLICAS}_{ts}.xlsx')
        df.to_excel(path, index=False)

    print(f"\nResultados guardados en: {path}")


if __name__ == '__main__':
    ejecutar_doe()