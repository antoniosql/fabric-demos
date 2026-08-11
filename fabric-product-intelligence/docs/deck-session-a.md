---
marp: true
title: Gobierno de principio a fin en Microsoft Fabric
---

# Gobierno de principio a fin en Microsoft Fabric

Calidad, linaje, Purview y una app operativa de gobierno

---

# La pregunta incomoda

¿Confiarias este dato a un agente?

- Origen
- Owner
- Actualizacion
- Calidad
- Linaje
- Impacto

---

# Arquitectura

CSV en OneLake -> tablas raw.* -> Curated -> Reglas gov_* -> SQL database/App -> Accion

---

# Calidad Como Contrato

- Profiling para entender
- Reglas para declarar expectativa
- Score para medir
- Acciones para remediar
- Tendencia para mejorar

---

# Gobierno Operativo

`gov_asset`, `gov_quality_rule`, `gov_quality_run`, `gov_quality_result`, `gov_lineage_edge`, `gov_policy_signal`, `gov_action`

---

# Cierre

La app convierte señales dispersas en una experiencia de gestion.
