# Fabric AI Functions — Demo 1 (FraSoHome)

Despliegue **desde cero** de la demo para trabajar con las AI Functions en Fabric

El script crea un **workspace** de Fabric, lo asigna a tu **capacidad**, crea un **Lakehouse**, sube
los datos de FraSoHome e importa el **notebook** de la demo listo para ejecutar.

La demo aplica AI Functions (sentimiento, clasificación y extracción) sobre el feedback de clientes
de **FraSoHome**, un retailer omnicanal de hogar y decoración.

---

## Contenido del repo

```
fabric-ai-functions/
├── README.md
├── config.example.json          # Plantilla de configuración (subscription, tenant, capacidad…)
├── .gitignore
├── data/
│   ├── feedback_clientes.csv     # Reseñas de clientes (con sentimiento y tema etiquetados a mano)
│   └── tickets_atencion_cliente.csv
├── notebooks/
│   └── 01_ai_functions_feedback.ipynb   # Notebook de la demo
└── scripts/
    ├── FabricApi.psm1            # Módulo auxiliar (REST Fabric + subida a OneLake)
    ├── deploy.ps1               # Despliegue de extremo a extremo
    └── cleanup.ps1             # Borra el workspace (no la capacidad)
```

---

## Requisitos previos

1. **PowerShell 7+** (`pwsh`).
2. **Azure CLI** (`az`) instalada.
3. Un usuario con permisos para:
   - crear **workspaces** en Fabric,
   - **asignar** workspaces a la capacidad,
   - ser **administrador de la capacidad** .
4. La **capacidad Fabric** debe estar **activa** (no pausada).
5. Tenant switch de **Copilot / funciones basadas en Azure OpenAI** habilitado en el tenant
   (necesario para las AI Functions).

## Despliegue en 3 pasos

```powershell
# 1) Autentícate en el tenant correcto
az login --tenant <TU TENANT ID>

# 2) (Opcional) copia la config y ajusta nombres de workspace/lakehouse
Copy-Item config.example.json config.local.json

Configura los parámetros en tu config.local.json
# 3) Despliega
./scripts/deploy.ps1
```

Al terminar verás la URL del workspace en el portal. Abre el notebook
**`01_ai_functions_feedback`** y ejecútalo de arriba a abajo.

> El notebook se importa con el Lakehouse ya asociado como **lakehouse por defecto**, así que
> `pd.read_csv("/lakehouse/default/Files/frasohome/...")` funciona sin configuración adicional.

---

## Qué hace el despliegue (`deploy.ps1`)

1. Obtiene tokens de acceso vía Azure CLI (Fabric API y OneLake storage).
2. Localiza la capacidad.
3. Crea (o reutiliza) el workspace `FraSoHome-AI-Functions` y lo **asigna a la capacidad**.
4. Crea (o reutiliza) el Lakehouse `lh_frasohome`.
5. Sube los CSV a `Files/frasohome/` en OneLake.
6. Importa el notebook de la demo con el Lakehouse por defecto ya vinculado.

Es **idempotente**: si vuelves a ejecutarlo, reutiliza lo que ya exista y actualiza el notebook.

---

## La demo (notebook)

| Paso | AI Function | Qué muestra |
| --- | --- | --- |
| Sentimiento | `ai.analyze_sentiment` (etiquetas propias) | Compara la salida de la IA con la etiqueta humana y calcula el % de acuerdo |
| Tema | `ai.classify` | Clasifica el feedback en las categorías reales del negocio |
| Categoría de producto | `ai.classify` | Infiere la categoría (Sofás, Iluminación…) desde el texto |
| Entidades | `ai.extract` / `ExtractLabel` | Extrae producto y atributos criticados |
| Tickets | `ai.summarize`, `ai.classify`, `ai.generate_response` | Resume, clasifica y redacta un borrador de respuesta |
| Consumo | `ai.stats` | Tokens y modelo utilizados (gpt-5-mini por defecto) |

---

## Limpieza

```powershell
./scripts/cleanup.ps1        # pide confirmación; borra el workspace, no la capacidad
```

---

## Notas

- Las AI Functions requieren **Fabric Runtime 1.3 o superior**; el modelo por defecto es
  **gpt-5-mini** (`reasoning_effort="low"`).
- El consumo se mide en **Capacity Units (CU)** y aparece en la **Fabric Capacity Metrics app** como
  operación **AI Functions**. Prototipa con muestras antes de procesar todo el histórico.
- `config.local.json` está en `.gitignore` para no versionar tus identificadores.
