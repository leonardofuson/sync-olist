import os
import requests
import psycopg2
import time
from flask import Flask, jsonify
from datetime import datetime

# --- Configuração Inicial ---
app = Flask(__name__)

# Carrega as chaves secretas das variáveis de ambiente do Render
TINY_API_TOKEN = os.getenv("TINY_API_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
TINY_API_URL = "https://api.tiny.com.br/api2/produtos.pesquisa.php"

# --- Funções do Banco de Dados ---

def get_db_connection():
    """Cria e retorna uma nova conexão com o banco de dados."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except psycopg2.OperationalError as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        return None

def insert_product_in_db(cursor, produto):
    """Insere ou atualiza um produto no banco de dados (agora com GTIN)."""
    # Adicionamos 'gtin' nas listas de colunas
    sql = """
        INSERT INTO produtos (
            id_tiny, nome, sku, gtin, preco, preco_custo, unidade, ativo, 
            data_criacao_tiny, data_atualizacao_tiny, ultima_sincronizacao
        ) VALUES (
            %(id)s, %(nome)s, %(sku)s, %(gtin)s, %(preco)s, %(preco_custo)s, %(unidade)s, %(situacao)s,
            %(data_criacao)s, %(data_atualizacao)s, CURRENT_TIMESTAMP
        )
        ON CONFLICT (id_tiny) DO UPDATE SET
            nome = EXCLUDED.nome,
            sku = EXCLUDED.sku,
            gtin = EXCLUDED.gtin, -- Adicionado no UPDATE
            preco = EXCLUDED.preco,
            preco_custo = EXCLUDED.preco_custo,
            unidade = EXCLUDED.unidade,
            ativo = EXCLUDED.ativo,
            data_atualizacao_tiny = EXCLUDED.data_atualizacao_tiny,
            ultima_sincronizacao = CURRENT_TIMESTAMP;
    """
    situacao_boolean = True if produto.get('situacao') == 'A' else False
    preco_str = str(produto.get('preco', '0'))
    preco_custo_str = str(produto.get('preco_custo', '0'))
    preco_formatado = float(preco_str.replace(',', '.'))
    preco_custo_formatado = float(preco_custo_str.replace(',', '.'))
    data_criacao_obj = datetime.strptime(produto['data_criacao'], '%d/%m/%Y %H:%M:%S') if produto.get('data_criacao') else None
    data_atualizacao_obj = datetime.strptime(produto['data_atualizacao'], '%d/%m/%Y %H:%M:%S') if produto.get('data_atualizacao') else None
    
    # Adicionamos 'gtin' ao dicionário de dados
    dados_produto = {
        'id': int(produto['id']),
        'nome': produto['nome'],
        'sku': produto.get('codigo', None),
        'gtin': produto.get('gtin', None), # Nova linha!
        'preco': preco_formatado,
        'preco_custo': preco_custo_formatado,
        'unidade': produto.get('unidade', None),
        'situacao': situacao_boolean,
        'data_criacao': data_criacao_obj,
        'data_atualizacao': data_atualizacao_obj
    }
    
    cursor.execute(sql, dados_produto)


# --- Rotas da Aplicação (Endpoints) ---

@app.route("/")
def hello_world():
    """Página inicial para verificar o status do serviço."""
    status_token = "encontrado" if TINY_API_TOKEN else "NÃO configurado"
    status_db = "encontrada" if DATABASE_URL else "NÃO configurada"
    return (f"<h1>Robô Sincronizador Tiny</h1>"
            f"<p>Status: Online.</p>"
            f"<p>Token da API: {status_token}.</p>"
            f"<p>URL do Banco de Dados: {status_db}.</p>"
            f"<p>Para iniciar, acesse a rota /sincronizar</p>")

@app.route("/sincronizar")
def sincronizar_produtos():
    """
    Endpoint principal que dispara a sincronização.
    Busca TODOS os produtos na API do Tiny, página por página, e os salva no banco.
    """
    print("-> Iniciando processo de sincronização COMPLETA de produtos...")

    if not TINY_API_TOKEN or not DATABASE_URL:
        return jsonify({"status": "erro", "mensagem": "Variáveis de ambiente não configuradas."}), 500

    pagina_atual = 1
    total_produtos_sincronizados = 0
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "erro", "mensagem": "Não foi possível conectar ao banco de dados."}), 500

    try:
        while True:
            print(f"Buscando produtos - Página: {pagina_atual}...")
            
            params = {
                'token': TINY_API_TOKEN,
                'formato': 'json',
                'pagina': pagina_atual
            }
            
            try:
                response = requests.get(TINY_API_URL, params=params)
                response.raise_for_status()
                data = response.json()
            except requests.exceptions.RequestException as e:
                raise Exception(f"Falha na comunicação com a API do Tiny na página {pagina_atual}: {e}")

            # Verificação de erro da API
            if data['retorno']['status'] == 'ERRO':
                erro_msg = data['retorno']['erros'][0]['erro']
                if 'A pagina nao foi encontrada' in erro_msg:
                    print("API informou que não há mais páginas. Fim da sincronização.")
                    break
                else:
                    raise Exception(f"API do Tiny retornou um erro na página {pagina_atual}: {erro_msg}")

            # --- INÍCIO DA CORREÇÃO ---
            # Usar .get() para buscar a lista de produtos de forma segura.
            # Se a chave 'produtos' não existir, retorna uma lista vazia [].
            produtos_da_pagina = data['retorno'].get('produtos', [])
            # --- FIM DA CORREÇÃO ---
            
            if not produtos_da_pagina:
                print("Página retornou sem produtos. Fim da sincronização.")
                break

            num_produtos_pagina = len(produtos_da_pagina)
            total_produtos_sincronizados += num_produtos_pagina
            print(f"Encontrados {num_produtos_pagina} produtos na página {pagina_atual}. Sincronizando com o banco...")

            with conn.cursor() as cursor:
                for item in produtos_da_pagina:
                    produto = item['produto']
                    insert_product_in_db(cursor, produto)
            
            conn.commit()

            pagina_atual += 1
            time.sleep(1)

    except Exception as e:
        conn.rollback()
        print(f"ERRO GERAL: {e}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500
    finally:
        conn.close()

    print(f"-> Sucesso! {total_produtos_sincronizados} produtos no total foram sincronizados.")
    return jsonify({
        "status": "sucesso",
        "total_produtos_sincronizados": total_produtos_sincronizados,
        "paginas_processadas": pagina_atual - 1

    })
# Este bloco permite que o Render inicie a aplicação.
if __name__ == "__main__":
    # Apenas para teste local, o Render usa o Gunicorn para iniciar.
    app.run()
    
