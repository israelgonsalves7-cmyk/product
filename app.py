import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import date
from io import BytesIO
import json

# =========================================================
# CONFIGURAÇÃO DA PÁGINA (ESTILO HÍBRIDO FLEURY + MONDAY WORK OS)
# =========================================================

st.set_page_config(
    page_title="Gestão Unificada | Product & Work OS",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB = "sistema_unificado_produtividade.db"


# =========================================================
# BANCO DE DADOS (CRIAÇÃO E MENSAGERIA UNIFICADA)
# =========================================================

def conectar():
    return sqlite3.connect(DB)


def criar_banco():
    conn = conectar()
    cursor = conn.cursor()

    # Tabela unificada integrando métricas Product + Gestão de Projetos estilo Monday
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS produtividade_unificada (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            colaborador TEXT NOT NULL,
            projeto TEXT NOT NULL,
            status_tarefa TEXT DEFAULT 'Não Iniciado',
            prioridade TEXT DEFAULT 'Média',
            sysvet_erro INTEGER DEFAULT 0,
            sysvet_exito INTEGER DEFAULT 0,
            faturado INTEGER DEFAULT 0,
            auditoria INTEGER DEFAULT 0,
            horas_estimadas REAL DEFAULT 0.0,
            observacao TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS colaboradores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuracoes (
            id INTEGER PRIMARY KEY,
            senha TEXT NOT NULL
        )
    """)

    cursor.execute("SELECT COUNT(*) FROM configuracoes")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO configuracoes (id, senha) VALUES (1, ?)", ("2010",))

    conn.commit()
    conn.close()


criar_banco()


# =========================================================
# FUNÇÕES DE APOIO
# =========================================================

def buscar_senha():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT senha FROM configuracoes WHERE id = 1")
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] if resultado else "2010"


def buscar_colaboradores():
    conn = conectar()
    df = pd.read_sql_query("SELECT * FROM colaboradores ORDER BY nome", conn)
    conn.close()
    return df


def buscar_dados():
    conn = conectar()
    df = pd.read_sql_query("SELECT * FROM produtividade_unificada ORDER BY data DESC, id DESC", conn)
    conn.close()

    if not df.empty:
        df["data"] = pd.to_datetime(df["data"], errors="coerce")
        df["sysvet_erro"] = pd.to_numeric(df["sysvet_erro"], errors="coerce").fillna(0).astype(int)
        df["sysvet_exito"] = pd.to_numeric(df["sysvet_exito"], errors="coerce").fillna(0).astype(int)
        df["faturado"] = pd.to_numeric(df["faturado"], errors="coerce").fillna(0).astype(int)
        df["auditoria"] = pd.to_numeric(df["auditoria"], errors="coerce").fillna(0).astype(int)
        df["horas_estimadas"] = pd.to_numeric(df["horas_estimadas"], errors="coerce").fillna(0.0)
        df["observacao"] = df["observacao"].fillna("")

        df["total_sysvet"] = df["sysvet_erro"] + df["sysvet_exito"]
        df["produtividade_total"] = df["sysvet_erro"] + df["sysvet_exito"] + df["faturado"] + df["auditoria"]
        df["taxa_exito"] = df.apply(
            lambda row: (row["sysvet_exito"] / row["total_sysvet"] * 100) if row["total_sysvet"] > 0 else 0,
            axis=1
        )
    return df


# =========================================================
# ESTILIZAÇÃO VISUAL (MODO CLARO / NOTURNO)
# =========================================================

if "modo_noturno" not in st.session_state:
    st.session_state.modo_noturno = False

if not st.session_state.modo_noturno:
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@300;400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; }
    .stApp { background-color: #F8FAFC; color: #002B49; }
    div.stButton > button {
        background-color: #006699; color: white; border-radius: 6px; font-weight: 600; border: none;
    }
    div.stButton > button:hover { background-color: #004D73; color: white; }
    [data-testid="stSidebar"] { background-color: #002B49; color: #FFFFFF; }
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] span, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] p {
        color: #FFFFFF !important;
    }
    </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@300;400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; }
    .stApp { background-color: #0B192C; color: #F8FAFC; }
    div.stButton > button {
        background-color: #0088CC; color: white; border-radius: 6px; font-weight: 600; border: none;
    }
    </style>
    """, unsafe_allow_html=True)


# =========================================================
# AUTENTICAÇÃO DO SISTEMA ÚNICO
# =========================================================

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown("<h1 style='text-align: center; color: #006699;'>🧬 Work OS Product</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #555555;'>Sistema Unificado de Projetos e Produtividade Operacional</p><br>", unsafe_allow_html=True)
        
        senha_input = st.text_input("Senha Master de Acesso", type="password")
        if st.button("🔐 ENTRAR NO SISTEMA", use_container_width=True):
            if senha_input == buscar_senha():
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("❌ Senha incorreta.")
    st.stop()


# =========================================================
# BARRA LATERAL (MENU E CONFIGURAÇÕES)
# =========================================================

st.sidebar.markdown("## 🧬 WORK OS PRODUCT")
st.sidebar.markdown("---")

menu = st.sidebar.radio(
    "Navegação Principal",
    ["📊 Dashboard Executivo", "📋 Quadro de Projetos (Board)", "📝 Registrar Atividade / Tarefa", "👥 Gerenciar Colaboradores", "📥 Exportar Dados"]
)

st.sidebar.markdown("---")
if st.sidebar.button("🌓 Alternar Aparência", use_container_width=True):
    st.session_state.modo_noturno = not st.session_state.modo_noturno
    st.rerun()

if st.sidebar.button("🚪 Sair do Sistema", use_container_width=True):
    st.session_state.autenticado = False
    st.rerun()


#
