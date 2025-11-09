# Título: Desenvolvimento de um Sistema Acadêmico Colaborativo
# Matéria: Projeto Integrador Multidisciplinar (PIM)
# Turma: [DS2P44]
# Autores: Oliver V. C. Santos (Líder), Richard I. Lima, Danilo H. C. Ferreira, Raphael L. Lopes

import tkinter as tk # biblioteca padrão do Python para criar interfaces gráficas
from tkinter import ttk, messagebox  # ttk: widgets modernos com tema; messagebox: caixas de diálogo
import requests # para fazer requisições HTTP ao backend (FastAPI)
import socketio # para comunicação em tempo real (websocket) com o servidor
import logging # sistema de logs para depuração
from typing import List, Dict  # tipos para anotações
from functools import partial  # permite criar funções com argumentos pré-definidos
import threading  # para rodar requisições HTTP em threads separadas (evitar travar a UI)


logging.basicConfig(level=logging.WARNING) # configura o nível de log para warning (só mostra erros graves)
logger = logging.getLogger(__name__) # cria um logger específico para este módulo

def tema_escuro(root): # finção para definir o tema do sistema, root é a janela principal

    # usa o tema 'clam' do ttk (permite personalização)
    style = ttk.Style()
    style.theme_use('clam')

    # cores do tema escuro
    bg = "#2b2b2b" # fundo geral
    fg = "#ffffff" # texto
    select_bg = "#0078d7" # cor de seleção
    entry_bg = "#3c3f41" # fundo de entradas
    button_bg = "#0078d7" #fundo dos botões
    root.configure(bg=bg) # aplica a cor de fundo na janela principal

    style.configure(".", background=bg, foreground=fg, font=("Segoe UI", 10)) # configura o estilo de todos os widgets

    # estilos específicos por tipo de widget
    style.configure("TLabel", background=bg, foreground=fg)
    style.configure("TButton", background=button_bg, foreground=fg, padding=6)
    style.configure("TEntry", fieldbackground=entry_bg, foreground=fg)
    style.configure("TCombobox", fieldbackground=entry_bg, foreground=fg)        
    style.configure("Treeview", background=bg, foreground=fg, fieldbackground=bg, rowheight=28, anchor="center") # treeview: tabela; rowheight: altura das linhas; anchor: alinhamento
    style.configure("Treeview.Heading", background="#404040", foreground=fg, font=("Segoe UI", 10, "bold"), anchor="center")
    style.map("Treeview", background=[("selected", select_bg)]) # cor de quando uma linha é selecionada 
    style.map("TButton", background=[("active", "#005a9e")]) # estilo de quando passa o mouse no botão
    style.map("TCombobox", fieldbackground=[("readonly", entry_bg)]) # combo box não editável

class SistemaAcademico:
    def __init__(self, root):
        self.root = root # guarda a janela
        self.root.title("Sistema Acadêmico") # título
        self.root.geometry("1280x800") # tamanho
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing) # evento ao fechar
        tema_escuro(self.root) # aplica o tema escuro na janela

        self.base_url = "http://localhost:8000" # url base do servidor (fastapi rodando localmente)
        self.sio = socketio.Client() # atualização em tempo real
        self.token = None # token jwt após login
        self.atualizando = {} # controla se uma entidade está sendo atualizada

        # cache local dos dados
        self.cache_cursos = []
        self.cache_turmas = []
        self.cache_materias = []


        self.loading = None # janela de loading

        # para saber se o cache já foi carregado pela primeira vez
        self.cache_inicializado = {
            "alunos": False, "cursos": False, "turmas": False,
            "materias": False, "chatbot": False }

        # inicializa websocket e mostra tela de login
        self.setup_websocket()
        self.pagina_login()

    def setup_websocket(self): # função para conexão em tempo real
        try:
            self.sio.connect(self.base_url, transports=['websocket']) # conecta ao servidor
            logger.info("WebSocket conectado com sucesso!")

            # lista de eventos  que o servidor pode emitir
            eventos = ["atualizar_alunos", "atualizar_cursos", "atualizar_turmas", "atualizar_materias", "atualizar_chatbot"]
            for evento in eventos:
                entidade = evento.replace("atualizar_", "")
                self.sio.on(evento, lambda data, ent=entidade: self.atualizar_pagina_websocket(ent))
                # usa lambda como fixo para evitar que uma função interna acesse e use variáveis do escopo externo

            # evento padrão do socket.io                                                                                     
            @self.sio.event
            def connect(): logger.info("WebSocket: conectado")
            @self.sio.event
            def disconnect(): logger.info("WebSocket: desconectado")
            @self.sio.event
            def connect_error(data): logger.error(f"WebSocket erro: {data}")

        except Exception as e:
            messagebox.showerror("Erro", f"WebSocket falhou: {e}") # mostra erro se não conseguir conectar
            logger.error(f"WebSocket: {e}")

    def on_closing(self): # desconecta do websocket antes de fechar
        if self.sio.connected:
            self.sio.disconnect()
        self.root.destroy()

    def titulo_centralizado(self, texto: str): # função para criar um título grande e centralizado
        label = ttk.Label(self.frame_main, text=texto, font=("Segoe UI", 18, "bold"))
        label.pack(pady=(20, 10), fill="x")
        label.pack_configure(anchor="center")

    def pagina_login(self): # função para a tela de acesso
        self.limpar_tudo() # remove todos os widgets

        # tela de login com título e subtítulo
        frame = ttk.Frame(self.root, padding=40) 
        frame.pack(expand=True)
        ttk.Label(frame, text="Sistema Acadêmico", font=("Segoe UI", 20, "bold")).pack(pady=20)
        ttk.Label(frame, text="Faça login para continuar", font=("Segoe UI", 10)).pack(pady=(0, 20))

        # campo de usuário e campo de senha
        self.username_entry = ttk.Entry(frame, width=35, font=("Segoe UI", 11))
        self.username_entry.pack(pady=8)
        self.username_entry.insert(0, "Usuário")
        self.username_entry.bind("<FocusIn>", lambda e: self.username_entry.delete(0, tk.END) if self.username_entry.get() == "Usuário" else None)

        self.password_entry = ttk.Entry(frame, width=35, font=("Segoe UI", 11), show="*")
        self.password_entry.pack(pady=8)
        self.password_entry.insert(0, "Senha")
        self.password_entry.bind("<FocusIn>", lambda e: self.password_entry.delete(0, tk.END) if self.password_entry.get() == "Senha" else None)


        # botões para fazer login e/ou se registrar
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text="Entrar", command=self.login).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Registrar", command=self.register).pack(side="left", padx=5)

    def login(self): # função para fazer login
        username = self.username_entry.get().strip() # get () pega o texto do campo e strip() remove espaços
        password = self.password_entry.get().strip()
        if not username or not password or username in ["Usuário", "Senha"]:
            return messagebox.showerror("Erro", "Preencha usuário e senha")
        self.mostrar_loading("Fazendo login...") 


        # função que é passada como argumento para outra função e que vai ser executada após a resposta do servidor
        def callback(sucesso, dados, erro):
            self.esconder_loading()
            if sucesso:
                self.token = dados["access_token"]
                self.montar_interface()
                self.mostrar_pagina("alunos")
                self.inicializar_perguntas_chatbot()
            else:
                messagebox.showerror("Erro", erro or "Falha no login")

        # envia dados do cliente para o servidor em um fluxo de execução separado
        self.http_em_thread("POST", f"{self.base_url}/login", {"username": username, "password": password}, callback)

    def register(self): # mesma lógica que a função de login, só que envia para o /register
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        if not username or not password or username in ["Usuário", "Senha"]:
            return messagebox.showerror("Erro", "Preencha todos os campos")
        if len(password.encode('utf-8')) > 72:
            return messagebox.showerror("Erro", "Senha muito longa (máx 72 bytes)")
        self.mostrar_loading("Registrando...")

        def callback(sucesso, dados, erro):
            self.esconder_loading()
            if sucesso:
                messagebox.showinfo("Sucesso", "Usuário criado! Faça login.")
            else:
                messagebox.showerror("Erro", erro or "Erro ao registrar")

        self.http_em_thread("POST", f"{self.base_url}/register", {"username": username, "password": password}, callback)

    def inicializar_perguntas_chatbot(self): # função que cria perguntas ao abrir o sistema

        #lista de perguntas e respostas padrão  
        perguntas_prontas = [
            {"pergunta": "O que é o Sistema Acadêmico?", "resposta": "Sistema para gerenciar alunos, cursos, turmas, matérias e dúvidas via chatbot."},
            {"pergunta": "Como adicionar um aluno?", "resposta": "Vá em 'Alunos', preencha nome, RA, e-mail, selecione curso e turma, clique em 'Adicionar'."},
            {"pergunta": "Como criar um curso?", "resposta": "Em 'Cursos', informe nome, sigla (ex: ADS), área e descrição."},
            {"pergunta": "O que é sigla do curso?", "resposta": "Abreviação como 'ADS' para Análise e Desenvolvimento de Sistemas."},
            {"pergunta": "Como criar uma turma?", "resposta": "Em 'Turmas', digite nome (ex: 1º ADS Manhã), selecione curso e descrição opcional."},
            {"pergunta": "Como associar aluno a turma?", "resposta": "Ao adicionar aluno, selecione a turma. O curso será preenchido automaticamente."},
            {"pergunta": "Como criar uma matéria?", "resposta": "Em 'Matérias', informe nome, professor, e-mail, curso e turma."},
            {"pergunta": "O sistema atualiza em tempo real?", "resposta": "Sim! Todas as alterações são sincronizadas imediatamente via WebSocket."},
            {"pergunta": "Posso alterar ou excluir itens?", "resposta": "Sim. Selecione na tabela e clique em 'Alterar' ou 'Excluir'."},
            {"pergunta": "Como buscar?", "resposta": "Use o campo de busca no topo de cada página. Filtra em tempo real."},
            {"pergunta": "Como sair?", "resposta": "Clique em 'Sair' no menu lateral."},
        ]

        def callback(sucesso, dados, erro):
            if not sucesso: return
            existentes = {p["pergunta"].strip().lower(): p for p in dados} # dicionário com perguntas existentes
            for item in perguntas_prontas:
                key = item["pergunta"].strip().lower()
                if key not in existentes: # adiciona pergunta se não existir
                    self.http_em_thread("POST", f"{self.base_url}/chatbot_respostas", item, lambda s, d, e: None)
            self.atualizar_pagina_websocket("chatbot")

        self.http_em_thread("GET", f"{self.base_url}/chatbot_respostas", callback=callback)

    def montar_interface(self): # função para exibir menu lateral e área principal
        self.limpar_tudo()
        self.menu_lateral()
        self.area_principal()

    def limpar_tudo(self):
        for widget in self.root.winfo_children():
            widget.destroy() # remove tudo da janela

    def menu_lateral(self): # função para criar o menu lateral a esquerda
        menu = ttk.Frame(self.root, width=220, padding=15)
        menu.pack(side="left", fill="y")
        menu.pack_propagate(False) # impede que o frame encolha
        ttk.Label(menu, text="MENU", font=("Segoe UI", 14, "bold")).pack(pady=(0, 20))
        opcoes = [("Alunos", "alunos"), ("Cursos", "cursos"), ("Turmas", "turmas"), ("Matérias", "materias"), ("Chatbot", "chatbot"), ("Sair", None)]
        for texto, pagina in opcoes:
            if pagina:                                      # partial () define qual página abrir
                btn = ttk.Button(menu, text=texto, width=20, command=partial(self.mostrar_pagina, pagina))
                btn.pack(pady=4)
            else:                                           
                btn = ttk.Button(menu, text=texto, width=20, command=self.root.quit)
                btn.pack(pady=20)

    def area_principal(self): # função que cria área principal a direita
        self.frame_main = ttk.Frame(self.root, padding=20)
        self.frame_main.pack(side="right", fill="both", expand=True)

    def limpar_area(self): # limpa conteúdo ao mudar de página
        for widget in self.frame_main.winfo_children():
            widget.destroy()
        for attr in list(self.__dict__.keys()):
            if attr.startswith("tree_"):
                delattr(self, attr)
        self.atualizando = {}

    def get_colunas_e_chaves(self, entidade: str) -> Dict:
        mapeamento = {
            "alunos": {"colunas": ["Aluno", "RA", "E-mail", "Curso", "Turma"], "chaves": ["aluno", "ra", "email", "curso_sigla", "turma"]},
            "cursos": {"colunas": ["Curso", "Sigla", "Área", "Descrição"], "chaves": ["curso", "sigla", "area", "descricao"]},
            "turmas": {"colunas": ["Turma", "Curso", "Descrição"], "chaves": ["turma", "curso_sigla", "descricao"]},
            "materias": {"colunas": ["Matéria", "Professor", "E-mail", "Curso", "Turma", "Descrição"], "chaves": ["materia", "professor", "email", "curso_sigla", "turma", "descricao"]},
            "chatbot": {"colunas": ["Pergunta", "Resposta"], "chaves": ["pergunta", "resposta"]}
        }
        return mapeamento.get(entidade, {"colunas": [], "chaves": []})

    def criar_tabela(self, entidade: str): # função para criar tabelas
        info = self.get_colunas_e_chaves(entidade)
        tree = ttk.Treeview(self.frame_main, columns=info["colunas"], show="headings", height=16, selectmode="browse")
        for col in info["colunas"]:         # configura cada coluna
            largura = 300 if col in ["Descrição", "Resposta"] else 150
            tree.heading(col, text=info["colunas"][info["colunas"].index(col)], anchor="center")
            tree.column(col, width=largura, anchor="center")
        tree.bind("<Button-1>", lambda e: self._selecionar_linha(tree, e))         # clicar com o botão esquerdo seleciona a linha
        tree.pack(fill="both", expand=True, pady=(10, 0))
        setattr(self, f"tree_{entidade}", tree) # salva a tabela como atributo: tree_alunos, tree_cursos, etc
        self.atualizando[entidade] = True   # inicia atualização automática
        self.root.after(1000, lambda: self.atualizar_pagina_websocket(entidade)) # atualiza interface no fluxo de execução principal a cada um segundo

        # duplo clique abre detalhes
        if entidade in ["alunos", "cursos", "turmas", "materias", "chatbot"]:
            def on_double_click(event):
                item = tree.identify_row(event.y)
                if not item:
                    return
                id_item = tree.item(item, "tags")[0]
                dados = getattr(self, f"cache_{entidade}", [])
                entidade_data = next((d for d in dados if str(d["id"]) == id_item), None)
                if not entidade_data:
                    return
                self.mostrar_detalhes_entidade(entidade, entidade_data)

            tree.bind("<Double-1>", on_double_click)
        return tree

    def mostrar_detalhes_entidade(self, entidade: str, dados: Dict): # abre uma página que mostra todos os detalhes
        janela = tk.Toplevel(self.root)
        janela.title(f"Detalhes - {entidade.title()}")
        janela.geometry("700x500")
        janela.configure(bg="#2b2b2b")
        janela.transient(self.root)
        janela.grab_set()

        frame = ttk.Frame(janela, padding=20)
        frame.pack(fill="both", expand=True)

        rotulos = {
            "aluno": "Aluno", "ra": "RA", "email": "E-mail", "curso_sigla": "Curso", "turma": "Turma",
            "curso": "Curso", "sigla": "Sigla", "area": "Área", "descricao": "Descrição",
            "materia": "Matéria", "professor": "Professor", "email": "E-mail", "curso_sigla": "Curso", "turma": "Turma", "descricao": "Descrição",
            "pergunta": "Pergunta", "resposta": "Resposta"
        }

        info = self.get_colunas_e_chaves(entidade)
        chaves = info["chaves"]

        row = 0
        for chave in chaves:
            if chave not in dados:
                continue
            valor = dados[chave] or "(vazio)"
            rotulo = rotulos.get(chave, chave.title())

            # rótulo bonito
            ttk.Label(frame, text=rotulo + ":", font=("Segoe UI", 10, "bold"), anchor="e").grid(row=row, column=0, sticky="e", padx=5, pady=6)
        
            # texto longo em text widget
            if chave in ["descricao", "resposta"] or len(str(valor)) > 50:
                text = tk.Text(frame, height=4, wrap="word", font=("Segoe UI", 10), bg="#3c3f41", fg="white")
                text.insert("1.0", str(valor))
                text.configure(state="disabled")
                text.grid(row=row, column=1, padx=5, pady=6, sticky="ew")
                scroll = ttk.Scrollbar(frame, command=text.yview)
                text.configure(yscrollcommand=scroll.set)
                scroll.grid(row=row, column=2, sticky="ns", pady=6)
            else:
                ttk.Label(frame, text=str(valor), font=("Segoe UI", 10), anchor="w").grid(row=row, column=1, padx=5, pady=6, sticky="w")

            row += 1

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=row, column=0, columnspan=3, pady=20)
        ttk.Button(btn_frame, text="Fechar", command=janela.destroy).pack()

        frame.columnconfigure(1, weight=1)

    def _selecionar_linha(self, tree, event): 
        item = tree.identify_row(event.y)
        if item:
            tree.selection_set(item)
            tree.focus(item)

    def mostrar_texto_completo(self, titulo: str, texto: str):
        janela = tk.Toplevel(self.root)
        janela.title(titulo)
        janela.geometry("750x550")
        janela.configure(bg="#2b2b2b")
        text_widget = tk.Text(janela, wrap="word", font=("Segoe UI", 10), bg="#3c3f41", fg="white", padx=10, pady=10)
        text_widget.insert("1.0", texto)
        text_widget.pack(fill="both", expand=True, padx=15, pady=15)
        scroll = ttk.Scrollbar(janela, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")

    def preencher_tabela(self, tree, dados: List[Dict], chaves: List[str]):
        for i in tree.get_children(): # limpa a tabela
            tree.delete(i)
        for idx, item in enumerate(dados):
            valores = []
            for chave in chaves: # trunca textos longos
                valor = item.get(chave, "")
                if chave == "resposta" and len(valor) > 100: valor = valor[:97] + "..."
                if chave == "descricao" and len(valor) > 80: valor = valor[:77] + "..."
                valores.append(str(valor))
            tag = "even" if idx % 2 == 0 else "odd" # even/odd são cores alternadas
            tree.insert("", "end", values=valores, tags=(str(item["id"]), tag)) # insere uma linha com valores e ID
        
        # linhas alternadas com cores diferentes
        tree.tag_configure("even", background="#353535") 
        tree.tag_configure("odd", background="#2d2d2d")

    def _executar_callback_com_selecao(self, entidade: str, dados: List[Dict], tree):
        selecao_atual = None
        if tree and tree.selection():
            item = tree.selection()[0]
            selecao_atual = tree.item(item, "tags")[0]

        info = self.get_colunas_e_chaves(entidade)
        self.preencher_tabela(tree, dados, info["chaves"])

        if selecao_atual and tree:
            for child in tree.get_children():
                if tree.item(child, "tags")[0] == selecao_atual:
                    tree.selection_set(child)
                    tree.focus(child)
                    tree.see(child)
                    break

    def atualizar_pagina_websocket(self, entidade: str):
        if not self.token or entidade not in self.atualizando or not self.atualizando[entidade]:
            return
        self.get_dados(entidade, force_refresh=True) # força atualização do servidor
        if entidade in self.atualizando and self.atualizando[entidade]:
            self.root.after(1000, lambda: self.atualizar_pagina_websocket(entidade)) # repete a cada 1 (um) segundo

    def get_cursos(self, refresh=False):
        if not self.token: return []
        if not refresh and self.cache_cursos: 
            return [c["sigla"] for c in self.cache_cursos]
        if refresh:
            def callback(sucesso, dados, erro):
                if sucesso: 
                    self.cache_cursos = dados
                    if hasattr(self, "combo_curso") and self.combo_curso.winfo_exists():
                        self.root.after(100, self.atualizar_combos)
            self.http_em_thread("GET", f"{self.base_url}/cursos", callback=callback)
        return []

    def get_turmas(self, refresh=False):
        if not self.token: return []
        if not refresh and self.cache_turmas: 
            return [t["turma"] for t in self.cache_turmas]
        if refresh:
            def callback(sucesso, dados, erro):
                if sucesso: 
                    self.cache_turmas = dados
                    if hasattr(self, "combo_turma") and self.combo_turma.winfo_exists():
                        self.root.after(100, self.atualizar_combos)
            self.http_em_thread("GET", f"{self.base_url}/turmas", callback=callback)
        return []

    def get_materias(self, refresh=False):
        if not self.token: return ["Faça login primeiro"]
        if not refresh and self.cache_materias: return [m["materia"] for m in self.cache_materias]
        def callback(sucesso, dados, erro):
            if sucesso: self.cache_materias = dados
        self.http_em_thread("GET", f"{self.base_url}/materias", callback=callback)
        return ["Carregando..."]

    def get_dados(self, entidade: str, force_refresh=False):
        cache_attr = f"cache_{entidade}"
        tree = getattr(self, f"tree_{entidade}", None)
        if not force_refresh and hasattr(self, cache_attr) and getattr(self, cache_attr): # usa cache se disponível e não for forçado
            cached = getattr(self, cache_attr)
            if tree and tree.winfo_exists():
                info = self.get_colunas_e_chaves(entidade)
                self.preencher_tabela(tree, cached, info["chaves"])
            self.root.after(100, lambda: self._atualizar_em_background(entidade))
            return
        self._carregar_do_servidor(entidade) # pede cache ao servidor

    def _atualizar_em_background(self, entidade: str):
        def callback(sucesso, dados, erro):
            if sucesso:
                setattr(self, f"cache_{entidade}", dados)
                tree = getattr(self, f"tree_{entidade}", None)
                if tree and tree.winfo_exists():
                    self._executar_callback_com_selecao(entidade, dados, tree)
        url = f"{self.base_url}/{entidade}"
        if entidade == "chatbot": url = f"{self.base_url}/chatbot_respostas"
        self.http_em_thread("GET", url, callback=callback)

    def _carregar_do_servidor(self, entidade: str):
        if not self.cache_inicializado.get(entidade, False):
            self.mostrar_loading(f"Carregando {entidade}...")
        def callback(sucesso, dados, erro):
            if not self.cache_inicializado.get(entidade, False):
                self.esconder_loading()
            if sucesso:
                setattr(self, f"cache_{entidade}", dados)
                tree = getattr(self, f"tree_{entidade}", None)
                if tree and tree.winfo_exists():
                    self._executar_callback_com_selecao(entidade, dados, tree)
                self.cache_inicializado[entidade] = True
            else:
                messagebox.showerror("Erro", f"Não foi possível carregar {entidade}")
        url = f"{self.base_url}/{entidade}"
        if entidade == "chatbot": url = f"{self.base_url}/chatbot_respostas"
        self.http_em_thread("GET", url, callback=callback)

    def criar_busca_centralizada(self, texto_label: str, entidade: str):
        frame_busca = ttk.Frame(self.frame_main)
        frame_busca.pack(pady=(10, 5), fill="x", padx=20)
        ttk.Label(frame_busca, text=texto_label, width=15, anchor="e").pack(side="left", padx=(0, 8))
        entry = ttk.Entry(frame_busca, width=35, font=("Segoe UI", 10))
        entry.pack(side="left", fill="none")
        entry.bind("<KeyRelease>", lambda e: self.filtrar(entidade, entry.get()))
        return entry

    def mostrar_pagina(self, entidade: str):
        self.limpar_area()
        if entidade == "materias":
            self.get_turmas(refresh=True)
            self.get_cursos(refresh=True)
            self.root.after(800, lambda: getattr(self, f"pagina_{entidade}")())
        elif entidade == "alunos":
            self.get_cursos(refresh=True)
            self.get_turmas(refresh=True)
            self.root.after(800, lambda: getattr(self, f"pagina_{entidade}")())
        else:
            getattr(self, f"pagina_{entidade}")()

    def atualizar_combos(self):
        if not hasattr(self, "combo_curso") or not self.combo_curso.winfo_exists():
            return
        if not self.cache_cursos:
            self.curso_var.set("Carregando cursos...")
            self.combo_curso.configure(state="disabled")
            self.root.after(500, self.atualizar_combos)
            return

        siglas = [c["sigla"] for c in self.cache_cursos]
        self.combo_curso["values"] = siglas  # SEM "Selecione um curso"
        self.combo_curso.configure(state="readonly")
        self.curso_var.set("")  # Limpo

        if self.cache_turmas:
            turmas = [t["turma"] for t in self.cache_turmas]
            self.combo_turma["values"] = turmas
            self.combo_turma.configure(state="readonly")
            self.turma_var.set("")
        else:
            self.combo_turma["values"] = []
            self.combo_turma.configure(state="disabled")
            self.turma_var.set("")

    def sincroniza(self, event=None): # função para sincronizar turma e curso
        selected_turma = self.turma_var.get()
        if not selected_turma or not self.cache_turmas:
            return

        for t in self.cache_turmas: # quando seleciona turma, o curso é preenchido automaticamente
            if t["turma"] == selected_turma:
                self.curso_var.set(t["curso_sigla"])
                # Atualiza o combo também
                if hasattr(self, "combo_curso") and self.combo_curso.winfo_exists():
                    self.combo_curso.set(t["curso_sigla"])
                break

    def pagina_alunos(self):
        self.titulo_centralizado("Alunos")
        self.entry_busca = self.criar_busca_centralizada("Buscar Aluno:", "alunos")
        frame_form = ttk.Frame(self.frame_main)
        frame_form.pack(pady=15, padx=20, fill="x")

        labels = ["Aluno:", "RA:", "E-mail:"]
        self.aluno_entries = []
        for i, lbl in enumerate(labels):
            ttk.Label(frame_form, text=lbl).grid(row=i, column=0, sticky="e", padx=5, pady=3)
            e = ttk.Entry(frame_form, width=35)
            e.grid(row=i, column=1, padx=5, pady=3)
            self.aluno_entries.append(e)

        self.curso_var = tk.StringVar()
        ttk.Label(frame_form, text="Curso:").grid(row=0, column=2, sticky="e", padx=5, pady=3)
        self.combo_curso = ttk.Combobox(frame_form, textvariable=self.curso_var, state="readonly", width=32)
        self.combo_curso.grid(row=0, column=3, padx=5, pady=3)

        self.turma_var = tk.StringVar()
        ttk.Label(frame_form, text="Turma:").grid(row=1, column=2, sticky="e", padx=5, pady=3)
        self.combo_turma = ttk.Combobox(frame_form, textvariable=self.turma_var, state="disabled", width=32)
        self.combo_turma.grid(row=1, column=3, padx=5, pady=3)

        # sincroniza curso ao selecionar turma
        self.combo_turma.bind("<<ComboboxSelected>>", self.sincroniza)

        def adicionar():
            nome = self.aluno_entries[0].get().strip()
            ra = self.aluno_entries[1].get().strip()
            email = self.aluno_entries[2].get().strip()
            curso = self.curso_var.get()
            turma = self.turma_var.get()
            if not all([nome, ra, email, curso, turma]) or curso in ["Selecione um curso"]:
                return messagebox.showerror("Erro", "Preencha todos os campos")
            if not any(t["turma"] == turma and t["curso_sigla"] == curso for t in self.cache_turmas):
                return messagebox.showerror("Erro", "Turma não pertence ao curso")
            self.add_entidade("alunos", [nome, ra, email, curso, turma])
            for e in self.aluno_entries: e.delete(0, tk.END)
            self.curso_var.set("Selecione um curso")
            self.turma_var.set("")

        ttk.Button(frame_form, text="Adicionar", command=adicionar).grid(row=3, column=1, pady=10)
        tree = self.criar_tabela("alunos")
        self.get_dados("alunos")

        btn_frame = ttk.Frame(frame_form)
        btn_frame.grid(row=3, column=2, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="Alterar", command=partial(self.alterar_entidade, "alunos")).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Excluir", command=partial(self.excluir_entidade, "alunos")).pack(side="left", padx=5)

    def pagina_cursos(self):
        self.titulo_centralizado("Cursos")
        self.entry_busca = self.criar_busca_centralizada("Buscar Curso:", "cursos")
        frame_form = ttk.Frame(self.frame_main)
        frame_form.pack(pady=15, padx=20, fill="x")
        labels = ["Curso:", "Sigla:", "Área:", "Descrição:"]
        self.curso_entries = []
        for i, lbl in enumerate(labels):
            ttk.Label(frame_form, text=lbl).grid(row=i, column=0, sticky="e", padx=5, pady=3)
            e = ttk.Entry(frame_form, width=35)
            e.grid(row=i, column=1, padx=5, pady=3)
            self.curso_entries.append(e)

        def adicionar():
            valores = [e.get().strip() for e in self.curso_entries]
            if not all(valores[:3]):
                return messagebox.showerror("Erro", "Preencha nome, sigla e área")
            self.add_entidade("cursos", valores)
            for e in self.curso_entries: e.delete(0, tk.END)
        ttk.Button(frame_form, text="Adicionar", command=adicionar).grid(row=4, column=1, pady=10)
        tree = self.criar_tabela("cursos")
        self.get_dados("cursos")
        btn_frame = ttk.Frame(frame_form)
        btn_frame.grid(row=4, column=2, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="Alterar", command=partial(self.alterar_entidade, "cursos")).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Excluir", command=partial(self.excluir_entidade, "cursos")).pack(side="left", padx=5)

    def pagina_turmas(self):
        self.titulo_centralizado("Turmas")
        self.entry_busca = self.criar_busca_centralizada("Buscar Turma:", "turmas")
        frame_form = ttk.Frame(self.frame_main)
        frame_form.pack(pady=15, padx=20, fill="x")
        labels = ["Turma:", "Descrição:"]
        self.turma_entries = []
        for i, lbl in enumerate(labels):
            ttk.Label(frame_form, text=lbl).grid(row=i, column=0, sticky="e", padx=5, pady=3)
            e = ttk.Entry(frame_form, width=35)
            e.grid(row=i, column=1, padx=5, pady=3)
            self.turma_entries.append(e)

        self.curso_var = tk.StringVar()
        ttk.Label(frame_form, text="Curso:").grid(row=0, column=2, sticky="e", padx=5, pady=3)
        self.combo_curso = ttk.Combobox(frame_form, textvariable=self.curso_var, state="readonly", width=32)
        self.combo_curso.grid(row=0, column=3, padx=5, pady=3)

        self.get_cursos(refresh=True)
        self.root.after(800, self.atualizar_combos) 

        def adicionar():
            turma = self.turma_entries[0].get().strip()
            descricao = self.turma_entries[1].get().strip()
            curso = self.curso_var.get()
            if not turma or not curso:
                return messagebox.showerror("Erro", "Preencha turma e curso")
            self.add_entidade("turmas", [turma, curso, descricao])
            self.turma_entries[0].delete(0, tk.END)
            self.turma_entries[1].delete(0, tk.END)
            self.curso_var.set("")

        ttk.Button(frame_form, text="Adicionar", command=adicionar).grid(row=3, column=1, pady=10)
        tree = self.criar_tabela("turmas")
        self.get_dados("turmas")
        btn_frame = ttk.Frame(frame_form)
        btn_frame.grid(row=3, column=2, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="Alterar", command=partial(self.alterar_entidade, "turmas")).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Excluir", command=partial(self.excluir_entidade, "turmas")).pack(side="left", padx=5)

    def pagina_materias(self):
        self.titulo_centralizado("Matérias")
        self.entry_busca = self.criar_busca_centralizada("Buscar Matéria:", "materias")
        frame_form = ttk.Frame(self.frame_main)
        frame_form.pack(pady=15, padx=20, fill="x")

        labels = ["Matéria:", "Professor:", "E-mail:", "Descrição:"]
        self.materia_entries = []
        for i, lbl in enumerate(labels):
            ttk.Label(frame_form, text=lbl).grid(row=i, column=0, sticky="e", padx=5, pady=3)
            e = ttk.Entry(frame_form, width=35)
            e.grid(row=i, column=1, padx=5, pady=3)
            if lbl == "Descrição:": e.grid(columnspan=3)
            self.materia_entries.append(e)

        self.curso_var = tk.StringVar()
        self.combo_curso = ttk.Combobox(frame_form, textvariable=self.curso_var, state="readonly", width=32)
        self.combo_curso.grid(row=0, column=3, padx=5, pady=3)

        self.turma_var = tk.StringVar()
        self.combo_turma = ttk.Combobox(frame_form, textvariable=self.turma_var, state="disabled", width=32)
        self.combo_turma.grid(row=1, column=3, padx=5, pady=3)

        self.root.after(800, self.atualizar_combos)
        self.combo_turma.bind("<<ComboboxSelected>>", self.sincroniza)  # Sincroniza curso

        def adicionar():
            valores = [e.get().strip() for e in self.materia_entries]
            curso = self.curso_var.get()
            turma = self.turma_var.get()
            if not all(valores[:3]):
                return messagebox.showerror("Erro", "Preencha matéria, professor e e-mail")
            if curso in ["", "Selecione um curso"]:
                return messagebox.showerror("Erro", "Selecione um curso")
            if not turma:
                return messagebox.showerror("Erro", "Selecione uma turma")
            descricao = valores[3] if valores[3] else None
            self.add_entidade("materias", [valores[0], valores[1], valores[2], curso, turma, descricao])
            for e in self.materia_entries: e.delete(0, tk.END)
            self.curso_var.set(curso)
            self.root.after(800, self.atualizar_combos)
            self.combo_turma.bind("<<ComboboxSelected>>", self.sincroniza)

        ttk.Button(frame_form, text="Adicionar", command=adicionar).grid(row=4, column=1, pady=10)
        tree = self.criar_tabela("materias")
        self.get_dados("materias")
        btn_frame = ttk.Frame(frame_form)
        btn_frame.grid(row=4, column=2, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="Alterar", command=partial(self.alterar_entidade, "materias")).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Excluir", command=partial(self.excluir_entidade, "materias")).pack(side="left", padx=5)

    def pagina_chatbot(self):
        self.titulo_centralizado("Chatbot - Perguntas Frequentes")
        self.entry_busca = self.criar_busca_centralizada("Buscar Pergunta:", "chatbot")
        frame_form = ttk.Frame(self.frame_main)
        frame_form.pack(pady=15, padx=20, fill="x")
        ttk.Label(frame_form, text="Pergunta:").grid(row=0, column=0, sticky="e", padx=5, pady=3)
        self.pergunta_entry = ttk.Entry(frame_form, width=35)
        self.pergunta_entry.grid(row=0, column=1, padx=5, pady=3, sticky="ew")
        ttk.Label(frame_form, text="Resposta:").grid(row=1, column=0, sticky="n", padx=5, pady=3)
        self.resposta_text = tk.Text(frame_form, height=4, width=35, wrap="word", font=("Segoe UI", 10))
        self.resposta_text.grid(row=1, column=1, padx=5, pady=3, sticky="ew")
        frame_form.columnconfigure(1, weight=1)
        tree = self.criar_tabela("chatbot")
        self.get_dados("chatbot")
        btn_frame = ttk.Frame(frame_form)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=10, sticky="e")
        ttk.Button(btn_frame, text="Alterar", command=partial(self.alterar_entidade, "chatbot")).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Adicionar", command=self._adicionar_chatbot).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Excluir", command=partial(self.excluir_entidade, "chatbot_respostas")).pack(side="left", padx=5)

    def _adicionar_chatbot(self):
        pergunta = self.pergunta_entry.get().strip()
        resposta = self.resposta_text.get("1.0", "end-1c").strip()
        if not pergunta or not resposta:
            return messagebox.showerror("Erro", "Preencha pergunta e resposta")
        self.add_entidade("chatbot_respostas", [pergunta, resposta])
        self.pergunta_entry.delete(0, tk.END)
        self.resposta_text.delete("1.0", "end")

    def add_entidade(self, entidade: str, valores: List[str]):
        chaves = self.get_colunas_e_chaves(entidade.split("_")[0] if "_" in entidade else entidade)["chaves"]
        if len(valores) != len(chaves):
            return messagebox.showerror("Erro", "Campos inválidos")
        valores = [v if v != "" else None for v in valores]
        payload = dict(zip(chaves, valores)) # converte listas em dicionários com chaves corretas
        def callback(sucesso, dados, erro):
            if sucesso:
                messagebox.showinfo("Sucesso", "Adicionado!")
                self.get_dados(entidade.split("_")[0] if "_" in entidade else entidade, force_refresh=True)
            else:
                messagebox.showerror("Erro", erro or "Falha")
        url = f"{self.base_url}/{entidade}"
        if entidade == "chatbot_respostas":
            url = f"{self.base_url}/chatbot_respostas"
        self.http_em_thread("POST", url, payload, callback) # envia post com os dados

    def alterar_entidade(self, entidade: str):
        tree = getattr(self, f"tree_{entidade}", None)
        if not tree or not tree.selection():
            return messagebox.showwarning("Atenção", "Selecione um item")
        item = tree.selection()[0]
        id_item = tree.item(item, "tags")[0]
        valores = tree.item(item, "values")
        entidade_url = "chatbot_respostas" if entidade == "chatbot" else entidade
        self.abrir_janela_alterar(entidade_url, valores, id_item)

    def abrir_janela_alterar(self, entidade: str, valores: tuple, id_item: str):
        janela = tk.Toplevel(self.root) # janela secundária
        janela.title(f"Alterar {entidade.replace('_', ' ').title()}")
        janela.geometry("950x600")
        janela.configure(bg="#2b2b2b")

        # bloqueia a janela principal até fechar a secundária
        janela.transient(self.root)
        janela.grab_set()

        frame = ttk.Frame(janela, padding=20)
        frame.pack(fill="both", expand=True)
        info = self.get_colunas_e_chaves(entidade.split("_")[0] if "_" in entidade else entidade)
        chaves = info["chaves"]
        entradas = []
        vars_dict = {}
        for i, (chave, valor) in enumerate(zip(chaves, valores)):
            rotulo = {"curso_sigla": "Curso", "turma": "Turma", "materia": "Matéria", "descricao": "Descrição", "aluno": "Aluno", "ra": "RA", "email": "E-mail", "professor": "Professor"}.get(chave, chave.title())
            ttk.Label(frame, text=rotulo + ":", anchor="e").grid(row=i, column=0, sticky="e", padx=5, pady=6)
            if chave == "curso_sigla" and entidade not in ["cursos"]:
                var = tk.StringVar(value=valor)
                vars_dict["curso_sigla"] = var
                combo = ttk.Combobox(frame, textvariable=var, values=self.get_cursos(), state="readonly", width=30)
                combo.grid(row=i, column=1, padx=5, pady=6, sticky="ew")
                entradas.append(combo)
            elif chave == "turma" and entidade not in ["turmas"]:
                var = tk.StringVar(value=valor)
                vars_dict["turma"] = var
                combo = ttk.Combobox(frame, textvariable=var, values=self.get_turmas(), state="readonly", width=30)
                combo.grid(row=i, column=1, padx=5, pady=6, sticky="ew")
                entradas.append(combo)
            elif chave == "descricao":
                entry = ttk.Entry(frame, width=35)
                entry.insert(0, valor)
                entry.grid(row=i, column=1, columnspan=2, padx=5, pady=6, sticky="ew")
                entradas.append(entry)
            elif chave == "resposta":
                text = tk.Text(frame, height=6, width=35, wrap="word", font=("Segoe UI", 10))
                text.insert("1.0", valor)
                text.grid(row=i, column=1, columnspan=2, padx=5, pady=6, sticky="ew")
                entradas.append(text)
            else:
                entry = ttk.Entry(frame, width=35)
                entry.insert(0, valor)
                entry.grid(row=i, column=1, padx=5, pady=6, sticky="ew")
                entradas.append(entry)

        if "turma" in vars_dict and "curso_sigla" in vars_dict:
            def sincroniza_curso(event=None):
                sel_turma = vars_dict["turma"].get()
                if sel_turma and self.cache_turmas:
                    for t in self.cache_turmas:
                        if t["turma"] == sel_turma:
                            vars_dict["curso_sigla"].set(t["curso_sigla"])
                            break

            combo_turma = next((e for e in entradas if isinstance(e, ttk.Combobox) and e.cget("textvariable") == str(vars_dict.get("turma"))), None)
            if combo_turma:
                combo_turma.bind("<<ComboboxSelected>>", sincroniza_curso)
                self.root.after(150, sincroniza_curso, None)  # Preenche ao abrir

        def salvar():
            novos = []
            for e in entradas:
                if isinstance(e, tk.Text):
                    valor = e.get("1.0", "end-1c").strip()
                elif isinstance(e, ttk.Combobox):
                    valor = e.get()
                else:
                    valor = e.get().strip()
                novos.append(valor)
            obrigatorios = [i for i, c in enumerate(chaves) if c not in ["descricao", "resposta"]]
            if any(not novos[i] for i in obrigatorios):
                return messagebox.showerror("Erro", "Preencha todos os campos obrigatórios")
            payload = dict(zip(chaves, novos))
            def callback(sucesso, dados, erro):
                if sucesso:
                    messagebox.showinfo("Sucesso", "Alterado!")
                    janela.destroy()
                    self.get_dados(entidade.split("_")[0] if "_" in entidade else entidade, force_refresh=True)
                else:
                    messagebox.showerror("Erro", erro or "Falha")
            url = f"{self.base_url}/{entidade}/{id_item}"
            if entidade == "chatbot_respostas": url = f"{self.base_url}/chatbot_respostas/{id_item}"
            self.http_em_thread("PUT", url, payload, callback)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=len(chaves), column=0, columnspan=3, pady=20)
        ttk.Button(btn_frame, text="Salvar", command=salvar).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancelar", command=janela.destroy).pack(side="left", padx=5)
        frame.columnconfigure(1, weight=1)

    def excluir_entidade(self, entidade: str):
        tree = getattr(self, f"tree_{entidade.split('_')[0] if '_' in entidade else entidade}", None)
        if not tree:
            return messagebox.showwarning("Atenção", "Tabela não carregada")
        selecionados = tree.selection()
        if not selecionados:
            return messagebox.showwarning("Atenção", "Selecione um item")
        id_item = tree.item(selecionados[0], "tags")[0]
        if messagebox.askyesno("Confirmação", "Excluir permanentemente?"): # exibe caixa de diálogo com sim e não
            def callback(sucesso, dados, erro):
                if sucesso:
                    messagebox.showinfo("Sucesso", "Excluído!")
                    self.get_dados(entidade.split("_")[0] if "_" in entidade else entidade, force_refresh=True)
            url = f"{self.base_url}/{entidade}/{id_item}"
            if entidade == "chatbot_respostas": url = f"{self.base_url}/chatbot_respostas/{id_item}"
            self.http_em_thread("DELETE", url, callback=callback)

    def filtrar(self, entidade: str, termo: str):
        dados = getattr(self, f"cache_{entidade}", [])
        if termo:
            chave_busca = {"alunos": "aluno", "cursos": "curso", "turmas": "turma", "materias": "materia", "chatbot": "pergunta"}.get(entidade, "")
            if chave_busca:
                dados = [d for d in dados if termo.lower() in d.get(chave_busca, "").lower()]
        tree = getattr(self, f"tree_{entidade}", None)
        if tree:
            info = self.get_colunas_e_chaves(entidade)
            self.preencher_tabela(tree, dados, info["chaves"])

    def http_em_thread(self, metodo, url, dados=None, callback=None):
        def tarefa():
            try:
                headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
                r = requests.request(metodo, url, json=dados or {}, headers=headers, timeout=10)
                sucesso = r.status_code in (200, 201, 204)
                resultado = r.json() if sucesso and r.text else {}
                erro = r.json().get("detail") if not sucesso else None
                if callback:
                    self.root.after(0, callback, sucesso, resultado, erro) # atualiza UI no fluxo principal
            except Exception as e:
                if callback:
                    self.root.after(0, callback, False, None, str(e))
        threading.Thread(target=tarefa, daemon=True).start() # fluxo não bloqueia a UI

    def mostrar_loading(self, texto="Carregando..."):
        if hasattr(self, "loading") and self.loading:
            return
        self.loading = tk.Toplevel(self.root)
        self.loading.title("")
        self.loading.geometry("300x100")
        self.loading.transient(self.root)
        self.loading.grab_set()
        self.loading.configure(bg="#2b2b2b")
        ttk.Label(self.loading, text=texto, font=("Segoe UI", 11)).pack(pady=20)
        spinner = ttk.Progressbar(self.loading, mode="indeterminate")
        spinner.pack(fill="x", padx=20)
        spinner.start()

    def esconder_loading(self):
        if hasattr(self, "loading") and self.loading:
            self.loading.destroy()
            self.loading = None



    
if __name__ == "__main__":

    root = tk.Tk()
    app = SistemaAcademico(root)
    root.mainloop()
