# Sistema Acadêmico Colaborativo

# Funcionalidades
- Cadastro de alunos, cursos, turmas e matérias
- Chatbot com respostas automáticas
- Atualização em tempo real (WebSocket)

# Executável
Baixe a versão mais recente:
[Download SistemaAcademico.exe](https://github.com/OliverValentim/Sistema_Academico/releases/latest)

## Desenvolvimento
```bash
# Backend
uvicorn backend.servidor:app_sio --reload

# Frontend (ou use o .exe)
python frontend/cliente.py
