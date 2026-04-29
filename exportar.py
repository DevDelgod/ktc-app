import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd

# Passo 1: Mostrar o "Crachá" de acesso
cred = credentials.Certificate("chave-firebase.json")
firebase_admin.initialize_app(cred)

# Passo 2: Conectar ao banco de dados
db = firestore.client()

# Passo 3: Buscar a coleção desejada (Mude 'treinos' para o nome da sua coleção no Firebase)
print("Buscando dados no Firebase...")
colecao_treinos = db.collection('treinos').stream()

# Passo 4: Organizar os documentos em uma lista
dados_extraidos = []
for documento in colecao_treinos:
    linha = documento.to_dict() # Transforma o formato do Firebase em um dicionário do Python
    linha['id_documento'] = documento.id # Salva o ID original do Firebase por segurança
    dados_extraidos.append(linha)

# Passo 5: Converter para tabela e salvar para o Power BI
if len(dados_extraidos) > 0:
    tabela = pd.DataFrame(dados_extraidos)
    tabela.to_csv("dados_para_powerbi.csv", index=False, encoding='utf-8')
    print("Sucesso! O arquivo 'dados_para_powerbi.csv' foi criado na sua pasta.")
else:
    print("Nenhum dado encontrado na coleção. Verifique se o nome está correto.")