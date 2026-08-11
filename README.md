# Fabric Demos

Colección de demos de **Microsoft Fabric**, listas para desplegar de un tirón, construidas alrededor
de **FraSoHome**, un retailer ficticio de hogar y decoración. Cada demo vive en su propia carpeta con
su propio entorno, dependencias y guía de despliegue — pero todas comparten un mismo hilo narrativo:
los mismos datos de FraSoHome, vistos desde ángulos distintos de la plataforma.

| | |
| --- | --- |
| **Casos de uso** | IA generativa sobre datos, agentes conversacionales sobre datos, RAG empresarial |
| **Plataforma** | Microsoft Fabric (Lakehouse, SQL Database, User Data Functions, Fabric Apps) |
| **Despliegue** | Scripts PowerShell / Python de extremo a extremo, idempotentes |
| **Dataset común** | FraSoHome — retailer omnicanal de hogar y decoración |

---

## Las demos

| Demo | En una frase | Stack |
| --- | --- | --- |
| [**Fabric AI Functions**](fabric-ai-functions/) | Sentimiento, clasificación y extracción con IA generativa sobre feedback de clientes, directo en el Lakehouse. | Notebook · AI Functions · PowerShell |
| [**Fabric Data Agent**](fabric-data-agent/) | Un chatbot que responde en lenguaje natural sobre el modelo retail de FraSoHome, con evaluación automática de calidad. | Fabric Data Agent SDK · Notebooks · PowerShell |
| [**FraSoHome RAG Demo**](frasohome-fabric-rag-demo/) | Aplicación RAG empresarial completa: SQL Database en Fabric, backend serverless y frontend web, para resolver una devolución compleja. | SQL Database in Fabric · User Data Functions · Fabric App (React) |
| [**Fabric Product Intelligence**](fabric-product-intelligence/) | Dos sesiones end-to-end: gobierno del dato (calidad, linaje, SQL Database) e IA aplicada (features, scoring de clientes, ontología, Data Agent). | CLI Python · Notebooks · SQL Database in Fabric · Fabric App (Rayfin/React) · Data Agent |
| [**Fabric Medallion Scaffold**](fabric-medallion-scaffold/) | Diseña sin caos: monta el esqueleto de dominio, workspaces por capa y capacidad, y ejecuta un medallión metadata-driven (Bronze/Silver/Gold) sobre los datos retail de FraSoHome. | Dominios/Workspaces · Notebooks PySpark · REST API · runner local (pandas) |

---

### [`fabric-ai-functions/`](fabric-ai-functions/) — AI Functions

Aplica las **AI Functions** de Fabric (`ai.analyze_sentiment`, `ai.classify`, `ai.extract`,
`ai.summarize`, `ai.generate_response`) sobre reseñas y tickets de atención al cliente de FraSoHome,
directamente en un notebook con SQL/Python nativo del Lakehouse.

- Despliegue de extremo a extremo con un solo script: workspace, capacidad, Lakehouse y notebook listo
  para ejecutar.
- Compara la salida del modelo con etiquetas humanas y mide el % de acuerdo.
- Incluye seguimiento de consumo (Capacity Units) por función.

→ [Ver guía de despliegue](fabric-ai-functions/README.md)

### [`fabric-medallion-scaffold/`](fabric-medallion-scaffold/) — Diseña sin caos

Monta el **esqueleto medallón** de FraSoHome aplicando las cuatro decisiones de diseño de la sesión
*Dominios, Workspaces y Capacidades*: separación de **ítems**, **workspaces**, **dominios** y
**capacidades**. La ingesta es **metadata-driven** (`config/ingestion/*.json`) y sigue las convenciones
del "segundo cerebro" de agente (`.agent/reference/`).

- Despliegue idempotente y con *dry-run*: dominio `Retail`, workspaces por capa y capacidad, vía REST API.
- Notebooks PySpark `Bronze → Silver → Gold` (star schema) con columnas de trazabilidad y reglas de calidad.
- **Runner local en pandas** que reproduce el flujo sin tenant — ideal para presentar en vivo.

→ [Ver guía de despliegue](fabric-medallion-scaffold/README.md)

### [`fabric-data-agent/`](fabric-data-agent/) — Data Agent

Construye y publica un **Fabric Data Agent** — *"el chatbot que sí sabe de tus datos"* — sobre un
modelo retail *gold* de FraSoHome (ventas, stock, devoluciones, alertas), y lo evalúa con un set de
referencia.

- Dos notebooks: uno construye las tablas y publica el agente vía SDK; otro lo evalúa automáticamente.
- Preguntas de negocio en lenguaje natural, incluida una prueba negativa para mostrar los límites del
  grano de los datos.
- Despliegue idempotente con `deploy.ps1` / limpieza con `cleanup.ps1`.

→ [Ver guía de despliegue](fabric-data-agent/README.md)

### [`frasohome-fabric-rag-demo/`](frasohome-fabric-rag-demo/) — RAG empresarial

La demo más completa: una aplicación **RAG (Retrieval-Augmented Generation)** de extremo a extremo
para resolver una solicitud de devolución compleja, combinando datos operacionales y políticas internas.

- **SQL Database in Microsoft Fabric** con recuperación híbrida (lexical T-SQL + vectorial) y auditoría.
- **Fabric User Data Functions** como backend Python serverless.
- **Fabric App (Rayfin / React)** como frontend desplegado en Fabric, con login Entra ID.
- Pensada para funcionar aunque las capacidades vectoriales SQL preview no estén habilitadas en tu
  tenant.

→ [Ver guía de despliegue](frasohome-fabric-rag-demo/README.md)

### [`fabric-product-intelligence/`](fabric-product-intelligence/) — Gobierno + IA aplicada

Repositorio pensado para dos sesiones seguidas sobre el mismo dataset retail omnicanal de FraSoHome:
**gobierno del dato de extremo a extremo** y **IA aplicada** sobre ese mismo modelo ya gobernado.

- CLI Python (`fabric_sessions`) que despliega workspace, Lakehouse, SQL Database y Data Agent, sube
  el dataset a OneLake y ejecuta la cadena completa de notebooks en Fabric.
- Notebooks encadenados: ingesta cruda → curado → calidad/linaje (gobierno) → features/scoring con
  MLflow → export de datos para la app (inteligencia).
- Fabric App (Rayfin/React) con vistas de gobierno e inteligencia sobre los mismos datos.
- Incluye contrato TMDL de modelo semántico, ontología y preguntas prevalidadas para el Data Agent.

→ [Ver guía de despliegue](fabric-product-intelligence/README.md)

---

## Estructura del repositorio

Cada demo es autocontenida — no comparten código ni dependencias entre sí:

```text
fabric-demos/
├── fabric-ai-functions/          # Notebook + scripts PowerShell + datos + config propia
├── fabric-data-agent/            # Notebooks + scripts PowerShell + datos + config propia
├── frasohome-fabric-rag-demo/    # App React + SQL + User Data Functions + venv + requirements.txt
└── fabric-product-intelligence/  # CLI Python + notebooks + SQL + Fabric App + venv propia
```

Sigue el README de cada carpeta para desplegarla: cada una documenta sus propios requisitos previos,
variables de entorno/configuración (`config.example.json` o `.env.example`) y pasos de limpieza.
