import streamlit as st
import datetime
import random
import sqlite3
import time
from PIL import Image
import qrcode
import io
import hashlib

# --- CONFIGURAÇÃO DA PÁGINA (DEVE SER A PRIMEIRA CHAMADA) ---
st.set_page_config(
    page_title="Sistema de Apostas",
    page_icon="🎰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CONSTANTES ---
CHAVE_PIX = "11984673296"  # Sua chave PIX
TEMPO_VALIDADE = 1800  # 30 minutos em segundos
MAX_NUMEROS_APOSTA = 15  # Limite de números por aposta

# --- FUNÇÕES AUXILIARES PIX ---
def gerar_payload_pix(chave, valor, beneficiario="Apostas Online", cidade="Sao Paulo"):
    """Gera o payload PIX conforme padrão BCB"""
    valor_str = f"{valor:.2f}"
    
    payload = [
        "000201",  # Início do payload
        "26580014br.gov.bcb.pix",
        f"01{len(chave)}{chave}",
        "52040000",
        "5303986",
        f"54{valor_str}",
        "5802BR",
        f"59{beneficiario[:25]}",
        f"60{cidade[:15]}",
        "62070503***",
        "6304"
    ]
    
    return "".join(payload)

def gerar_qr_code_pix(valor, chave_pix):
    """Gera QR Code PIX copia e cola"""
    payload = gerar_payload_pix(chave_pix, valor)
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    return img_byte_arr.getvalue(), payload

# --- BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('apostas.db')
    c = conn.cursor()
    
    # Tabela de usuários
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 nome TEXT NOT NULL,
                 email TEXT UNIQUE NOT NULL,
                 celular TEXT,
                 senha TEXT NOT NULL)''')
    
    # Tabela de apostas
    c.execute('''CREATE TABLE IF NOT EXISTS apostas
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 usuario_id INTEGER NOT NULL,
                 numeros TEXT NOT NULL,
                 valor REAL NOT NULL,
                 data TEXT NOT NULL,
                 pago BOOLEAN DEFAULT FALSE,
                 FOREIGN KEY (usuario_id) REFERENCES usuarios (id))''')
    
    # Tabela de sorteios
    c.execute('''CREATE TABLE IF NOT EXISTS sorteios
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 data TEXT NOT NULL,
                 numeros_sorteados TEXT NOT NULL)''')
    
    conn.commit()
    conn.close()

def criar_usuario(nome, email, celular, senha):
    conn = sqlite3.connect('apostas.db')
    c = conn.cursor()
    senha_hash = hashlib.sha256(senha.encode()).hexdigest()
    try:
        c.execute("INSERT INTO usuarios (nome, email, celular, senha) VALUES (?, ?, ?, ?)",
                  (nome, email, celular, senha_hash))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def verificar_login(email, senha):
    conn = sqlite3.connect('apostas.db')
    c = conn.cursor()
    senha_hash = hashlib.sha256(senha.encode()).hexdigest()
    c.execute("SELECT id, nome FROM usuarios WHERE email = ? AND senha = ?", (email, senha_hash))
    usuario = c.fetchone()
    conn.close()
    return usuario

def registrar_aposta(usuario_id, numeros, valor):
    conn = sqlite3.connect('apostas.db')
    c = conn.cursor()
    c.execute("INSERT INTO apostas (usuario_id, numeros, valor, data, pago) VALUES (?, ?, ?, ?, ?)",
              (usuario_id, ','.join(map(str, numeros)), valor, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), True))
    conn.commit()
    conn.close()

def obter_apostas_usuario(usuario_id):
    conn = sqlite3.connect('apostas.db')
    c = conn.cursor()
    c.execute("SELECT id, numeros, valor, data FROM apostas WHERE usuario_id = ? ORDER BY data DESC", (usuario_id,))
    apostas = c.fetchall()
    conn.close()
    return apostas

def realizar_sorteio_db(numeros_sorteados):
    conn = sqlite3.connect('apostas.db')
    c = conn.cursor()
    c.execute("INSERT INTO sorteios (data, numeros_sorteados) VALUES (?, ?)",
              (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ','.join(map(str, numeros_sorteados))))
    conn.commit()
    conn.close()

def obter_ultimo_sorteio():
    conn = sqlite3.connect('apostas.db')
    c = conn.cursor()
    c.execute("SELECT id, data, numeros_sorteados FROM sorteios ORDER BY id DESC LIMIT 1")
    sorteio = c.fetchone()
    conn.close()
    return sorteio

def obter_todas_apostas():
    conn = sqlite3.connect('apostas.db')
    c = conn.cursor()
    c.execute("SELECT a.id, u.nome, a.numeros FROM apostas a JOIN usuarios u ON a.usuario_id = u.id")
    apostas = c.fetchall()
    conn.close()
    return apostas

def realizar_sorteio(max_numeros=50):
    """Sorteia 5 números únicos entre 1 e max_numeros"""
    return random.sample(range(1, max_numeros + 1), 5)

def verificar_ganhadores(apostas, numeros_sorteados):
    resultados = []
    for aposta in apostas:
        numeros_aposta = list(map(int, aposta[2].split(',')))
        acertos = len(set(numeros_aposta).intersection(numeros_sorteados))
        resultados.append({
            'id': aposta[0],
            'nome': aposta[1],
            'numeros': numeros_aposta,
            'acertos': acertos,
            'ganhou': acertos >= 3  # Ganha com 3+ acertos
        })
    
    # Garante que pelo menos um ganhador (se houver apostas)
    if resultados and not any(r['ganhou'] for r in resultados):
        melhor_aposta = max(resultados, key=lambda x: x['acertos'])
        melhor_aposta['ganhou'] = True
    
    return resultados

def mostrar_pagamento_pix(valor_total):
    """Exibe as opções de pagamento PIX"""
    qr_img, payload = gerar_qr_code_pix(valor_total, CHAVE_PIX)
    
    st.success("Pagamento gerado com sucesso!")
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.image(qr_img, caption="QR Code PIX", width=250)
    
    with col2:
        st.write(f"**Valor:** R$ {valor_total:.2f}")
        st.write(f"**Chave PIX:** {CHAVE_PIX}")
        st.write("**Beneficiário:** Apostas Online")
        st.write("**Tempo para pagamento:** 30 minutos")
        
        with st.expander("Código PIX (copia e cola)"):
            st.code(payload, language="text")
        
        st.info("""
        **Instruções:**
        1. Abra seu aplicativo bancário
        2. Escolha pagar via PIX
        3. Escaneie o QR Code ou copie o código
        4. Confirme o pagamento
        """)
    
    if st.button("Confirmar Pagamento"):
        return True
    return False

# --- INICIALIZAÇÃO ---
init_db()

if 'autenticado' not in st.session_state:
    st.session_state.update({
        'autenticado': False,
        'usuario': None,
        'numeros_selecionados': [],
        'pagamento_gerado': False,
        'valor_total': 0
    })

# --- PÁGINAS DE AUTENTICAÇÃO ---
if not st.session_state.autenticado:
    tab_login, tab_cadastro = st.tabs(["Login", "Cadastro"])
    
    with tab_login:
        with st.form("login_form"):
            email = st.text_input("E-mail")
            senha = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar"):
                usuario = verificar_login(email, senha)
                if usuario:
                    st.session_state.autenticado = True
                    st.session_state.usuario = {'id': usuario[0], 'nome': usuario[1]}
                    st.rerun()
                else:
                    st.error("E-mail ou senha incorretos")
    
    with tab_cadastro:
        with st.form("cadastro_form"):
            nome = st.text_input("Nome Completo")
            email = st.text_input("E-mail")
            celular = st.text_input("Celular")
            senha = st.text_input("Senha", type="password")
            if st.form_submit_button("Cadastrar"):
                if criar_usuario(nome, email, celular, senha):
                    st.success("Cadastro realizado com sucesso! Faça login para continuar.")
                else:
                    st.error("E-mail já cadastrado")
    
    st.stop()

# --- PÁGINA PRINCIPAL (APÓS LOGIN) ---
st.title(f"🎰 Sistema de Apostas - Bem-vindo, {st.session_state.usuario['nome']}")

# Sidebar com configurações e logout
with st.sidebar:
    st.write(f"Usuário: {st.session_state.usuario['nome']}")
    if st.button("Sair"):
        st.session_state.autenticado = False
        st.rerun()
    
    st.markdown("---")
    st.header("Configurações do Sorteio")
    data_sorteio = st.date_input("Data do próximo sorteio", datetime.date.today() + datetime.timedelta(days=7))
    valor_aposta = st.number_input("Valor por número (R$)", min_value=1.0, value=2.0, step=0.5)
    max_numeros = st.slider("Quantidade máxima de números", 10, 100, 50)

# Abas principais
tab1, tab2, tab3, tab4 = st.tabs(["Apostar", "Minhas Apostas", "Sorteio", "Resultados"])

with tab1:
    st.subheader("Faça sua aposta")
    
    # Talão virtual
    colunas = 10
    linhas = max_numeros // colunas + (1 if max_numeros % colunas else 0)

    for linha in range(linhas):
        cols = st.columns(colunas)
        for col in range(colunas):
            numero = linha * colunas + col + 1
            if numero <= max_numeros:
                with cols[col]:
                    if st.button(str(numero), key=f"btn_{numero}"):
                        if numero in st.session_state.numeros_selecionados:
                            st.session_state.numeros_selecionados.remove(numero)
                        else:
                            if len(st.session_state.numeros_selecionados) < MAX_NUMEROS_APOSTA:
                                st.session_state.numeros_selecionados.append(numero)
                            else:
                                st.warning(f"Limite de {MAX_NUMEROS_APOSTA} números por aposta!")

    # Mostra números selecionados e valor total
    if st.session_state.numeros_selecionados:
        st.write(f"**Números selecionados:** {sorted(st.session_state.numeros_selecionados)}")
        valor_total = len(st.session_state.numeros_selecionados) * valor_aposta
        st.write(f"**Valor total:** R$ {valor_total:.2f}")
        
        if not st.session_state.pagamento_gerado:
            if st.button("Gerar PIX para pagamento"):
                st.session_state.pagamento_gerado = True
                st.session_state.valor_total = valor_total
        else:
            if mostrar_pagamento_pix(st.session_state.valor_total):
                registrar_aposta(
                    st.session_state.usuario['id'],
                    st.session_state.numeros_selecionados,
                    st.session_state.valor_total
                )
                st.balloons()
                st.success("Pagamento confirmado! Aposta registrada com sucesso.")
                st.session_state.numeros_selecionados = []
                st.session_state.pagamento_gerado = False
                time.sleep(2)
                st.rerun()
    else:
        st.info(f"Selecione de 1 a {MAX_NUMEROS_APOSTA} números para apostar")

with tab2:
    st.subheader("Minhas Apostas")
    apostas = obter_apostas_usuario(st.session_state.usuario['id'])
    
    if apostas:
        for aposta in apostas:
            with st.expander(f"Aposta #{aposta[0]} - {aposta[3]}"):
                st.write(f"**Números:** {aposta[1]}")
                st.write(f"**Valor:** R$ {aposta[2]:.2f}")
    else:
        st.info("Você ainda não fez nenhuma aposta.")

with tab3:
    st.subheader("Realizar Sorteio")
    
    if st.button("Realizar Sorteio"):
        with st.spinner("Sorteando..."):
            numeros_sorteados = realizar_sorteio(max_numeros)
            realizar_sorteio_db(numeros_sorteados)
            time.sleep(2)
            st.success("Sorteio realizado com sucesso!")
            st.balloons()
    
    ultimo_sorteio = obter_ultimo_sorteio()
    if ultimo_sorteio:
        st.write(f"**Último sorteio:** {ultimo_sorteio[1]}")
        st.write(f"**Números sorteados:** {ultimo_sorteio[2]}")

with tab4:
    st.subheader("Resultados")
    
    ultimo_sorteio = obter_ultimo_sorteio()
    if ultimo_sorteio:
        numeros_sorteados = list(map(int, ultimo_sorteio[2].split(',')))
        apostas = obter_todas_apostas()
        resultados = verificar_ganhadores(apostas, numeros_sorteados)
        
        st.write(f"**Números sorteados:** {numeros_sorteados}")
        st.write(f"**Total de apostas:** {len(resultados)}")
        
        ganhadores = [r for r in resultados if r['ganhou']]
        st.write(f"**Total de ganhadores:** {len(ganhadores)}")
        
        if ganhadores:
            st.subheader("Ganhadores")
            for ganhador in ganhadores:
                st.write(f"🎉 {ganhador['nome']} - Acertou {ganhador['acertos']} números")
    else:
        st.info("Nenhum sorteio realizado ainda.")

# Rodapé
st.markdown("---")
st.write(f"**Próximo sorteio:** {data_sorteio.strftime('%d/%m/%Y')}")
st.write(f"**Números disponíveis:** 1 a {max_numeros}")
st.write("**Números sorteados:** 5")