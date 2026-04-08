"""
Ferramenta: Vault GitHub - Acesso ao Obsidian via GitHub API com cache
Lê arquivos do vault Obsidian sincronizado no GitHub - funciona 24/7 no servidor
Autor: VENTURI-AI

CONFIGURAÇÃO:
1. No OpenWebUI, vá em Admin → Settings → Environment Variables
2. Adicione: GITHUB_TOKEN = seu_token_aqui
3. O token precisa ter acesso ao repositório privado do seu vault
"""

import requests
import json
import base64
import os
from typing import Optional, List
from pydantic import Field


class VaultGitHubAPI:
    """Acessa vault Obsidian via GitHub API com cache local"""
    
    def __init__(self, repo: str = "isaquecarlo/obsidian-vault", subpasta: str = "VENTURI-AI", branch: str = "master", token: Optional[str] = None):
        self.repo = repo
        self.subpasta = subpasta
        self.branch = branch
        # Pega token de parâmetro ou variável de ambiente
        self.token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_PAT")
        if not self.token:
            raise Exception(
                "GITHUB_TOKEN não configurado. "
                "Vá em Admin → Settings → Environment Variables e adicione GITHUB_TOKEN"
            )
        self.base_url = f"https://api.github.com/repos/{repo}"
        self.cache = {}  # Cache simples em memória
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "VENTURI-AI-Vault-Tool",
            "Authorization": f"Bearer {self.token}"
        }
    
    def _make_request(self, url: str, use_cache: bool = True) -> dict:
        """Faz request com cache e tratamento de erro robusto"""
        cache_key = url.replace("https://api.github.com", "")
        
        # Verifica cache primeiro
        if use_cache and cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            
            # Trata rate limit
            if response.status_code == 403:
                remaining = response.headers.get("X-RateLimit-Remaining", "0")
                if remaining == "0":
                    reset_time = response.headers.get("X-RateLimit-Reset", "0")
                    raise Exception(
                        f"GitHub rate limit atingido. "
                        f"Reset em {reset_time}. "
                        f"Configure GITHUB_TOKEN para mais requisições."
                    )
            
            # Trata outros erros
            if response.status_code == 404:
                raise Exception(f"Arquivo/pasta não encontrado: {url}")
            
            if response.status_code == 401:
                raise Exception("Token inválido. Verifique se GITHUB_TOKEN está correto.")
            
            if response.status_code != 200:
                raise Exception(f"Erro GitHub {response.status_code}: {response.text[:200]}")
            
            data = response.json()
            
            # Salva no cache
            if use_cache:
                self.cache[cache_key] = data
            
            return data
            
        except requests.exceptions.Timeout:
            raise Exception("Timeout ao conectar com GitHub. Tente novamente.")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Erro de conexão: {str(e)}")
    
    def _adicionar_prefixo(self, caminho: str) -> str:
        """Adiciona prefixo da subpasta se necessário"""
        if not caminho:
            return self.subpasta
        if caminho.startswith(self.subpasta + "/") or caminho == self.subpasta:
            return caminho
        return f"{self.subpasta}/{caminho}"
    
    def listar_arquivos(self, caminho: str = "") -> List[dict]:
        """Lista arquivos de uma pasta no repositório"""
        caminho_completo = self._adicionar_prefixo(caminho)
        url = f"{self.base_url}/contents/{caminho_completo}?ref={self.branch}"
        data = self._make_request(url)
        
        if not isinstance(data, list):
            raise Exception(f"'{caminho}' não é uma pasta válida")
        
        return [
            {
                "nome": item["name"],
                "tipo": "pasta" if item["type"] == "dir" else "arquivo",
                "caminho": item["path"].replace(f"{self.subpasta}/", ""),
                "tamanho": item.get("size", 0),
                "url": item["html_url"]
            }
            for item in data
        ]
    
    def ler_arquivo(self, caminho: str) -> str:
        """Lê conteúdo de um arquivo"""
        caminho_completo = self._adicionar_prefixo(caminho)
        url = f"{self.base_url}/contents/{caminho_completo}?ref={self.branch}"
        data = self._make_request(url, use_cache=False)  # Sempre pega versão atual
        
        if data.get("type") != "file":
            raise Exception(f"'{caminho}' não é um arquivo")
        
        # Decodifica conteúdo base64
        content = base64.b64decode(data["content"]).decode("utf-8")
        return content
    
    def buscar_arquivos(self, query: str, max_resultados: int = 10) -> List[dict]:
        """Busca arquivos por nome ou conteúdo"""
        resultados = []
        
        # Primeiro lista todos os arquivos
        def listar_recursivo(caminho: str = ""):
            try:
                items = self.listar_arquivos(caminho)
                for item in items:
                    if item["tipo"] == "pasta":
                        listar_recursivo(item["caminho"])
                    elif item["tipo"] == "arquivo":
                        # Verifica se o nome matcha
                        if query.lower() in item["nome"].lower():
                            resultados.append(item)
                            if len(resultados) >= max_resultados:
                                return
            except:
                pass  # Ignora pastas sem acesso
        
        listar_recursivo()
        return resultados


class Tools:
    """
    Ferramenta Vault GitHub: Acessa o vault Obsidian via GitHub API.
    Lê notas, lista pastas e busca arquivos. Funciona 24/7 no servidor.
    """
    
    def __init__(self):
        # Inicializa com repositório padrão
        self.vault = VaultGitHubAPI()
    
    def ler_nota(
        self,
        caminho_nota: str = Field(
            description="Caminho da nota no vault (ex: 'INICIO.md', 'PROJETOS/Leo/ESTADO.md')"
        )
    ) -> str:
        """
        Lê uma nota específica do vault Obsidian via GitHub.
        Retorna o conteúdo completo do arquivo.
        """
        try:
            # Limpa o caminho
            caminho = caminho_nota.strip("/")
            
            # Adiciona extensão .md se não tiver
            if "." not in caminho.split("/")[-1]:
                caminho += ".md"
            
            conteudo = self.vault.ler_arquivo(caminho)
            
            return f"✅ Arquivo: {caminho_nota}\n📁 Fonte: https://github.com/{self.vault.repo}/blob/{self.vault.branch}/{caminho}\n\n{conteudo}"
            
        except Exception as e:
            return f"❌ Erro: {str(e)}\n💡 Dica: Use 'listar_pasta' para ver os arquivos disponíveis"
    
    def listar_pasta(
        self,
        caminho_pasta: str = Field(
            default="",
            description="Caminho da pasta (deixe vazio para raiz do vault). Ex: 'PROJETOS', 'IA-DIARIO/2026-04'"
        )
    ) -> str:
        """
        Lista arquivos e pastas de uma pasta no vault Obsidian.
        Útil para navegar pela estrutura do vault.
        """
        try:
            caminho = caminho_pasta.strip("/")
            arquivos = self.vault.listar_arquivos(caminho)
            
            # Separa pastas e arquivos
            pastas = [a for a in arquivos if a["tipo"] == "pasta"]
            arqs = [a for a in arquivos if a["tipo"] == "arquivo"]
            
            resultado = f"📂 Pasta: {caminho or 'raiz'}\n"
            resultado += f"📊 Total: {len(arquivos)} itens\n\n"
            
            if pastas:
                resultado += "📁 Pastas:\n"
                for p in pastas:
                    resultado += f"  - {p['nome']}/\n"
                resultado += "\n"
            
            if arqs:
                resultado += "📄 Arquivos:\n"
                for a in arqs:
                    resultado += f"  - {a['nome']}\n"
            
            return resultado
            
        except Exception as e:
            return f"❌ Erro: {str(e)}"
    
    def buscar_vault(
        self,
        termo: str = Field(
            description="Termo para buscar nos nomes dos arquivos (ex: 'INICIO', 'LEO', 'PROJETO')"
        ),
        max_resultados: int = Field(
            default=10,
            description="Máximo de resultados (padrão: 10)"
        )
    ) -> str:
        """
        Busca arquivos no vault pelo nome.
        Útil para encontrar notas quando não sabe o caminho exato.
        """
        try:
            resultados = self.vault.buscar_arquivos(termo, max_resultados)
            
            if not resultados:
                return f"🔍 Nenhum arquivo encontrado com '{termo}'"
            
            resultado = f"🔍 Busca: '{termo}'\n"
            resultado += f"📊 Encontrados: {len(resultados)} arquivos\n\n"
            
            for item in resultados:
                resultado += f"📄 {item['caminho']}\n"
            
            resultado += f"\n💡 Use 'ler_nota' com o caminho completo para ler o arquivo"
            
            return resultado
            
        except Exception as e:
            return f"❌ Erro: {str(e)}"
