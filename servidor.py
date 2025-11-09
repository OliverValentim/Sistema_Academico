# Título: Desenvolvimento de um Sistema Acadêmico Colaborativo
# Matéria: Projeto Integrador Multidisciplinar (PIM)
# Turma: [DS2P44]
# Autores: Oliver V. C. Santos (Líder), Richard I. Lima, Danilo H. C. Ferreira, Raphael L. Lopes

import psycopg2 # driver oficial para PostgreSQL (o banco de dados)
from psycopg2 import pool # reutiliza conexões
from decouple import config #lê variáveis de ambiente do arquivo .env
# fastapi: framework web; status: códigos http (200, 404, etc)
from fastapi import FastAPI, status, HTTPException, Depends #httpexception: erros personalizados; depends: injeção de dependência (ex: autenticação)
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm # autenticação via token jwt e formulário de login
from pydantic import BaseModel # validação automática de dados
from jose import JWTError, jwt # cria e verifica tokens jwt
from passlib.context import CryptContext # segurança para senhas
import socketio # websocket em tempo real
import uvicorn # servidor ASGI (roda FastAPI)
import secrets # para gerar uma chave forte

#logs e controle de expiração de token
import logging
from datetime import datetime, timedelta

# configuração básica para mostrar mensagens info
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# FastAPI + Socket.IO integrados
app = FastAPI()
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*") # permite qualquer origem (cliente.py)
app_sio = socketio.ASGIApp(sio, app)

# configuração do banco de dados, informações lidas no .env
db_config = {
    "dbname": config("DB_NAME", default="sistema_academico"), # nome do banco
    "user": config("DB_USER", default="postgres"), # usuário do PostgreSQL
    "password": config("DB_PASSWORD"), # senha
    "host": config("DB_HOST", default="localhost"), # host do banco
    "port": config("DB_PORT", default="5432") # porta padrão do PostgreSQL
}
connection_pool = psycopg2.pool.SimpleConnectionPool(minconn=1, maxconn=5, **db_config) # pool de conexões: evita abrir/fechar conexão a cada requisição

# JWT
SECRET_KEY = config("SECRET_KEY") # senha para assinar tokens
ALGORITHM = "HS256" # tipo de criptografia
ACCESS_TOKEN_EXPIRE_MINUTES = 30 # token expira em trinta minutos
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login") # informa que o token vem do login
print(secrets.token_urlsafe(32)) ## gera algo como "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8S9t0U"

# gerenciador do banco
class DadosSistemaServidor: # define uma classe
    def __init__(self): # construtor que roda ao criar o objeto
        self._criar_tabelas()

    def get_connection(self):
        return connection_pool.getconn()

    def release_connection(self, conn):
        connection_pool.putconn(conn)

    def _criar_tabelas(self):
        conn = self.get_connection() # variável que recebe o valor
        cursor = conn.cursor() # ponteiro para executar SQL

        # SERIAL PRIMARY KEY: id automático;  UNIQUE: evita duplicar; TEXT NOT NULL: texto obrigatório;
        # FOREIGN KEY: referência; ON DELETE CASCADE: apaga dependências
        cursor.execute(""" 
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cursos (
                id SERIAL PRIMARY KEY,
                curso TEXT NOT NULL UNIQUE,
                sigla TEXT UNIQUE NOT NULL,
                area TEXT NOT NULL,
                descricao TEXT
            );
            CREATE TABLE IF NOT EXISTS turmas (
                id SERIAL PRIMARY KEY,
                turma TEXT NOT NULL UNIQUE,
                curso_sigla TEXT NOT NULL,
                descricao TEXT,
                FOREIGN KEY (curso_sigla) REFERENCES cursos(sigla) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS alunos (
                id SERIAL PRIMARY KEY,
                aluno TEXT NOT NULL UNIQUE,
                ra TEXT UNIQUE NOT NULL,
                email TEXT,
                curso_sigla TEXT NOT NULL,
                turma TEXT NOT NULL,
                FOREIGN KEY (curso_sigla) REFERENCES cursos(sigla) ON DELETE CASCADE,
                FOREIGN KEY (turma) REFERENCES turmas(turma) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS materias (
                id SERIAL PRIMARY KEY,
                materia TEXT NOT NULL UNIQUE,
                professor TEXT NOT NULL,
                email TEXT NOT NULL,
                curso_sigla TEXT NOT NULL,
                turma TEXT NOT NULL,
                descricao TEXT,
                FOREIGN KEY (curso_sigla) REFERENCES cursos(sigla) ON DELETE CASCADE,
                FOREIGN KEY (turma) REFERENCES turmas(turma) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS chatbot_respostas (
                id SERIAL PRIMARY KEY,
                pergunta TEXT NOT NULL,
                resposta TEXT NOT NULL
            );
        """)
        conn.commit() # salva as mudanças no banco de dados
        cursor.close()
        self.release_connection(conn)

    def executar(self, sql, params=()): # parâmetros com tupla vazia por padrão
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, params)
            conn.commit()
        except Exception as e: 
            conn.rollback() # se der erro, desfaz
            raise e # lança erro
        finally: # fecha tudo
            cursor.close()
            self.release_connection(conn)

    def consultar(self, sql, params=()):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        results = cursor.fetchall() # pega todos os resultados
        cursor.close()
        self.release_connection(conn)
        return results

db_servidor = DadosSistemaServidor() # instância global

# Modelos pydantic
class LoginData(BaseModel):
    username: str # str é a abreviação de string
    password: str

class AlunoCreate(BaseModel):
    aluno: str
    ra: str
    email: str
    curso_sigla: str
    turma: str

class CursoCreate(BaseModel):
    curso: str
    sigla: str
    area: str
    descricao: str

class TurmaCreate(BaseModel):
    turma: str
    curso_sigla: str
    descricao: str

class MateriaCreate(BaseModel):
    materia: str
    professor: str
    email: str
    curso_sigla: str
    turma: str
    descricao: str | None = None  

class ChatbotRespostaCreate(BaseModel):
    pergunta: str
    resposta: str

# Autenticação
def create_access_token(data: dict): # parâmetro do tipo dicionário
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES) # utcnow() hora atual em UTC
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM) # cria o token

async def get_current_user(token: str = Depends(oauth2_scheme)): # verifica token e, se inválido, erro 401
    credentials_exception = HTTPException(
        status_code=401,
        detail="Credenciais inválidas",
        headers={"WWW-Authenticate": "Bearer"}
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]) # lê o token
        username: str = payload.get("sub")
        if not username:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    conn = connection_pool.getconn()
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    cursor.close()
    connection_pool.putconn(conn)
    if not user:
        raise credentials_exception
    return user[0]

# endpoints de autenticação
@app.post("/register") # adiciona funcionalidade
async def register_user(user: LoginData): # valida com pydantic
    hashed = pwd_context.hash(user.password) # criptografa a senha
    try:
        db_servidor.executar(
            "INSERT INTO users (username, hashed_password) VALUES (%s, %s)",
            (user.username, hashed)
        )
        return {"message": "Usuário registrado"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/login")
async def login(data: LoginData):
    conn = connection_pool.getconn()
    cursor = conn.cursor()
    cursor.execute("SELECT hashed_password FROM users WHERE username = %s", (data.username,))
    user = cursor.fetchone()
    cursor.close()
    connection_pool.putconn(conn)
    
    if not user or not pwd_context.verify(data.password, user[0]):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    
    token = create_access_token({"sub": data.username})
    return {"access_token": token, "token_type": "bearer"}

@app.post("/alunos")
async def add_aluno(aluno: AlunoCreate, current_user: str = Depends(get_current_user)):
    try:
        db_servidor.executar(
            "INSERT INTO alunos (aluno, ra, email, curso_sigla, turma) VALUES (%s, %s, %s, %s, %s)",
            (aluno.aluno.title(), aluno.ra.upper(), aluno.email.lower(), aluno.curso_sigla.upper(), aluno.turma.upper())
        )
        await sio.emit("atualizar_alunos", {}) # atualiza sistema em tempo real
        return {"message": "Aluno adicionado"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/alunos") # lista
async def get_alunos(current_user: str = Depends(get_current_user)):
    dados = db_servidor.consultar("SELECT id, aluno, ra, email, curso_sigla, turma FROM alunos ORDER BY aluno")
    return [{"id": d[0], "aluno": d[1], "ra": d[2], "email": d[3], "curso_sigla": d[4], "turma": d[5]} for d in dados]

@app.put("/alunos/{aluno_id}") # altera
async def update_aluno(aluno_id: int, aluno: AlunoCreate, current_user: str = Depends(get_current_user)):
    try:
        db_servidor.executar(
            "UPDATE alunos SET aluno=%s, ra=%s, email=%s, curso_sigla=%s, turma=%s WHERE id=%s",
            (aluno.aluno.title(), aluno.ra.upper(), aluno.email.lower(), aluno.curso_sigla.upper(), aluno.turma.upper(), aluno_id)
        )
        await sio.emit("atualizar_alunos", {})
        return {"message": "Aluno alterado"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/alunos/{aluno_id}")
async def delete_aluno(aluno_id: int, current_user: str = Depends(get_current_user)):
    try:
        db_servidor.executar("DELETE FROM alunos WHERE id=%s", (aluno_id,))
        await sio.emit("atualizar_alunos", {})
        return {"message": "Aluno excluído"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/cursos")
async def add_curso(curso: CursoCreate, current_user: str = Depends(get_current_user)):
    try:
        db_servidor.executar(
            "INSERT INTO cursos (curso, sigla, area, descricao) VALUES (%s, %s, %s, %s)",
            (curso.curso.title(), curso.sigla.upper(), curso.area.title(), curso.descricao.strip())
        )
        await sio.emit("atualizar_cursos", {})
        return {"message": "Curso adicionado"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/cursos")
async def get_cursos(current_user: str = Depends(get_current_user)):
    dados = db_servidor.consultar("SELECT id, curso, sigla, area, descricao FROM cursos ORDER BY curso")
    return [{"id": d[0], "curso": d[1], "sigla": d[2], "area": d[3], "descricao": d[4]} for d in dados]

@app.put("/cursos/{curso_id}")
async def update_curso(curso_id: int, curso: CursoCreate, current_user: str = Depends(get_current_user)):
    atual = db_servidor.consultar("SELECT sigla FROM cursos WHERE id = %s", (curso_id,))
    if not atual:
        raise HTTPException(status_code=404, detail="Curso não encontrado")
    sigla_atual = atual[0][0]
    nova_sigla = curso.sigla.upper()
    if sigla_atual != nova_sigla:
        turmas = db_servidor.consultar("SELECT 1 FROM turmas WHERE curso_sigla = %s LIMIT 1", (sigla_atual,))
        if turmas:
            raise HTTPException(status_code=400, detail="Não é possível alterar a sigla: há turmas associadas.")
    try:
        db_servidor.executar(
            "UPDATE cursos SET curso=%s, sigla=%s, area=%s, descricao=%s WHERE id=%s",
            (curso.curso.title(), nova_sigla, curso.area.title(), curso.descricao.strip(), curso_id)
        )
        await sio.emit("atualizar_cursos", {})
        return {"message": "Curso alterado"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/cursos/{curso_id}")
async def delete_curso(curso_id: int, current_user: str = Depends(get_current_user)):
    try:
        db_servidor.executar("DELETE FROM cursos WHERE id=%s", (curso_id,))
        await sio.emit("atualizar_cursos", {})
        return {"message": "Curso excluído"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/cursos/{curso_id}/cascade")
async def delete_curso_cascade(curso_id: int, current_user: str = Depends(get_current_user)):
    if not db_servidor.consultar("SELECT 1 FROM cursos WHERE id = %s", (curso_id,)):
        raise HTTPException(status_code=404, detail="Curso não encontrado")
    try:
        db_servidor.executar("DELETE FROM cursos WHERE id = %s", (curso_id,))
        await sio.emit("atualizar_cursos", {})
        await sio.emit("atualizar_turmas", {})
        await sio.emit("atualizar_alunos", {})
        await sio.emit("atualizar_materias", {})
        return {"message": "Curso e tudo relacionado excluído"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/turmas")
async def add_turma(turma: TurmaCreate, current_user: str = Depends(get_current_user)):
    try:
        db_servidor.executar(
            "INSERT INTO turmas (turma, curso_sigla, descricao) VALUES (%s, %s, %s)",
            (turma.turma.upper(), turma.curso_sigla.upper(), turma.descricao.strip())
        )
        await sio.emit("atualizar_turmas", {})
        return {"message": "Turma adicionada"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/turmas")
async def get_turmas(current_user: str = Depends(get_current_user)):
    dados = db_servidor.consultar("SELECT id, turma, curso_sigla, descricao FROM turmas ORDER BY turma")
    return [{"id": d[0], "turma": d[1], "curso_sigla": d[2], "descricao": d[3]} for d in dados]

@app.put("/turmas/{turma_id}")
async def update_turma(turma_id: int, turma: TurmaCreate, current_user: str = Depends(get_current_user)):
    try:
        db_servidor.executar(
            "UPDATE turmas SET turma=%s, curso_sigla=%s, descricao=%s WHERE id=%s",
            (turma.turma.upper(), turma.curso_sigla.upper(), turma.descricao.strip(), turma_id)
        )
        await sio.emit("atualizar_turmas", {})
        return {"message": "Turma alterada"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/turmas/{turma_id}")
async def delete_turma(turma_id: int, current_user: str = Depends(get_current_user)):
    try:
        db_servidor.executar("DELETE FROM turmas WHERE id=%s", (turma_id,))
        await sio.emit("atualizar_turmas", {})
        return {"message": "Turma excluída"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/materias")
async def add_materia(materia: MateriaCreate, current_user: str = Depends(get_current_user)):
    try:
        db_servidor.executar(
            "INSERT INTO materias (materia, professor, email, curso_sigla, turma, descricao) VALUES (%s, %s, %s, %s, %s, %s)",
            (materia.materia.title(), materia.professor.title(), materia.email.lower(), materia.curso_sigla.upper(), materia.turma.upper(), materia.descricao.strip())
        )
        await sio.emit("atualizar_materias", {})
        return {"message": "Matéria adicionada"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/materias")
async def get_materias(current_user: str = Depends(get_current_user)):
    dados = db_servidor.consultar("SELECT id, materia, professor, email, curso_sigla, turma, descricao FROM materias ORDER BY materia")
    return [{"id": d[0], "materia": d[1], "professor": d[2], "email": d[3], "curso_sigla": d[4], "turma": d[5], "descricao": d[6]} for d in dados]

@app.put("/materias/{materia_id}")
async def update_materia(materia_id: int, materia: MateriaCreate, current_user: str = Depends(get_current_user)):
    try:
        db_servidor.executar(
            "UPDATE materias SET materia=%s, professor=%s, email=%s, curso_sigla=%s, turma=%s, descricao=%s WHERE id=%s",
            (materia.materia.title(), materia.professor.title(), materia.email.lower(), materia.curso_sigla.upper(), materia.turma.upper(), materia.descricao.strip (), materia_id)
        )
        await sio.emit("atualizar_materias", {})
        return {"message": "Matéria alterada"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/materias/{materia_id}")
async def delete_materia(materia_id: int, current_user: str = Depends(get_current_user)):
    try:
        db_servidor.executar("DELETE FROM materias WHERE id=%s", (materia_id,))
        await sio.emit("atualizar_materias", {})
        return {"message": "Matéria excluída"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/chatbot_respostas")
async def add_chatbot_resposta(resposta: ChatbotRespostaCreate, current_user: str = Depends(get_current_user)):
    try:
        db_servidor.executar(
            "INSERT INTO chatbot_respostas (pergunta, resposta) VALUES (%s, %s)",
            (resposta.pergunta, resposta.resposta)
        )
        await sio.emit("atualizar_chatbot", {})
        return {"message": "Resposta adicionada"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/chatbot_respostas")
async def get_chatbot_respostas(current_user: str = Depends(get_current_user)):
    dados = db_servidor.consultar("SELECT id, pergunta, resposta FROM chatbot_respostas ORDER BY pergunta")
    return [{"id": d[0], "pergunta": d[1], "resposta": d[2]} for d in dados]

@app.put("/chatbot_respostas/{resposta_id}")
async def update_chatbot_resposta(resposta_id: int, resposta: ChatbotRespostaCreate, current_user: str = Depends(get_current_user)):
    try:
        db_servidor.executar(
            "UPDATE chatbot_respostas SET pergunta=%s, resposta=%s WHERE id=%s",
            (resposta.pergunta, resposta.resposta, resposta_id)
        )
        await sio.emit("atualizar_chatbot", {})
        return {"message": "Resposta alterada"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/chatbot_respostas/{resposta_id}")
async def delete_chatbot_resposta(resposta_id: int, current_user: str = Depends(get_current_user)):
    try:
        db_servidor.executar("DELETE FROM chatbot_respostas WHERE id=%s", (resposta_id,))
        await sio.emit("atualizar_chatbot", {})
        return {"message": "Resposta excluída"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# websocket
@sio.event # decorador para evento
async def connect(sid, environ):
    logger.info(f"Cliente conectado: {sid}") # f"..." é uma string formatada

@sio.event
async def disconnect(sid):
    logger.info(f"Cliente desconectado: {sid}")

if __name__ == "__main__": # __name__ é o nome do arquivo e "__main__" só roda se for o arquivo principal
    uvicorn.run("servidor:app_sio", host="0.0.0.0", port=8000, log_level="info") # roda na porta 8000; app_sio: FastAPI + Socket.IO