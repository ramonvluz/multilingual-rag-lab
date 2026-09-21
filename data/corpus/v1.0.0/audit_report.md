# Auditoria do corpus

**Status:** PASS
**Documentos:** 24
**Seções estáveis:** 186
**Palavras extraíveis sem XLSX:** 17800
**Estimativa:** 178 chunks de 100 palavras ou 119 de 150 palavras, antes de overlap e tratamento tabular.

## Distribuições

- Idiomas: {'pt-BR': 12, 'en': 8, 'es': 4}
- Formatos: {'md': 5, 'html': 5, 'docx': 5, 'pdf': 5, 'csv': 3, 'xlsx': 1}
- Categorias: {'produto_e_funcionalidades': 4, 'suporte_e_troubleshooting': 4, 'seguranca_autenticacao_acesso': 3, 'operacoes_e_runbooks': 3, 'release_notes': 3, 'planos_limites_sla': 3, 'incidentes_postmortems': 2, 'politicas_procedimentos_internos': 2}
- Desafios: {'semantic': 15, 'ambiguous': 14, 'multi-context': 12, 'exact': 13, 'mixed': 9, 'cross-lingual': 10, 'versions': 5, 'conflict': 4}

## Limitações

- Synthetic corpus only
- One XLSX workbook
- No images or scanned documents
- Repeated governance sections add realistic template noise
