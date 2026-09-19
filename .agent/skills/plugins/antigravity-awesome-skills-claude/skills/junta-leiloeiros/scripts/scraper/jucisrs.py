"""
Scraper JUCISRS — Junta Comercial, Industrial e Servicos do Rio Grande do Sul
URL: https://sistemas.jucisrs.rs.gov.br/leiloeiros/
Metodo: httpx POST com verificacao de SSL ativa (definir JUCISRS_CA_BUNDLE para cert autoassinado)
Mecanismo real descoberto em 2026-02-25:
  - GET  https://sistemas.jucisrs.rs.gov.br/leiloeiros/
         -> retorna formulario de busca PHP/Bootstrap
  - POST https://sistemas.jucisrs.rs.gov.br/leiloeiros/busca/listar
         com Nome=Todos (retorna todos os 376 registros)
Estrutura HTML: <b><font color="#A01A14">MATRICULA</font> - NOME<br>
  separados por <hr> entre entradas
Total: 376 leiloeiros (261 ativos + 111 cancelados)
Nota: Antigo dominio jucers.rs.gov.br foi aposentado. Junta renomeada para JUCISRS.
"""
from __future__ import annotations

import logging
import os
import re
from typing import List

from .base_scraper import AbstractJuntaScraper, Leiloeiro

logger = logging.getLogger(__name__)

# Regex para extrair dados do formato plano JUCISRS
RE_MATRICULA_NOME = re.compile(r"(\d+)\s*-\s*(.+)")
RE_POSSE = re.compile(r"[Pp]osse\s*:\s*(\d{2}/\d{2}/\d{4})")
RE_TELEFONE = re.compile(r"[Tt]elefone\s*:\s*(.+)")
RE_EMAIL = re.compile(r"[Ee]-[Mm]ail\s*:\s*(.+)")
RE_PREPOSTO = re.compile(r"[Pp]reposto\s*:\s*(.+)")
RE_CEP = re.compile(r"CEP\s+([\d.]+)")
RE_CANCELADO = re.compile(r"CANCELAD|CANCELAMENTO|canc\.", re.IGNORECASE)
RE_CIDADE_UF = re.compile(r"^([A-ZÁÉÍÓÚÀÃÕÇ][A-ZÁÉÍÓÚÀÃÕÇ\s]+)\s+-\s+RS$")


class JucisrsScraper(AbstractJuntaScraper):
    estado = "RS"
    junta = "JUCISRS"
    url = "https://sistemas.jucisrs.rs.gov.br/leiloeiros/"
    url_fallback = "https://jucisrs.rs