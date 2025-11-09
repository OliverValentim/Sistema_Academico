# Sistema Acadêmico Colaborativo

# Funcionalidades
- Cadastro de alunos, cursos, turmas e matérias
- Chatbot com respostas automáticas
- Atualização em tempo real (WebSocket)

# Executável
1. Baixe a versão mais recente: [Download SistemaAcademico.exe](https://github.com/OliverValentim/Sistema_Academico/releases/latest)
2. Extraia a pasta
3. **Dê dois cliques em `sistema.bat`**
4. Tudo roda automaticamente!

## Desenvolvimento
```bash
# Backend
uvicorn backend.servidor:app_sio --reload

# Frontend (ou use o .exe)
python frontend/cliente.py

