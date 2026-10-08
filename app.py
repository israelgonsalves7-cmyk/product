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

    # Tabela de colaboradores com suporte a senha pessoal
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS colaboradores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE,
            senha TEXT NOT NULL DEFAULT '1234'
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

    # Inserir um colaborador padrão de forma segura usando OR IGNORE
    cursor.execute("""
        INSERT OR IGNORE INTO colaboradores (nome, senha) 
        VALUES (?, ?)
    """, ("Colaborador Padrão", "1234"))

    conn.commit()
    conn.close()


criar_banco()


# =========================================================
# FUNÇÕES DE APOIO
# =========================================================

def buscar_senha_admin():
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


def buscar_dados(colaborador_filtro=None):
    conn = conectar()
    if colaborador_filtro:
        df = pd.read_sql_query("SELECT * FROM produtividade_unificada WHERE colaborador = ? ORDER BY data DESC, id DESC", conn, params=(colaborador_filtro,))
    else:
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
# AUTENTICAÇÃO E SELEÇÃO DE AMBIENTE INDIVIDUAL
# =========================================================

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.perfil = None
    st.session_state.usuario_nome = None

if not st.session_state.autenticado:
    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.3, 1])
    with c2:
        st.markdown("<h1 style='text-align: center; color: #006699;'>🧬 Work OS Fleury</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #555555;'>Ambiente de Acesso Individual e Gestão Unificada</p><br>", unsafe_allow_html=True)
        
        tipo_acesso = st.radio("Selecione o Tipo de Acesso", ["Colaborador (Painel Pessoal)", "Gestor / Administrador (Visão Geral)"], horizontal=False)
        st.markdown("---")

        if tipo_acesso == "Colaborador (Painel Pessoal)":
            df_colabs = buscar_colaboradores()
            lista_nomes = df_colabs["nome"].tolist() if not df_colabs.empty else []
            
            if not lista_nomes:
                st.warning("Nenhum colaborador cadastrado. Entre como Administrador para cadastrar.")
            else:
                colab_escolhido = st.selectbox("Selecione seu Nome", lista_nomes)
                senha_colab = st.text_input("Senha de Acesso Pessoal", type="password")
                
                if st.button("🚀 ENTRAR NO MEU AMBIENTE", use_container_width=True):
                    reg = df_colabs[df_colabs["nome"] == colab_escolhido].iloc[0]
                    if senha_colab == reg["senha"]:
                        st.session_state.autenticado = True
                        st.session_state.perfil = "colaborador"
                        st.session_state.usuario_nome = colab_escolhido
                        st.rerun()
                    else:
                        st.error("❌ Senha pessoal incorreta.")
        else:
            senha_master = st.text_input("Senha Master de Gestão", type="password")
            if st.button("🔐 ENTRAR COMO GESTOR", use_container_width=True):
                if senha_master == buscar_senha_admin():
                    st.session_state.autenticado = True
                    st.session_state.perfil = "admin"
                    st.session_state.usuario_nome = "Administrador"
                    st.rerun()
                else:
                    st.error("❌ Senha Master incorreta.")
    st.stop()


# =========================================================
# BARRA LATERAL (MENU DINÂMICO CONFORME O PERFIL)
# =========================================================

st.sidebar.markdown(f"## 🧬 WORK OS FLEURY")
st.sidebar.markdown(f"👤 **Logado como:** `{st.session_state.usuario_nome}`")
st.sidebar.markdown(f"🔑 **Perfil:** `{st.session_state.perfil.upper()}`")
st.sidebar.markdown("---")

if st.session_state.perfil == "admin":
    menu = st.sidebar.radio(
        "Navegação Principal",
        ["📊 Dashboard Executivo", "📋 Quadro de Projetos (Board)", "📝 Registrar Atividade / Tarefa", "👥 Gerenciar Colaboradores", "📥 Exportar Dados"]
    )
else:
    menu = st.sidebar.radio(
        "Navegação Pessoal",
        ["📊 Meu Painel Pessoal", "📝 Registrar Minha Atividade", "📋 Meus Registros"]
    )

st.sidebar.markdown("---")
if st.sidebar.button("🌓 Alternar Aparência", use_container_width=True):
    st.session_state.modo_noturno = not st.session_state.modo_noturno
    st.rerun()

if st.sidebar.button("🚪 Sair do Sistema", use_container_width=True):
    st.session_state.autenticado = False
    st.session_state.perfil = None
    st.session_state.usuario_nome = None
    st.rerun()


# =========================================================
# PAINEL DO COLABORADOR (INDIVIDUAL)
# =========================================================

if st.session_state.perfil == "colaborador":
    nome_usuario = st.session_state.usuario_nome

    if menu == "📊 Meu Painel Pessoal":
        st.title(f"📊 Meu Painel de Produtividade — {nome_usuario}")
        st.caption("Seus indicadores individuais de projetos e métricas")

        df = buscar_dados(colaborador_filtro=nome_usuario)
        if df.empty:
            st.info("Você ainda não possui registros de produtividade cadastrados.")
            st.stop()

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("❌ sysvet_erro", f"{df['sysvet_erro'].sum():,}")
        c2.metric("✅ sysvet_exito", f"{df['sysvet_exito'].sum():,}")
        c3.metric("📁 faturado", f"{df['faturado'].sum():,}")
        c4.metric("🔍 auditoria", f"{df['auditoria'].sum():,}")
        c5.metric("🎯 Taxa de Êxito", f"{df['taxa_exito'].mean():.1f}%")

        st.markdown("---")
        col_g1, col_g2 = st.columns(2)

        with col_g1:
            st.subheader("📈 Suas Atividades por Projeto")
            df_proj = df.groupby("projeto")[["sysvet_exito", "faturado", "auditoria"]].sum().reset_index()
            df_proj_melt = df_proj.melt(id_vars=["projeto"], value_vars=["sysvet_exito", "faturado", "auditoria"])
            fig1 = px.bar(df_proj_melt, x="projeto", y="value", color="variable", barmode="group",
                          template="plotly_dark" if st.session_state.modo_noturno else "plotly_white",
                          color_discrete_sequence=["#006699", "#00A86B", "#FFB703"])
            st.plotly_chart(fig1, use_container_width=True)

        with col_g2:
            st.subheader("📌 Status das Suas Tarefas")
            df_status = df.groupby("status_tarefa").size().reset_index(name="quantidade")
            fig2 = px.pie(df_status, names="status_tarefa", values="quantidade", hole=0.4,
                          template="plotly_dark" if st.session_state.modo_noturno else "plotly_white",
                          color_discrete_sequence=px.colors.qualitative.Prism)
            st.plotly_chart(fig2, use_container_width=True)

    elif menu == "📝 Registrar Minha Atividade":
        st.title("📝 Lançamento de Produtividade Pessoal")
        st.caption(f"Lançamento vinculado automaticamente ao seu usuário: **{nome_usuario}**")

        with st.form("form_colab_individual"):
            st.markdown("### ⚙️ Informações do Projeto e Atribuição")
            c1, c2 = st.columns(2)
            with c1:
                data_reg = st.date_input("📅 Data de Lançamento", value=date.today())
            with c2:
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

            salvar = st.form_submit_button("💾 SALVAR MEU REGISTRO", use_container_width=True)

            if salvar:
                conn = conectar()
                conn.execute("""
                    INSERT INTO produtividade_unificada (
                        data, colaborador, projeto, status_tarefa, prioridade, 
                        sysvet_erro, sysvet_exito, faturado, auditoria, horas_estimadas, observacao
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(data_reg), nome_usuario, projeto.strip(), status_tarefa, prioridade,
                    int(sysvet_erro), int(sysvet_exito), int(faturado), int(auditoria),
                    float(horas_estimadas), observacao.strip()
                ))
                conn.commit()
                conn.close()
                st.success("✅ Atividade e métricas registradas com sucesso em seu ambiente!")
                st.rerun()

    elif menu == "📋 Meus Registros":
        st.title("📋 Histórico dos Meus Registros")
        df = buscar_dados(colaborador_filtro=nome_usuario)
        if df.empty:
            st.info("Nenhum registro encontrado em seu ambiente.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)


# =========================================================
# PAINEL DO ADMINISTRADOR / GESTOR
# =========================================================

elif st.session_state.perfil == "admin":

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
            st.subheader("📈 Produtividade por Colaborador")
            df_colab_prod = df.groupby("colaborador")[["sysvet_exito", "faturado", "auditoria"]].sum().reset_index()
            df_colab_melt = df_colab_prod.melt(id_vars=["colaborador"], value_vars=["sysvet_exito", "faturado", "auditoria"])
            fig1 = px.bar(df_colab_melt, x="colaborador", y="value", color="variable", barmode="group",
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

    elif menu == "📋 Quadro de Projetos (Board)":
        st.title("📋 Quadro Geral de Projetos e Tarefas")
        st.caption("Visão em formato de tabela interativa (Estilo Monday.com Board)")

        df = buscar_dados()
        if df.empty:
            st.info("Nenhum registro encontrado no quadro.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)

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

    elif menu == "👥 Gerenciar Colaboradores":
        st.title("👥 Gestão de Colaboradores e Credenciais")

        with st.form("form_colab"):
            st.subheader("Cadastrar Novo Colaborador")
            nome_novo = st.text_input("Nome Completo")
            senha_nova = st.text_input("Senha de Acesso Pessoal", type="password", value="1234")
            if st.form_submit_button("Cadastrar Colaborador", use_container_width=True):
                if nome_novo.strip():
                    try:
                        conn = conectar()
                        conn.execute("INSERT INTO colaboradores (nome, senha) VALUES (?, ?)", (nome_novo.strip(), senha_nova.strip()))
                        conn.commit()
                        conn.close()
                        st.success(f"Colaborador {nome_novo.strip()} cadastrado com sucesso!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Colaborador já cadastrado.")

        st.markdown("---")
        st.subheader("Colaboradores Cadastrados")
        df_c = buscar_colaboradores()
        if not df_c.empty:
            st.dataframe(df_c, use_container_width=True, hide_index=True)

    elif menu == "📥 Exportar Dados":
        st.title("📥 Exportação de Dados do Sistema")
        df = buscar_dados()
        if not df.empty:
            json_str = df.to_json(orient="records", force_ascii=False, indent=4)
            st.download_button("Baixar Backup em JSON", data=json_str, file_name="backup_sistema_unificado.json", mime="application/json")
