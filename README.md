# fabric-demos

Repositorio único que agrupa varias demos independientes de Microsoft Fabric. Cada carpeta es
autocontenida: tiene su propio entorno, dependencias, configuración y README con instrucciones de
despliegue. No comparten código entre sí.

## Demos

- [`fabric-ai-functions/`](fabric-ai-functions/) — AI Functions de Fabric (sentimiento, clasificación,
  extracción) sobre feedback de clientes de FraSoHome.
- [`fabric-data-agent/`](fabric-data-agent/) — Fabric Data Agent: chatbot sobre datos retail de
  FraSoHome, con notebook de construcción/publicación y otro de evaluación.
- [`frasohome-fabric-rag-demo/`](frasohome-fabric-rag-demo/) — Solución RAG completa (SQL Database in
  Fabric + User Data Functions + Fabric App) para gestión de devoluciones de FraSoHome.

Cada carpeta incluye su propio `.gitignore`, ficheros de configuración (`config.example.json` /
`.env.example`) y dependencias (`requirements.txt`, `package.json`, etc.) — sigue el README dentro de
cada una para desplegarla.
