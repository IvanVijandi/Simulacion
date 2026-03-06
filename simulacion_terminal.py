import simpy
import numpy as np
from scipy import stats
import pandas as pd
import matplotlib.pyplot as plt


# <-- Distribuciones -->
def dagum_rv(k, alpha, beta, gamma=0):
    """
    Genera variable aleatoria de distribución Dagum
    PDF: f(x) = (k*alpha/beta) * ((x-gamma)/beta)^(alpha*k-1) / (1 + ((x-gamma)/beta)^alpha)^(k+1)
    """
    u = np.random.uniform(0, 1)
    x = beta * ((u**(-1/k) - 1)**(-1/alpha)) + gamma #Inversa de dagum
    return x


def wakeby_rv(alpha, beta, gamma, delta, xi):
    """
    Genera variable aleatoria de distribución Wakeby
    Cuantil inverso: Q(F) = xi + alpha/beta * (1 - (1-F)^beta) - gamma/delta * (1 - (1-F)^(-delta))
    """
    F = np.random.uniform(0, 1)
    
    if beta != 0 and delta != 0:
        term1 = alpha / beta * (1 - (1 - F)**beta)
        term2 = gamma / delta * (1 - (1 - F)**(-delta))
        x = xi + term1 - term2
    elif beta == 0 and delta != 0:
        term1 = alpha * np.log(1 / (1 - F))
        term2 = gamma / delta * (1 - (1 - F)**(-delta))
        x = xi + term1 - term2
    elif beta != 0 and delta == 0:
        term1 = alpha / beta * (1 - (1 - F)**beta)
        term2 = -gamma * np.log(1 - F)
        x = xi + term1 - term2
    else:
        term1 = alpha * np.log(1 / (1 - F))
        term2 = -gamma * np.log(1 - F)
        x = xi + term1 - term2
    
    return max(x, 0)  # Asegurar no negatividad


def gamma_3p_rv(alpha, beta, gamma):
    """
    Genera variable aleatoria de distribución Gamma 3P
    X = gamma + Y, con Y ~ Gamma(shape=alpha, scale=beta)
    """
    y = np.random.gamma(shape=alpha, scale=beta)
    x = gamma + y
    return max(x, 0)  # Asegurar no negatividad


# <-- Parametros de la simulacion -->

# Parámetros Dagum para tiempo entre llegadas (por hora)
LLEGADAS_PARAMS = {
    '11-12': {'k': 0.76795, 'alpha': 3.4325, 'beta': 12.669, 'gamma': 0},
    '12-13': {'k': 0.87594, 'alpha': 3.2189, 'beta': 13.484, 'gamma': 0},
    '13-14': {'k': 0.92783, 'alpha': 2.2157, 'beta': 12.952, 'gamma': 0}
}

# Parámetros [Tiempo de servicio]
SERVICIO_PARAMS = {
    'alpha': 156.3,
    'beta': 8.5432,
    'gamma': 65.464,
    'delta': -0.66427,
    'xi': 247.21
}

# Parámetros [Tiempo de reposicion] - Gamma 3P
REPOSICION_PARAMS = {
    'alpha': 1.8741,
    'beta': 303.21,
    'gamma': 313.7
}

# Capacidad del micro
CAPACIDAD_MICRO = 55

# Rango horario simulado
HORA_INICIO = 11
HORA_FIN = 14

# Tiempo de simulación (en segundos)
TIEMPO_SIMULACION = (HORA_FIN - HORA_INICIO) * 3600  # 3 horas (11-14)



# <-- CLASES Y FUNCIONES DE LA SIMULACIÓN -->

class TerminalMicros:
    """Clase para gestionar la terminal de micros"""
   
    ## Constructor
    def __init__(self, env):
        self.env = env
        self.cola = []  
        self.pasajeros_atendidos = 0
        self.micros_despachados = 0
        
        # Métricas
        self.tiempos_espera = []
        self.longitudes_cola = []
        self.tiempos_registro = []
        self.pasajeros_por_micro = []
        self.tiempo_total_servicio = []
        
    def registrar_metricas(self):
        """Registra el estado actual de la cola"""
        self.longitudes_cola.append(len(self.cola))
        self.tiempos_registro.append(self.env.now)


def obtener_franja_dagum(tiempo_simulacion):
    """Devuelve la franja horaria Dagum según el tiempo transcurrido de simulación."""
    hora_actual = HORA_INICIO + tiempo_simulacion / 3600

    if hora_actual < 12:
        return '11-12'
    if hora_actual < 13:
        return '12-13'
    return '13-14'


def llegada_pasajeros(env, terminal):
    """Proceso de llegada de pasajeros a la terminal"""
    contPasajeros = 0
    
    while True:
        # Elegir parámetros según la hora simulada (11-12, 12-13, 13-14)
        franja = obtener_franja_dagum(env.now)
        params = LLEGADAS_PARAMS[franja]
        
        # Generar tiempo entre llegadas 
        tiempo_entre_llegadas = dagum_rv(params['k'], params['alpha'], 
                                         params['beta'], params['gamma'])
        
        yield env.timeout(tiempo_entre_llegadas)
        
        # Registrar llegada del pasajero
        contPasajeros += 1
        tiempo_llegada = env.now
        terminal.cola.append({
            'Nro': contPasajeros,
            'tiempo_llegada': tiempo_llegada
        })
        
        terminal.registrar_metricas()
        
        print(f"[{env.now:.2f}s] Pasajero {contPasajeros} llega. Cola: {len(terminal.cola)}")


def despacho_micros(env, terminal):
    """Proceso de despacho de micros desde la plataforma"""
    
    primer_micro = False
    
    while True:
        if not primer_micro:
            tiempo_reposicion = gamma_3p_rv(**REPOSICION_PARAMS)
            yield env.timeout(tiempo_reposicion) ## Simula el tiempo de reposición entre micros / se siguen corrriendo demas procesos (llegada de pasajeros)
        else:
            primer_micro = False
        
        terminal.micros_despachados += 1
        print(f"\n[{env.now:.2f}s] ===== MICRO {terminal.micros_despachados} LLEGA A LA PLATAFORMA =====")
        print(f"Pasajeros en cola: {len(terminal.cola)}")
        
        # Determinar cuántos pasajeros subirán
        pasajeros_a_subir = min(len(terminal.cola), CAPACIDAD_MICRO)
        
        if pasajeros_a_subir == 0:
            print(f"[{env.now:.2f}s] Micro {terminal.micros_despachados} parte vacío (no hay pasajeros)")
            terminal.pasajeros_por_micro.append(0)
            terminal.tiempo_total_servicio.append(0)
            continue
        
        # Servicio (FIFO)
        pasajeros_subiendo = terminal.cola[:pasajeros_a_subir] # Tomar los primeros pasajeros de la cola
        terminal.cola = terminal.cola[pasajeros_a_subir:] # Eliminar los pasajeros que suben de la cola
        
        # Calcular tiempo de servicio TOTAL (una sola muestra Wakeby para todo el grupo)
        # El tiempo de servicio representa el tiempo total para que suban TODOS los pasajeros
        tiempo_servicio_total = wakeby_rv(**SERVICIO_PARAMS)
        
        # Simular el tiempo de servicio (subida de pasajeros)
        yield env.timeout(tiempo_servicio_total)
        
        # Calcular tiempo de espera de cada pasajero
        for pasajero in pasajeros_subiendo:
            tiempo_espera = env.now - pasajero['tiempo_llegada']
            terminal.tiempos_espera.append(tiempo_espera)
        
        terminal.pasajeros_atendidos += pasajeros_a_subir
        terminal.pasajeros_por_micro.append(pasajeros_a_subir)
        terminal.tiempo_total_servicio.append(tiempo_servicio_total)
        
        print(f"[{env.now:.2f}s] Micro {terminal.micros_despachados} parte con {pasajeros_a_subir} pasajeros")
        print(f"Tiempo de carga: {tiempo_servicio_total:.2f}s")
        print(f"Pasajeros restantes en cola: {len(terminal.cola)}")
        
        terminal.registrar_metricas()


def monitor_cola(env, terminal, intervalo=60):
    """Monitorea el estado de la cola periódicamente"""
    while True:
        yield env.timeout(intervalo)
        terminal.registrar_metricas()



# <-- FUNCIÓN PRINCIPAL DE SIMULACIÓN -->


def ejecutar_simulacion():
    """Ejecuta la simulación y genera reportes"""
    
    print("="*70)
    print("SIMULACIÓN DE TERMINAL DE MICROS - LA PLATA")
    print("="*70)
    print(f"Capacidad del micro: {CAPACIDAD_MICRO} pasajeros")
    print(f"Horario simulado: {HORA_INICIO}:00 a {HORA_FIN}:00")
    print(f"Tiempo de simulación: {TIEMPO_SIMULACION/3600:.1f} horas")
    print("="*70)
    print()
    
    # Creamos entorno de simulación y terminal
    env = simpy.Environment()
    terminal = TerminalMicros(env)
    
    # Iniciar procesos
    env.process(llegada_pasajeros(env, terminal))
    env.process(despacho_micros(env, terminal))
    env.process(monitor_cola(env, terminal, intervalo=60))
    
    # Ejecutar simulación
    env.run(until=TIEMPO_SIMULACION)
    
    print("\n" + "="*70)
    print("SIMULACIÓN COMPLETADA")
    print("="*70)
    
    # ========================================================================
    # GENERAR REPORTE DE RESULTADOS
    # ========================================================================
    
    print("\n" + "="*70)
    print("RESULTADOS DE LA SIMULACIÓN")
    print("="*70)
    
    print(f"\n📊 ESTADÍSTICAS GENERALES:")
    print(f"   - Total de pasajeros que llegaron: {len(terminal.cola) + terminal.pasajeros_atendidos}")
    print(f"   - Pasajeros atendidos: {terminal.pasajeros_atendidos}")
    print(f"   - Pasajeros en cola al final: {len(terminal.cola)}")
    print(f"   - Micros despachados: {terminal.micros_despachados}")
    
    if terminal.pasajeros_por_micro:
        print(f"\n🚌 ESTADÍSTICAS DE MICROS:")
        print(f"   - Promedio de pasajeros por micro: {np.mean(terminal.pasajeros_por_micro):.2f}")
        print(f"   - Máximo de pasajeros en un micro: {np.max(terminal.pasajeros_por_micro)}")
        print(f"   - Mínimo de pasajeros en un micro: {np.min(terminal.pasajeros_por_micro)}")
        print(f"   - Micros a capacidad completa: {sum(1 for x in terminal.pasajeros_por_micro if x == CAPACIDAD_MICRO)}")
    
    if terminal.tiempos_espera:
        print(f"\n⏱️  TIEMPOS DE ESPERA:")
        print(f"   - Tiempo de espera promedio: {np.mean(terminal.tiempos_espera):.2f} segundos ({np.mean(terminal.tiempos_espera)/60:.2f} minutos)")
        print(f"   - Tiempo de espera máximo: {np.max(terminal.tiempos_espera):.2f} segundos ({np.max(terminal.tiempos_espera)/60:.2f} minutos)")
        print(f"   - Tiempo de espera mínimo: {np.min(terminal.tiempos_espera):.2f} segundos ({np.min(terminal.tiempos_espera)/60:.2f} minutos)")
        print(f"   - Desviación estándar: {np.std(terminal.tiempos_espera):.2f} segundos")
    
    if terminal.longitudes_cola:
        print(f"\n👥 LONGITUD DE LA COLA:")
        print(f"   - Longitud promedio: {np.mean(terminal.longitudes_cola):.2f} pasajeros")
        print(f"   - Longitud máxima: {np.max(terminal.longitudes_cola)} pasajeros")
        print(f"   - Longitud al final: {terminal.longitudes_cola[-1]} pasajeros")
    
    if terminal.tiempo_total_servicio:
        print(f"\n⚙️  TIEMPOS DE SERVICIO:")
        print(f"   - Tiempo promedio de carga: {np.mean(terminal.tiempo_total_servicio):.2f} segundos ({np.mean(terminal.tiempo_total_servicio)/60:.2f} minutos)")
        print(f"   - Tiempo máximo de carga: {np.max(terminal.tiempo_total_servicio):.2f} segundos ({np.max(terminal.tiempo_total_servicio)/60:.2f} minutos)")
    
    
if __name__ == "__main__":
    ejecutar_simulacion()
