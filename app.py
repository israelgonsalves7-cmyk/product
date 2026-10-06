import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import date
from io import BytesIO
import json
import requests    # Necessário para enviar/puxar dados de outros sites/APIs
import urllib.parse    # Para tratar URLs com parâmetros de busca

# =========================================================
# CONFIGURAÇÃO DA PÁGINA
# =========================================================

st.set_page_config(
    page_title="PRODUCT | Enterprise Workspace",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB = "produtividade.db"


# =========================================================
# BANCO DE DADOS (CRIAÇÃO DO ZERO / MIGRAÇÃO AUTOMÁTICA)
# =========================================================

def conectar():
    return sqlite3.connect(DB)


def criar_banco():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS colaboradores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS produtividade (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            colaborador TEXT NOT NULL,
            sysvet_erro INTEGER DEFAULT 0,
            sysvet_exito INTEGER DEFAULT 0,
            faturado INTEGER DEFAULT 0,
            auditoria INTEGER DEFAULT 0,
            observacao TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuracoes (
            id INTEGER PRIMARY KEY,
            senha TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS acessos_colaboradores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE,
            senha TEXT NOT NULL
        )
    """)

    try:
        cursor.execute("ALTER TABLE produtividade ADD COLUMN auditoria INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE produtividade ADD COLUMN observacao TEXT")
    except sqlite3.OperationalError:
        pass

    cursor.execute("SELECT COUNT(*) FROM configuracoes")
    quantidade = cursor.fetchone()[0]

    if quantidade == 0:
        cursor.execute(
            "INSERT INTO configuracoes (id, senha) VALUES (1, ?)",
            ("2010",)
        )

    conn.commit()
    conn.close()


criar_banco()


# =========================================================
# FUNÇÕES DE APOIO E DADOS (E INTEGRAÇÃO EXTERNA INTELIGENTE)
# =========================================================

def buscar_senha():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT senha FROM configuracoes WHERE id = 1")
    resultado = cursor.fetchone()
    conn.close()
    if resultado:
        return resultado[0]
    return "2010"


def alterar_senha(nova_senha):
    conn = conectar()
    conn.execute("UPDATE configuracoes SET senha = ? WHERE id = 1", (nova_senha,))
    conn.commit()
    conn.close()


def buscar_colaboradores():
    conn = conectar()
    df = pd.read_sql_query("SELECT * FROM colaboradores ORDER BY nome", conn)
    conn.close()
    return df


def buscar_acessos():
    conn = conectar()
    df = pd.read_sql_query("SELECT * FROM acessos_colaboradores ORDER BY nome", conn)
    conn.close()
    return df


def buscar_produtividade():
    conn = conectar()
    df = pd.read_sql_query("SELECT * FROM produtividade ORDER BY data DESC, id DESC", conn)
    conn.close()

    if not df.empty:
        df["data"] = pd.to_datetime(df["data"], errors="coerce")
        df["sysvet_erro"] = pd.to_numeric(df["sysvet_erro"], errors="coerce").fillna(0).astype(int)
        df["sysvet_exito"] = pd.to_numeric(df["sysvet_exito"], errors="coerce").fillna(0).astype(int)
        df["faturado"] = pd.to_numeric(df["faturado"], errors="coerce").fillna(0).astype(int)

        if "auditoria" not in df.columns:
            df["auditoria"] = 0
        else:
            df["auditoria"] = pd.to_numeric(df["auditoria"], errors="coerce").fillna(0).astype(int)

        if "observacao" not in df.columns:
            df["observacao"] = ""
        else:
            df["observacao"] = df["observacao"].fillna("")

        df["total_sysvet"] = df["sysvet_erro"] + df["sysvet_exito"]
        df["produtividade_total"] = df["sysvet_erro"] + df["sysvet_exito"] + df["faturado"] + df["auditoria"]

        df["taxa_exito"] = df.apply(
            lambda linha: (linha["sysvet_exito"] / linha["total_sysvet"] * 100) if linha["total_sysvet"] > 0 else 0,
            axis=1
        )
    return df


def gerar_backup_json():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM colaboradores")
    cols = [desc[0] for desc in cursor.description]
    colaboradores = [dict(zip(cols, row)) for row in cursor.fetchall()]

    cursor.execute("SELECT * FROM produtividade")
    cols = [desc[0] for desc in cursor.description]
    produtividade = [dict(zip(cols, row)) for row in cursor.fetchall()]

    cursor.execute("SELECT * FROM acessos_colaboradores")
    cols = [desc[0] for desc in cursor.description]
    acessos = [dict(zip(cols, row)) for row in cursor.fetchall()]

    conn.close()

    dados_backup = {
        "colaboradores": colaboradores,
        "produtividade": produtividade,
        "acessos_colaboradores": acessos
    }
    return json.dumps(dados_backup, ensure_ascii=False, indent=4)


def enviar_dados_para_externo(dados_payload):
    try:
        url_destino = "https://seu-sistema-externo.com/api/receber"
        resposta = requests.post(url_destino, json=dados_payload, timeout=5)
        return resposta.status_code == 200
    except Exception:
        return False


# =========================================================
# DESIGN SYSTEM EXCLUSIVO (UI / UX)
# =========================================================

if "modo_noturno" not in st.session_state:
    st.session_state.modo_noturno = True

if not st.session_state.modo_noturno:
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }
    .stApp { background-color: #f8fafc; color: #0f172a; }
    </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }
    .stApp { background-color: #030712; color: #f8fafc; }
    </style>
    """, unsafe_allow_html=True)


# =========================================================
# CONTROLE DE SESSÃO / TELA DE LOGIN PREMIUM
# =========================================================

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "perfil" not in st.session_state:
    st.session_state.perfil = None
if "usuario_logado" not in st.session_state:
    st.session_state.usuario_logado = None


if not st.session_state.autenticado:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.3, 1])

    with col2:
        st.markdown("<h1 style='text-align: center; font-size: 2.5rem;'>⚡ PRODUCT</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; font-size: 1.05rem;'>Workspace Corporativo de Alta Performance</p>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        tipo_login = st.radio("Acessar como:", ["Administrador", "Colaborador"], horizontal=True)

        if tipo_login == "Administrador":
            senha_adm = st.text_input("Senha Master do Administrador", type="password", key="senha_adm_input")
            st.markdown("<br>", unsafe_allow_html=True)
            entrar = st.button("🔐 AUTENTICAR NO SISTEMA", use_container_width=True)

            if entrar:
                if senha_adm == buscar_senha():
                    st.session_state.autenticado = True
                    st.session_state.perfil = "admin"
                    st.session_state.usuario_logado = "Administrador Master"
                    st.rerun()
                else:
                    st.error("❌ Senha master incorreta.")
        else:
            df_acessos = buscar_acessos()
            if df_acessos.empty:
                st.warning("⚠ Nenhum acesso de colaborador configurado pelo Administrador.")
            else:
                colab_escolhido = st.selectbox("Selecione seu perfil", df_acessos["nome"].tolist())
                senha_colab = st.text_input("Senha de acesso pessoal", type="password", key="senha_colab_input")
                st.markdown("<br>", unsafe_allow_html=True)
                entrar_colab = st.button("🔐 AUTENTICAR NO SISTEMA", use_container_width=True)

                if entrar_colab:
                    senha_correta = df_acessos[df_acessos["nome"] == colab_escolhido]["senha"].values[0]
                    if senha_colab == senha_correta:
                        st.session_state.autenticado = True
                        st.session_state.perfil = "colaborador"
                        st.session_state.usuario_logado = colab_escolhido
                        st.rerun()
                    else:
                        st.error("❌ Senha incorreta.")

    st.stop()


# =========================================================
# MENU LATERAL REFINADO & BOT DE PASSO A PASSO
# =========================================================

st.sidebar.markdown("## ⚡ PRODUCT")
st.sidebar.markdown(f"""
<div style="background: rgba(255,255,255,0.04); padding: 12px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.08); margin-bottom: 15px;">
    <p style="margin:0; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em;">Sessão Ativa</p>
    <p style="margin:4px 0 0 0; font-weight: 700; font-size: 0.95rem;">👤 {st.session_state.usuario_logado}</p>
</div>
""", unsafe_allow_html=True)

# Nova Função de Bot para Passo a Passo na Sidebar
st.sidebar.markdown("### 🤖 Assistente Bot (Passo a Passo)")
passo_a_passo_input = st.sidebar.text_area("Digite o passo a passo desejado:", placeholder="Ex: 1. Organizar demandas\n2. Conferir faturamento...", height=100)

if st.sidebar.button("🚀 Processar Passo a Passo", use_container_width=True):
    if not passo_a_passo_input.strip():
        st.sidebar.warning("⚠️ Digite um passo a passo para o bot analisar.")
    else:
        st.sidebar.success("✅ Passo a passo recebido pelo Bot com sucesso!")
        linhas_passos = [l.strip() for l in passo_a_passo_input.split('\n') if l.strip()]
        st.sidebar.info(f"O bot identificou **{len(linhas_passos)}** etapas na sua instrução. Informações prontas para automação!")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🌐 Consulta Externa")

lista_unidades = ["PROVET-APOIO", "PROVET-MATRIZ", "PROVET-FILIAL"]
unidade_selecionada = st.sidebar.selectbox("🏥 Unidade", lista_unidades)

df_cols_sidebar = buscar_colaboradores()
lista_nomes_sidebar = df_cols_sidebar["nome"].tolist() if not df_cols_sidebar.empty else []

if lista_nomes_sidebar:
    usuario_atendimento = st.sidebar.selectbox("👨‍‍⚕️ Usuário de Atendimento", lista_nomes_sidebar)
else:
    usuario_atendimento = st.sidebar.text_input("👨‍⚕️ Usuário de Atendimento", value="Atendente Padrão")

meses_dict = {
    "Janeiro": "01", "Fevereiro": "02", "Março": "03", "Abril": "04",
    "Maio": "05", "Junho": "06", "Julho": "07", "Agosto": "08",
    "Setembro": "09", "Outubro": "10",
