# 🔍 CodeSpy — GitHub Repository Intelligence

> Radiografe qualquer repositório GitHub em segundos. Análise visual de atividade, saúde, linguagens, contribuidores e muito mais.

![CodeSpy Preview](docs/preview.png)

## ✨ Features

- **Score de Saúde** — Avalia atividade, documentação, popularidade e manutenção (grade S→D)
- **Linguagens** — Distribuição visual com cores por linguagem
- **Atividade** — Histórico de commits dos últimos 12 meses
- **Horário dos commits** — Descubra quando o time realmente trabalha
- **Top Contribuidores** — Ranking visual com barra proporcional
- **Issues** — Donut chart com taxa de resolução
- **Releases** — Timeline das últimas versões
- **Zero dependências no frontend** — HTML/CSS/JS puro

## 🚀 Como rodar

### 1. Clone o repositório

```bash
git clone https://github.com/seu-usuario/codespy.git
cd codespy
```

### 2. Configure o backend

```bash
cd backend
pip install -r requirements.txt
```

### 3. (Opcional) Token do GitHub

Sem token, a API do GitHub permite 60 requisições/hora. Com token, sobe para 5.000.

```bash
export GITHUB_TOKEN=ghp_seu_token_aqui
```

> Gere um token em: **GitHub → Settings → Developer settings → Personal access tokens**

### 4. Rode o servidor

```bash
uvicorn main:app --reload
```

### 5. Abra o frontend

```bash
# Em outro terminal, na raiz do projeto:
cd frontend
python -m http.server 3000
```

Acesse: **http://localhost:3000**

---

## 🛠 Stack

| Camada | Tecnologia |
|--------|-----------|
| Backend | Python + FastAPI |
| HTTP Client | httpx (async) |
| Frontend | HTML + CSS + JS (vanilla) |
| API | GitHub REST API v3 |

## 📁 Estrutura

```
codespy/
├── backend/
│   ├── main.py          # API FastAPI
│   └── requirements.txt
├── frontend/
│   └── index.html       # App completo (single file)
├── .github/
│   └── workflows/
│       └── ci.yml       # GitHub Actions
└── README.md
```

## 🔌 Endpoints da API

```
GET /api/analyze/{owner}/{repo}   — Análise completa do repositório
GET /api/user/{username}          — Perfil e top repos do usuário
```

## 🤝 Contribuindo

Pull requests são bem-vindos! Abra uma issue primeiro para discutir mudanças maiores.

## 📄 Licença

MIT © Paulo
