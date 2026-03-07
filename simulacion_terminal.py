import simpy
import numpy as np
from scipy import stats
import pandas as pd
import os
from itertools import product
import matplotlib.pyplot as plt
from datetime import datetime


def burr_rv(k, alpha, beta, gamma=0):
    """ Genera variable aleatoria de distribución Burr """
    u = np.random.uniform(0, 1)
    x = gamma + beta * (((1 - u)**(-1/k) - 1)**(1/alpha))
    return x


def wakeby_rv(alpha, beta, gamma, delta, xi):
    """Genera variable aleatoria Wakeby por transformación inversa."""
    u = np.random.uniform(np.finfo(float).eps, 1 - np.finfo(float).eps)

    if beta != 0 and delta != 0:
        term1 = alpha / beta * (1 - (1 - u)**beta)
        term2 = gamma / delta * (1 - (1 - u)**(-delta))
        x = xi + term1 - term2
    elif beta == 0 and delta != 0:
        term1 = alpha * np.log(1 / (1 - u))
        term2 = gamma / delta * (1 - (1 - u)**(-delta))
        x = xi + term1 - term2
    elif beta != 0 and delta == 0:
        term1 = alpha / beta * (1 - (1 - u)**beta)
        term2 = -gamma * np.log(1 - u)
        x = xi + term1 - term2
    else:
        term1 = alpha * np.log(1 / (1 - u))
        term2 = -gamma * np.log(1 - u)
        x = xi + term1 - term2
    
    return max(x, 0)  


def gamma_3p_rv(alpha, beta, gamma):
    """ Genera variable aleatoria de distribución Gamma 3P por transformación inversa"""
    u = np.random.uniform(np.finfo(float).eps, 1 - np.finfo(float).eps)
    y = stats.gamma.ppf(u, a=alpha, scale=beta)
    x = gamma + y
    return max(x, 0)  


LLEGADAS_PARAMS_BASE = {'k': 1.1786, 'alpha': 2.9348, 'beta': 12.183, 'gamma': 0}

SERVICIO_PARAMS_BASE = {
    'alpha': 156.3,
    'beta': 8.5432,
    'gamma': 65.464,
    'delta': -0.66427,
    'xi': 247.21
}

REPOSICION_PARAMS_BASE = {
    'alpha': 1.8741,
    'beta': 303.21,
    'gamma': 313.7
}

CAPACIDAD_MICRO = 55
TIEMPO_SIMULACION = 3600
NUM_REPLICAS = 3


DOE_NIVELES = {
    'arribos': {
        'bajo': 15.2,
        'alto': 10.1
    },
    'servicio': {
        'bajo': 1.20,
        'alto': 0.80
    },
    'reposicion': {
        'bajo': 1.20,
        'alto': 0.80
    }
}

class TerminalMicros:
    """Clase para gestionar la terminal de micros"""

    def __init__(self, env):
        self.env = env
        self.cola = []
        self.total_llegadas = 0
        self.pasajeros_atendidos = 0
        self.micros_despachados = 0

        self.tiempos_entre_llegadas = []
        self.tiempos_espera = []
        self.tiempo_total_servicio = []
        self.tiempos_reposicion = []
        self.micro_cargando = False

        self.eventos_tiempo = [0.0]
        self.hist_cola = [0]
        self.hist_arribos_acum = [0]
        self.hist_atendidos_acum = [0]
        self.tiempos_llegada_micro = []
        self.tiempos_partida_micro = []
        self.estado_carga_t = [0.0]
        self.estado_carga_y = [0]

    def registrar_evento_cola(self):
        """Registra el estado del sistema para gráficos temporales."""
        self.eventos_tiempo.append(self.env.now)
        self.hist_cola.append(len(self.cola))
        self.hist_arribos_acum.append(self.total_llegadas)
        self.hist_atendidos_acum.append(self.pasajeros_atendidos)


def llegada_pasajeros(env, terminal, llegadas_params):
    """Proceso de llegada de pasajeros a la terminal"""
    contPasajeros = 0
    
    while True:
        tiempo_entre_llegadas = burr_rv(
            llegadas_params['k'],
            llegadas_params['alpha'],
            llegadas_params['beta'],
            llegadas_params['gamma']
        )
        terminal.tiempos_entre_llegadas.append(tiempo_entre_llegadas)
        
        yield env.timeout(tiempo_entre_llegadas)
        
        contPasajeros += 1
        terminal.total_llegadas += 1
        tiempo_llegada = env.now
        terminal.cola.append({
            'Nro': contPasajeros,
            'tiempo_llegada': tiempo_llegada
        })
        terminal.registrar_evento_cola()


def despacho_micros(env, terminal, servicio_params, reposicion_params, factor_servicio, factor_reposicion):
    """Proceso de despacho de micros desde la plataforma"""
    
    primer_micro = False
    
    while True:
        if not primer_micro:
            tiempo_reposicion = gamma_3p_rv(**reposicion_params) * factor_reposicion
            terminal.tiempos_reposicion.append(tiempo_reposicion)
            yield env.timeout(tiempo_reposicion)
        else:
            primer_micro = False
        
        terminal.micros_despachados += 1
        terminal.tiempos_llegada_micro.append(env.now)

        if len(terminal.cola) == 0:
            terminal.tiempo_total_servicio.append(0)
            continue

        # Durante la carga siguen llegando pasajeros a la cola.
        tiempo_servicio_total = wakeby_rv(**servicio_params) * factor_servicio
        terminal.micro_cargando = True
        terminal.estado_carga_t.append(env.now)
        terminal.estado_carga_y.append(1)

        yield env.timeout(tiempo_servicio_total)
        terminal.micro_cargando = False
        terminal.estado_carga_t.append(env.now)
        terminal.estado_carga_y.append(0)

        # Al finalizar la carga, suben en FIFO hasta capacidad.
        pasajeros_a_subir = min(len(terminal.cola), CAPACIDAD_MICRO)
        pasajeros_subiendo = terminal.cola[:pasajeros_a_subir]
        terminal.cola = terminal.cola[pasajeros_a_subir:]

        for pasajero in pasajeros_subiendo:
            tiempo_espera = env.now - pasajero['tiempo_llegada']
            terminal.tiempos_espera.append(tiempo_espera)
        
        terminal.pasajeros_atendidos += pasajeros_a_subir
        terminal.tiempo_total_servicio.append(tiempo_servicio_total)
        terminal.tiempos_partida_micro.append(env.now)
        terminal.registrar_evento_cola()

def ejecutar_escenario(llegadas_params, servicio_params, reposicion_params, factor_servicio, factor_reposicion):
    """Ejecuta un escenario individual y devuelve métricas DoE."""

    env = simpy.Environment()
    terminal = TerminalMicros(env)

    env.process(llegada_pasajeros(env, terminal, llegadas_params))
    env.process(despacho_micros(env, terminal, servicio_params, reposicion_params, factor_servicio, factor_reposicion))
    
    # Ejecutar simulación: si el horizonte corta durante una carga,
    # se continúa hasta que ese micro termine de subir pasajeros.
    while True:
        proximo_evento = env.peek()
        if proximo_evento == float('inf'):
            break
        if (not terminal.micro_cargando) and (proximo_evento > TIEMPO_SIMULACION):
            break
        env.step()
    
    tiempos_servicio_validos = [t for t in terminal.tiempo_total_servicio if t > 0]
    tiempo_llegadas_promedio = np.mean(terminal.tiempos_entre_llegadas) if terminal.tiempos_entre_llegadas else 0
    tiempo_servicio_promedio = np.mean(tiempos_servicio_validos) if tiempos_servicio_validos else 0
    tiempo_reposicion_promedio = np.mean(terminal.tiempos_reposicion) if terminal.tiempos_reposicion else 0
    tiempo_espera_cola_promedio = np.mean(terminal.tiempos_espera) if terminal.tiempos_espera else 0

    return {
        'tiempo_llegadas_promedio_segundos': tiempo_llegadas_promedio,
        'tiempo_servicio_promedio_segundos': tiempo_servicio_promedio,
        'tiempo_reposicion_promedio_segundos': tiempo_reposicion_promedio,
        'tiempo_espera_cola_promedio_segundos': tiempo_espera_cola_promedio,
    }, terminal


def generar_grafico_operativo(terminal, resultados_dir):
    """Genera gráfico no-DoE con evolución de llegadas, micros y cola."""
    tiempo_horas = np.array(terminal.eventos_tiempo) / 3600
    llegadas_micro_horas = np.array(terminal.tiempos_llegada_micro) / 3600 if terminal.tiempos_llegada_micro else np.array([])
    partidas_micro_horas = np.array(terminal.tiempos_partida_micro) / 3600 if terminal.tiempos_partida_micro else np.array([])
    estado_t_horas = np.array(terminal.estado_carga_t) / 3600

    fig, axs = plt.subplots(3, 1, figsize=(12, 10), sharex=True)

    axs[0].step(tiempo_horas, terminal.hist_cola, where="post", color="tab:orange", linewidth=2, label="Pasajeros en cola")
    for i, t in enumerate(llegadas_micro_horas):
        axs[0].axvline(t, color="tab:blue", linestyle="--", alpha=0.35, linewidth=1.2,
                       label="Llegada de micro" if i == 0 else None)
    for i, t in enumerate(partidas_micro_horas):
        axs[0].axvline(t, color="tab:red", linestyle=":", alpha=0.45, linewidth=1.2,
                       label="Partida de micro" if i == 0 else None)
    axs[0].set_ylabel("Cola")
    axs[0].set_title("Evolución operativa: llegadas de pasajeros y micros")
    axs[0].grid(True, alpha=0.25)
    axs[0].legend(loc="upper left")

    axs[1].step(tiempo_horas, terminal.hist_arribos_acum, where="post", color="tab:green", linewidth=2,
                label="Arribos acumulados")
    axs[1].step(tiempo_horas, terminal.hist_atendidos_acum, where="post", color="tab:purple", linewidth=2,
                label="Atendidos acumulados")
    axs[1].set_ylabel("Acumulado")
    axs[1].grid(True, alpha=0.25)
    axs[1].legend(loc="upper left")

    axs[2].step(estado_t_horas, terminal.estado_carga_y, where="post", color="tab:brown", linewidth=2,
                label="Estado de carga")
    axs[2].set_yticks([0, 1])
    axs[2].set_yticklabels(["No cargando", "Cargando"])
    axs[2].set_ylabel("Micro")
    axs[2].set_xlabel("Tiempo simulado (horas)")
    axs[2].grid(True, alpha=0.25)
    axs[2].legend(loc="upper left")

    fig.tight_layout()
    fig.savefig(os.path.join(resultados_dir, "evolucion_operativa.png"), dpi=150)
    plt.close(fig)


def ejecutar_doe():
    """Ejecuta DoE 2^3 + punto central con réplicas."""

    resultados = []
    corrida_idx = 0

    escenarios_factoriales = list(product(['bajo', 'alto'], repeat=3))
    escenarios = escenarios_factoriales + [('centro', 'centro', 'centro')]

    for nivel_arribos, nivel_servicio, nivel_reposicion in escenarios:
        corrida_idx += 1
        for replica in range(1, NUM_REPLICAS + 1):
            print(f"Ejecutando corrida {corrida_idx}, replica {replica}/{NUM_REPLICAS}: "
                  f"A_nivel={1 if nivel_arribos=='bajo' else (-1 if nivel_arribos=='alto' else 0)}, "
                  f"S_nivel={1 if nivel_servicio=='bajo' else (-1 if nivel_servicio=='alto' else 0)}, "
                  f"R_nivel={1 if nivel_reposicion=='bajo' else (-1 if nivel_reposicion=='alto' else 0)}")

            llegadas_params = dict(LLEGADAS_PARAMS_BASE)
            if nivel_arribos != 'centro':
                llegadas_params['beta'] = DOE_NIVELES['arribos'][nivel_arribos]

            factor_servicio = DOE_NIVELES['servicio'][nivel_servicio] if nivel_servicio != 'centro' else 1.0
            factor_reposicion = DOE_NIVELES['reposicion'][nivel_reposicion] if nivel_reposicion != 'centro' else 1.0

            metricas, _ = ejecutar_escenario(
                llegadas_params=llegadas_params,
                servicio_params=SERVICIO_PARAMS_BASE,
                reposicion_params=REPOSICION_PARAMS_BASE,
                factor_servicio=factor_servicio,
                factor_reposicion=factor_reposicion,
            )

            metricas['corrida'] = corrida_idx
            metricas['replica'] = replica
            metricas['A_nivel'] = 1 if nivel_arribos == 'bajo' else (-1 if nivel_arribos == 'alto' else 0)
            metricas['S_nivel'] = 1 if nivel_servicio == 'bajo' else (-1 if nivel_servicio == 'alto' else 0)
            metricas['R_nivel'] = 1 if nivel_reposicion == 'bajo' else (-1 if nivel_reposicion == 'alto' else 0)
            metricas['A'] = metricas['tiempo_llegadas_promedio_segundos']
            metricas['S'] = metricas['tiempo_servicio_promedio_segundos']
            metricas['R'] = metricas['tiempo_reposicion_promedio_segundos']

            resultados.append(metricas)

    resultados_dir = os.path.join(os.path.dirname(__file__), "resultados")
    os.makedirs(resultados_dir, exist_ok=True)

    for obsolete in ["doe_3factores_2niveles.csv", "graficos_doe.png"]:
        obsolete_path = os.path.join(resultados_dir, obsolete)
        if os.path.exists(obsolete_path):
            os.remove(obsolete_path)

    df_resultados = pd.DataFrame(resultados)
    
    cols_orden = ['corrida', 'replica', 'A_nivel', 'S_nivel', 'R_nivel', 'A', 'S', 'R',
                  'tiempo_espera_cola_promedio_segundos']
    df_resultados = df_resultados[cols_orden]
    df_resultados = df_resultados.rename(columns={'tiempo_espera_cola_promedio_segundos': 'Wq'})
    
    excel_path = os.path.join(resultados_dir, f"doe_3factores_2niveles_r{NUM_REPLICAS}.xlsx")
    try:
        df_resultados.to_excel(excel_path, index=False)
        print(f"\nResultados DoE guardados en: {excel_path}")
    except PermissionError:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        excel_path = os.path.join(resultados_dir, f"doe_3factores_2niveles_r{NUM_REPLICAS}_{ts}.xlsx")
        df_resultados.to_excel(excel_path, index=False)
        print(f"\nResultados DoE guardados en: {excel_path} (copía con timestamp)")

    _, terminal_ref = ejecutar_escenario(
        llegadas_params=LLEGADAS_PARAMS_BASE,
        servicio_params=SERVICIO_PARAMS_BASE,
        reposicion_params=REPOSICION_PARAMS_BASE,
        factor_servicio=1.0,
        factor_reposicion=1.0,
    )
    generar_grafico_operativo(terminal_ref, resultados_dir)
    
    
if __name__ == "__main__":
    ejecutar_doe()
