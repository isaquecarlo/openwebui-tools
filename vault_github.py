"""
title: Vault GitHub Seguro
version: 3.0.0
description: Acessa vault Obsidian via GitHub API usando variável de ambiente. Seguro - token não exposto no código.
author: VENTURI-AI
requirements: GITHUB_TOKEN (variável de ambiente no OpenWebUI)
"""

import os
import requests
import base64
from typing import Optional
from pydantic import BaseModel, Field


class Tools:
    """Ferramentas seguras para acessar vault Obsidian via GitHub API"""
    
    def __init__(self):
        # Lê token da variável de ambiente (seguro, não exposto no código)
        self.token = os.environ.get("GITHUB_TOKEN", "")
        self.repo = "isaquecarlo/obsidian-vault"
        self.subpasta = "VENTURI-AI"
        self.branch = "master"
        self.base_url = f"https://api.github.com/repos/{self.repo}"
        
        if not self.token:
            print("⚠️  AVISO: GITHUB_TOKEN não configurado. Configure em Admin → Settings → Environment Variables")
        
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "VENTURI-AI-Vault-Tool",
            "Authorization": f"Bearer {self.token}"
        }
    
    def _make_request(self, url: str) -> dict:
        """Faz request à API do GitHub"""
        if not self.token:
            raise Exception("GITHUB_TOKEN não configurado. Configure em Admin → Settings → Environment Variables")
        
        response = requests.get(url, headers=self.headers, timeout=30)
        
        if response.status_code == 404:
            raise Exception("Arquivo/pasta não encontrado")
        if response.status_code == 401:
            raise Exception("Token inválido ou expirado")
        if response.status_code == 403:
            raise Exception("Rate limit atingido. Verifique seu token.")
        if response.status_code != 200:
            raise Exception(f"Erro GitHub {response.status_code}: {response.text[:100]}")
        
        return response.json()
    
    def _adicionar_prefixo(self, caminho: str) -> str:
        """Adiciona prefixo da subpasta se necessário"""
        if not caminho:
            return self.subpasta
        if caminho.startswith(self.subpasta + "/") or caminho == self.subpasta:
            return caminho
        return f"{self.subpasta}/{caminho}"
    
    def ler_nota(
        self,
        caminho_nota: str = Field(
            description="Caminho da nota no vault (ex: 'INICIO.md', 'PROJETOS/Leo/ESTADO.md')"
        ),
        __user__: dict = {}
    ) -> str:
        """Lê uma nota específica do vault Obsidian via GitHub"""
        try:
            caminho = caminho_nota.strip("/")
            if "." not in caminho.split("/")[-1]:
                caminho += ".md"
            
            caminho_completo = self._adicionar_prefixo(caminho)
            url = f"{self.base_url}/contents/{caminho_completo}?ref={self.branch}"
            
            data = self._make_request(url)
            content = base64.b64decode(data["content"]).decode("utf-8")
            
            return f"""📄 **{caminho_nota}**

{content}

---
✅ Nota carregada ({len(content)} caracteres)"""
            
        except Exception as e:
            return f"❌ Erro: {str(e)}"
    
    def listar_pasta(
        self,
        caminho_pasta: str = Field(
            default="",
            description="Caminho da pasta (vazio = raiz). Ex: 'PROJETOS', 'IA-DIARIO'"
        ),
        __user__: dict = {}
    ) -> str:
        """Lista arquivos e pastas do vault"""
        try:
            caminho = caminho_pasta.strip("/")
            caminho_completo = self._adicionar_prefixo(caminho)
            url = f"{self.base_url}/contents/{caminho_completo}?ref={self.branch}"
            
            data = self._make_request(url)
            
            if not isinstance(data, list):
                return "❌ Não é uma pasta válida"
            
            pastas = [item["name"] for item in data if item["type"] == "dir"]
            arquivos = [item["name"] for item in data if item["type"] == "file"]
            
            resultado = f"📁 **Pasta:** {caminho or 'raiz'}\n\n"
            
            if pastas:
                resultado += f"📂 **Pastas:**\n" + "\n".join(f"  • {p}/" for p in pastas) + "\n\n"
            
            if arquivos:
                resultado += f"📄 **Arquivos:**\n" + "\n".join(f"  • {a}" for a in arquivos) + "\n\n"
            
            resultado += f"Total: {len(pastas)} pastas, {len(arquivos)} arquivos"
            return resultado
            
        except Exception as e:
            return f"❌ Erro: {str(e)}"
    
    def buscar_vault(
        self,
        termo: str = Field(
            description="Termo para buscar (ex: 'INICIO', 'LEO', 'PROJETO')"
        ),
        max_resultados: int = Field(
            default=10,
            description="Máximo de resultados"
        ),
        __user__: dict = {}
    ) -> str:
        """Busca arquivos no vault pelo nome"""
        try:
            resultados = []
            
            def buscar_recursivo(caminho: str = ""):
                try:
                    caminho_completo = self._adicionar_prefixo(caminho)
                    url = f"{self.base_url}/contents/{caminho_completo}?ref={self.branch}"
                    data = self._make_request(url)
                    
                    if not isinstance(data, list):
                        return
                    
                    for item in data:
                        if item["type"] == "dir":
                            nova_pasta = f"{caminho}/{item['name']}".strip("/")
                            buscar_recursivo(nova_pasta)
                        elif termo.lower() in item["name"].lower():
                            resultados.append(item["path"].replace(f"{self.subpasta}/", ""))
                            if len(resultados) >= max_resultados:
                                return
                except:
                    pass
            
            buscar_recursivo()
            
            if resultados:
                return f"🔍 **Encontrados {len(resultados)} arquivos:**\n\n" + "\n".join(f"  • {r}" for r in resultados)
            else:
                return f"🔍 Nenhum arquivo encontrado com '{termo}'"
                
        except Exception as e:
            return f"❌ Erro: {str(e)}"
