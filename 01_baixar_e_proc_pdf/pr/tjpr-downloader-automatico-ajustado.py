import os
import time
import datetime
import json
import logging
import traceback
import sys
import schedule
from bs4 import BeautifulSoup
import requests
import re
import concurrent.futures

# Configuração de logging
log_format = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("tjpr_autodownloader")

# Pasta onde os PDFs serão baixados
DEFAULT_DOWNLOAD_DIR = r"C:\Users\manoel\OneDrive\AmbVir\ARQUIVOS\pdfai\00 - para leitura"

# Pasta onde o script e arquivos de registro ficarão
SCRIPT_DIR = r"C:\Users\manoel\OneDrive\AmbVir\pdfai\2 - Dwld_diario"

# Arquivo de registro de downloads
DOWNLOAD_REGISTRY_FILE = os.path.join(SCRIPT_DIR, "tjpr_download_registry.json")

# Última edição conhecida
LAST_KNOWN_EDITION = 3850


class DiarioDownloader:
    def __init__(self, download_dir=DEFAULT_DOWNLOAD_DIR, script_dir=SCRIPT_DIR):
        self.base_url = 'https://portal.tjpr.jus.br'
        self.search_url = f"{self.base_url}/e-dj/publico/diario/pesquisar.do"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        }
        self.download_dir = download_dir
        self.script_dir = script_dir
        self.session = requests.Session()
        
        # Create directories if they don't exist
        for directory in [download_dir, script_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)
                logger.info(f"Diretório criado: {directory}")
            
        # Configurar arquivo de log no diretório do script
        self.log_file = os.path.join(script_dir, "tjpr_autodownload.log")
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setFormatter(logging.Formatter(log_format))
        logger.addHandler(file_handler)
        
        # Inicializar registro de downloads
        self.registry_file = DOWNLOAD_REGISTRY_FILE
        self.registry = self._load_registry()
        
        # Verificar se precisamos inicializar o registro com a última edição conhecida
        if self.registry.get("last_edition", 0) == 0:
            self.registry["last_edition"] = LAST_KNOWN_EDITION
            logger.info(f"Registro inicializado com a última edição conhecida: {LAST_KNOWN_EDITION}")
            self._save_registry()
    
    def _load_registry(self):
        """Carrega o registro de downloads a partir do arquivo JSON"""
        if os.path.exists(self.registry_file):
            try:
                with open(self.registry_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Erro ao carregar registro de downloads: {e}")
                logger.error(traceback.format_exc())
                return {"last_check": None, "last_edition": LAST_KNOWN_EDITION, "downloaded_files": []}
        else:
            return {"last_check": None, "last_edition": LAST_KNOWN_EDITION, "downloaded_files": []}
    
    def _save_registry(self):
        """Salva o registro de downloads no arquivo JSON"""
        try:
            with open(self.registry_file, 'w', encoding='utf-8') as f:
                json.dump(self.registry, f, ensure_ascii=False, indent=2)
            logger.info(f"Registro de downloads salvo em: {self.registry_file}")
        except Exception as e:
            logger.error(f"Erro ao salvar registro de downloads: {e}")
            logger.error(traceback.format_exc())
    
    def initialize_session(self):
        """Initialize session and get cookies if needed"""
        try:
            logger.info("Inicializando sessão...")
            response = self.session.get(self.search_url, headers=self.headers)
            if response.status_code != 200:
                logger.error(f"Falha ao inicializar sessão: código {response.status_code}")
                return False
                
            logger.info("Sessão inicializada com sucesso")
            return True
        except Exception as e:
            logger.error(f"Erro ao inicializar sessão: {e}")
            logger.error(traceback.format_exc())
            return False

    def get_all_editions(self, max_editions=20):
        """Get information for available editions up to max_editions"""
        # Initialize session
        if not self.initialize_session():
            logger.error("Falha ao inicializar sessão, abortando")
            return []
            
        editions = []
        editions_found = 0
        page = 1
        max_pages = 5  # Limitamos a 5 páginas para verificação diária
        
        logger.info(f"Buscando até {max_editions} edições mais recentes...")
        
        while editions_found < max_editions and page <= max_pages:
            try:
                logger.info(f"Requisitando página {page}...")
                params = {'numeroPagina': page}
                response = self.session.get(self.search_url, params=params, headers=self.headers)
                
                if response.status_code != 200:
                    logger.error(f"Falha ao obter página {page}: código {response.status_code}")
                    break
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find rows with download links
                edition_rows = []
                tables = soup.find_all('table')
                
                for table in tables:
                    rows = table.find_all('tr')
                    for row in rows:
                        # Check if row has download link
                        link = row.find('a', href=re.compile(r'javascript:downloadWindow'))
                        if link:
                            edition_rows.append(row)
                
                if not edition_rows:
                    logger.info(f"Nenhuma edição encontrada na página {page}")
                    break
                
                logger.info(f"Encontradas {len(edition_rows)} possíveis edições na página {page}")
                
                # Process edition rows
                page_editions = []
                for row in edition_rows:
                    cells = row.find_all('td')
                    if len(cells) < 2:
                        continue
                        
                    numero = cells[0].text.strip() if len(cells) > 0 else ""
                    data = cells[1].text.strip() if len(cells) > 1 else ""
                    
                    # Find download link
                    link = row.find('a', href=re.compile(r'javascript:downloadWindow'))
                    
                    if not (numero and data and link):
                        continue
                        
                    # Extract download path
                    download_js = link.get('href', '')
                    download_path_match = re.search(r"downloadWindow\('([^']+)'\)", download_js)
                    
                    if download_path_match:
                        download_path = download_path_match.group(1)
                        full_url = f"{self.base_url}{download_path}"
                        
                        # Format date for filename - com prefixo PR_
                        clean_data = data.replace('/', '_').replace('-', '_').replace(' ', '_')
                        filename = f"PR_diario_{numero}_{clean_data}.pdf"
                        
                        # Criar identificador único para este diário
                        edition_id = f"{numero}_{clean_data}"
                        
                        # Adicionar apenas se o número for um inteiro
                        try:
                            edition_number = int(numero)
                            page_editions.append({
                                'id': edition_id,
                                'url': full_url,
                                'filename': filename,
                                'numero': numero,
                                'edition_number': edition_number,
                                'data': data
                            })
                        except ValueError:
                            logger.warning(f"Ignorando edição com número inválido: {numero}")
                
                # Add new editions to the main list
                for edition in page_editions:
                    editions.append(edition)
                    editions_found += 1
                    
                    if editions_found >= max_editions:
                        break
                
                if editions_found >= max_editions:
                    break
                
                page += 1
                time.sleep(1)  # Be nice to the server
                
            except Exception as e:
                logger.error(f"Erro ao processar página {page}: {e}")
                logger.error(traceback.format_exc())
                page += 1
                time.sleep(2)
        
        logger.info(f"Total de edições encontradas: {len(editions)}")
        return editions

    def download_file(self, url, filename):
        """Download a file from the given URL and save it with the given filename"""
        filepath = os.path.join(self.download_dir, filename)
        
        # Skip if file already exists
        if os.path.exists(filepath):
            logger.info(f"Arquivo já existe: {filename}")
            return True
            
        try:
            logger.info(f"Baixando: {filename}")
            response = self.session.get(url, headers=self.headers, stream=True)
            
            if response.status_code != 200:
                logger.error(f"Erro ao baixar {filename}: código {response.status_code}")
                return False
                
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # Verify file was downloaded and has content
            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                filesize_kb = os.path.getsize(filepath) / 1024
                logger.info(f"Baixado: {filename} ({filesize_kb:.1f} KB)")
                return True
            else:
                logger.error(f"Erro: Arquivo baixado está vazio")
                if os.path.exists(filepath):
                    os.remove(filepath)
                return False
            
        except Exception as e:
            logger.error(f"Erro ao baixar {filename}: {e}")
            logger.error(traceback.format_exc())
            if os.path.exists(filepath):
                os.remove(filepath)
            return False

    def check_and_download_new_editions(self):
        """Verifica e baixa novas edições não registradas no histórico"""
        logger.info("=" * 60)
        logger.info(f"Verificando novas edições em {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)
        
        # Atualizar timestamp de verificação
        self.registry["last_check"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Obter edições disponíveis mais recentes
        editions = self.get_all_editions(max_editions=20)  # Verificamos apenas as 20 mais recentes por vez
        
        if not editions:
            logger.warning("Nenhuma edição encontrada para verificação")
            self._save_registry()
            return []
        
        # Ordenar edições por número (decrescente)
        editions = sorted(editions, key=lambda x: int(x['numero']), reverse=True)
        
        # Verificar a edição mais recente
        latest_edition = int(editions[0]['numero'])
        if latest_edition > self.registry["last_edition"]:
            logger.info(f"Nova edição mais recente encontrada: {latest_edition} (anterior: {self.registry['last_edition']})")
            self.registry["last_edition"] = latest_edition
        
        # Identificar edições novas que não estão no registro
        downloaded_ids = set([entry["id"] for entry in self.registry["downloaded_files"]])
        new_editions = [edition for edition in editions if edition["id"] not in downloaded_ids]
        
        if not new_editions:
            logger.info("Nenhuma edição nova encontrada para download")
            self._save_registry()
            return []
        
        logger.info(f"Encontradas {len(new_editions)} novas edições para download")
        
        # Baixar novas edições
        downloaded = []
        for edition in new_editions:
            try:
                logger.info(f"Processando edição {edition['numero']} de {edition['data']}")
                
                # Verificar se o arquivo já existe
                filepath = os.path.join(self.download_dir, edition['filename'])
                if os.path.exists(filepath):
                    logger.info(f"Arquivo já existe: {edition['filename']}")
                    success = True
                else:
                    # Baixar o arquivo
                    success = self.download_file(edition['url'], edition['filename'])
                
                if success:
                    # Adicionar ao registro
                    download_entry = {
                        "id": edition["id"],
                        "numero": edition["numero"],
                        "data": edition["data"],
                        "filename": edition["filename"],
                        "download_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    self.registry["downloaded_files"].append(download_entry)
                    downloaded.append(edition)
                    logger.info(f"Edição {edition['numero']} baixada e registrada com sucesso")
                else:
                    logger.error(f"Falha ao baixar edição {edition['numero']}")
                
            except Exception as e:
                logger.error(f"Erro ao processar edição {edition['numero']}: {e}")
                logger.error(traceback.format_exc())
        
        # Salvar registro atualizado
        self._save_registry()
        
        # Resumo
        logger.info(f"Download concluído: {len(downloaded)}/{len(new_editions)} novas edições baixadas")
        return downloaded

    def verify_missing_editions(self, limit=170):
        """Verifica edições que podem estar faltando no registro"""
        logger.info("=" * 60)
        logger.info(f"Verificando edições ausentes em {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)
        
        # Obter todas as edições disponíveis
        all_editions = self.get_all_editions(max_editions=limit)
        
        if not all_editions:
            logger.warning("Nenhuma edição encontrada para verificação")
            return []
        
        # Identificar edições ausentes do registro
        downloaded_ids = set([entry["id"] for entry in self.registry["downloaded_files"]])
        missing_editions = [edition for edition in all_editions if edition["id"] not in downloaded_ids]
        
        if not missing_editions:
            logger.info("Nenhuma edição ausente encontrada")
            return []
        
        logger.info(f"Encontradas {len(missing_editions)} edições ausentes")
        
        # Baixar edições ausentes com processamento paralelo
        downloaded = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            # Submeter tarefas de download
            future_to_edition = {
                executor.submit(self._download_missing_edition, edition): edition 
                for edition in missing_editions
            }
            
            # Processar resultados
            for i, future in enumerate(concurrent.futures.as_completed(future_to_edition)):
                edition = future_to_edition[future]
                try:
                    result = future.result()
                    if result:
                        downloaded.append(edition)
                    
                    logger.info(f"Progresso: {i+1}/{len(missing_editions)} ({((i+1)/len(missing_editions))*100:.1f}%)")
                    
                except Exception as e:
                    logger.error(f"Erro ao baixar edição {edition['numero']}: {e}")
                    logger.error(traceback.format_exc())
        
        # Verificar edição mais recente encontrada
        latest_numbers = [int(e["numero"]) for e in all_editions]
        if latest_numbers:
            latest_edition = max(latest_numbers)
            if latest_edition > self.registry["last_edition"]:
                self.registry["last_edition"] = latest_edition
                logger.info(f"Atualizada última edição para: {latest_edition}")
        
        # Salvar registro atualizado
        self._save_registry()
        
        # Resumo
        logger.info(f"Verificação concluída: {len(downloaded)}/{len(missing_editions)} edições ausentes baixadas")
        return downloaded
    
    def _download_missing_edition(self, edition):
        """Baixa uma edição ausente e atualiza o registro"""
        try:
            logger.info(f"Baixando edição ausente {edition['numero']} de {edition['data']}")
            
            # Verificar se o arquivo já existe
            filepath = os.path.join(self.download_dir, edition['filename'])
            if os.path.exists(filepath):
                logger.info(f"Arquivo já existe: {edition['filename']}")
                success = True
            else:
                # Baixar o arquivo
                success = self.download_file(edition['url'], edition['filename'])
            
            if success:
                # Adicionar ao registro
                download_entry = {
                    "id": edition["id"],
                    "numero": edition["numero"],
                    "data": edition["data"],
                    "filename": edition["filename"],
                    "download_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                # Thread-safe update of registry
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    ex.submit(self._update_registry, download_entry)
                
                logger.info(f"Edição ausente {edition['numero']} baixada com sucesso")
                return True
            else:
                logger.error(f"Falha ao baixar edição ausente {edition['numero']}")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao baixar edição ausente {edition['numero']}: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def _update_registry(self, entry):
        """Atualiza o registro de forma thread-safe"""
        self.registry["downloaded_files"].append(entry)


def run_daily_check():
    """Executa a verificação diária de novos diários"""
    download_dir = DEFAULT_DOWNLOAD_DIR
    script_dir = SCRIPT_DIR
    
    print(f"Iniciando verificação diária em {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Pasta de downloads: {download_dir}")
    print(f"Pasta de logs e registros: {script_dir}")
    
    try:
        downloader = DiarioDownloader(download_dir, script_dir)
        
        # Verificar e baixar novas edições
        new_editions = downloader.check_and_download_new_editions()
        
        # Mostrar resumo
        if new_editions:
            print(f"\n{len(new_editions)} novos diários foram baixados:")
            for edition in new_editions:
                print(f"- Diário {edition['numero']} de {edition['data']}")
        else:
            print("\nNenhuma nova edição encontrada.")
        
    except Exception as e:
        logger.error(f"Erro durante a verificação diária: {e}")
        logger.error(traceback.format_exc())
        print(f"\nErro durante verificação: {e}")


def verify_all_missing():
    """Verifica e baixa todas as edições ausentes"""
    download_dir = DEFAULT_DOWNLOAD_DIR
    script_dir = SCRIPT_DIR
    
    print(f"Iniciando verificação completa em {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Pasta de downloads: {download_dir}")
    print(f"Pasta de logs e registros: {script_dir}")
    print("Esta operação pode levar vários minutos...")
    
    try:
        downloader = DiarioDownloader(download_dir, script_dir)
        
        # Verificar e baixar edições ausentes
        missing_editions = downloader.verify_missing_editions(limit=170)
        
        # Mostrar resumo
        if missing_editions:
            print(f"\n{len(missing_editions)} diários ausentes foram baixados.")
        else:
            print("\nNenhuma edição ausente encontrada. O registro está completo.")
        
    except Exception as e:
        logger.error(f"Erro durante a verificação completa: {e}")
        logger.error(traceback.format_exc())
        print(f"\nErro durante verificação: {e}")


def schedule_daily_checks(hour="09:00"):
    """Programa verificações diárias em um horário específico"""
    schedule.every().day.at(hour).do(run_daily_check)
    
    print(f"Verificação diária programada para às {hour}")
    print(f"Pasta de downloads: {DEFAULT_DOWNLOAD_DIR}")
    print(f"Pasta de logs e registros: {SCRIPT_DIR}")
    print("Pressione Ctrl+C para interromper o programa")
    
    try:
        # Executar verificação imediata
        run_daily_check()
        
        while True:
            schedule.run_pending()
            time.sleep(60)  # Verifica a cada minuto
    except KeyboardInterrupt:
        print("\nPrograma interrompido pelo usuário")


def print_help():
    """Exibe ajuda sobre como usar o script"""
    print("\nTJPR - Download Automático de Diários Oficiais")
    print("=" * 50)
    print(f"\nPasta de downloads: {DEFAULT_DOWNLOAD_DIR}")
    print(f"Pasta de logs e registros: {SCRIPT_DIR}")
    print(f"Última edição conhecida: {LAST_KNOWN_EDITION}")
    print("\nOpções disponíveis:")
    print("  --check       Verifica e baixa novos diários disponíveis")
    print("  --verify-all  Verifica e baixa todos os diários ausentes (até 170)")
    print("  --schedule    Programa verificações diárias automáticas")
    print("  --hour=HH:MM  Define o horário da verificação diária (usar com --schedule)")
    print("  --help        Exibe esta ajuda")
    print("\nExemplos:")
    print("  python tjpr_autodownload.py --check")
    print("  python tjpr_autodownload.py --verify-all")
    print("  python tjpr_autodownload.py --schedule --hour=09:00")


def main():
    """Função principal que processa os argumentos e executa as ações"""
    # Criar diretório do script se não existir
    if not os.path.exists(SCRIPT_DIR):
        try:
            os.makedirs(SCRIPT_DIR)
            print(f"Diretório do script criado: {SCRIPT_DIR}")
        except Exception as e:
            print(f"Erro ao criar diretório do script: {e}")
    
    if len(sys.argv) < 2 or "--help" in sys.argv:
        print_help()
        return
    
    if "--check" in sys.argv:
        run_daily_check()
    
    elif "--verify-all" in sys.argv:
        verify_all_missing()
    
    elif "--schedule" in sys.argv:
        # Verificar se há um horário especificado
        hour = "09:00"  # Horário padrão
        for arg in sys.argv:
            if arg.startswith("--hour="):
                hour = arg.split("=")[1]
                break
        
        schedule_daily_checks(hour)
    
    else:
        print("Opção inválida. Use --help para ver as opções disponíveis.")


if __name__ == "__main__":
    main()
