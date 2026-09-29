"""
banco.py
--------
Camada de banco de dados do Sistema de Vendas de Veículos.

TODO o SQL do projeto fica neste arquivo. O app.py só chama estas funções.
Cada função recebe a conexão como primeiro parâmetro: ela é criada uma
única vez no app.py e guardada com @st.cache_resource.

Tabelas:
    veiculos  -> estoque da concessionária
    clientes  -> compradores
    vendas    -> liga um veículo a um cliente (chaves estrangeiras)
"""

import sqlite3

import pandas as pd

NOME_BANCO = "concessionaria.db"


# =====================================================================
# CONEXÃO E CRIAÇÃO DAS TABELAS
# =====================================================================

def conectar():
    """Abre a conexão com o arquivo SQLite."""
    # check_same_thread=False: o Streamlit usa threads diferentes a cada recarga
    conexao = sqlite3.connect(NOME_BANCO, check_same_thread=False)
    # O SQLite só respeita chaves estrangeiras quando isso é ativado
    conexao.execute("PRAGMA foreign_keys = ON")
    return conexao


def criar_tabelas(conexao):
    """Cria as três tabelas caso ainda não existam."""
    conexao.executescript("""
        CREATE TABLE IF NOT EXISTS veiculos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            marca TEXT NOT NULL,
            modelo TEXT NOT NULL,
            ano INTEGER NOT NULL,
            cor TEXT NOT NULL,
            placa TEXT NOT NULL UNIQUE,
            quilometragem INTEGER NOT NULL DEFAULT 0,
            combustivel TEXT NOT NULL,
            preco REAL NOT NULL CHECK (preco >= 0),
            status TEXT NOT NULL DEFAULT 'Disponível'
                CHECK (status IN ('Disponível', 'Vendido'))
        );

        CREATE TABLE IF NOT EXISTS clientes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            cpf TEXT NOT NULL UNIQUE,
            telefone TEXT,
            cidade TEXT
        );

        CREATE TABLE IF NOT EXISTS vendas(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            veiculo_id INTEGER NOT NULL UNIQUE,   -- UNIQUE: um carro só pode ser vendido uma vez
            cliente_id INTEGER NOT NULL,
            vendedor TEXT NOT NULL,
            valor REAL NOT NULL CHECK (valor >= 0),
            forma_pagamento TEXT NOT NULL,
            data TEXT NOT NULL,
            FOREIGN KEY (veiculo_id) REFERENCES veiculos(id),
            FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        );
    """)
    conexao.commit()


# =====================================================================
# VEÍCULOS (estoque)
# =====================================================================

def inserir_veiculo(conexao, marca, modelo, ano, cor, placa, quilometragem, combustivel, preco):
    """Cadastra um veículo no estoque com status 'Disponível'."""
    try:
        conexao.execute(
            """
            INSERT INTO veiculos (marca, modelo, ano, cor, placa, quilometragem, combustivel, preco)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (marca, modelo, ano, cor, placa.upper(), quilometragem, combustivel, preco)
        )
        conexao.commit()
    except sqlite3.IntegrityError:
        conexao.rollback()
        raise ValueError(f"Já existe um veículo com a placa {placa.upper()}.")


def listar_veiculos(conexao):
    """Devolve todos os veículos em um DataFrame."""
    return pd.read_sql_query("SELECT * FROM veiculos ORDER BY id DESC", conexao)


def excluir_veiculo(conexao, id_veiculo):
    """Exclui um veículo pelo id (bloqueado se ele tiver venda registrada)."""
    try:
        cursor = conexao.execute("DELETE FROM veiculos WHERE id = ?", (id_veiculo,))
        conexao.commit()
    except sqlite3.IntegrityError:
        conexao.rollback()
        raise ValueError("Esse veículo tem venda registrada. Exclua a venda antes.")
    if cursor.rowcount == 0:
        raise ValueError(f"Veículo {id_veiculo} não encontrado.")


# =====================================================================
# CLIENTES
# =====================================================================

def inserir_cliente(conexao, nome, cpf, telefone, cidade):
    """Cadastra um cliente. O CPF não pode se repetir."""
    try:
        conexao.execute(
            "INSERT INTO clientes (nome, cpf, telefone, cidade) VALUES (?,?,?,?)",
            (nome, cpf, telefone, cidade)
        )
        conexao.commit()
    except sqlite3.IntegrityError:
        conexao.rollback()
        raise ValueError(f"Já existe um cliente com o CPF {cpf}.")


def listar_clientes(conexao):
    """Devolve todos os clientes em um DataFrame."""
    return pd.read_sql_query("SELECT * FROM clientes ORDER BY nome", conexao)


def excluir_cliente(conexao, id_cliente):
    """Exclui um cliente pelo id (bloqueado se ele tiver compras)."""
    try:
        cursor = conexao.execute("DELETE FROM clientes WHERE id = ?", (id_cliente,))
        conexao.commit()
    except sqlite3.IntegrityError:
        conexao.rollback()
        raise ValueError("Esse cliente tem compras registradas e não pode ser excluído.")
    if cursor.rowcount == 0:
        raise ValueError(f"Cliente {id_cliente} não encontrado.")


# =====================================================================
# VENDAS
# =====================================================================

def inserir_venda(conexao, veiculo_id, cliente_id, vendedor, valor, forma_pagamento, data):
    """
    Registra uma venda e marca o veículo como 'Vendido'.
    As duas operações acontecem na mesma transação: ou as duas dão certo,
    ou nenhuma é gravada (rollback).
    """
    try:
        linha = conexao.execute(
            "SELECT status FROM veiculos WHERE id = ?", (veiculo_id,)
        ).fetchone()
        if linha is None or linha[0] != "Disponível":
            raise ValueError("Esse veículo não está disponível para venda.")

        conexao.execute(
            """
            INSERT INTO vendas (veiculo_id, cliente_id, vendedor, valor, forma_pagamento, data)
            VALUES (?,?,?,?,?,?)
            """,
            (veiculo_id, cliente_id, vendedor, valor, forma_pagamento, data)
        )
        conexao.execute("UPDATE veiculos SET status = 'Vendido' WHERE id = ?", (veiculo_id,))
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise


def listar_vendas(conexao):
    """
    Devolve todas as vendas em um DataFrame, já com os dados do veículo
    e o nome do cliente (JOIN entre as três tabelas).
    """
    return pd.read_sql_query(
        """
        SELECT v.id,
               v.data,
               ve.marca,
               ve.modelo,
               ve.ano,
               ve.placa,
               c.nome AS cliente,
               v.vendedor,
               v.forma_pagamento,
               ve.preco AS preco_tabela,
               v.valor
        FROM vendas v
        JOIN veiculos ve ON ve.id = v.veiculo_id
        JOIN clientes c  ON c.id  = v.cliente_id
        ORDER BY v.data DESC, v.id DESC
        """,
        conexao
    )


def excluir_venda(conexao, id_venda):
    """Exclui uma venda pelo id e devolve o veículo ao estoque."""
    try:
        linha = conexao.execute(
            "SELECT veiculo_id FROM vendas WHERE id = ?", (id_venda,)
        ).fetchone()
        if linha is None:
            raise ValueError(f"Venda {id_venda} não encontrada.")

        conexao.execute("DELETE FROM vendas WHERE id = ?", (id_venda,))
        conexao.execute("UPDATE veiculos SET status = 'Disponível' WHERE id = ?", (linha[0],))
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
