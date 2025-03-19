import requests
from bs4 import BeautifulSoup
import re
import os
import time
from datetime import datetime

class TJPRDiarioDownloader:
    def __init__(self, download_dir=r"C:\Users\manoel\OneDrive\AmbVir\ARQUIVOS\pdfai\00 - para leitura"):
        self.base_url = 'https://portal.tjpr.jus.br'
        self.search_url = f"{self.base_url}/e-dj/publico/diario/pesquisar.do"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        }
        self.download_dir = download_dir
        self.session = requests.Session()
        
        # Criar diretório de download se não existir
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)
            print(f"Criado diretório de download: {download_dir}")


    def download_diarios(self):
        """Baixar diários conforme solicitação do usuário"""
        # Solicitar quantidade de diários
        while True:
            try:
                num_diarios = int(input("""\n
    ╔════════════════════════════════════════════════╗
    ║           TJPR - DIÁRIO OFICIAL               ║
    ╠════════════════════════════════════════════════╣
    ║ Quantos diários você deseja baixar?           ║
    ║ Serão baixados do mais recente ao mais antigo ║
    ╚════════════════════════════════════════════════╝
    Número de diários: """))

                if num_diarios > 0:
                    break
                else:
                    print("Por favor, insira um número positivo.")
            except ValueError:
                print("Entrada inválida. Digite um número inteiro.")

        downloaded_diarios = []
        current_page = 1

        # Página inicial
        response = self.session.get(self.search_url, headers=self.headers)

        while len(downloaded_diarios) < num_diarios:
            print(f"\n=== Processando Página {current_page} ===")

            # Parsear o conteúdo da página
            soup = BeautifulSoup(response.text, 'html.parser')

            # Encontrar tabelas com diários
            tables = soup.find_all('table')

            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    if len(downloaded_diarios) >= num_diarios:
                        break

                    # Encontrar link de download
                    link = row.find('a', href=re.compile(r'javascript:downloadWindow'))
                    if not link:
                        continue

                    cells = row.find_all('td')
                    if len(cells) < 2:
                        continue

                    # Extrair informações
                    numero = cells[0].text.strip()

                    # Extrair data do código próximo ao número
                    try:
                        # Procurar em todas as células da linha
                        data_match = None
                        for cell in cells:
                            data_match = re.search(r'(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})', cell.text)
                            if data_match:
                                data = data_match.group(1)
                                break

                        # Se não encontrar, usar a coluna de data padrão
                        if not data_match:
                            data = cells[1].text.strip()
                    except Exception as e:
                        print(f"Erro ao extrair data: {e}")
                        data = cells[1].text.strip()

                    # Extrair caminho de download do JavaScript
                    download_js = link.get('href', '')
                    download_match = re.search(r"downloadWindow\('([^']+)'\)", download_js)

                    if download_match:
                        download_path = download_match.group(1)
                        full_url = f"{self.base_url}{download_path}"

                        # Formatar nome do arquivo
                        try:
                            # Tenta primeiro o formato yyyy-mm-dd
                            data_obj = datetime.strptime(data, "%Y-%m-%d")
                        except ValueError:
                            try:
                                # Se falhar, tenta o formato dd/mm/yyyy
                                data_obj = datetime.strptime(data, "%d/%m/%Y")
                            except ValueError:
                                # Se ambos falharem, usa a data atual
                                data_obj = datetime.now()
                                print(f"Erro ao processar a data '{data}' para o diário {numero}. Usando data atual.")

                        filename = f"PR_DIARIO_{numero}_{data_obj.strftime('%Y_%m_%d')}.pdf"
                        filepath = os.path.join(self.download_dir, filename)

                        # Baixar diário
                        try:
                            response_download = self.session.get(full_url, headers=self.headers)

                            if response_download.status_code == 200:
                                with open(filepath, 'wb') as f:
                                    f.write(response_download.content)

                                print(f"Baixado diário {numero} - {data}")
                                downloaded_diarios.append({
                                    'numero': numero,
                                    'data': data,
                                    'filename': filename
                                })
                        except Exception as e:
                            print(f"Erro ao baixar diário {numero}: {e}")

                if len(downloaded_diarios) >= num_diarios:
                    break

            # Se atingiu o número desejado de diários, interromper
            if len(downloaded_diarios) >= num_diarios:
                break

            # Navegar para próxima página
            current_page += 1
            form_data = {
                'pageNumber': str(current_page),
                'sortColumn': 'dataVeiculacao',
                'sortOrder': 'DESC'
            }

            try:
                response = self.session.post(self.search_url, headers=self.headers, data=form_data)
            except Exception as e:
                print(f"Erro ao navegar para próxima página: {e}")
                break

        return downloaded_diarios


# Executar download
if __name__ == '__main__':
    downloader = TJPRDiarioDownloader()
    diarios_baixados = downloader.download_diarios()

    print("\n╔════════════════════════════════════════════════╗")
    print("║               RESUMO DOWNLOAD                ║")
    print("╠════════════════════════════════════════════════╣")
    for diario in diarios_baixados:
        print(f"║ Diário {diario['numero']} - {diario['data']} ║")
    print(f"╠════════════════════════════════════════════════╣")
    print(f"║ Total de diários baixados: {len(diarios_baixados)}             ║")
    print("╚════════════════════════════════════════════════╝")