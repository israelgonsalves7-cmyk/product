import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import date
from io import BytesIO
import json
import requests
import urllib.parse

# =========================================================
# CONFIGURAÇÃO DA PÁGINA (ESTILO GRUPO FLEURY)
# =========================================================

st.set_page_config(
    page_title="Product | Workspace Médico e Operacional",
    page_icon="🧬",
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
# FUNÇÕES DE APOIO E DADOS
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


# =========================================================
# DESIGN SYSTEM GRUPO FLEURY (UI / UX CORPORATIVO E SAÚDE)
# =========================================================

if "modo_noturno" not in st.session_state:
    st.session_state.modo_noturno = False  # Padrão limpo/claro hospitalar

if not st.session_state.modo_noturno:
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] { 
        font-family: 'Open Sans', sans-serif; 
    }
    .stApp { 
        background-color: #F4F7F9; 
        color: #002B49; 
    }
    /* Estilização personalizada de Inputs e Botões inspirada no Fleury */
    div.stButton > button {
        background-color: #006699;
        color: white;
        border-radius: 6px;
        font-weight: 600;
        border: none;
        padding: 0.5rem 1rem;
        transition: all 0.3s ease;
    }
    div.stButton > button:hover {
        background-color: #004D73;
        color: #ffffff;
    }
    /* Sidebar com tom Azul Petróleo Corporativo */
    [data-testid="stSidebar"] {
        background-color: #002B49;
        color: #FFFFFF;
    }
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
        background-color: #0088CC;
        color: white;
        border-radius: 6px;
        font-weight: 600;
        border: none;
    }
    </style>
    """, unsafe_allow_html=True)


# =========================================================
# CONTROLE DE SESSÃO / TELA DE LOGIN FLEURY
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
        st.markdown("<h1 style='text-align: center; color: #006699; font-size: 2.2rem;'>🧬 GRUPO FLEURY</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; font-size: 1rem; color: #555555;'>Sistema Integrado de Gestão Diagnóstica e Produtividade</p>", unsafe_allow_html=True)
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
# MENU LATERAL (PADRÃO CORPORATIVO SAÚDE)
# =========================================================

st.sidebar.markdown("## 🧬 GRUPO FLEURY")
st.sidebar.markdown(f"""
<div style="background: rgba(255,255,255,0.08); padding: 12px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.15); margin-bottom: 15px;">
    <p style="margin:0; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em; color: #A0C4DF;">Sessão Ativa</p>
    <p style="margin:4px 0 0 0; font-weight: 700; font-size: 0.9rem; color: #FFFFFF;">👤 {st.session_state.usuario_logado}</p>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("### 🌐 Unidades e Atendimento")

lista_unidades = ["PROVET-APOIO", "PROVET-MATRIZ", "PROVET-FILIAL"]
unidade_selecionada = st.sidebar.selectbox("🏥 Unidade Operacional", lista_unidades)

df_cols_sidebar = buscar_colaboradores()
lista_nomes_sidebar = df_cols_sidebar["nome"].tolist() if not df_cols_sidebar.empty else []

if lista_nomes_sidebar:
    usuario_atendimento = st.sidebar.selectbox("👨‍⚕️ Colaborador / Atendente", lista_nomes_sidebar)
else:
    usuario_atendimento = st.sidebar.text_input("👨‍⚕️ Colaborador / Atendente", value="Atendente Padrão")

paciente_pesquisa = st.sidebar.text_input("🐾 Pesquisar Paciente / Exame", placeholder="Ex: Mel, Thor...")

meses_dict = {
    "Janeiro": "01", "Fevereiro": "02", "Março": "03", "Abril": "04",
    "Maio": "05", "Junho": "06", "Julho": "07", "Agosto": "08",
    "Setembro": "09", "Outubro": "10", "Novembro": "11", "Dezembro": "12"
}

col_m1, col_m2 = st.sidebar.columns(2)
with col_m1:
    mes_escolhido_nome = st.selectbox("📅 Mês", list(meses_dict.keys()), index=date.today().month - 1)
    mes_num = meses_dict[mes_escolhido_nome]
with col_m2:
    ano_escolhido = st.number_input("📅 Ano", min_value=2020, max_value=2035, value=date.today().year, step=1)

url_base_externa = f"https://provet-korus.pixeonkorus.com/RotinaDiaria/Situacao.aspx?ad=provet&unidade={urllib.parse.quote(unidade_selecionada)}"
if usuario_atendimento:
    url_base_externa += f"&usuario={urllib.parse.quote(usuario_atendimento)}"
if paciente_pesquisa:
    url_base_externa += f"&paciente={urllib.parse.quote(paciente_pesquisa)}"

st.sidebar.link_button(f"🔗 Portal Korus ({unidade_selecionada})", url_base_externa, use_container_width=True)

if st.sidebar.button("📥 Consultar Dados Externos", use_container_width=True):
    if not paciente_pesquisa.strip():
        st.sidebar.warning("⚠️ Informe o nome do paciente para realizar a busca.")
    else:
        with st.spinner(f"Buscando informações para '{paciente_pesquisa}'..."):
            dados_paciente = puxar_dados_paciente_externo(unidade_selecionada, usuario_atendimento, paciente_pesquisa, mes_num, ano_escolhido)
            if dados_paciente:
                st.sidebar.success("✅ Dados carregados com sucesso!")
            else:
                st.sidebar.warning("⚠️ Nenhum registro encontrado.")

st.sidebar.markdown("<br>", unsafe_allow_html=True)

texto_modo = "☀️ Alternar Modo Claro" if st.session_state.modo_noturno else "🌙 Alternar Modo Noturno"
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
# DASHBOARD EXECUTIVO
# =========================================================

if pagina == "📊 Dashboard Executivo" and st.session_state.perfil == "admin":
    st.title("📊 Dashboard Executivo — Central de Indicadores")
    st.caption("Painel analítico corporativo de desempenho assistencial e operacional")

    df = buscar_produtividade()
    if df.empty:
        st.info("Ainda não existem registros de produtividade para renderizar o painel.")
        st.stop()

    st.markdown("### 🎛️ Filtros Globais")
    col_f1, col_f2, col_f3 = st.columns([2, 2, 1])
    lista_colaboradores = sorted(df["colaborador"].unique().tolist())

    with col_f1:
        colaborador_filtro = st.selectbox("👤 Filtrar por Colaborador", ["Todos os colaboradores"] + lista_colaboradores)

    data_min = df["data"].min().date()
    data_max = df["data"].max().date()

    with col_f2:
        periodo = st.date_input("📅 Janela Temporal", value=(data_min, data_max), min_value=data_min, max_value=data_max)

    with col_f3:
        st.write("")
        st.write("")
        if st.button("🔄 Atualizar Dados", use_container_width=True):
            st.rerun()

    if isinstance(periodo, tuple) and len(periodo) == 2:
        inicio, fim = periodo
        df_filtrado = df[(df["data"].dt.date >= inicio) & (df["data"].dt.date <= fim)].copy()
    else:
        df_filtrado = df.copy()

    if colaborador_filtro != "Todos os colaboradores":
        df_filtrado = df_filtrado[df_filtrado["colaborador"] == colaborador_filtro].copy()

    if df_filtrado.empty:
        st.warning("⚠️ Não há dados consolidados para os parâmetros selecionados.")
        st.stop()

    erro = int(df_filtrado["sysvet_erro"].sum())
    exito = int(df_filtrado["sysvet_exito"].sum())
    faturado = int(df_filtrado["faturado"].sum())
    auditoria = int(df_filtrado["auditoria"].sum())
    total_sysvet = erro + exito
    produtividade = erro + exito + faturado + auditoria
    taxa_media = (exito / total_sysvet * 100) if total_sysvet > 0 else 0

    st.markdown("---")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("❌ Erro Sistema", f"{erro:,}")
    c2.metric("✅ Êxito Sistema", f"{exito:,}")
    c3.metric("📁 Faturado", f"{faturado:,}")
    c4.metric("🔍 Auditoria", f"{auditoria:,}")
    c5.metric("📊 Volume Total", f"{produtividade:,}")
    c6.metric("🎯 Taxa de Êxito", f"{taxa_media:.1f}%")
    st.markdown("---")

    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.subheader("📈 Evolução Temporal das Entregas")
        df_tempo = df_filtrado.groupby(df_filtrado["data"].dt.date)[["sysvet_exito", "faturado", "auditoria"]].sum().reset_index()
        df_tempo_melted = df_tempo.melt(id_vars=["data"], value_vars=["sysvet_exito", "faturado", "auditoria"], var_name="Métrica", value_name="Quantidade")
        
        fig_linha = px.line(
            df_tempo_melted, x="data", y="Quantidade", color="Métrica", markers=True,
            template="plotly_dark" if st.session_state.modo_noturno else "plotly_white",
            color_discrete_sequence=["#006699", "#00A86B", "#FFB703"]
        )
        st.plotly_chart(fig_linha, use_container_width=True)

    with col_g2:
        st.subheader("👥 Produtividade por Colaborador")
        df_colab = df_filtrado.groupby("colaborador")[["sysvet_exito", "faturado", "auditoria", "sysvet_erro"]].sum().reset_index()
        df_colab_melted = df_colab.melt(id_vars=["colaborador"], value_vars=["sysvet_exito", "faturado", "auditoria", "sysvet_erro"], var_name="Categoria", value_name="Total")
        
        fig_barra = px.bar(
            df_colab_melted, x="colaborador", y="Total", color="Categoria", barmode="stack",
            template="plotly_dark" if st.session_state.modo_noturno else "plotly_white",
            color_discrete_sequence=["#006699", "#00A86B", "#FFB703", "#D90429"]
        )
        st.plotly_chart(fig_barra, use_container_width=True)


# =========================================================
# LANÇAR PRODUTIVIDADE
# =========================================================

elif pagina == "📝 Lançar Produtividade":
    st.title("📝 Lançamento de Produtividade Diária")
    st.caption("Insira os indicadores quantitativos correspondentes às suas entregas")

    colaboradores = buscar_colaboradores()

    if colaboradores.empty:
        st.warning("⚠️ Cadastre colaboradores antes de realizar lançamentos.")
    else:
        with st.form("form_produtividade"):
            data_lancamento = st.date_input("📅 Data de Referência", value=date.today())

            if st.session_state.perfil == "admin":
                colaborador = st.selectbox("👤 Colaborador Responsável", colaboradores["nome"].tolist())
            else:
                colaborador = st.session_state.usuario_logado
                st.info(f"👤 Registrando atividade em nome de: **{colaborador}**")

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                erro = st.number_input("❌ Erro de Sistema", min_value=0, value=0, step=1)
            with col2:
                exito = st.number_input("✅ Êxito de Sistema", min_value=0, value=0, step=1)
            with col3:
                faturado = st.number_input("📁 Faturado", min_value=0, value=0, step=1)
            with col4:
                auditoria = st.number_input("🔍 Auditoria", min_value=0, value=0, step=1)

            observacao = st.text_area("💬 Observações / Informações Complementares", placeholder="Detalhes de ocorrências, laudos ou observações relevantes...")

            total = erro + exito + faturado + auditoria
            st.markdown(f"### 📊 Total computado do lançamento: `{total}`")

            salvar = st.form_submit_button("💾 SALVAR REGISTRO OFICIAL", use_container_width=True)

            if salvar:
                conn = conectar()
                conn.execute(
                    """
                    INSERT INTO produtividade (data, colaborador, sysvet_erro, sysvet_exito, faturado, auditoria, observacao)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (str(data_lancamento), colaborador, int(erro), int(exito), int(faturado), int(auditoria), observacao.strip())
                )
                conn.commit()
                conn.close()

                payload_externo = {
                    "data": str(data_lancamento),
                    "colaborador": colaborador,
                    "sysvet_erro": int(erro),
                    "sysvet_exito": int(exito),
                    "faturado": int(faturado),
                    "auditoria": int(auditoria),
                    "total": total,
                    "observacao": observacao.strip()
                }
                
                enviar_dados_para_externo(payload_externo)
                st.success("✅ Atividade registrada e salva no banco de dados com sucesso!")
                st.rerun()


# =========================================================
# COLABORADORES
# =========================================================

elif pagina == "👥 Gerenciar Colaboradores" and st.session_state.perfil == "admin":
    st.title("👥 Gestão de Colaboradores")

    with st.form("form_colaborador"):
        st.subheader("➕ Adicionar Novo Membro")
        nome = st.text_input("Nome Completo do Colaborador")
        cadastrar = st.form_submit_button("CADASTRAR NOVO MEMBRO", use_container_width=True)

        if cadastrar:
            if not nome.strip():
                st.error("Informe o nome do colaborador.")
            else:
                try:
                    conn = conectar()
                    conn.execute("INSERT INTO colaboradores (nome) VALUES (?)", (nome.strip(),))
                    conn.commit()
                    conn.close()
                    st.success(f"✅ {nome} cadastrado com sucesso!")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("⚠️ Este colaborador já se encontra cadastrado no sistema.")

    colaboradores = buscar_colaboradores()
    if not colaboradores.empty:
        st.dataframe(colaboradores[["id", "nome"]], use_container_width=True, hide_index=True)


# =========================================================
# HISTÓRICO GERAL
# =========================================================

elif pagina == "📋 Histórico Geral":
    st.title("📋 Histórico Geral de Produtividade")
    df_hist = buscar_produtividade()
    if df_hist.empty:
        st.info("Nenhum registro encontrado.")
    else:
        st.dataframe(df_hist, use_container_width=True, hide_index=True)


# =========================================================
# DEMAIS MÓDULOS DE SUPORTE (EXCLUSÕES, ACESSOS, BACKUP)
# =========================================================

elif pagina == "🗑️ Excluir Colaborador" and st.session_state.perfil == "admin":
    st.title("🗑️ Gerenciamento e Exclusão de Colaboradores")
    colaboradores = buscar_colaboradores()
    if colaboradores.empty:
        st.info("Nenhum colaborador cadastrado.")
    else:
        st.dataframe(colaboradores, use_container_width=True, hide_index=True)
        colab_exc = st.selectbox("Colaborador", colaboradores["nome"].tolist())
        if st.button("Remover Colaborador"):
            conn = conectar()
            conn.execute("DELETE FROM colaboradores WHERE nome = ?", (colab_exc,))
            conn.commit()
            conn.close()
            st.success("Colaborador removido.")
            st.rerun()

elif pagina == "🔑 Configurar Acessos" and st.session_state.perfil == "admin":
    st.title("🔑 Controle de Acessos Individuais")
    colaboradores_disp = buscar_colaboradores()
    if not colaboradores_disp.empty:
        with st.form("form_acesso"):
            colab_nome = st.selectbox("Colaborador", colaboradores_disp["nome"].tolist())
            senha_colab = st.text_input("Definir Senha de Acesso", type="password")
            if st.form_submit_button("💾 SALVAR CREDENCIAIS", use_container_width=True):
                conn = conectar()
                conn.execute("INSERT OR REPLACE INTO acessos_colaboradores (nome, senha) VALUES (?, ?)", (colab_nome, senha_colab))
                conn.commit()
                conn.close()
                st.success("Acesso salvo com sucesso!")

elif pagina == "🗑️ Excluir Histórico" and st.session_state.perfil == "admin":
    st.title("🗑️ Gerenciamento de Histórico")
    df_hist = buscar_produtividade()
    if not df_hist.empty:
        st.dataframe(df_hist, use_container_width=True, hide_index=True)
        id_del = st.number_input("ID para apagar", min_value=1, step=1)
        if st.button("Apagar Registro"):
            conn = conectar()
            conn.execute("DELETE FROM produtividade WHERE id = ?", (int(id_del),))
            conn.commit()
            conn.close()
            st.success("Registro apagado.")
            st.rerun()

elif pagina == "📥 Importar Dados" and st.session_state.perfil == "admin":
    st.title("📥 Importação de Dados")
    st.file_uploader("Selecione o arquivo CSV ou Excel", type=["csv", "xlsx", "xls"])

elif pagina == "📥 Backup & Exportação" and st.session_state.perfil == "admin":
    st.title("📥 Backup & Exportação")
    if st.button("Gerar JSON de Backup"):
        st.download_button("Baixar Backup", data=gerar_backup_json(), file_name="backup_sistema.json", mime="application/json")

elif pagina == "🔐 Segurança / Senha" and st.session_state.perfil == "admin":
    st.title("🔐 Alterar Senha Master")
    nova_s = st.text_input("Nova Senha Master", type="password")
    if st.button("Atualizar Senha"):
        alterar_senha(nova_s)
        st.success("Senha atualizada com sucesso!")
