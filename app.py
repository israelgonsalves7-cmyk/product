import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import date
from io import BytesIO
import json
import requests  # Necessário para enviar/puxar dados de outros sites/APIs
import urllib.parse  # Para tratar URLs com parâmetros de busca
import os
import shutil

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


# INTEGRAÇÃO EXTERNA: Puxa dados considerando a Unidade PROVET-APOIO, o usuário e o paciente
def puxar_dados_paciente_externo(unidade, usuario_atendimento, paciente_busca, mes, ano):
    try:
        uni_tratada = urllib.parse.quote(unidade)
        usu_tratado = urllib.parse.quote(usuario_atendimento)
        pac_tratado = urllib.parse.quote(paciente_busca)
        
        url_api = f"https://provet-korus.pixeonkorus.com/RotinaDiaria/api/paciente?unidade={uni_tratada}&usuario={usu_tratado}&paciente={pac_tratado}&mes={mes}&ano={ano}"
        
        resposta = requests.get(url_api, timeout=5)
        if resposta.status_code == 200:
            return resposta.json()
    except Exception:
        return None
    return None


def enviar_dados_para_externo(dados_payload):
    try:
        url_destino = "https://seu-sistema-externo.com/api/receber"
        resposta = requests.post(url_destino, json=dados_payload, timeout=5)
        return resposta.status_code == 200
    except Exception:
        return False


# BOT INTELIGENTE DE INTEGRAÇÃO DE ARQUIVOS
def processar_arquivos_com_bot(caminho_usuario):
    """
    Varre passo a passo a pasta informada, classifica fotos/PDFs,
    integra com o sistema externo e organiza em uma nova pasta.
    """
    if not os.path.exists(caminho_usuario):
        return {"status": "erro", "mensagem": "O caminho informado não foi encontrado."}

    pasta_principal = os.path.join(caminho_usuario, "Arquivos_Organizados_Bot")
    pasta_fotos = os.path.join(pasta_principal, "Fotos")
    pasta_pdfs = os.path.join(pasta_principal, "PDFs")
    pasta_outros = os.path.join(pasta_principal, "Outros")

    for pasta in [pasta_principal, pasta_fotos, pasta_pdfs, pasta_outros]:
        os.makedirs(pasta, exist_ok=True)

    contador_fotos = 0
    contador_pdfs = 0
    contador_outros = 0
    detalhes_processamento = []

    for item in os.listdir(caminho_usuario):
        caminho_completo = os.path.join(caminho_usuario, item)
        
        if os.path.isdir(caminho_completo):
            continue
            
        extensao = item.lower().split('.')[-1]
        
        # Simulação/Envio de dados para o sistema integrado via API por cada arquivo processado
        try:
            payload_arquivo = {"arquivo": item, "caminho": caminho_completo, "status": "processando"}
            # enviar_dados_para_externo(payload_arquivo) # Ative se houver endpoint ativo
        except Exception:
            pass

        if extensao in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp']:
            shutil.move(caminho_completo, os.path.join(pasta_fotos, item))
            contador_fotos += 1
            detalhes_processamento.append(f"📸 Foto movida: {item}")
        elif extensao == 'pdf':
            shutil.move(caminho_completo, os.path.join(pasta_pdfs, item))
            contador_pdfs += 1
            detalhes_processamento.append(f"📄 PDF movido: {item}")
        else:
            if item != "Arquivos_Organizados_Bot":
                shutil.move(caminho_completo, os.path.join(pasta_outros, item))
                contador_outros += 1
                detalhes_processamento.append(f"📁 Outro arquivo movido: {item}")

    return {
        "status": "sucesso",
        "fotos": contador_fotos,
        "pdfs": contador_pdfs,
        "outros": contador_outros,
        "destino": pasta_principal,
        "logs": detalhes_processamento
    }


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
        st.markdown("<p style='text-align: center; font-size: 1.05rem;'>Workspace Corporativo de Alta
