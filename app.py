import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import date
from io import BytesIO
import json
import os
import glob

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
# FUNÇÕES DE APOIO E LEITURA AUTOMÁTICA DE EXCEL
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


# NOVA FUNÇÃO: Busca o último arquivo Excel na pasta e conta pacientes por colaborador
def buscar_ultimo_arquivo_excel_e_contar_pacientes(pasta_diretorio):
    try:
        if not os.path.exists(pasta_diretorio):
            return None, "O diretório informado não existe."

        # Procura por arquivos .xlsx e .xls na pasta
        arquivos_xlsx = glob.glob(os.path.join(pasta_diretorio, "*.xlsx"))
        arquivos_xls = glob.glob(os.path.join(pasta_diretorio, "*.xls"))
        todos_arquivos = arquivos_xlsx + arquivos_xls

        if not todos_arquivos:
            return None, "Nenhum arquivo Excel encontrado na pasta especificada."

        # Pega o arquivo mais recente baseado na data de modificação
        ultimo_arquivo = max(todos_arquivos, key=os.path.getmtime)

        # Lê o arquivo Excel (ajuste os nomes das colunas 'colaborador' e 'paciente' conforme sua planilha real)
        df_excel = pd.read_excel(ultimo_arquivo)

        # Exemplo de tratamento: agrupando por colaborador para contar quantas vezes ele aparece (cadastros de pacientes)
        # Certifique-se de que as colunas na sua planilha se chamem algo parecido com 'colaborador' e 'paciente'
        col_colab = next((c for c in df_excel.columns if 'colaborador' in c.lower() or 'usuario' in c.lower() or 'atendente' in c.lower()), None)
        
        if not col_colab:
            return None, f"Coluna de colaborador não identificada no arquivo. Colunas disponíveis: {list(df_excel.columns)}"

        # Agrupa e conta os cadastros por colaborador
        resumo_contagem = df_excel.groupby(col_colab).size().reset_index(name='total_pacientes')
        
        return {
            "arquivo_lido": os.path.basename(ultimo_arquivo),
            "dados": resumo_contagem
        }, None

    except Exception as e:
        return None, str(e)


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
# MENU LATERAL REFINADO (BUSCA AUTOMÁTICA DO ÚLTIMO EXCEL)
# =========================================================

st.sidebar.markdown("## ⚡ PRODUCT")
st.sidebar.markdown(f"""
<div style="background: rgba(255,255,255,0.04); padding: 12px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.08); margin-bottom: 15px;">
    <p style="margin:0; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em;">Sessão Ativa</p>
    <p style="margin:4px 0 0 0; font-weight: 700; font-size: 0.95rem;">👤 {st.session_state.usuario_logado}</p>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("### 📁 Importação Automática (Excel)")
pasta_caminho_input = st.sidebar.text_input("Caminho da Pasta dos Relatórios", value="./relatorios")

# Botão para buscar o último Excel e processar a quantidade de cadastros
if st.sidebar.button("🔄 Puxar Cadastros do Último Excel", use_container_width=True):
    with st.spinner("Buscando o arquivo Excel mais recente..."):
        resultado_leitura, erro_msg = buscar_ultimo_arquivo_excel_e_contar_pacientes(pasta_caminho_input)
        
        if erro_msg:
            st.sidebar.error(f"⚠️ {erro_msg}")
        else:
            st.sidebar.success(f"✅ Arquivo '{resultado_leitura['arquivo_lido']}' processado!")
            st.session_state["dados_excel_recente"] = resultado_leitura["dados"]

# Se houver dados processados na sessão, exibe um breve resumo na barra lateral
if "dados_excel_recente" in st.session_state:
    st.sidebar.markdown("#### 📊 Resumo Recente")
    st.sidebar.dataframe(st.session_state["dados_excel_recente"], hide_index=True, use_container_width=True)

st.sidebar.markdown("<br>", unsafe_allow_html=True)

if st.session_state.modo_noturno:
    texto_modo = "☀️ Alternar Modo Claro"
else:
    texto_modo = "🌙 Alternar Modo Noturno"

if st.sidebar.button(texto_modo, use_container_width=True):
    st.session_state.modo_noturno = not st.session_state.modo_noturno
    st.rerun()

st.sidebar.markdown("<br>", unsafe_allow_html=True)

if st.session_state.perfil == "admin":
    paginas = [
        "📊 Dashboard Executivo",
        "📝 Lançar Produtividade",
        "👥 Gerenciar Colaboradores",
        "🗑️ Excluir Colaborador",
        "🔑 Configurar Acessos",
        "📋 Histórico Geral",
        "🗑️ Excluir Histórico",
        "📥 Importar Dados",
        "📥 Backup & Exportação",
        "🔐 Segurança / Senha"
    ]
else:
    paginas = [
        "📝 Lançar Produtividade",
        "📋 Histórico Geral"
    ]

pagina = st.sidebar.radio("NAVEGAÇÃO PRINCIPAL", paginas)

st.sidebar.markdown("<br><br>", unsafe_allow_html=True)

if st.sidebar.button("🚪 ENCERRAR SESSÃO", use_container_width=True):
    st.session_state.autenticado = False
    st.session_state.perfil = None
    st.session_state.usuario_logado = None
    st.rerun()


# =========================================================
# RESTANTE DO CÓDIGO (DASHBOARD, FORMULÁRIOS E GESTÃO)
# =========================================================
# (O restante das páginas continua idêntico ao seu app original)
