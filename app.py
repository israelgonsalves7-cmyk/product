import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import date
from io import BytesIO
import json
import requests  # Necessário para enviar/puxar dados de outros sites/APIs
import urllib.parse  # Para tratar URLs com parâmetros de busca

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
    return sqlite3.connect(DB, check_same_thread=False)


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

    # Migrações automáticas estruturadas
    cursor.execute("PRAGMA table_info(produtividade)")
    colunas_prod = [col[1] for col in cursor.fetchall()]

    if "auditoria" not in colunas_prod:
        cursor.execute("ALTER TABLE produtividade ADD COLUMN auditoria INTEGER DEFAULT 0")
    if "observacao" not in colunas_prod:
        cursor.execute("ALTER TABLE produtividade ADD COLUMN observacao TEXT")

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
# FUNÇÕES DE APOIO E DADOS (COM CACHE AUTOMATIZADO)
# =========================================================

def buscar_senha():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT senha FROM configuracoes WHERE id = 1")
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] if resultado else "2010"


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
        df["auditoria"] = pd.to_numeric(df["auditoria"], errors="coerce").fillna(0).astype(int)
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
    cols_c = [desc[0] for desc in cursor.description]
    colaboradores = [dict(zip(cols_c, row)) for row in cursor.fetchall()]

    cursor.execute("SELECT * FROM produtividade")
    cols_p = [desc[0] for desc in cursor.description]
    produtividade = [dict(zip(cols_p, row)) for row in cursor.fetchall()]

    cursor.execute("SELECT * FROM acessos_colaboradores")
    cols_a = [desc[0] for desc in cursor.description]
    acessos = [dict(zip(cols_a, row)) for row in cursor.fetchall()]

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
# DESIGN SYSTEM EXCLUSIVO (UI / UX)
# =========================================================

if "modo_noturno" not in st.session_state:
    st.session_state.modo_noturno = True

modo_tema = "dark" if st.session_state.modo_noturno else "light"
bg_app = "#030712" if modo_tema == "dark" else "#f8fafc"
txt_app = "#f8fafc" if modo_tema == "dark" else "#0f172a"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');
html, body, [class*="css"] {{ font-family: 'Plus Jakarta Sans', sans-serif; }}
.stApp {{ background-color: {bg_app}; color: {txt_app}; }}
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
# MENU LATERAL REFINADO
# =========================================================

st.sidebar.markdown("## ⚡ PRODUCT")
st.sidebar.markdown(f"""
<div style="background: rgba(255,255,255,0.04); padding: 12px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.08); margin-bottom: 15px;">
    <p style="margin:0; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em;">Sessão Ativa</p>
    <p style="margin:4px 0 0 0; font-weight: 700; font-size: 0.95rem;">👤 {st.session_state.usuario_logado}</p>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("### 🌐 Consulta Externa / Pacientes")
lista_unidades = ["PROVET-APOIO", "PROVET-MATRIZ", "PROVET-FILIAL"]
unidade_selecionada = st.sidebar.selectbox("🏥 Unidade", lista_unidades)

df_cols_sidebar = buscar_colaboradores()
lista_nomes_sidebar = df_cols_sidebar["nome"].tolist() if not df_cols_sidebar.empty else []

if lista_nomes_sidebar:
    usuario_atendimento = st.sidebar.selectbox("👨‍⚕️ Usuário de Atendimento", lista_nomes_sidebar)
else:
    usuario_atendimento = st.sidebar.text_input("👨‍⚕️ Usuário de Atendimento", value="Atendente Padrão")

paciente_pesquisa = st.sidebar.text_input("🐾 Pesquisar Nome do Paciente", placeholder="Ex: Mel, Thor...")

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

st.sidebar.link_button(f"🔗 Abrir Sistema ({unidade_selecionada})", url_base_externa, use_container_width=True)

if st.sidebar.button("📥 Puxar Dados do Paciente", use_container_width=True):
    if not paciente_pesquisa.strip():
        st.sidebar.warning("⚠️ Informe o nome do paciente para realizar a busca.")
    else:
        with st.spinner(f"Buscando informações para '{paciente_pesquisa}' em {unidade_selecionada}..."):
            dados_paciente = puxar_dados_paciente_externo(unidade_selecionada, usuario_atendimento, paciente_pesquisa, mes_num, ano_escolhido)
            if dados_paciente:
                st.sidebar.success(f"✅ Dados do paciente '{paciente_pesquisa}' carregados com sucesso!")
            else:
                st.sidebar.warning("⚠️ Nenhum registro encontrado para este paciente na unidade selecionada.")

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
    st.title("📊 Dashboard Executivo — Business Intelligence")
    st.caption("Painel analítico integrado com filtros globais e visualizações consolidadas")

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
        periodo = st.date_input("📅 Janela Temporal (Filtro de Data)", value=(data_min, data_max), min_value=data_min, max_value=data_max)

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
    c1.metric("❌ Erro SYSVET", f"{erro:,}")
    c2.metric("✅ Êxito SYSVET", f"{exito:,}")
    c3.metric("📁 Faturado", f"{faturado:,}")
    c4.metric("🔍 Auditoria", f"{auditoria:,}")
    c5.metric("📊 Volume Total", f"{produtividade:,}")
    c6.metric("🎯 Taxa Êxito", f"{taxa_media:.1f}%")
    st.markdown("---")

    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.subheader("📈 Evolução Temporal da Produtividade")
        df_tempo = df_filtrado.groupby(df_filtrado["data"].dt.date)[["sysvet_exito", "faturado", "auditoria"]].sum().reset_index()
        df_tempo_melted = df_tempo.melt(id_vars=["data"], value_vars=["sysvet_exito", "faturado", "auditoria"], var_name="Métrica", value_name="Quantidade")
        
        fig_linha = px.line(
            df_tempo_melted, 
            x="data", 
            y="Quantidade", 
            color="Métrica", 
            markers=True,
            template="plotly_dark" if st.session_state.modo_noturno else "plotly_white"
        )
        fig_linha.update_layout(xaxis_title="Data", yaxis_title="Volume", legend_title="Indicadores")
        st.plotly_chart(fig_linha, use_container_width=True)

    with col_g2:
        st.subheader("👥 Produtividade por Colaborador")
        df_colab = df_filtrado.groupby("colaborador")[["sysvet_exito", "faturado", "auditoria", "sysvet_erro"]].sum().reset_index()
        df_colab_melted = df_colab.melt(id_vars=["colaborador"], value_vars=["sysvet_exito", "faturado", "auditoria", "sysvet_erro"], var_name="Categoria", value_name="Total")
        
        fig_barra = px.bar(
            df_colab_melted, 
            x="colaborador", 
            y="Total", 
            color="Categoria", 
            barmode="stack",
            template="plotly_dark" if st.session_state.modo_noturno else "plotly_white"
        )
        fig_barra.update_layout(xaxis_title="Colaborador", yaxis_title="Total Acumulado", legend_title="Métricas")
        st.plotly_chart(fig_barra, use_container_width=True)

    col_g3, col_g4 = st.columns(2)

    with col_g3:
        st.subheader("🍩 Distribuição dos Tipos de Atividades")
        df_pizza = pd.DataFrame({
            "Categoria": ["Sysvet Êxito", "Sysvet Erro", "Faturado", "Auditoria"],
            "Total": [exito, erro, faturado, auditoria]
        })
        fig_pizza = px.pie(
            df_pizza, 
            names="Categoria", 
            values="Total", 
            hole=0.4,
            template="plotly_dark" if st.session_state.modo_noturno else "plotly_white"
        )
        st.plotly_chart(fig_pizza, use_container_width=True)

    with col_g4:
        st.subheader("📊 Taxa de Êxito Individual por Colaborador")
        df_taxa = df_filtrado.groupby("colaborador").agg({
            "sysvet_exito": "sum",
            "total_sysvet": "sum"
        }).reset_index()
        df_taxa["Taxa (%)"] = df_taxa.apply(lambda x: (x["sysvet_exito"] / x["total_sysvet"] * 100) if x["total_sysvet"] > 0 else 0, axis=1)

        fig_taxa = px.bar(
            df_taxa,
            x="colaborador",
            y="Taxa (%)",
            text="Taxa (%)",
            template="plotly_dark" if st.session_state.modo_noturno else "plotly_white"
        )
        fig_taxa.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        fig_taxa.update_layout(xaxis_title="Colaborador", yaxis_title="Taxa de Êxito (%)")
        st.plotly_chart(fig_taxa, use_container_width=True)


# =========================================================
# LANÇAR PRODUTIVIDADE
# =========================================================

elif pagina == "📝 Lançar Produtividade":
    st.title("📝 Lançar Produtividade")
    st.caption("Preencha os indicadores correspondentes às entregas diárias")

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
                erro = st.number_input("❌ SYSVET Erro", min_value=0, value=0, step=1)
            with col2:
                exito = st.number_input("✅ SYSVET Êxito", min_value=0, value=0, step=1)
            with col3:
                faturado = st.number_input("📁 Faturado", min_value=0, value=0, step=1)
            with col4:
                auditoria = st.number_input("🔍 Auditoria", min_value=0, value=0, step=1)

            observacao = st.text_area("💬 Observações / Detalhes da Produtividade (Opcional)", placeholder="Descreva algo sobre a produtividade, ocorrências ou detalhes relevantes...")

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
# EXCLUIR COLABORADOR
# =========================================================

elif pagina == "🗑️ Excluir Colaborador" and st.session_state.perfil == "admin":
    st.title("🗑️ Gerenciamento e Exclusão de Colaboradores")
    st.caption("Selecione um colaborador para removê-lo definitivamente do cadastro do sistema.")

    colaboradores = buscar_colaboradores()

    if colaboradores.empty:
        st.info("Nenhum colaborador cadastrado no momento.")
    else:
        st.dataframe(colaboradores[["id", "nome"]], use_container_width=True, hide_index=True)
        st.markdown("---")

        with st.form("form_excluir_colaborador"):
            st.subheader("❌ Remover Colaborador")
            colab_para_excluir = st.selectbox("Selecione o colaborador a ser excluído", colaboradores["nome"].tolist())
            
            confirmar_exclusao = st.checkbox("Estou ciente de que a remoção excluirá o cadastro do colaborador")
            deletar_colab = st.form_submit_button("🗑 EXCLUIR COLABORADOR SELECIONADO", use_container_width=True)

            if deletar_colab:
                if confirmar_exclusao:
                    conn = conectar()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM colaboradores WHERE nome = ?", (colab_para_excluir,))
                    cursor.execute("DELETE FROM acessos_colaboradores WHERE nome = ?", (colab_para_excluir,))
                    conn.commit()
                    conn.close()
                    
                    st.success(f"✅ O colaborador '{colab_para_excluir}' foi removido com sucesso!")
                    st.rerun()
                else:
                    st.error("❌ Marque a caixa de confirmação acima para autorizar a exclusão.")


# =========================================================
# GERENCIAR ACESSOS
# =========================================================

elif pagina == "🔑 Configurar Acessos" and st.session_state.perfil == "admin":
    st.title("🔑 Controle de Acessos Individuais")
    colaboradores_disp = buscar_colaboradores()

    if not colaboradores_disp.empty:
        with st.form("form_acesso"):
            colab_nome = st.selectbox("Colaborador", colaboradores_disp["nome"].tolist())
            senha_colab = st.text_input("Definir Senha de Acesso", type="password")
            salvar_acesso = st.form_submit_button("💾 SALVAR CREDENCIAIS", use_container_width=True)

            if salvar_acesso and senha_colab.strip():
                conn = conectar()
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM acessos_colaboradores WHERE nome = ?", (colab_nome,))
                existe = cursor.fetchone()

                if existe:
                    cursor.execute("UPDATE acessos_colaboradores SET senha = ? WHERE nome = ?", (senha_colab.strip(), colab_nome))
                else:
                    cursor.execute("INSERT INTO acessos_colaboradores (nome, senha) VALUES (?, ?)", (colab_nome, senha_colab.strip()))

                conn.commit()
                conn.close()
                st.success(f"✅ Credenciais salvas para {colab_nome}!")
                st.rerun()


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
# EXCLUIR HISTÓRICO
# =========================================================

elif pagina == "🗑️ Excluir Histórico" and st.session_state.perfil == "admin":
    st.title("🗑️ Gerenciamento e Exclusão de Registros")
    st.caption("Consulte a coluna 'id' dos lançamentos abaixo para realizar exclusões pontuais ou limpezas completas.")

    df_hist = buscar_produtividade()

    if df_hist.empty:
        st.info("Nenhum registro de produtividade cadastrado para excluir.")
    else:
        st.dataframe(df_hist, use_container_width=True, hide_index=True)
        st.markdown("---")
        
        col_del1, col_del2 = st.columns(2)

        with col_del1:
            st.subheader("🗑️ Excluir Lançamento Específico")
            id_para_excluir = st.number_input("Informe o ID do registro que deseja apagar", min_value=1, step=1)
            
            if st.button("❌ APAGAR ESTE REGISTRO", use_container_width=True):
                conn = conectar()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM produtividade WHERE id = ?", (int(id_para_excluir),))
                linhas_afetadas = cursor.rowcount
                conn.commit()
                conn.close()

                if linhas_afetadas > 0:
                    st.success(f"✅ Registro com ID {id_para_excluir} excluído com sucesso!")
                    st.rerun()
                else:
                    st.warning(f"⚠️ Nenhum registro encontrado com o ID {id_para_excluir}.")

        with col_del2:
            st.subheader("⚠ Zona de Perigo (Limpeza Total)")
            st.write("Atenção: Esta ação removerá **todos** os lançamentos salvos no banco de dados permanentemente.")
            
            confirmar_limpeza = st.checkbox("Estou ciente e quero limpar todo o histórico")
            
            if st.button("🚨 EXCLUIR TODO O HISTÓRICO", use_container_width=True):
                if confirmar_limpeza:
                    conn = conectar()
                    conn.execute("DELETE FROM produtividade")
                    conn.commit()
                    conn.close()
                    st.success("✅ Todo o histórico de produtividade foi apagado com sucesso!")
                    st.rerun()
                else:
                    st.error("❌ Marque a caixa de confirmação acima para autorizar a limpeza total.")


# =========================================================
# IMPORTAR DADOS (EXCEL / CSV AUTOMATIZADO)
# =========================================================

elif pagina == "📥 Importar Dados" and st.session_state.perfil == "admin":
    st.title("📥 Importação de Planilhas (Excel / CSV)")
    st.caption("Faça upload de arquivos .xlsx, .xls ou .csv contendo os dados de produtividade.")

    arquivo_upload = st.file_uploader("Selecione o arquivo", type=["xlsx", "xls", "csv"])

    if arquivo_upload is not None:
        try:
            nome_arquivo = arquivo_upload.name.lower()
            
            if nome_arquivo.endswith(".csv"):
                df_importado = pd.read_csv(arquivo_upload)
            elif nome_arquivo.endswith(".xlsx"):
                df_importado = pd.read_excel(arquivo_upload, engine="openpyxl")
            elif nome_arquivo.endswith(".xls"):
                df_importado = pd.read_excel(arquivo_upload, engine="xlrd")
            else:
                st.error("❌ Formato de arquivo não suportado.")
                st.stop()

            st.success("✅ Arquivo lido com sucesso! Pré-visualização abaixo:")
            st.dataframe(df_importado.head(), use_container_width=True)

            if st.button("🚀 Confirmar e Importar para o Banco", use_container_width=True):
                conn = conectar()
                importados = 0
                for _, row in df_importado.iterrows():
                    data = str(row.get("data", date.today()))
                    colaborador = str(row.get("colaborador", "Desconhecido"))
                    sysvet_erro = int(row.get("sysvet_erro", 0))
                    sysvet_exito = int(row.get("sysvet_exito", 0))
                    faturado = int(row.get("faturado", 0))
                    auditoria = int(row.get("auditoria", 0))
                    observacao = str(row.get("observacao", ""))

                    conn.execute(
                        """
                        INSERT INTO produtividade (data, colaborador, sysvet_erro, sysvet_exito, faturado, auditoria, observacao)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (data, colaborador, sysvet_erro, sysvet_exito, faturado, auditoria, observacao)
                    )
                    importados += 1
                
                conn.commit()
                conn.close()
                st.success(f"✅ {importados} registros importados com sucesso para o banco de dados!")
        except Exception as e:
            st.error(f"❌ Erro ao processar o arquivo: {e}")


# =========================================================
# BACKUP & EXPORTAÇÃO
# =========================================================

elif pagina == "📥 Backup & Exportação" and st.session_state.perfil == "admin":
    st.title("📥 Backup & Exportação de Dados")
    st.caption("Baixe uma cópia de segurança em formato JSON ou exporte a tabela de produtividade para Excel/CSV.")

    json_str = gerar_backup_json()
    st.download_button(
        label="📥 Baixar Backup Completo (JSON)",
        data=json_str,
        file_name=f"backup_produtividade_{date.today()}.json",
        mime="application/json",
        use_container_width=True
    )

    st.markdown("---")
    df_export = buscar_produtividade()
    if not df_export.empty:
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_export.to_excel(writer, index=False, sheet_name='Produtividade')
        
        st.download_button(
            label="📊 Baixar Histórico em Excel (.xlsx)",
            data=buffer.getvalue(),
            file_name=f"historico_produtividade_{date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )


# =========================================================
# SEGURANÇA / SENHA
# =========================================================

elif pagina == "🔐 Segurança / Senha" and st.session_state.perfil == "admin":
    st.title("🔐 Configurações de Segurança")
    
    with st.form("form_senha"):
        st.subheader("🔑 Alterar Senha Master do Administrador")
        senha_atual = st.text_input("Senha Master Atual", type="password")
        nova_senha = st.text_input("Nova Senha Master", type="password")
        confirma_senha = st.text_input("Confirme a Nova Senha Master", type="password")
        
        atualizar = st.form_submit_button("ALTERAR SENHA MASTER", use_container_width=True)

        if atualizar:
            if senha_atual != buscar_senha():
                st.error("❌ A senha master atual está incorreta.")
            elif not nova_senha.strip():
                st.error("❌ A nova senha não pode estar em branco.")
            elif nova_senha != confirma_senha:
                st.error("❌ As novas senhas não coincidem.")
            else:
                alterar_senha(nova_senha.strip())
                st.success("✅ Senha master alterada com sucesso!")
