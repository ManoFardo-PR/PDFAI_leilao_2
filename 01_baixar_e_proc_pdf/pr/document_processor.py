import os
import shutil
import pdfplumber
import re
import logging
from tqdm import tqdm

# Configuração do caminho base
BASE_DIR = r"C:\Users\manoel\OneDrive\AmbVir\ARQUIVOS\pdfai"

# Configuração do logging
logging.basicConfig(filename=os.path.join(BASE_DIR, 'processing_log.txt'), level=logging.INFO,
                    format='%(asctime)s:%(levelname)s:%(message)s')

def extract_publication_date(text):
    match = re.search(r'Curitiba, (\d{1,2}) de (\w+) de (\d{4})', text)
    if match:
        day, month, year = match.groups()
        month_number = {
            'janeiro': '01', 'fevereiro': '02', 'março': '03', 'abril': '04',
            'maio': '05', 'junho': '06', 'julho': '07', 'agosto': '08',
            'setembro': '09', 'outubro': '10', 'novembro': '11', 'dezembro': '12'
        }.get(month.lower(), '00')
        return f"{day.zfill(2)}/{month_number}/{year}"
    return "Data não encontrada"

def extract_publication_number(text):
    match = re.search(r'Edição nº (\d+)', text)
    return match.group(1) if match else "Número não encontrado"

def preprocess_text(text):
    text = re.sub(r'Curitiba, \d{1,2} de \w+ de \d{4} - Edição nº \d+', '', text)
    text = re.sub(r'Diário Eletrônico do Tr[^\n]*', '', text)
    text = re.sub(r'ribunal de Justiça do Paraná', '', text)
    text = re.sub(r'- \d+ -', '', text)
    text = re.sub(r'\n-+\n', '\n', text)
    text = re.sub(r'\(\#Pag\) -', '', text)
    text = re.sub(r'\n+', ' ', text)
    return text

def extract_blocks(text):
    blocks = re.split(r'(?=IDMATERIA\d+IDMATERIA)', text)
    result = []
    for block in blocks:
        match = re.search(r'(IDMATERIA\d+IDMATERIA)([\s\S]*)', block)
        if match:
            id_materia, content = match.groups()
            result.append((id_materia, content.strip()))
    return result

def classify_blocks(blocks, keywords=['leilão', 'leilões']):
    leiloes, decretos = [], []
    for id_materia, block in blocks:
        if any(keyword in block.lower() for keyword in keywords):
            leiloes.append((id_materia, block))
        else:
            decretos.append((id_materia, block))
    return leiloes, decretos

def write_blocks_to_file(blocks, filepath, pub_date, pub_number):
    with open(filepath, 'w', encoding='utf-8') as file:
        for block_number, (id_materia, block) in enumerate(blocks, 1):
            id_number = id_materia.replace('IDMATERIA', '')
            header = f"""************************************************************
ID: {id_number}
Data Pub.: {pub_date}
Número Pub.: {pub_number}
Número Bloco: {block_number:05d}

"""
            file.write(header)
            file.write(block + '\n\n')

def process_pdf_file(pdf_path):
    text = ''
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in tqdm(pdf.pages, desc="Processing PDF", unit="page", leave=False):
                largura = page.width
                coluna_esquerda = page.crop((0, page.height * 0.015, largura * 0.488, page.height * 0.96))
                coluna_direita = page.crop((largura * 0.488, page.height * 0.015, largura, page.height * 0.96))
                texto_esquerda = coluna_esquerda.extract_text() or ''
                texto_direita = coluna_direita.extract_text() or ''
                text += texto_esquerda + ' ' + texto_direita
    except Exception as e:
        logging.error(f"Erro ao processar o arquivo PDF: {e}")
    return text


def process_single_file(selected_file):
    processed_directory = os.path.join(BASE_DIR, '01 - arquivos lidos')
    leiloes_directory = os.path.join(BASE_DIR, '02 - arquivos com leilões')
    decretos_directory = os.path.join(BASE_DIR, '03 - arquivos com decretos')

    text = process_pdf_file(selected_file)
    if text:
        pub_date = extract_publication_date(text)
        pub_number = extract_publication_number(text)
        text_cleaned = preprocess_text(text)

        # Extrair o índice
        index_match = re.search(r'(Índice de Publicação[\s\S]*?)(?=IDMATERIA)', text_cleaned)
        index_text = index_match.group(1).strip() if index_match else "Índice não encontrado"

        blocks = extract_blocks(text_cleaned)

        # Salvar o arquivo de texto completo
        full_text_filename = os.path.splitext(os.path.basename(selected_file))[0] + '.txt'
        full_text_path = os.path.join(processed_directory, full_text_filename)

        with open(full_text_path, 'w', encoding='utf-8') as full_file:
            full_file.write(f"Data de Publicação: {pub_date}\n")
            full_file.write(f"Número da Publicação: {pub_number}\n\n")
            full_file.write("ÍNDICE\n")
            full_file.write(f"{index_text}\n\n")
            full_file.write("************************************************************\n\n")

            for block_number, (id_materia, block) in enumerate(blocks, 1):
                id_number = id_materia.replace('IDMATERIA', '')
                header = f"""************************************************************
ID: {id_number}
Data Pub.: {pub_date}
Número Pub.: {pub_number}
Número Bloco: {block_number:05d}

"""
                full_file.write(header)
                full_file.write(block + '\n\n')

        # Continuar com a separação de leilões e decretos
        leiloes, decretos = classify_blocks(blocks)

        write_blocks_to_file(leiloes, os.path.join(leiloes_directory, f'Leilões_{pub_date.replace("/", "_")}.txt'),
                             pub_date, pub_number)
        write_blocks_to_file(decretos, os.path.join(decretos_directory, f'Decretos_{pub_date.replace("/", "_")}.txt'),
                             pub_date, pub_number)

        # Mover o arquivo PDF processado
        shutil.move(selected_file, os.path.join(processed_directory, os.path.basename(selected_file)))

        logging.info(f"Processamento concluído para {os.path.basename(selected_file)}.")
        print(f"Processamento concluído para {os.path.basename(selected_file)}.")
        print(f"Arquivo de texto completo salvo em: {full_text_path}")
    else:
        logging.error(f"Falha ao processar o arquivo {selected_file}.")
"""def process_single_file(selected_file):
    processed_directory = os.path.join(BASE_DIR, '01 - arquivos lidos')
    leiloes_directory = os.path.join(BASE_DIR, '02 - arquivos com leilões')
    decretos_directory = os.path.join(BASE_DIR, '03 - arquivos com decretos')

    text = process_pdf_file(selected_file)
    if text:
        pub_date = extract_publication_date(text)
        pub_number = extract_publication_number(text)
        text_cleaned = preprocess_text(text)
        blocks = extract_blocks(text_cleaned)
        leiloes, decretos = classify_blocks(blocks)

        write_blocks_to_file(leiloes, os.path.join(leiloes_directory, f'Leilões_{pub_date.replace("/", "_")}.txt'),
                             pub_date, pub_number)
        write_blocks_to_file(decretos, os.path.join(decretos_directory, f'Decretos_{pub_date.replace("/", "_")}.txt'),
                             pub_date, pub_number)

        shutil.move(selected_file, os.path.join(processed_directory, os.path.basename(selected_file)))
        logging.info(f"Processamento concluído para {os.path.basename(selected_file)}.")
        print(f"Processamento concluído para {os.path.basename(selected_file)}.")
    else:
        logging.error(f"Falha ao processar o arquivo {selected_file}.")
"""
def process_all_files():
    read_directory = os.path.join(BASE_DIR, '00 - para leitura')
    pdf_files = [f for f in os.listdir(read_directory) if f.endswith('.pdf')]

    for pdf_file in tqdm(pdf_files, desc="Processando arquivos PDF"):
        process_single_file(os.path.join(read_directory, pdf_file))

def main():
    read_directory = os.path.join(BASE_DIR, '00 - para leitura')
    choice = input("Deseja processar todos os arquivos? (S/N): ").strip().lower()
    if choice == 's':
        process_all_files()
    else:
        pdf_files = [f for f in os.listdir(read_directory) if f.endswith('.pdf')]
        if not pdf_files:
            print("Não há arquivos para serem lidos.")
            return
        print("Arquivos disponíveis para leitura:")
        for idx, file in enumerate(pdf_files, 1):
            print(f"{idx}. {file}")
        choice = input("Digite o número do arquivo que deseja processar: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(pdf_files):
            selected_file = os.path.join(read_directory, pdf_files[int(choice) - 1])
            process_single_file(selected_file)
        else:
            print("Escolha inválida.")

if __name__ == "__main__":
    main()
