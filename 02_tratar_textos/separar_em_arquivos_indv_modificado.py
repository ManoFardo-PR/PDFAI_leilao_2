import os
import re
import shutil
from datetime import datetime
import glob
# Importando a função do classificador de leilão
from classificador_leilao_simplificado import classificar_texto_leilao

# Configuração dos diretórios
ORIGEM_DIR = r"C:\Users\manoel\OneDrive\AmbVir\ARQUIVOS\pdfai\02 - arquivos com leilões"
DESTINO_DIR = r"C:\Users\manoel\OneDrive\AmbVir\ARQUIVOS\pdfai\02 - arquivos com leilões\separados"
DESTINO_NAO_LEILAO_DIR = r"C:\Users\manoel\OneDrive\AmbVir\ARQUIVOS\pdfai\02 - arquivos com leilões\classificado não leilão"

# Certifica-se de que os diretórios de destino existem
if not os.path.exists(DESTINO_DIR):
    os.makedirs(DESTINO_DIR)
if not os.path.exists(DESTINO_NAO_LEILAO_DIR):
    os.makedirs(DESTINO_NAO_LEILAO_DIR)


def extrair_informacoes(texto):
    """
    Extrai o ID do documento e data de publicação do cabeçalho do bloco.
    Retorna uma tupla (estado, id_doc, data_publicacao, num_publicacao, num_bloco)
    """
    # Define o estado como PR para todos os documentos
    estado = "PR"

    # Padrão para encontrar ID do documento - busca em todo o texto
    padrao_id = r'ID\s*[:\.]\s*(\d+)'
    match_id = re.search(padrao_id, texto, re.IGNORECASE)
    id_doc = match_id.group(1) if match_id else "000000"  # Default se não encontrar

    # Padrão para encontrar data de publicação - busca em todo o texto com padrões mais flexíveis
    padroes_data = [
        r'Data\s+Pub\.\s*[:\.]\s*(\d{2}/\d{2}/\d{4})',
        r'DATA\s+DE\s+PUBLICAÇÃO\s*[:\.]\s*(\d{2}/\d{2}/\d{4})',
        r'DATA\s+PUB\.\s*[:\.]\s*(\d{2}/\d{2}/\d{4})',
        r'PUBLICADO\s+EM\s*[:\.]\s*(\d{2}/\d{2}/\d{4})',
        r'Data\s+Pub\s*[:\.]\s*(\d{2}/\d{2}/\d{4})',
        r'(\d{2}/\d{2}/\d{4})'  # Tenta encontrar qualquer data no formato DD/MM/AAAA
    ]

    data_publicacao = None
    for padrao in padroes_data:
        match_data = re.search(padrao, texto, re.IGNORECASE)
        if match_data:
            data_publicacao = match_data.group(1)
            break

    # Se não encontrou nenhuma data, usa a data atual como fallback
    if not data_publicacao:
        data_publicacao = datetime.now().strftime("%d/%m/%Y")

    # Obter número de publicação - padrões mais flexíveis
    padroes_num_pub = [
        r'Número\s+Pub\.\s*[:\.]\s*(\d+)',
        r'NÚMERO\s+PUB\.\s*[:\.]\s*(\d+)',
        r'Número\s+Pub\s*[:\.]\s*(\d+)',
        r'Nº\s+(?:da\s+)?Publ?(?:icação)?\s*[:\.]\s*(\d+)'
    ]

    num_publicacao = ""
    for padrao in padroes_num_pub:
        match_num_pub = re.search(padrao, texto, re.IGNORECASE)
        if match_num_pub:
            num_publicacao = match_num_pub.group(1)
            break

    # Obter número do bloco - padrões mais flexíveis
    padroes_num_bloco = [
        r'Número\s+Bloco\s*[:\.]\s*(\d+)',
        r'NÚMERO\s+BLOCO\s*[:\.]\s*(\d+)',
        r'Nº\s+(?:do\s+)?Bloco\s*[:\.]\s*(\d+)'
    ]

    num_bloco = ""
    for padrao in padroes_num_bloco:
        match_num_bloco = re.search(padrao, texto, re.IGNORECASE)
        if match_num_bloco:
            num_bloco = match_num_bloco.group(1)
            break

    # Analisa a data para extrair componentes (dia, mês, ano)
    try:
        dia, mes, ano = data_publicacao.split('/')
    except ValueError:
        # Se a data não estiver no formato esperado, usa a data atual
        hoje = datetime.now()
        dia, mes, ano = hoje.strftime("%d"), hoje.strftime("%m"), hoje.strftime("%Y")

    # Debug: imprime informações extraídas para cada bloco
    print(
        f"Informações extraídas: Estado={estado}, ID={id_doc}, Data={data_publicacao}, Pub={num_publicacao}, Bloco={num_bloco}")

    return estado, id_doc, (ano, mes, dia), num_publicacao, num_bloco


def processar_arquivo(caminho_arquivo):
    """
    Processa um arquivo TXT, dividindo-o em blocos delimitados por '************'
    e salvando cada bloco como um arquivo individual.
    """
    nome_arquivo_base = os.path.basename(caminho_arquivo)
    print(f"Processando arquivo: {nome_arquivo_base}")

    try:
        # Lê o arquivo original
        with open(caminho_arquivo, 'r', encoding='utf-8', errors='ignore') as arquivo:
            conteudo = arquivo.read()

        # Divide o conteúdo em blocos usando apenas sequências longas de asteriscos (12 ou mais)
        blocos = re.split(r'\*{12,}', conteudo)

        contador_blocos = 0
        contador_nao_leilao = 0
        for i, bloco in enumerate(blocos):
            bloco = bloco.strip()
            if bloco:  # Ignora blocos vazios
                contador_blocos += 1
                # Classifica se o bloco é um edital de leilão ou não
                e_leilao, pontuacao = classificar_texto_leilao(bloco)

                # Extrai informações para o nome do arquivo
                try:
                    estado, id_doc, (ano, mes, dia), num_publicacao, num_bloco = extrair_informacoes(bloco)
                except Exception as e:
                    print(f"Erro ao extrair informações do bloco {i + 1}: {str(e)}")
                    estado = "PR"
                    id_doc = f"B{i + 1}"
                    hoje = datetime.now()
                    ano, mes, dia = hoje.strftime("%Y"), hoje.strftime("%m"), hoje.strftime("%d")
                    num_publicacao = ""
                    num_bloco = ""

                # Formata o nome do arquivo conforme o padrão PR_AAAA_MM_DD_PUB_ID_BLOCK.txt
                componentes_nome = [estado, ano, mes, dia]

                # Adiciona número da publicação se disponível
                if num_publicacao:
                    componentes_nome.append(f"P{num_publicacao}")
                else:
                    componentes_nome.append("P0000")

                # Adiciona ID do documento
                componentes_nome.append(f"ID{id_doc}")

                # Adiciona número do bloco se disponível
                if num_bloco:
                    componentes_nome.append(f"B{num_bloco}")
                else:
                    componentes_nome.append(f"B{i + 1:05d}")

                # Adiciona sufixo para não-leilão se aplicável
                nome_base = "_".join(componentes_nome)

                # Determina o diretório de destino e nome do arquivo
                if not e_leilao:
                    nome_arquivo_bloco = nome_base + "_nao_leilao.txt"
                    contador_nao_leilao += 1
                    diretorio_destino = DESTINO_NAO_LEILAO_DIR
                else:
                    nome_arquivo_bloco = nome_base + ".txt"
                    diretorio_destino = DESTINO_DIR

                caminho_arquivo_bloco = os.path.join(diretorio_destino, nome_arquivo_bloco)

                # Verifica se o arquivo já existe em qualquer um dos diretórios de destino
                caminho_check_leilao = os.path.join(DESTINO_DIR, nome_base + ".txt")
                caminho_check_nao_leilao = os.path.join(DESTINO_NAO_LEILAO_DIR, nome_base + "_nao_leilao.txt")

                # Evita sobrescrever arquivos existentes em qualquer diretório
                contador = 1
                while (os.path.exists(caminho_arquivo_bloco) or
                       os.path.exists(caminho_check_leilao) or
                       os.path.exists(caminho_check_nao_leilao)):
                    componentes_nome_unique = componentes_nome.copy()
                    componentes_nome_unique.append(str(contador))
                    nome_base_unique = "_".join(componentes_nome_unique)

                    if not e_leilao:
                        nome_arquivo_bloco = nome_base_unique + "_nao_leilao.txt"
                    else:
                        nome_arquivo_bloco = nome_base_unique + ".txt"

                    caminho_arquivo_bloco = os.path.join(diretorio_destino, nome_arquivo_bloco)
                    caminho_check_leilao = os.path.join(DESTINO_DIR, nome_base_unique + ".txt")
                    caminho_check_nao_leilao = os.path.join(DESTINO_NAO_LEILAO_DIR,
                                                            nome_base_unique + "_nao_leilao.txt")
                    contador += 1

                # Salva o bloco como um arquivo individual
                with open(caminho_arquivo_bloco, 'w', encoding='utf-8') as arquivo_bloco:
                    arquivo_bloco.write(bloco)

                status_leilao = "NÃO é leilão" if not e_leilao else "é leilão"
                print(
                    f"  - Bloco {contador_blocos} ({status_leilao}, pontuação: {pontuacao:.2f}) salvo como: {nome_arquivo_bloco}")

        print(
            f"Concluído! {contador_blocos} blocos extraídos de {nome_arquivo_base} (Leilões: {contador_blocos - contador_nao_leilao}, Não-leilões: {contador_nao_leilao})")
        return contador_blocos, contador_nao_leilao

    except Exception as e:
        print(f"Erro ao processar o arquivo {nome_arquivo_base}: {str(e)}")
        return 0, 0


def processar_todos_arquivos():
    """
    Processa todos os arquivos TXT no diretório de origem.
    """
    # Lista todos os arquivos TXT no diretório de origem
    padrao_busca = os.path.join(ORIGEM_DIR, "*.txt")
    arquivos_txt = glob.glob(padrao_busca)

    if not arquivos_txt:
        print(f"Nenhum arquivo TXT encontrado em {ORIGEM_DIR}")
        return

    total_arquivos = len(arquivos_txt)
    total_blocos = 0
    total_nao_leilao = 0

    print(f"Encontrados {total_arquivos} arquivos para processar.")

    for i, arquivo in enumerate(arquivos_txt, 1):
        print(f"\nProcessando arquivo {i}/{total_arquivos}: {os.path.basename(arquivo)}")
        blocos_extraidos, nao_leilao = processar_arquivo(arquivo)
        total_blocos += blocos_extraidos
        total_nao_leilao += nao_leilao

    print(f"\nProcessamento concluído! Total de {total_blocos} blocos extraídos de {total_arquivos} arquivos.")
    print(f"Leilões: {total_blocos - total_nao_leilao}, Não-leilões: {total_nao_leilao}")
    print(f"Os blocos de leilão foram salvos em: {DESTINO_DIR}")
    print(f"Os blocos que não são leilão foram salvos em: {DESTINO_NAO_LEILAO_DIR}")


if __name__ == "__main__":
    print("=== Separador de Blocos de Editais de Leilão ===")
    print(f"Diretório de origem: {ORIGEM_DIR}")
    print(f"Diretório de destino para leilões: {DESTINO_DIR}")
    print(f"Diretório de destino para não-leilões: {DESTINO_NAO_LEILAO_DIR}")

    processar_todos_arquivos()