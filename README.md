# Simulación de Terminal de Micros

Proyecto final de Simulación — Modelado y análisis de una terminal de micros mediante simulación de eventos discretos y diseño de experimentos (DoE 2³).

**Autores:** Vijandi Iván Andres · Benjamín Elizalde

---

## ¿Qué hace el proyecto?

Simula la operación de una terminal de micros donde los pasajeros llegan según una distribución Burr, los micros cargan pasajeros según una distribución Wakeby y la reposición de micros sigue una Gamma 3P.

Se ejecuta un **diseño factorial 2³ + punto central** variando tres factores:
- **A** — tiempo entre llegadas de pasajeros
- **S** — tiempo de servicio (carga del micro)
- **R** — tiempo de reposición del micro

El resultado principal es una tabla con el tiempo de espera en cola **Wq** para cada corrida y réplica, exportada a Excel.

---

## Estructura

```
simulacion_terminal.py   # Simulación + DoE → genera el Excel
SuperficieRespuesa.py    # Gráfico 3D de la superficie de respuesta
DiseñoFactorial.py       # Gráfico del cubo 2³ con punto central
resultados/              # Salidas generadas (Excel, imágenes)
```

---

## Instalación

```bash
pip install -r requirements.txt
```

---

## Cómo correr

### Simulación + DoE (genera el Excel)
```bash
python simulacion_terminal.py
```
Genera `resultados/doe_r3.xlsx` con las métricas de cada corrida y réplica.

### Gráfico de superficie de respuesta
```bash
python SuperficieRespuesa.py
```
Genera `resultados/superficie_respuesta.png`.

### Gráfico del diseño factorial
```bash
python DiseñoFactorial.py
```
Genera `resultados/diseno_doe.png`.

