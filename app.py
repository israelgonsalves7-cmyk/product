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
    page_title="Gestão Unificada | Fleury & Work OS",
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

    # Tabela unificada integrando métricas Fleury + Gestão de Projetos estilo Monday
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
        st.markdown("<h1 style='text-align: center; color: #006699;'>🧬 Work OS Fleury</h1>", unsafe_allow_html=True)
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

st.sidebar.markdown("## 🧬 WORK OS FLEURY")
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


# =========================================================
# DASHBOARD EXECUTIVO
# =========================================================

if menu == "📊 Dashboard Executivo":
    st.title("📊 Dashboard Executivo — Visão Consolidada")
    st.caption("Indicadores integrados de projetos e métricas de desempenho")

    df = buscar_dados()
    if df.empty:
        st.info("Nenhum dado cadastrado no sistema unificado.")
        st.stop()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("❌ sysvet_erro", f"{df['sysvet_erro'].sum():,}")
    c2.metric("✅ sysvet_exito", f"{df['sysvet_exito'].sum():,}")
    c3.metric("📁 faturado", f"{df['faturado'].sum():,}")
    c4.metric("🔍 auditoria", f"{df['auditoria'].sum():,}")
    c5.metric("🎯 Taxa Média Êxito", f"{df['taxa_exito'].mean():.1f}%")

    st.markdown("---")
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.subheader("📈 Produtividade por Projeto")
        df_proj = df.groupby("projeto")[["sysvet_exito", "faturado", "auditoria"]].sum().reset_index()
        df_proj_melt = df_proj.melt(id_vars=["projeto"], value_vars=["sysvet_exito", "faturado", "auditoria"])
        fig1 = px.bar(df_proj_melt, x="projeto", y="value", color="variable", barmode="group",
                      template="plotly_dark" if st.session_state.modo_noturno else "plotly_white",
                      color_discrete_sequence=["#006699", "#00A86B", "#FFB703"])
        st.plotly_chart(fig1, use_container_width=True)

    with col_g2:
        st.subheader("📌 Status das Tarefas (Work OS)")
        df_status = df.groupby("status_tarefa").size().reset_index(name="quantidade")
        fig2 = px.pie(df_status, names="status_tarefa", values="quantidade", hole=0.4,
                      template="plotly_dark" if st.session_state.modo_noturno else "plotly_white",
                      color_discrete_sequence=px.colors.qualitative.Prism)
        st.plotly_chart(fig2, use_container_width=True)


# =========================================================
# QUADRO DE PROJETOS (ESTILO MONDAY BOARD)
# =========================================================

elif menu == "📋 Quadro de Projetos (Board)":
    st.title("📋 Quadro Geral de Projetos e Tarefas")
    st.caption("Visão em formato de tabela interativa (Estilo Monday.com Board)")

    df = buscar_dados()
    if df.empty:
        st.info("Nenhum registro encontrado no quadro.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)


# =========================================================
# REGISTRAR ATIVIDADE / TAREFA (COM OS CAMPOS FLEURY OBRIGATÓRIOS)
# =========================================================

elif menu == "📝 Registrar Atividade / Tarefa":
    st.title("📝 Lançamento Unificado de Produtividade")
    st.caption("Preencha os dados do projeto, acompanhamento estilo Work OS e as métricas do Grupo Fleury")

    colabs = buscar_colaboradores()
    lista_colabs = colabs["nome"].tolist() if not colabs.empty else ["Colaborador Padrão"]

    with st.form("form_unificado"):
        st.markdown("### ⚙️ Informações do Projeto e Atribuição")
        c1, c2, c3 = st.columns(3)
        with c1:
            data_reg = st.date_input("📅 Data de Lançamento", value=date.today())
        with c2:
            colaborador = st.selectbox("👤 Responsável (Colaborador)", lista_colabs)
        with c3:
            projeto = st.text_input("📁 Nome do Projeto / Demanda", value="Implantação Korus 2026")

        c4, c5, c6 = st.columns(3)
        with c4:
            status_tarefa = st.selectbox("📌 Status da Tarefa", ["Não Iniciado", "Em Andamento", "Revisão", "Concluído", "Bloqueado"])
        with c5:
            prioridade = st.selectbox("⚡ Prioridade", ["Baixa", "Média", "Alta", "Urgente"])
        with c6:
            horas_estimadas = st.number_input("⏱️ Horas Estimadas", min_value=0.0, value=8.0, step=0.5)

        st.markdown("---")
        st.markdown("### 🔬 Métricas Oficiais do Sistema Fleury")
        
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        with col_f1:
            sysvet_erro = st.number_input("❌ sysvet_erro", min_value=0, value=0, step=1)
        with col_f2:
            sysvet_exito = st.number_input("✅ sysvet_exito", min_value=0, value=0, step=1)
        with col_f3:
            faturado = st.number_input("📁 faturado", min_value=0, value=0, step=1)
        with col_f4:
            auditoria = st.number_input("🔍 auditoria", min_value=0, value=0, step=1)

        observacao = st.text_area("💬 observacao / Detalhes da Execução", placeholder="Descreva os entregáveis, impedimentos ou observações importantes...")

        total_computado = sysvet_erro + sysvet_exito + faturado + auditoria
        st.markdown(f"**Total Computado (sysvet_erro + sysvet_exito + faturado + auditoria):** `{total_computado}`")

        salvar = st.form_submit_button("💾 SALVAR DADOS NO SISTEMA UNIFICADO", use_container_width=True)

        if salvar:
            conn = conectar()
            conn.execute("""
                INSERT INTO produtividade_unificada (
                    data, colaborador, projeto, status_tarefa, prioridade, 
                    sysvet_erro, sysvet_exito, faturado, auditoria, horas_estimadas, observacao
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(data_reg), colaborador, projeto.strip(), status_tarefa, prioridade,
                int(sysvet_erro), int(sysvet_exito), int(faturado), int(auditoria),
                float(horas_estimadas), observacao.strip()
            ))
            conn.commit()
            conn.close()
            st.success("✅ Atividade e métricas registradas com sucesso no sistema unificado!")
            st.rerun()


# =========================================================
# GERENCIAR COLABORADORES
# =========================================================

elif menu == "👥 Gerenciar Colaboradores":
    st.title("👥 Gestão de Colaboradores")

    with st.form("form_colab"):
        nome_novo = st.text_input("Nome Completo")
        if st.form_submit_button("Cadastrar Colaborador", use_container_width=True):
            if nome_novo.strip():
                try:
                    conn = conectar()
                    conn.execute("INSERT INTO colaboradores (nome) VALUES (?)", (nome_novo.strip(),))
                    conn.commit()
                    conn.close()
                    st.success("Colaborador cadastrado!")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Colaborador já cadastrado.")

    df_c = buscar_colaboradores()
    if not df_c.empty:
        st.dataframe(df_c, use_container_width=True, hide_index=True)


# =========================================================
# EXPORTAR DADOS
# =========================================================

elif menu == "📥 Exportar Dados":
    st.title("📥 Exportação de Dados do Sistema")
    df = buscar_dados()
    if not df.empty:
        json_str = df.to_json(orient="records", force_ascii=False, indent=4)
        st.download_button("Baixar Backup em JSON", data=json_str, file_name="backup_sistema_unificado.json", mime="application/json")
