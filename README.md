# Batalha Naval Multiplayer (Real-time)

Este projeto consiste em um jogo de Batalha Naval multiplayer em tempo real, utilizando uma arquitetura distribuída com comunicação via WebSockets. O sistema é composto por um backend em Python e um frontend em JavaScript.

Para acessar o jogo online: https://batalha-naval-2scs.onrender.com/

## Arquitetura de Deploy

A aplicação utiliza uma estratégia de deploy híbrido para otimizar a persistência de dados e a performance de entrega:

* **Frontend (Vercel):** Hospeda os arquivos estáticos (HTML, CSS, JS) com entrega otimizada via CDN.
* **Backend (Render):** Executa o servidor ASGI que mantém as conexões WebSocket ativas para a comunicação entre os jogadores.



## Tecnologias Utilizadas

### Backend
* **FastAPI:** Framework Python de alta performance para construção de APIs e WebSockets.
* **WebSockets:** Protocolo para comunicação bidirecional de baixa latência.
* **Uvicorn:** Servidor ASGI utilizado para servir a aplicação Python.

### Frontend
* **JavaScript (Vanilla):** Gerenciamento de estado do jogo e manipulação do DOM sem bibliotecas externas.
* **CSS3:** Interface responsiva com foco em CSS Grid e Flexbox.
* **HTML5:** Estrutura da interface do usuário.

## Funcionalidades

* **Sistema de Salas:** Criação e entrada em salas privadas via código alfanumérico de 4 dígitos.
* **Sincronização de Turnos:** Lógica de jogo processada no servidor para garantir a integridade da partida.
* **Interface Dinâmica:** Atualização visual imediata de acertos e erros nos tabuleiros.
* **Revanche:** Sistema para reiniciar a partida mantendo os mesmos jogadores na sala.

## Instruções para Execução Local

### Pré-requisitos
* Python 3.10 ou superior.

### Configuração do Ambiente

1. Clone o repositório:
```Bash
git clone [https://github.com/pedro-rafaiel/batalha-naval.git](https://github.com/pedro-rafaiel/batalha-naval.git)
cd batalha-naval
```

Crie e ative o ambiente virtual:

Bash
### Criar o ambiente
python -m venv venv

### Ativar no Windows:
venv\Scripts\activate

### Ativar no Linux/Mac:
source venv/bin/activate
Instale as dependências:

```Bash
pip install -r requirements.txt
```
Inicie o servidor:

```Bash
uvicorn server:app --reload
```
Nota: O servidor estará disponível em http://127.0.0.1:8000. O frontend está configurado para detectar o ambiente e conectar automaticamente ao host local.

Estrutura do Projeto
server.py: Código principal do backend e gerenciamento de WebSockets.

static/: Pasta contendo client.html, style.css e main.js.

vercel.json: Configurações específicas para o deploy na Vercel.

requirements.txt: Dependências do projeto (FastAPI, Uvicorn, Websockets).
