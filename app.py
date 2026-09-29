"""
app.py
------
Interface do Sistema de Vendas de Veículos (Streamlit).

Este arquivo NÃO contém SQL: toda leitura e gravação passa pelas
funções importadas do banco.py.

Abas:
    Painel   -> métricas, gráficos e tabela, todos respeitando os filtros
    Vendas   -> registrar e excluir vendas
    Estoque  -> cadastrar e excluir veículos
    Clientes -> cadastrar e excluir clientes
"""

from datetime import date

import streamlit as st

from banco import (
    conectar, criar_tabelas,
    inserir_veiculo, listar_veiculos, excluir_veiculo,
    inserir_cliente, listar_clientes, excluir_cliente,
    inserir_venda, listar_vendas, excluir_venda,
)

st.set_page_config(page_title="Concessionária - Vendas de Veículos", page_icon="🚗", layout="wide")


# =====================================================================
# CONEXÃO (criada uma única vez e reaproveitada em todas as recargas)
# =====================================================================

@st.cache_resource
def obter_conexao():
    """Guarda a conexão em cache para não reabrir o banco a cada clique."""
    return conectar()


conexao = obter_conexao()
criar_tabelas(conexao)


# =====================================================================
# FUNÇÕES AUXILIARES
# =====================================================================

def moeda(valor):
    """Formata um número no padrão brasileiro: R$ 1.234,56"""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def confirmar_e_recarregar(mensagem):
    """
    Guarda a mensagem de sucesso e recarrega a tela com st.rerun().
    A mensagem é exibida logo depois da recarga (sem isso ela sumiria).
    """
    st.session_state["mensagem_sucesso"] = mensagem
    st.rerun()


# =====================================================================
# CABEÇALHO E MENSAGEM DE CONFIRMAÇÃO
# =====================================================================

st.title("🚗 Sistema de Vendas de Veículos")

if "mensagem_sucesso" in st.session_state:
    st.success(st.session_state.pop("mensagem_sucesso"))

# Carrega os dados do banco (DataFrames do pandas)
df_vendas = listar_vendas(conexao)
df_veiculos = listar_veiculos(conexao)
df_clientes = listar_clientes(conexao)
df_disponiveis = df_veiculos[df_veiculos["status"] == "Disponível"]


# =====================================================================
# FILTROS (barra lateral) -> afetam métricas, gráficos e tabela do Painel
# =====================================================================

st.sidebar.header("🔎 Filtros")
st.sidebar.caption("Valem para as métricas, os gráficos e a tabela do Painel.")

df_filtrado = df_vendas.copy()

if len(df_vendas) > 0:
    # Filtro 1: marca (selectbox)
    opcoes_marca = ["Todas"] + sorted(df_vendas["marca"].unique().tolist())
    marca_escolhida = st.sidebar.selectbox("Marca:", opcoes_marca)

    # Filtro 2: vendedor (selectbox)
    opcoes_vendedor = ["Todos"] + sorted(df_vendas["vendedor"].unique().tolist())
    vendedor_escolhido = st.sidebar.selectbox("Vendedor:", opcoes_vendedor)

    # Filtro 3: faixa de valor da venda (slider)
    valor_minimo = float(df_vendas["valor"].min())
    valor_maximo = float(df_vendas["valor"].max())
    if valor_minimo < valor_maximo:
        faixa_valor = st.sidebar.slider(
            "Faixa de valor (R$):",
            min_value=valor_minimo,
            max_value=valor_maximo,
            value=(valor_minimo, valor_maximo),
        )
    else:
        # Com um único valor não há faixa para escolher
        faixa_valor = (valor_minimo, valor_maximo)

    # Aplica os filtros com pandas
    if marca_escolhida != "Todas":
        df_filtrado = df_filtrado[df_filtrado["marca"] == marca_escolhida]
    if vendedor_escolhido != "Todos":
        df_filtrado = df_filtrado[df_filtrado["vendedor"] == vendedor_escolhido]
    df_filtrado = df_filtrado[df_filtrado["valor"].between(faixa_valor[0], faixa_valor[1])]
else:
    st.sidebar.info("Os filtros aparecem depois da primeira venda.")


aba_painel, aba_vendas, aba_estoque, aba_clientes = st.tabs(
    ["📊 Painel", "💰 Vendas", "🚙 Estoque", "👤 Clientes"]
)

# =====================================================================
# ABA PAINEL: métricas, gráficos (groupby) e tabela filtrada
# =====================================================================
with aba_painel:
    if len(df_vendas) == 0:
        st.info("Nenhuma venda registrada ainda. Cadastre veículos e clientes e registre uma venda na aba Vendas.")
    elif len(df_filtrado) == 0:
        st.warning("Nenhuma venda encontrada com os filtros selecionados.")
    else:
        # ---- Métricas calculadas com pandas ----
        faturamento_total = df_filtrado["valor"].sum()
        ticket_medio = df_filtrado["valor"].mean()
        quantidade_vendida = len(df_filtrado)
        desconto_medio = (df_filtrado["preco_tabela"] - df_filtrado["valor"]).mean()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Faturamento total", moeda(faturamento_total))
        col2.metric("Ticket médio", moeda(ticket_medio))
        col3.metric("Veículos vendidos", quantidade_vendida)
        col4.metric("Desconto médio", moeda(desconto_medio),
                    help="Diferença média entre o preço de tabela e o valor vendido")

        # ---- Gráficos com groupby ----
        grafico1, grafico2 = st.columns(2)
        with grafico1:
            st.write("**Faturamento por vendedor**")
            st.bar_chart(df_filtrado.groupby("vendedor")["valor"].sum())
        with grafico2:
            st.write("**Faturamento por marca**")
            st.bar_chart(df_filtrado.groupby("marca")["valor"].sum())

        grafico3, grafico4 = st.columns(2)
        with grafico3:
            st.write("**Faturamento por mês**")
            # A data está no formato AAAA-MM-DD; os 7 primeiros caracteres são AAAA-MM
            faturamento_mes = df_filtrado.assign(mes=df_filtrado["data"].str[:7]).groupby("mes")["valor"].sum()
            st.line_chart(faturamento_mes)
        with grafico4:
            st.write("**Quantidade de vendas por forma de pagamento**")
            st.bar_chart(df_filtrado.groupby("forma_pagamento")["id"].count())

        # ---- Tabela com as vendas filtradas ----
        st.subheader("Vendas (conforme filtros)")
        st.dataframe(df_filtrado, hide_index=True)

    st.caption(
        f"Estoque atual: {len(df_disponiveis)} veículo(s) disponível(is), "
        f"somando {moeda(df_disponiveis['preco'].sum())} em preço de tabela."
    )

# =====================================================================
# ABA VENDAS: registrar (st.form) e excluir por id
# =====================================================================
with aba_vendas:
    st.subheader("Registrar nova venda")

    if len(df_disponiveis) == 0 or len(df_clientes) == 0:
        st.warning("Para registrar uma venda é preciso ter ao menos um veículo disponível e um cliente cadastrado.")
    else:
        # O veículo fica FORA do formulário para que o preço sugerido
        # seja atualizado assim que o usuário troca de carro
        rotulos_veiculos = {
            int(v.id): f"{v.marca} {v.modelo} {v.ano} - {v.placa} ({moeda(v.preco)})"
            for v in df_disponiveis.itertuples()
        }
        veiculo_id = st.selectbox("Veículo:", list(rotulos_veiculos), format_func=rotulos_veiculos.get)
        preco_tabela = float(df_disponiveis.loc[df_disponiveis["id"] == veiculo_id, "preco"].iloc[0])

        rotulos_clientes = {int(c.id): f"{c.nome} - CPF {c.cpf}" for c in df_clientes.itertuples()}

        with st.form("form_venda", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            with col_a:
                cliente_id = st.selectbox("Cliente:", list(rotulos_clientes), format_func=rotulos_clientes.get)
                vendedor = st.text_input("Vendedor:")
                forma_pagamento = st.selectbox(
                    "Forma de pagamento:",
                    ["À vista", "Financiamento", "Consórcio", "Troca + diferença"]
                )
            with col_b:
                valor = st.number_input(
                    "Valor negociado (R$):",
                    min_value=0.0,
                    value=preco_tabela,
                    step=500.0,
                    key=f"valor_{veiculo_id}",  # chave muda com o veículo -> valor sugerido atualiza
                )
                data_venda = st.date_input("Data da venda:", value=date.today(), format="DD/MM/YYYY")

            enviado = st.form_submit_button("Registrar venda", type="primary")

            if enviado:
                # Validação dos campos obrigatórios
                if vendedor.strip() == "":
                    st.error("Informe o nome do vendedor antes de salvar.")
                elif valor <= 0:
                    st.error("O valor da venda precisa ser maior que zero.")
                else:
                    try:
                        inserir_venda(conexao, veiculo_id, cliente_id, vendedor.strip(),
                                      valor, forma_pagamento, str(data_venda))
                        confirmar_e_recarregar(f"Venda de {rotulos_veiculos[veiculo_id]} registrada com sucesso!")
                    except ValueError as erro:
                        st.error(str(erro))

    st.divider()
    st.subheader("Todas as vendas")

    if len(df_vendas) == 0:
        st.info("Nenhuma venda registrada.")
    else:
        st.dataframe(df_vendas, hide_index=True)

        with st.expander("Excluir uma venda cadastrada por engano"):
            rotulos_vendas = {
                int(v.id): f"ID {v.id} - {v.marca} {v.modelo} ({v.placa}) - {v.cliente}"
                for v in df_vendas.itertuples()
            }
            id_venda = st.selectbox("Venda:", list(rotulos_vendas), format_func=rotulos_vendas.get)
            st.caption("O veículo volta para o estoque como Disponível.")
            if st.button("Excluir venda"):
                try:
                    excluir_venda(conexao, id_venda)
                    confirmar_e_recarregar(f"Venda ID {id_venda} excluída e veículo devolvido ao estoque.")
                except ValueError as erro:
                    st.error(str(erro))

# =====================================================================
# ABA ESTOQUE: cadastrar (st.form) e excluir veículos
# =====================================================================
with aba_estoque:
    st.subheader("Cadastrar veículo")

    with st.form("form_veiculo", clear_on_submit=True):
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            marca = st.text_input("Marca:")
            modelo = st.text_input("Modelo:")
            ano = st.number_input("Ano:", min_value=1950, max_value=date.today().year + 1,
                                  value=date.today().year, step=1)
        with col_b:
            cor = st.text_input("Cor:")
            placa = st.text_input("Placa:", max_chars=8)
            quilometragem = st.number_input("Quilometragem:", min_value=0, step=1000)
        with col_c:
            combustivel = st.selectbox("Combustível:", ["Flex", "Gasolina", "Etanol", "Diesel", "Híbrido", "Elétrico"])
            preco = st.number_input("Preço de tabela (R$):", min_value=0.0, step=1000.0)

        if st.form_submit_button("Salvar veículo"):
            campos_obrigatorios = [marca, modelo, cor, placa]
            if any(campo.strip() == "" for campo in campos_obrigatorios):
                st.error("Preencha marca, modelo, cor e placa antes de salvar.")
            elif preco <= 0:
                st.error("Informe um preço maior que zero.")
            else:
                try:
                    inserir_veiculo(conexao, marca.strip(), modelo.strip(), int(ano), cor.strip(),
                                    placa.strip(), int(quilometragem), combustivel, preco)
                    confirmar_e_recarregar(f"{marca} {modelo} cadastrado no estoque.")
                except ValueError as erro:
                    st.error(str(erro))

    st.divider()
    st.subheader("Veículos")

    filtro_status = st.radio("Mostrar:", ["Todos", "Disponível", "Vendido"], horizontal=True)
    if filtro_status == "Todos":
        df_veiculos_exibidos = df_veiculos
    else:
        df_veiculos_exibidos = df_veiculos[df_veiculos["status"] == filtro_status]

    if len(df_veiculos_exibidos) == 0:
        st.info("Nenhum veículo encontrado.")
    else:
        st.dataframe(df_veiculos_exibidos, hide_index=True)

    if len(df_disponiveis) > 0:
        with st.expander("Excluir um veículo do estoque"):
            rotulos_estoque = {
                int(v.id): f"ID {v.id} - {v.marca} {v.modelo} ({v.placa})"
                for v in df_disponiveis.itertuples()
            }
            id_veiculo = st.selectbox("Veículo:", list(rotulos_estoque),
                                      format_func=rotulos_estoque.get, key="excluir_veiculo")
            if st.button("Excluir veículo"):
                try:
                    excluir_veiculo(conexao, id_veiculo)
                    confirmar_e_recarregar(f"Veículo ID {id_veiculo} excluído.")
                except ValueError as erro:
                    st.error(str(erro))

# =====================================================================
# ABA CLIENTES: cadastrar (st.form) e excluir clientes
# =====================================================================
with aba_clientes:
    st.subheader("Cadastrar cliente")

    with st.form("form_cliente", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        with col_a:
            nome = st.text_input("Nome:")
            cpf = st.text_input("CPF:", max_chars=14, placeholder="000.000.000-00")
        with col_b:
            telefone = st.text_input("Telefone:")
            cidade = st.text_input("Cidade:")

        if st.form_submit_button("Salvar cliente"):
            if nome.strip() == "" or cpf.strip() == "":
                st.error("Preencha nome e CPF antes de salvar.")
            else:
                try:
                    inserir_cliente(conexao, nome.strip(), cpf.strip(), telefone.strip(), cidade.strip())
                    confirmar_e_recarregar(f"Cliente {nome.strip()} cadastrado com sucesso.")
                except ValueError as erro:
                    st.error(str(erro))

    st.divider()

    if len(df_clientes) == 0:
        st.info("Nenhum cliente cadastrado.")
    else:
        st.dataframe(df_clientes, hide_index=True)

        with st.expander("Excluir um cliente"):
            rotulos_excluir_cliente = {int(c.id): f"ID {c.id} - {c.nome}" for c in df_clientes.itertuples()}
            id_cliente = st.selectbox("Cliente:", list(rotulos_excluir_cliente),
                                      format_func=rotulos_excluir_cliente.get, key="excluir_cliente")
            if st.button("Excluir cliente"):
                try:
                    excluir_cliente(conexao, id_cliente)
                    confirmar_e_recarregar(f"Cliente ID {id_cliente} excluído.")
                except ValueError as erro:
                    st.error(str(erro))
