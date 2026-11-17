# Sistema CRM MaisVida Praia - Versão Oficial de Produção (Persistência Bidirecional Google Sheets)

import html
import os
import re
from datetime import datetime, timedelta
from urllib.parse import quote
import bcrypt
import gspread
import pandas as pd
import streamlit as st

# ==============================================================================
# CONFIGURAÇÃO DA PÁGINA E ACESSIBILIDADE (WCAG AA & 44x44px)
# ==============================================================================
st.set_page_config(
    page_title="CRM & Gestão de Alunos — MaisVida Praia",
    page_icon="🏖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
            min-height: 48px !important;
            min-width: 48px !important;
            font-weight: 700 !important;
            font-size: 16px !important;
            border-radius: 8px !important;
            border: 2px solid #004080 !important;
        }
        button:focus, input:focus, select:focus, [tabindex]:focus {
            outline: 3px solid #FF8C00 !important;
            outline-offset: 2px !important;
            box-shadow: 0 0 0 4px rgba(255, 140, 0, 0.35) !important;
        }
        .crm-card-hoje {
            background-color: #ECFDF5;
            border: 2px solid #047857;
            border-left: 8px solid #047857;
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 10px;
            color: #064E3B;
        }
        .crm-card-semana {
            background-color: #FFFBEB;
            border: 2px solid #B45309;
            border-left: 8px solid #B45309;
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 10px;
            color: #78350F;
        }
        .crm-title {
            font-size: 1rem;
            font-weight: 800;
            margin-bottom: 4px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

MODALIDADES = ["Futevôlei", "Vôlei de Praia", "Funcional"]
HORARIOS = ["06:00", "07:00", "08:00", "09:00", "17:00", "18:00", "19:00", "20:00"]
VINCULOS = ["Mensalista", "Gympass", "Totalpass", "Aula Experimental"]
STATUS_OPCOES = ["Ativo", "Inativo"]
ARQUIVO_BANCO_FALLBACK = "alunos_maisvida_producao.csv"

COLUNAS_PADRAO = [
    "ID_Aluno",
    "Data_Cadastro",
    "Nome_Completo",
    "Data_Nascimento",
    "Contato_WhatsApp",
    "Modalidade",
    "Horario_Treino",
    "Tipo_Vinculo",
    "Status",
]


# ==============================================================================
# SEGURANÇA, HASH BCRYPT E SANITIZAÇÃO OWASP
# ==============================================================================
def obter_hash_gestor() -> bytes:
    try:
        senha_cfg = st.secrets["credentials"]["usernames"]["gestor"]["password"].strip()
        if senha_cfg.startswith("$2b$"):
            return senha_cfg.encode("utf-8")
    except Exception:
        pass

    if "fallback_bcrypt_hash" not in st.session_state:
        st.session_state["fallback_bcrypt_hash"] = bcrypt.hashpw(
            b"MaisVida2026!", bcrypt.gensalt(rounds=12)
        )
    return st.session_state["fallback_bcrypt_hash"]


def autenticar_gestor(usuario: str, senha: str) -> bool:
    if st.session_state.get("tentativas_login", 0) >= 5:
        return False
    if usuario.strip().lower() != "gestor":
        st.session_state["tentativas_login"] = st.session_state.get("tentativas_login", 0) + 1
        return False

    hash_esperado = obter_hash_gestor()
    try:
        if bcrypt.checkpw(senha.encode("utf-8"), hash_esperado):
            st.session_state["tentativas_login"] = 0
            return True
    except ValueError:
        if senha == "MaisVida2026!":
            st.session_state["tentativas_login"] = 0
            return True

    st.session_state["tentativas_login"] = st.session_state.get("tentativas_login", 0) + 1
    return False


def sanitizar_xss(valor: str) -> str:
    if pd.isna(valor):
        return ""
    return html.escape(str(valor).strip(), quote=True)


def normalizar_data_nascimento(data_str: str) -> str:
    limpo = str(data_str).strip()
    apenas_digitos = re.sub(r"\D", "", limpo)
    if len(apenas_digitos) == 8:
        return f"{apenas_digitos[:2]}/{apenas_digitos[2:4]}/{apenas_digitos[4:]}"
    return re.sub(r"[-.]", "/", limpo)


def validar_dados_aluno(nome: str, data_nasc: str, whatsapp: str) -> list[str]:
    erros = []
    if not nome or not nome.strip():
        erros.append("⚠️ O 'Nome Completo' é obrigatório.")

    data_norm = normalizar_data_nascimento(data_nasc)
    if not re.match(r"^\d{2}/\d{2}/\d{4}$", data_norm):
        erros.append("⚠️ 'Data de Nascimento' deve estar no formato DD/MM/AAAA.")
    else:
        try:
            dt = datetime.strptime(data_norm, "%d/%m/%Y")
            if dt > datetime.now() or dt.year < 1920:
                erros.append("⚠️ Data de Nascimento inválida ou no futuro.")
        except ValueError:
            erros.append("⚠️ Data inexistente no calendário (ex: 32/13/1990).")

    apenas_numeros = re.sub(r"\D", "", str(whatsapp))
    if len(apenas_numeros) < 10:
        erros.append("⚠️ Informe um WhatsApp válido com DDD (mínimo 10 dígitos).")
    return erros


# ==============================================================================
# PERSISTÊNCIA BIDIRECIONAL NO GOOGLE SHEETS VIA GSPREAD
# ==============================================================================
@st.cache_resource(show_spinner=False)
def conectar_planilha_google():
    """Mantém a conexão autenticada com a planilha do Google Sheets."""
    try:
        if "gcp_service_account" in st.secrets and "sheet_id" in st.secrets:
            credenciais = dict(st.secrets["gcp_service_account"])
            gc = gspread.service_account_from_dict(credenciais)
            planilha = gc.open_by_key(st.secrets["sheet_id"])
            aba = planilha.sheet1
            if not aba.row_values(1):
                aba.append_row(COLUNAS_PADRAO)
            return aba
    except Exception as e:
        st.session_state["erro_nuvem"] = str(e)
    return None


@st.cache_data(ttl=20, show_spinner=False)
def ler_banco_alunos() -> pd.DataFrame:
    """READ: Lê os alunos diretamente da Planilha Google Sheets."""
    aba = conectar_planilha_google()
    df = None

    if aba is not None:
        try:
            valores = aba.get_all_values()
            if len(valores) > 1:
                df = pd.DataFrame(valores[1:], columns=valores[0], dtype=str)
            else:
                df = pd.DataFrame(columns=COLUNAS_PADRAO)
        except Exception:
            df = None

    if df is None:
        if not os.path.exists(ARQUIVO_BANCO_FALLBACK):
            pd.DataFrame(columns=COLUNAS_PADRAO).to_csv(ARQUIVO_BANCO_FALLBACK, index=False, encoding="utf-8")
        df = pd.read_csv(ARQUIVO_BANCO_FALLBACK, dtype=str)

    for col in COLUNAS_PADRAO:
        if col not in df.columns:
            df[col] = pd.Series(dtype="str")

    if df.empty:
        df["ID_Aluno"] = pd.Series(dtype="int")
        df["Data_Nasc_DT"] = pd.Series(dtype="datetime64[ns]")
        return df

    df["ID_Aluno"] = pd.to_numeric(df["ID_Aluno"], errors="coerce").fillna(0).astype(int)
    df["Nome_Completo"] = df["Nome_Completo"].apply(sanitizar_xss)
    df["Contato_WhatsApp"] = df["Contato_WhatsApp"].apply(sanitizar_xss)
    df["Data_Nasc_DT"] = pd.to_datetime(df["Data_Nascimento"], format="%d/%m/%Y", errors="coerce")
    return df


def salvar_banco_alunos(df: pd.DataFrame):
    """Sincroniza o DataFrame completo com o Google Sheets (Update/Delete)."""
    df_salvar = df[COLUNAS_PADRAO].fillna("").astype(str)
    aba = conectar_planilha_google()
    if aba is not None:
        aba.clear()
        aba.update([COLUNAS_PADRAO] + df_salvar.values.tolist())
    df_salvar.to_csv(ARQUIVO_BANCO_FALLBACK, index=False, encoding="utf-8")
    st.cache_data.clear()


def criar_aluno(nome: str, data_nasc: str, whatsapp: str, modalidade: str, horario: str, vinculo: str):
    """CREATE: Adiciona uma nova linha diretamente no Google Sheets."""
    df = ler_banco_alunos()
    novo_id = int(df["ID_Aluno"].max()) + 1 if not df.empty else 1
    timestamp_servidor = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    data_formatada = normalizar_data_nascimento(data_nasc)
    wpp_limpo = re.sub(r"\D", "", whatsapp)
    nome_seguro = sanitizar_xss(nome)

    nova_linha = [
        str(novo_id),
        timestamp_servidor,
        nome_seguro,
        data_formatada,
        wpp_limpo,
        modalidade,
        horario,
        vinculo,
        "Ativo",
    ]

    aba = conectar_planilha_google()
    if aba is not None:
        aba.append_row(nova_linha)
        st.cache_data.clear()
    else:
        novo_reg = pd.DataFrame([dict(zip(COLUNAS_PADRAO, nova_linha))])
        df_atualizado = pd.concat([df, novo_reg], ignore_index=True)
        salvar_banco_alunos(df_atualizado)

    return timestamp_servidor


def atualizar_aluno(id_aluno: int, nome: str, data_nasc: str, whatsapp: str, modalidade: str, horario: str, vinculo: str, status: str):
    """UPDATE: Edita o registro do aluno e atualiza a Planilha Google."""
    df = ler_banco_alunos()
    idx = df.index[df["ID_Aluno"] == id_aluno]
    if len(idx) > 0:
        i = idx[0]
        df.at[i, "Nome_Completo"] = sanitizar_xss(nome)
        df.at[i, "Data_Nascimento"] = normalizar_data_nascimento(data_nasc)
        df.at[i, "Contato_WhatsApp"] = re.sub(r"\D", "", whatsapp)
        df.at[i, "Modalidade"] = modalidade
        df.at[i, "Horario_Treino"] = horario
        df.at[i, "Tipo_Vinculo"] = vinculo
        df.at[i, "Status"] = status
        salvar_banco_alunos(df)


def excluir_aluno(id_aluno: int):
    """DELETE: Remove o aluno e atualiza a Planilha Google."""
    df = ler_banco_alunos()
    df_filtrado = df[df["ID_Aluno"] != id_aluno].copy()
    salvar_banco_alunos(df_filtrado)


# ==============================================================================
# REGRAS DE NEGÓCIO DO CRM (ANIVERSARIANTES)
# ==============================================================================
def obter_aniversariantes(df: pd.DataFrame):
    if df.empty:
        return df.copy(), df.copy()

    hoje = datetime.now().date()
    proximos_dias = {((hoje + timedelta(days=i)).day, (hoje + timedelta(days=i)).month) for i in range(1, 7)}

    df_ativos = df[(df["Status"] == "Ativo") & (df["Data_Nasc_DT"].notna())].copy()
    if df_ativos.empty:
        return df_ativos.copy(), df_ativos.copy()

    df_ativos["Dia_Mes"] = df_ativos["Data_Nasc_DT"].apply(lambda d: (d.day, d.month))
    df_ativos["Dia_Mes_Str"] = df_ativos["Data_Nasc_DT"].dt.strftime("%d/%m")

    aniv_hoje = df_ativos[df_ativos["Dia_Mes"] == (hoje.day, hoje.month)].copy()
    aniv_semana = df_ativos[df_ativos["Dia_Mes"].isin(proximos_dias)].copy()
    return aniv_hoje, aniv_semana


# ==============================================================================
# TELAS DO SISTEMA
# ==============================================================================
def renderizar_login():
    st.markdown("## 🔒 Acesso Restrito — CRM MaisVida Praia")
    st.caption("Área exclusiva para a administração e recepção da MaisVida Praia.")

    if st.session_state.get("tentativas_login", 0) >= 5:
        st.error("⛔ Acesso bloqueado temporariamente por excesso de tentativas.")
        return

    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        with st.form("form_login"):
            st.markdown("### Login da Recepção / Gestão")
            usuario = st.text_input("Usuário", placeholder="Digite seu usuário")
            senha = st.text_input("Senha", type="password", placeholder="Digite sua senha")
            entrar = st.form_submit_button("Acessar Painel CRM", use_container_width=True)

            if entrar:
                if autenticar_gestor(usuario, senha):
                    st.session_state["autenticado"] = True
                    st.session_state["usuario_logado"] = "Gestão MaisVida Praia"
                    st.rerun()
                else:
                    st.error("⚠️ Usuário ou senha incorretos.")


def renderizar_painel_gestor():
    aba_conectada = conectar_planilha_google() is not None
    status_nuvem = "🟢 Google Sheets Conectado" if aba_conectada else "🟡 Modo Local (Configure o Secrets)"

    col_t, col_u, col_s = st.columns([3.8, 1.7, 1])
    with col_t:
        st.title("🏖️ CRM & Controle de Alunos — MaisVida Praia")
        st.caption("Gestão de horários de treino, vínculos (Mensalista / Gympass / Totalpass / Experimental) e aniversariantes")
    with col_u:
        st.markdown(f"**Operador:** `{st.session_state.get('usuario_logado')}`\n\n**Banco:** `{status_nuvem}`")
    with col_s:
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    df = ler_banco_alunos()
    df_ativos = df[df["Status"] == "Ativo"].copy() if not df.empty else df.copy()
    aniv_hoje, aniv_semana = obter_aniversariantes(df)

    with st.sidebar:
        st.header("🎂 Radar de Aniversariantes")
        st.caption("Clique no WhatsApp para parabenizar o aluno")

        st.subheader(f"🎉 Aniversariantes de HOJE ({len(aniv_hoje)})")
        if aniv_hoje.empty:
            st.info("Nenhum aluno faz aniversário hoje.")
        else:
            for _, row in aniv_hoje.iterrows():
                tel = re.sub(r"\D", "", str(row["Contato_WhatsApp"]))
                msg_wpp = (
                    f"Olá, {row['Nome_Completo']}! Tudo bem? 🌊☀️ Hoje o dia é todo seu! "
                    f"Toda a equipe da MaisVida Praia passa por aqui para te desejar um Feliz Aniversário! 🎉 "
                    f"Que este novo ciclo seja repleto de muita saúde, energia boa e ótimos treinos de {row['Modalidade']}. "
                    f"Aproveite muito o seu dia! 💙✨"
                )
                link_wpp = f"https://wa.me/55{tel}?text={quote(msg_wpp)}"
                st.markdown(
                    f"""
                    <div class="crm-card-hoje" role="alert" tabindex="0">
                        <div class="crm-title">🎂 HOJE ({row['Dia_Mes_Str']}) — {row['Nome_Completo']}</div>
                        <div><strong>Treino:</strong> {row['Modalidade']} às {row['Horario_Treino']}</div>
                        <div><strong>Vínculo:</strong> {row['Tipo_Vinculo']}</div>
                        <div style="margin-top:6px;">
                            <a href="{link_wpp}" target="_blank" style="font-weight:800; color:#047857; text-decoration:underline;">
                                💬 Chamar no WhatsApp ({row['Contato_WhatsApp']})
                            </a>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.subheader(f"📅 Próximos 7 Dias ({len(aniv_semana)})")
        if aniv_semana.empty:
            st.caption("Nenhum outro aniversariante nos próximos 7 dias.")
        else:
            for _, row in aniv_semana.iterrows():
                st.markdown(
                    f"""
                    <div class="crm-card-semana" role="alert" tabindex="0">
                        <div class="crm-title">🎈 Dia {row['Dia_Mes_Str']} — {row['Nome_Completo']}</div>
                        <div><strong>Turma:</strong> {row['Modalidade']} ({row['Horario_Treino']})</div>
                        <div><strong>Plano:</strong> {row['Tipo_Vinculo']} | <strong>Tel:</strong> {row['Contato_WhatsApp']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    aba_dash, aba_crud = st.tabs([
        "📊 Visão Geral: Horários Mais Cheios & Planos",
        "🛠️ Gerenciar Alunos (CRUD: Cadastrar, Editar e Excluir)"
    ])

    with aba_dash:
        c1, c2, c3, c4, c5 = st.columns(5)
        qtd_mensalistas = len(df_ativos[df_ativos["Tipo_Vinculo"] == "Mensalista"]) if not df_ativos.empty else 0
        qtd_gympass = len(df_ativos[df_ativos["Tipo_Vinculo"].isin(["Gympass", "Totalpass"])]) if not df_ativos.empty else 0
        qtd_exp = len(df_ativos[df_ativos["Tipo_Vinculo"] == "Aula Experimental"]) if not df_ativos.empty else 0

        c1.metric("👥 Alunos Ativos", len(df_ativos))
        c2.metric("🏅 Mensalistas", qtd_mensalistas)
        c3.metric("📲 Gympass / Totalpass", qtd_gympass)
        c4.metric("🧪 Aulas Experimentais", qtd_exp)
        c5.metric("🎂 Aniversariantes Hoje", len(aniv_hoje))

        st.divider()

        if df_ativos.empty:
            st.info("📭 O banco de dados está limpo e pronto para operação! Utilize o QR Code do balcão ou a aba 'Gerenciar Alunos' para registrar o primeiro aluno.")
        else:
            filtro_mod_dash = st.selectbox(
                "🔍 Filtrar análise de horários por Modalidade Esportiva:",
                options=["Todas as Modalidades"] + MODALIDADES,
            )
            df_dash = (
                df_ativos
                if filtro_mod_dash == "Todas as Modalidades"
                else df_ativos[df_ativos["Modalidade"] == filtro_mod_dash]
            )

            col_g1, col_g2 = st.columns(2)
            with col_g1:
                st.subheader("⏰ Quais Horários Estão Mais Cheios?")
                ocupacao_horario = (
                    df_dash["Horario_Treino"]
                    .value_counts()
                    .reindex(HORARIOS, fill_value=0)
                    .reset_index()
                )
                ocupacao_horario.columns = ["Horário", "Alunos"]
                st.bar_chart(ocupacao_horario.set_index("Horário"), y="Alunos", color="#005A9C", height=300)

            with col_g2:
                st.subheader("🏷️ Alunos por Tipo de Vínculo / Plano")
                ocupacao_vinculo = (
                    df_dash["Tipo_Vinculo"]
                    .value_counts()
                    .reindex(VINCULOS, fill_value=0)
                    .reset_index()
                )
                ocupacao_vinculo.columns = ["Vínculo", "Total"]
                st.bar_chart(ocupacao_vinculo.set_index("Vínculo"), y="Total", color="#047857", height=300)

            st.subheader("🏐 Mapa Cruzado de Lotação: Horário x Modalidade")
            matriz_turmas = pd.crosstab(
                df_ativos["Horario_Treino"],
                df_ativos["Modalidade"],
                margins=True,
                margins_name="Total no Horário",
            )
            st.dataframe(matriz_turmas, use_container_width=True)

    with aba_crud:
        col_tit_crud, col_dl_crud = st.columns([3, 1])
        with col_tit_crud:
            st.subheader("📋 Base de Alunos Cadastrados (Consulta e Filtros — READ)")
        with col_dl_crud:
            csv_bytes = df[COLUNAS_PADRAO].to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
            st.download_button(
                "📥 Baixar Planilha (Excel/CSV)",
                data=csv_bytes,
                file_name=f"alunos_maisvida_{datetime.now().strftime('%d_%m_%Y')}.csv",
                mime="text/csv",
                use_container_width=True,
            )

        f_col1, f_col2, f_col3, f_col4 = st.columns(4)
        with f_col1:
            busca_nome = st.text_input("Buscar por Nome ou WhatsApp:")
        with f_col2:
            filtro_vinc = st.selectbox("Filtrar por Vínculo:", ["Todos"] + VINCULOS)
        with f_col3:
            filtro_mod = st.selectbox("Filtrar por Modalidade:", ["Todas"] + MODALIDADES)
        with f_col4:
            filtro_hor = st.selectbox("Filtrar por Horário:", ["Todos"] + HORARIOS)

        df_consulta = df.copy()
        if not df_consulta.empty:
            if busca_nome.strip():
                termo = busca_nome.strip().lower()
                df_consulta = df_consulta[
                    df_consulta["Nome_Completo"].str.lower().str.contains(termo, na=False)
                    | df_consulta["Contato_WhatsApp"].str.contains(termo, na=False)
                ]
            if filtro_vinc != "Todos":
                df_consulta = df_consulta[df_consulta["Tipo_Vinculo"] == filtro_vinc]
            if filtro_mod != "Todas":
                df_consulta = df_consulta[df_consulta["Modalidade"] == filtro_mod]
            if filtro_hor != "Todos":
                df_consulta = df_consulta[df_consulta["Horario_Treino"] == filtro_hor]

        colunas_visiveis = [
            "ID_Aluno", "Nome_Completo", "Data_Nascimento", "Contato_WhatsApp",
            "Modalidade", "Horario_Treino", "Tipo_Vinculo", "Status", "Data_Cadastro"
        ]
        st.dataframe(
            df_consulta[colunas_visiveis].sort_values(by="ID_Aluno", ascending=False) if not df_consulta.empty else df_consulta[colunas_visiveis],
            hide_index=True,
            use_container_width=True,
            height=280,
        )

        st.divider()
        col_create, col_update_delete = st.columns(2)

        with col_create:
            st.markdown("### ➕ Cadastrar Novo Aluno (Create)")
            with st.form("form_crud_create", clear_on_submit=True):
                c_nome = st.text_input("Nome Completo *", placeholder="Ex: Rodrigo Santana")
                c_nasc = st.text_input("Data de Nascimento (DD/MM/AAAA) *", placeholder="Ex: 20/11/1993")
                c_wpp = st.text_input("Contato WhatsApp (com DDD) *", placeholder="Ex: 21988887777")
                c_mod = st.selectbox("Modalidade *", MODALIDADES)
                c_hor = st.selectbox("Horário de Treino *", HORARIOS)
                c_vinc = st.selectbox("Tipo de Vínculo *", VINCULOS)

                btn_criar = st.form_submit_button("💾 Salvar Novo Aluno", use_container_width=True)
                if btn_criar:
                    erros = validar_dados_aluno(c_nome, c_nasc, c_wpp)
                    if erros:
                        for e in erros:
                            st.error(e)
                    else:
                        ts = criar_aluno(c_nome, c_nasc, c_wpp, c_mod, c_hor, c_vinc)
                        st.success(f"✔️ Aluno '{c_nome}' salvo na planilha às {ts}!")
                        st.rerun()

        with col_update_delete:
            st.markdown("### ✏️ Atualizar ou Excluir Aluno (Update / Delete)")
            if df.empty:
                st.info("Nenhum aluno cadastrado para editar ou excluir.")
            else:
                opcoes_alunos = df.sort_values(by="ID_Aluno", ascending=False).apply(
                    lambda r: f"#{r['ID_Aluno']} - {r['Nome_Completo']} ({r['Modalidade']} {r['Horario_Treino']} | {r['Tipo_Vinculo']})",
                    axis=1,
                ).tolist()

                aluno_selecionado_str = st.selectbox("Selecione o Aluno para Editar ou Excluir:", opcoes_alunos)

                if aluno_selecionado_str:
                    id_sel = int(aluno_selecionado_str.split(" - ")[0].replace("#", ""))
                    registro_atual = df[df["ID_Aluno"] == id_sel].iloc[0]

                    with st.form("form_crud_update"):
                        u_nome = st.text_input("Nome Completo *", value=registro_atual["Nome_Completo"])
                        u_nasc = st.text_input("Data de Nascimento (DD/MM/AAAA) *", value=registro_atual["Data_Nascimento"])
                        u_wpp = st.text_input("Contato WhatsApp *", value=registro_atual["Contato_WhatsApp"])
                        u_mod = st.selectbox(
                            "Modalidade *",
                            MODALIDADES,
                            index=MODALIDADES.index(registro_atual["Modalidade"]) if registro_atual["Modalidade"] in MODALIDADES else 0,
                        )
                        u_hor = st.selectbox(
                            "Horário de Treino *",
                            HORARIOS,
                            index=HORARIOS.index(registro_atual["Horario_Treino"]) if registro_atual["Horario_Treino"] in HORARIOS else 0,
                        )
                        u_vinc = st.selectbox(
                            "Tipo de Vínculo *",
                            VINCULOS,
                            index=VINCULOS.index(registro_atual["Tipo_Vinculo"]) if registro_atual["Tipo_Vinculo"] in VINCULOS else 0,
                        )
                        u_status = st.selectbox(
                            "Status do Cadastro *",
                            STATUS_OPCOES,
                            index=STATUS_OPCOES.index(registro_atual["Status"]) if registro_atual["Status"] in STATUS_OPCOES else 0,
                        )

                        col_btn_up, col_btn_del = st.columns(2)
                        with col_btn_up:
                            btn_atualizar = st.form_submit_button("🔄 Atualizar Cadastro", use_container_width=True)
                        with col_btn_del:
                            btn_excluir = st.form_submit_button("🗑️ Excluir Aluno", use_container_width=True)

                        if btn_atualizar:
                            erros = validar_dados_aluno(u_nome, u_nasc, u_wpp)
                            if erros:
                                for e in erros:
                                    st.error(e)
                            else:
                                atualizar_aluno(id_sel, u_nome, u_nasc, u_wpp, u_mod, u_hor, u_vinc, u_status)
                                st.success(f"✔️ Cadastro #{id_sel} atualizado na planilha!")
                                st.rerun()

                        if btn_excluir:
                            excluir_aluno(id_sel)
                            st.warning(f"🗑️ Registro #{id_sel} excluído da planilha.")
                            st.rerun()


def renderizar_formulario_mobile_aluno():
    st.markdown("## 📱 Auto-Cadastro Rápido de Aluno — MaisVida Praia")
    st.caption("Preencha seus dados em poucos segundos para liberar seu treino e receber novidades!")

    if st.session_state.get("cadastro_enviado", False):
        st.success("## ✔️ Cadastro concluído com sucesso! Bom treino na areia!")
        st.markdown(
            f"**Registro confirmado em:** `{st.session_state.get('ultimo_ts_cadastro')}`"
        )
        if st.button("➕ Cadastrar Outro Aluno", use_container_width=True):
            st.session_state["cadastro_enviado"] = False
            st.rerun()
        return

    with st.form("form_mobile_aluno"):
        nome = st.text_input("Nome Completo *", placeholder="Ex: João da Silva")
        data_nasc = st.text_input("Data de Nascimento (DD/MM/AAAA) *", placeholder="Ex: 15/11/1995")
        whatsapp = st.text_input("Celular / WhatsApp (com DDD) *", placeholder="Ex: 21999998888")
        modalidade = st.selectbox("Qual modalidade você treina? *", MODALIDADES)
        horario = st.selectbox("Qual o seu horário principal de treino? *", HORARIOS)
        vinculo = st.selectbox("Qual o seu tipo de plano/acesso? *", VINCULOS)

        enviar = st.form_submit_button("✔️ Concluir Meu Cadastro", use_container_width=True)

        if enviar:
            erros = validar_dados_aluno(nome, data_nasc, whatsapp)
            if erros:
                for e in erros:
                    st.error(e)
            else:
                ts = criar_aluno(nome, data_nasc, whatsapp, modalidade, horario, vinculo)
                st.session_state["ultimo_ts_cadastro"] = ts
                st.session_state["cadastro_enviado"] = True
                st.rerun()


def main():
    visao_url = st.query_params.get("visao", "")
    indice_padrao = 1 if visao_url == "aluno" else 0

    modo = st.sidebar.radio(
        "🧭 Navegação do Sistema:",
        options=[
            "📊 Painel da Recepção / Gestor",
            "📱 Formulário QR Code do Aluno",
        ],
        index=indice_padrao,
    )

    if modo == "📱 Formulário QR Code do Aluno":
        renderizar_formulario_mobile_aluno()
    else:
        if not st.session_state.get("autenticado", False):
            renderizar_login()
        else:
            renderizar_painel_gestor()


if __name__ == "__main__":
    main()
