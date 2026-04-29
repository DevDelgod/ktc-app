🎯 Kafu Tiro Certo - Performance App
Este repositório contém o código-fonte do ecossistema de dados da Kafu Tiro Certo, projetado para transformar a coleta de dados de campo em inteligência esportiva de alto nível.

🚀 Funcionalidades Atuais
Renderização de Alta Precisão: Alvos oficiais renderizados via HTML5 Canvas, permitindo a marcação exata das coordenadas X e Y de cada impacto.

Banco de Dados em Tempo Real: Sincronização instantânea com Firebase Firestore, garantindo latência quase zero no salvamento de séries.

Arquitetura Hierárquica: Organização de dados em estrutura Pai-Filho (Sessões > Disparos), otimizando o consumo de dados e a performance do app.

ETL Automatizado: Script em Python para extração e tratamento de dados NoSQL, convertendo-os em tabelas relacionais prontas para análise.

🛠️ Stack Técnica
Front-end: HTML5, CSS3 e JavaScript (ES6+).

Banco de Dados: Firebase Firestore (NoSQL).

Integração & ETL: Python (Pandas & Firebase-Admin).

Visualização: Power BI (Dashboards de agrupamento e consistência).

Controle de Versão: Git & GitHub.

🏗️ Estrutura do Banco (Firestore)
treinos/ (Coleção Pai): Armazena metadados da sessão (Atleta, Clima, Distância, Data).

disparos/ (Subcoleção Filho): Armazena as coordenadas cartesianas e pontuações de cada flecha individual.

🗺️ Roadmap de Desenvolvimento
[ ] Refatoração Modular: Separação completa de HTML, CSS e Lógica JS para melhor manutenção.

[ ] Modo Offline: Implementação de cache local para treinos em locais sem conectividade.

[ ] Dashboard Avançado: Integração direta via Python para cálculo automático de agrupamento (desvio padrão) no Power BI.

Propriedade intelectual de Gabriel Delgado Ribeiro - Kafu Tiro Certo © 2026