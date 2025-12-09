import os
import requests
import psycopg2
from flask import Flask, jsonify

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
    """
    Insere ou atualiza um produto no banco de dados.
    Usa a cláusula ON CONFLICT para evitar duplicados e apenas atualizar.
    """
    sql = """
        INSERT INTO produtos (
            id_tiny, nome, sku, preco, preco_custo, unidade, ativo, 
            data_criacao_tiny, data_atualizacao_tiny, ultima_sincronizacao
        ) VALUES (
            %(id)s, %(nome)s, %(sku)s, %(preco)s, %(preco_custo)s, %(unidade)s, %(situacao)s,
            %(data_criacao)s, %(data_atualizacao)s, CURRENT_TIMESTAMP
        )
        ON CONFLICT (id_tiny) DO UPDATE SET
            nome = EXCLUDED.nome,
            sku = EXCLUDED.sku,
            preco = EXCLUDED.preco,
            preco_custo = EXCLUDED.preco_custo,
            unidade = EXCLUDED.unidade,
            ativo = EXCLUDED.ativo,
            data_atualizacao_tiny = EXCLUDED.data_atualizacao_tiny,
            ultima_sincronizacao = CURRENT_TIMESTAMP;
    """
    situacao_boolean = True if produto.get('situacao') == 'A' else False
    
    # --- INÍCIO DA CORREÇÃO ---
    # Garante que o valor seja uma string antes de usar .replace()
    preco_str = str(produto.get('preco', '0'))
    preco_custo_str = str(produto.get('preco_custo', '0'))

    preco_formatado = float(preco_str.replace(',', '.'))
    preco_custo_formatado = float(preco_custo_str.replace(',', '.'))
    # --- FIM DA CORREÇÃO ---

    dados_produto = {
        'id': int(produto['id']),
        'nome': produto['nome'],
        'sku': produto.get('codigo', None),
        'preco': preco_formatado,
        'preco_custo': preco_custo_formatado,
        'unidade': produto.get('unidade', None),
        'situacao': situacao_boolean,
        'data_criacao': produto.get('data_criacao', None),
        'data_atualizacao': produto.get('data_atualizacao', None)
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
    Busca produtos na API do Tiny e os salva no banco de dados.
    """
    print("-> Iniciando processo de sincronização de produtos...")

    if not TINY_API_TOKEN or not DATABASE_URL:
        return jsonify({"status": "erro", "mensagem": "Variáveis de ambiente não configuradas."}), 500

    # 1. Buscar dados da API do Tiny
    params = {
        'token': TINY_API_TOKEN,
        'formato': 'json',
        'pagina': 1 # Por enquanto, buscamos apenas a primeira página
    }
    try:
        response = requests.get(TINY_API_URL, params=params)
        response.raise_for_status() # Lança um erro se a resposta for 4xx ou 5xx
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao chamar a API do Tiny: {e}")
        return jsonify({"status": "erro", "mensagem": f"Falha na comunicação com a API do Tiny: {e}"}), 500

    if data['retorno']['status'] == 'ERRO':
        erro_tiny = data['retorno']['erros'][0]['erro']
        print(f"Erro retornado pela API do Tiny: {erro_tiny}")
        return jsonify({"status": "erro", "mensagem": f"API do Tiny retornou um erro: {erro_tiny}"}), 400

    produtos = data['retorno']['produtos']
    print(f"Encontrados {len(produtos)} produtos na página 1.")

    # 2. Salvar dados no Banco de Dados
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "erro", "mensagem": "Não foi possível conectar ao banco de dados."}), 500
    
    try:
        with conn.cursor() as cursor:
            for item in produtos:
                produto = item['produto']
                insert_product_in_db(cursor, produto)
            conn.commit() # Efetiva todas as inserções/atualizações no banco
            print(f"-> Sucesso! {len(produtos)} produtos foram sincronizados com o banco de dados.")
    except Exception as e:
        conn.rollback() # Desfaz as alterações em caso de erro
        print(f"Erro ao salvar no banco de dados: {e}")
        return jsonify({"status": "erro", "mensagem": f"Ocorreu um erro no banco de dados: {e}"}), 500
    finally:
        conn.close() # Sempre fecha a conexão

    return jsonify({"status": "sucesso", "produtos_sincronizados": len(produtos)})

# Este bloco permite que o Render inicie a aplicação.
if __name__ == "__main__":
    # Apenas para teste local, o Render usa o Gunicorn para iniciar.
    app.run()
    
