import os
from dotenv import load_dotenv
from openai import OpenAI
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, List
import glob
import json
from datetime import datetime
from pathlib import Path

# Carrega as variáveis de ambiente
load_dotenv()

# Inicializa a API do FastAPI
app = FastAPI(title="Normalizador de Editais de Leilão")

# Configura os templates
templates = Jinja2Templates(directory="templates")

class Lote(BaseModel):
    numero_lote: Optional[str] = None
    descricao_dos_bens: Optional[str] = None
    valor_de_avaliacao: Optional[str] = None
    data_de_avaliacao: Optional[str] = None
    valor_atualizado: Optional[str] = None
    data_atualizado: Optional[str] = None
    localizacao_dos_bens: Optional[str] = None

class EditalNormalizado(BaseModel):
    id_do_edital: Optional[str] = None
    data_de_publicacao: Optional[str] = None
    numero_de_publicacao: Optional[str] = None
    tipo_do_processo: Optional[str] = None
    tipo_do_bem: Optional[str] = None
    tribunal_ou_local: Optional[str] = None
    numero_do_processo: Optional[str] = None
    executado: Optional[str] = None
    leiloeiro: Optional[str] = None
    site_do_leiloeiro: Optional[str] = None
    taxa_de_comissaoarrematacao: Optional[str] = None
    taxa_de_comissaoadjudicacao: Optional[str] = None
    data_do_1_leilao: Optional[str] = None
    hora_do_1_leilao: Optional[str] = None
    data_do_2_leilao: Optional[str] = None
    hora_do_2_leilao: Optional[str] = None
    data_demais_pracas: Optional[str] = None
    percentual_do_1_leilao: Optional[str] = None
    percentual_do_2_leilao: Optional[str] = None
    percentual_das_demais_pracas: Optional[str] = None
    divida_e_onusdebito_executado: Optional[str] = None
    divida_e_onusdebitos_sobre_o_bem: Optional[str] = None
    divida_e_onus_onus: Optional[str] = None
    informacoes_adicionais: Optional[str] = None
    lotes: List[Lote] = []

# Diretórios de entrada e saída
INPUT_DIR = r"C:\Users\manoel\OneDrive\AmbVir\ARQUIVOS\pdfai\02 - arquivos com leilões\separados"
OUTPUT_DIR = r"C:\Users\manoel\OneDrive\AmbVir\ARQUIVOS\pdfai\02 - arquivos com leilões\norm"
AUX_DIR = os.path.join(OUTPUT_DIR, "resto")
PROCESSED_DIR = os.path.join(INPUT_DIR, "normalizados")

# Garante que os diretórios de saída existem
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(AUX_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

def normalizar_edital(texto: str) -> str:
    """
    Envia o texto do edital para o modelo GPT-4 e recebe uma versão normalizada
    com as informações relevantes extraídas.
    """
    try:
        # Log do texto recebido
        print(f"Texto do edital recebido (primeiros 200 caracteres): {texto[:200]}")
        
        # Prompt detalhado com a estrutura esperada
        prompt = f"""Analise o seguinte edital de leilão judicial e extraia as informações relevantes.
        
        Se alguma informação não estiver disponível no edital, retorne null para o campo.
        
        Ao processar o edital, lembre-se da hierarquia de classificação dos bens:
        1. Um EDITAL pode conter MÚLTIPLOS LOTES (Lote 01, Lote 02, Lote 03, etc.)
        2. Cada LOTE pode conter UM ou MAIS BENS, indicados pela notação "Y/Z":
           - "Lote XX - 1/1": O lote XX contém apenas um bem
           - "Lote XX - 1/3", "Lote XX - 2/3", "Lote XX - 3/3": O lote XX contém três bens relacionados
        Mantenha esta estrutura exata no campo "lote" do JSON para cada bem identificado.

        IMPORTANTE: Retorne o JSON exatamente no formato abaixo, mantendo a estrutura e os nomes dos campos:

        {{
          "leiloes": [
            {{
              "numero_de_publicacao": ,
              "data_de_publicacao": ,
              "lote": ,
              "id_do_edital": ,
              "tipo_do_processo": ,
              "tribunal_ou_local": ,
              "tipo_do_bem": ,
              "executado": ,
              "numero_do_processo": ,
              "leiloeiro": ,
              "site_do_leiloeiro": ,
              "taxa_de_comissao": ,
              "data_do_1_leilao": ,
              "hora_do_1_leilao": ,
              "data_do_2_leilao": ,
              "hora_do_2_leilao": ,
              "data_demais_pracas": ,
              "percentual_do_1_leilao": ,
              "percentual_do_2_leilao": ,
              "percentual_das_demais_pracas": ,
              "descricao_dos_bens": ,
              "descricao_secundara_dos_bens": ,
              "valor_de_avaliacao": ,
              "data_de_avaliacao": ,
              "valor_atualizado": ,
              "data_atualizado": ,
              "divida_e_onus": ,
              "localizacao_dos_bens": ,
              "informacoes_adicionais":   
            }}
          ]
        }}

        Edital:
        {texto}
        """
        
        # Salva o prompt em um arquivo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prompt_filename = os.path.join(AUX_DIR, f"prompt_{timestamp}.txt")
        with open(prompt_filename, 'w', encoding='utf-8') as f:
            f.write(prompt)
        print(f"Prompt salvo em: {prompt_filename}")
        
        response = client.chat.completions.create(
            model="ft:gpt-4o-mini-2024-07-18:pdfaimanoel::BC5Cvkip",
            messages=[
                {
                    "role": "system", 
                    "content": "Você é um assistente especializado em extrair informações de editais de leilão. Sua tarefa é analisar o texto completo do edital e gerar um resumo estruturado em formato JSON seguindo o padrão estabelecido."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ]
        )
        
        # Log da resposta bruta
        resultado = response.choices[0].message.content
        print(f"Resposta bruta do modelo: {resultado}")
        
        # Salva a resposta bruta em um arquivo
        response_filename = os.path.join(AUX_DIR, f"response_{timestamp}.txt")
        with open(response_filename, 'w', encoding='utf-8') as f:
            f.write(resultado)
        print(f"Resposta salva em: {response_filename}")
        
        return resultado
    
    except Exception as e:
        print(f"Erro ao processar edital: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao processar o edital: {str(e)}")

def salvar_edital_normalizado(nome_arquivo: str, resultado: str):
    """
    Salva o edital normalizado em formato TXT
    """
    nome_base = Path(nome_arquivo).stem
    novo_nome = f"{nome_base}_NORM.txt"
    caminho_saida = os.path.join(OUTPUT_DIR, novo_nome)
    
    # Salva exatamente o que o modelo retornou
    with open(caminho_saida, 'w', encoding='utf-8') as f:
        f.write(resultado)

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """
    Página inicial com lista de arquivos disponíveis
    """
    arquivos = glob.glob(os.path.join(INPUT_DIR, "*.txt"))
    arquivos = [os.path.basename(f) for f in arquivos]
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "arquivos": arquivos}
    )

@app.post("/normalizar/{nome_arquivo}")
async def normalizar_arquivo(nome_arquivo: str):
    """
    Normaliza um arquivo específico
    """
    try:
        print(f"Iniciando processamento do arquivo: {nome_arquivo}")
        caminho_arquivo = os.path.join(INPUT_DIR, nome_arquivo)
        
        # Verifica se o arquivo existe
        if not os.path.exists(caminho_arquivo):
            raise HTTPException(status_code=404, detail=f"Arquivo não encontrado: {nome_arquivo}")
        
        # Log do tamanho do arquivo
        tamanho = os.path.getsize(caminho_arquivo)
        print(f"Tamanho do arquivo: {tamanho} bytes")
        
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            texto = f.read()
            print(f"Arquivo lido com sucesso. Tamanho do texto: {len(texto)} caracteres")
        
        # Salva o texto original
        nome_base = Path(nome_arquivo).stem
        texto_original_path = os.path.join(AUX_DIR, f"{nome_base}_ORIGINAL.txt")
        with open(texto_original_path, 'w', encoding='utf-8') as f:
            f.write(texto)
        print(f"Texto original salvo em: {texto_original_path}")
        
        resultado = normalizar_edital(texto)
        salvar_edital_normalizado(nome_arquivo, resultado)
        
        # Move o arquivo processado para a pasta de processados
        caminho_destino = os.path.join(PROCESSED_DIR, nome_arquivo)
        os.rename(caminho_arquivo, caminho_destino)
        print(f"Arquivo movido para: {caminho_destino}")
        
        return {"status": "success", "message": f"Arquivo normalizado salvo como {nome_arquivo}_NORM.txt"}
    
    except Exception as e:
        print(f"Erro no endpoint normalizar_arquivo: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Inicializa o cliente OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 