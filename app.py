import os
from flask import Flask

# Cria a aplicação principal
app = Flask(__name__)

# Obtém o token da API do Tiny a partir das variáveis de ambiente (o jeito seguro)
# Ainda não configuramos isso no Render, então por enquanto ele será None
TINY_API_TOKEN = os.getenv("TINY_API_TOKEN")

# Endpoint de teste para verificar se o robô está "vivo"
@app.route("/")
def hello_world():
    """
    Página inicial que mostra se o serviço está no ar e se o token foi carregado.
    """
    if TINY_API_TOKEN:
        status = "Token da API do Tiny foi encontrado!"
    else:
        status = "Token da API do Tiny AINDA NÃO foi configurado."
        
    return f"<h1>Robô Sincronizador Tiny</h1><p>Status: Online.</p><p>{status}</p>"

# Função principal para buscar os produtos (ainda vazia)
def sincronizar_produtos():
    print("Iniciando a sincronização de produtos...")
    
    if not TINY_API_TOKEN:
        print("ERRO: Token da API não configurado. Impossível sincronizar.")
        return

    # --- Lógica para buscar produtos na API do Tiny virá aqui ---
    print("Lógica de sincronização ainda não implementada.")
    
    # --- Lógica para salvar no banco de dados virá aqui ---
    print("Sincronização de produtos concluída.")


# Este bloco permite que o Render inicie a aplicação.
if __name__ == "__main__":
    # Apenas para teste local, o Render usa o Gunicorn para iniciar.
    app.run()

