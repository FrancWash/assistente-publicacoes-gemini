import json
import os
from dotenv import load_dotenv
import google.generativeai as genai

# Definição das ferramentas (tools) para o Germini usar no Function Calling
tools = [
    {
        "function_declarations": [
            {
                "name": "get_book_details",
                "description": "Obter detalhes de um livro pelo titulo.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "book_title": {
                            "type": "string",
                            "description": "Titulo do livro",
                        }
                    },
                    "required": ["book_title"],
                },
            },
            {
                "name": "find_stores_selling_book",
                "description": "Encontrar livrarias que vendem o livro, pelo título e cidade (opcional). Se cidade não for informada, restornar lojas online.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "book_title": {
                            "type": "string",
                            "description": "Título do livro",
                        },
                        "city": {"type": "string", "description": "Nome da cidade"},
                    },
                    "required": ["book_title"],
                },
            },
        ]
    }
]

# caminho do arquivo (relativo à pasta src/)
CATALOG_PATH = os.path.join(os.path.dirname(__file__), "..", "mock_catalog.json")


# Função para carregar o catálogo de livros a partir do arquivo JSON
def carregar_catalogo():
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalogo = json.load(f)
    return catalogo


# Função para buscar detalhes de um livro pelo título no catálogo
def get_book_details(catalogo, book_title):
    for book in catalogo["books"]:
        if book["title"].lower() == book_title.lower():
            return {
                "title": book["title"],
                "author": book["author"],
                "imprint": book["imprint"],
                "release_date": book["release_date"],
                "synopsis": book["synopsis"],
            }
    return None


# Função para encontrar lojas físicas (por cidade) ou online onde o livro está disponível
def find_stores_selling_book(catalogo, book_title, city=None):
    for book in catalogo["books"]:
        if book["title"].lower() == book_title.lower():
            if city and city in book["availability"]:
                return book["availability"][city]
            elif "Online" in book["availability"]:
                return book["availability"]["Online"]
            else:
                return []
    return []


# (opcional) Chat Simulado - só para estudo, não é usado no desafio
# def chat_loop():
#    print("\nBem-vindo ao Assistente Editorial Elo! Digite 'sair' para encerras.\n")
#    historico = []
#    while True:
#        user_msg = input("Você: ").strip()
#        if user_msg.lower() == "sair":
#            print("Até logo!")
#            break
#        historico.append({"role": "user", "text": user_msg})
#        resposta = f"[Simulação] Você perguntou: '{user_msg}'"
#        print("Assistente:", resposta)
#        historico.append({"role": "assistant", "text": resposta})


# Loop principal do chat: gerencia a conversa, chama o Gemini e executa funções via Function Calling
def chat_loop_gemini(model, catalogo):
    print("\nBem-vindo ao Assistente Editorial Elo! Digite 'sair' para encerrar.\n")
    historico = []
    ultimo_livro = None  # Para contexto

    while True:
        user_msg = input("Você: ").strip()
        if user_msg.lower() == "sair":
            print("Até logo!")
            break

        historico.append({"role": "user", "parts": [user_msg]})

        # Chama o Gemini (com tools)
        response = model.generate_content(historico, tools=tools)

        content = response.candidates[0].content

        # Checa se Gemini quer chamar função
        fc = None
        for part in content.parts:
            if hasattr(part, "function_call") and part.function_call:
                fc = part.function_call
                break

        if fc:
            # Pega nome e argumentos da função
            nome_func = fc.name
            args = fc.args

            # Executa a função Python correspondente
            if nome_func == "get_book_details":
                resultado = get_book_details(catalogo, args["book_title"])
                ultimo_livro = args["book_title"]
            elif nome_func == "find_stores_selling_book":
                book_title = args.get("book_title", ultimo_livro)
                city = args.get("city")
                resultado = find_stores_selling_book(catalogo, book_title, city)
            else:
                resultado = {"erro": "função não encontrada"}

            # Adiciona resposta da função ao histórico
            historico.append(
                {
                    "role": "function",
                    "name": nome_func,
                    "parts": [json.dumps(resultado)],
                }
            )

            # Rechama o Gemini para ele gerar resposta final para o usuário
            response = model.generate_content(historico, tools=tools)
            content = response.candidates[0].content

            # Pega a resposta final (texto)
        resposta_final = ""
        for part in content.parts:
            if hasattr(part, "text") and part.text:
                resposta_final += part.text

        print("Assistente:", resposta_final.strip())
        historico.append({"role": "model", "parts": [resposta_final.strip()]})


if __name__ == "__main__":
    catalogo = carregar_catalogo()
    print(f"Total de livros encontrados: {len(catalogo['books'])}")
    # Mostra os títulos como teste
    for livro in catalogo["books"][:5]:
        print(f"- {livro['title']}")

    # Teste das funções
    print("\n--- Teste buscar detalhes do livro ---")
    detalhes = get_book_details(catalogo, "A Abelha")
    print(detalhes)

    print("\n--- Teste buscar lojas (São Paulo) ---")
    lojas_sp = find_stores_selling_book(catalogo, "A Abelha", city="São Paulo")
    print(lojas_sp)

    print("\n--- Teste buscar lojas (Onloine) ---")
    lojas_online = find_stores_selling_book(catalogo, "A Abelha")
    print(lojas_online)

    # Carregar variáveis de ambiente
    load_dotenv()
    API_KEY = os.getenv("GEMINI_API_KEY")

    if API_KEY:
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel("gemini-1.5-pro-latest", tools=tools)
        try:
            chat_loop_gemini(model, catalogo)
        except Exception as e:
            print("\n[ERRO GEMINI]:", e)
            print(
                "\n[AVISO]: Você atingiu o limite gratuito da API Gemini. Tente novamente mais tarde."
            )
    else:
        print("\n[GEMINI] APY KEY não encontrada. Verifique o arquivo .env.")
