# Sistema de Captura de Dados e CRM — MaisVida Praia

Aplicação web responsiva e painel de inteligência comercial desenvolvidos em Python e Streamlit para a gestão de relacionamento com clientes (CRM), controle de ocupação de turmas e retenção de alunos flutuantes (Gympass, Totalpass e aulas experimentais) na arena esportiva MaisVida Praia.

Projeto alinhado ao Objetivo de Desenvolvimento Sustentável 8 da ONU (Trabalho Decente e Crescimento Econômico — Meta 8.3), focado na modernização tecnológica e produtividade de micro e pequenas empresas locais.

---

## Arquitetura do Sistema

O software foi estruturado sob uma arquitetura lógica desacoplada em três camadas:

1. **Camada de Apresentação (Frontend Mobile & Painel Web):** Interface responsiva renderizada via Streamlit, contemplando o formulário público de autocadastro rápido via QR Code (fricção zero) e o painel restrito da recepção/gestão.
2. **Camada de Regras de Negócio e Segurança (Backend Python):** Processamento analítico com Pandas, validação estrita e normalização de datas via expressões regulares (RF01), sanitização de entradas contra ataques Cross-Site Scripting (XSS) via codificação de saída HTML (RNF02) e autenticação administrativa protegida por hash criptográfico Bcrypt com salt (RNF01).
3. **Camada de Persistência Híbrida (Dados):** Armazenamento tabular estruturado em arquivo CSV local (`alunos_maisvida.csv`) otimizado por cache em memória (`@st.cache_data`) e sincronização integrada a planilhas remotas (Google Forms / Google Sheets).

---

## Requisitos Implementados

### Requisitos Funcionais (RF)
* **RF01 — Validação e Normalização de Entrada:** Verificação de campos obrigatórios, validação de calendário real e normalização automática de datas digitadas com ou sem separadores para o padrão `DD/MM/AAAA`.
* **RF02 — Carimbo de Tempo Automático:** Registro imutável de data e hora (`Data_Cadastro`) gerado diretamente pelo servidor no ato da submissão.
* **RF03 — Radar de Aniversariantes e Integração WhatsApp:** Identificação automatizada de aniversariantes do dia e dos próximos 7 dias, com geração de link parametrizado (`urllib.parse.quote`) para envio de mensagens de felicitação via API do WhatsApp.
* **RF04 — Indicadores de Ocupação e Modalidades:** Consolidação gráfica da demanda de alunos ativos segmentada por horário de treino, tipo de vínculo e modalidade esportiva, acompanhada de matriz cruzada de lotação.

### Requisitos Não Funcionais (RNF)
* **RNF01 — Segurança de Acesso e Hash Robusto:** Controle de sessão administrativa (bloqueio por padrão / *deny by default*), proteção contra força bruta e verificação de credenciais com algoritmo `bcrypt` (OWASP A01:2021).
* **RNF02 — Proteção contra Injeção (OWASP A03:2021):** Sanitização de strings de entrada utilizando `html.escape` para neutralização de vetores XSS e aplicação do princípio de minimização de dados (Privacy by Design / LGPD).
* **RNF03 — Desempenho e Portabilidade:** Tempo de resposta e renderização inferior a 3,5 segundos para bases de 500 registros utilizando cache em memória, com deploy contínuo em nuvem.
* **RNF04 — Acessibilidade Técnica (WCAG 2.1 Nível AA):** Alto contraste cromático (relação superior a 4.5:1 para leitura sob incidência solar), áreas de toque mínimas de 48x48px, foco visível por teclado e alertas independentes de cor.

---

## Estrutura do Repositório

```text
maisvida-praia-crm/
├── .github/workflows/
│   └── ci.yml               # Pipeline de Integração Contínua (GitHub Actions)
├── .streamlit/
│   └── config.toml          # Configurações de tema claro e alto contraste (WCAG AA)
├── app.py                   # Aplicação principal (Frontend, Regras de Negócio e CRUD)
├── seed_data.py             # Script gerador de massa de testes (500 registros fictícios)
├── test_app.py              # Suíte de testes unitários automatizados (Pytest)
├── requirements.txt         # Dependências do ambiente Python
├── LICENSE                  # Licença MIT
└── README.md                # Documentação técnica do projeto
