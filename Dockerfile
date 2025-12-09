# Usar uma imagem oficial do Python 3.11 como base
FROM python:3.11-slim

# Definir o diretório de trabalho dentro do container
WORKDIR /app

# Copiar o arquivo de dependências primeiro (para otimizar o cache)
COPY requirements.txt .

# Instalar as dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o resto do código do projeto para o container
COPY . .

# Expor a porta que o Gunicorn vai usar (o Render vai mapear isso)
EXPOSE 10000

# Comando para iniciar a aplicação quando o container rodar
# O Render vai sobrescrever isso com nosso Start Command, mas é uma boa prática ter
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "--timeout", "300", "app:app"]
