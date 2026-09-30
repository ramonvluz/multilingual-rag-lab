# Multilingual RAG Lab

[English](README.md) | [Português (Brasil)](README.pt-BR.md)

Laboratório de Retrieval-Augmented Generation (RAG) multilíngue orientado por
avaliação, com documentos e perguntas em português brasileiro, inglês e espanhol,
incluindo retrieval cross-lingual. Combina embeddings locais, busca vetorial e
lexical, evidências rastreáveis e geração grounded opcional.

Este README é uma porta de entrada em português. O [README em inglês](README.md)
é a documentação técnica canônica; contratos, configurações e procedimentos
detalhados permanecem em inglês para evitar duplicação de manutenção.

## O que o projeto demonstra

- Arquitetura leve de ports-and-adapters, separando casos de uso de integrações.
- Ingestão idempotente de múltiplos formatos, com identidade SHA-256 e persistência
  dos originais, que permitem reconstruir o índice.
- Separação entre retrieval experimental, avaliado em nível de documento, e o
  contexto usado pela geração operacional.
- Avaliação reproduzível com Golden Dataset versionado, resultados por query,
  citações por chunk e abstention explícita quando não há evidência suficiente.

## Stack e arquitetura

Python 3.12, FastAPI e uv compõem a aplicação. Docling faz o parsing e seu
HybridChunker produz chunks estruturais e token-aware. O embedding local é
`Qwen/Qwen3-Embedding-0.6B`, executado em CPU no ambiente de referência.
Qdrant 1.19.1 armazena os vetores dense e sparse; FastEmbed `Qdrant/bm25` fornece
a representação lexical consultada no próprio Qdrant. Gemini é opcional para
geração grounded. Docker/Compose, pytest, Ruff, mypy e CI apoiam a execução e as
verificações de engenharia.

As entradas HTTP/CLI acionam casos de uso por interfaces, com adapters para
filesystem, parsing, modelos e Qdrant. As fontes operacionais são a fonte de
verdade; o índice é derivado e reconstruível. Reindex é explícito: uma collection
candidata é validada antes da promoção pelo alias `rag_active`, com manifest
persistente e preservação do índice anterior. Não há auto-reindex no startup.

## Corpus oficial

O [corpus v1.0.0](data/corpus/v1.0.0/manifest.json) contém **24 documentos
sintéticos** em PT-BR, inglês e espanhol, nos formatos PDF, DOCX, HTML, Markdown,
CSV e XLSX.

- `data/corpus/v1.0.0`: dataset oficial versionado e congelado.
- `runtime/documents`: cópias operacionais persistidas pela ingestão.
- Qdrant: índice derivado; as avaliações oficiais registram **189 pontos**.

O comando `ingest-corpus` valida manifest e arquivos antes de usar o mesmo caso de
uso da API. Executá-lo novamente reconhece documentos já ingeridos sem duplicação.

## Retrieval para geração operacional

O contexto de `QueryKnowledge` é construído nesta ordem:

1. Dense `top_k` com a pergunta original.
2. Sparse/BM25 `top_k` com a pergunta original.
3. Sparse/BM25 suplementar `top_k` com remoção de diacríticos via Unicode NFKD,
   somente quando a normalização muda a pergunta.
4. União deduplicada por `chunk_id`, preservando a primeira ocorrência.

Não há RRF nem reranker nesse caminho. O `top_k` padrão é 5 por branch; a pergunta
original e toda a união são enviadas ao LLM. A ordem de `sources` é a de construção
do contexto, não um ranking global. `retrieval_method` identifica a origem;
scores Dense e BM25 não são comparáveis entre si.

Gemini deve citar IDs de chunks recuperados e retornar exatamente
`INSUFFICIENT_EVIDENCE` quando a evidência for insuficiente. O sentinel ou a ausência
de qualquer citação recuperada válida produz abstention, preservando `sources` e
esvaziando `cited_chunk_ids`. IDs inventados são ignorados. Sem LLM configurado,
a API continua retornando evidências, mas se abstém de gerar uma resposta.
Validar IDs não equivale a verificar semanticamente todas as afirmações do modelo.

## Avaliação Golden V1

O [Golden V1](evaluation/datasets/golden_v1.jsonl) tem **48 queries**: 44 answerable
e 4 unanswerable. O ground truth é binário e **document-level**, com IDs estáveis
DOC-001 a DOC-024, resolvidos para os IDs operacionais SHA-256 durante a avaliação.
Chunks são convertidos em um ranking de documentos únicos, preservando a primeira
ocorrência, antes do cálculo das métricas.

| Variante | Pipeline experimental |
|---|---|
| A — Dense | Dense |
| B — Hybrid | Dense + BM25 + RRF |
| C — Hybrid + reranker | Dense + BM25 + RRF + Qwen3-Reranker-0.6B |

Essas variantes pertencem apenas à avaliação, não são opções da API pública e não
substituem a união usada na geração operacional. A/B são o default da CLI e do
wrapper oficial. C é experimental e exige seleção explícita.

Recall@1/@3/@5, MRR@10 e nDCG@5/@10 são macro-médias sobre as 44 answerable,
mantendo todos os documentos relevantes nas queries multi-document. As quatro
unanswerable ficam fora das métricas positivas e não são recuperadas pelo harness;
isso não é uma avaliação de abstention. Os relatórios incluem cortes por tipo de
query e idioma. A latência mean/p50/p95 é warm-state, após warm-up não medido,
excluindo inicialização dos modelos.

## Resultados de referência da V1

A [run-001](evaluation/results/retrieval-v1-run-001.json) permanece como benchmark
de referência. Ambiente: Docker CPU-only, Intel i5-8365U e 32 GB de RAM.
Valores arredondados a quatro casas para qualidade e uma para latência:

| Métrica — run-001 | Dense (A) | Hybrid (B) |
|---|---:|---:|
| Recall@1 | 0.6402 | 0.6061 |
| Recall@3 | 0.8561 | 0.7500 |
| Recall@5 | 0.9015 | 0.8523 |
| MRR@10 | 0.8186 | 0.7578 |
| nDCG@5 | 0.8197 | 0.7622 |
| nDCG@10 | 0.8398 | 0.7964 |
| Latência média (ms) | 1298.3 | 1294.9 |
| p50 (ms) | 1301.7 | 1290.8 |
| p95 (ms) | 1756.7 | 1809.7 |

Dense obteve métricas agregadas de qualidade superiores nesta execução e é o
baseline de referência, sem implicar superioridade universal. Hybrid permanece
experimental e teve vantagem no recorte de queries exatas. Consulte o
[resumo técnico](evaluation/reports/retrieval_v1_summary.md) para os demais recortes.

### Reprodução pós-freeze: run-002

A [run-002](evaluation/results/retrieval-v1-run-002.json), executada após o freeze
`e3d56f5`, é evidência de reprodutibilidade da release, não um novo benchmark principal.
Dense reproduziu exatamente os rankings document-level e as métricas de qualidade
das 44 answerable. Hybrid preservou Recall@1/@3/@5 agregado; 14/44 rankings mudaram,
mas 13 dessas 14 queries mantiveram suas métricas. Só Q-024 mudou métricas de
qualidade, com o documento relevante DOC-013 passando da posição 4 para 5.
Q-021 e Q-034 também mudaram a composição do top-10.

A [comparação oficial](evaluation/reports/retrieval_v1_comparison.md) detalha as
pequenas diferenças de MRR/nDCG e as latências observadas. A causa da variação
Hybrid não foi estabelecida. Duas runs não demonstram determinismo absoluto;
latência menor na run-002 não comprova melhoria de performance. Cache, warm state,
SO e condições térmicas não foram controlados estatisticamente.

C não tem resultado oficial completo: a tentativa anterior foi interrompida por
custo computacional excessivo e mostrou-se operacionalmente inviável na máquina
CPU-only de referência. Continua experimental; não foi necessária nova execução
de C para o fechamento.

## Limitações

- Corpus sintético pequeno e recortes com poucas queries limitam generalizações.
- Encontrar o documento correto não garante recuperar o chunk que contém a resposta.
- O benchmark de retrieval não mede a qualidade completa de geração, cobertura de
  afirmações, entailment semântico ou qualidade de abstention. Section-level é futuro.
- Latências são observações da máquina de referência, não promessas de desempenho.
- A API é uma demonstração local. Não deve ser exposta publicamente sem controles
  adicionais de autenticação, autorização, uploads e operação.

## Início rápido

Para **um ambiente novo**, use Docker Engine/Desktop com Compose v2 ou superior.
Execute na raiz do repositório. No PowerShell, use `Copy-Item .env.example .env`
no lugar de `cp`; não sobrescreva um `.env` privado existente. Em Linux nativo,
prepare primeiro as permissões do bind mount conforme o [README canônico](README.md#quick-start).

```bash
cp .env.example .env
docker compose up -d
# Somente na inicialização de um ambiente novo, criar o índice ativo vazio:
docker compose exec app rag-lab reindex
docker compose restart app
docker compose exec app rag-lab ingest-corpus /app/data/corpus/v1.0.0
```

Não reconstrua um índice existente apenas para consultar ou avaliar. O startup não
cria o índice; antes da inicialização explícita, readiness retorna 503.
A API fica em `http://127.0.0.1:8000`, com OpenAPI em `/docs`, liveness em
`/health/live` e readiness em `/health/ready`. Use `POST /query` com
`{"question":"..."}`. Gemini é opcional; nunca versione sua chave ou o `.env`.

Para desenvolvimento local, os pré-requisitos adicionais são Python 3.12 e uv;
o setup é `uv sync --locked --all-groups`. GNU Make é opcional. Consulte o README
canônico para configuração, comandos equivalentes, permissões e recuperação.
Os resultados oficiais já existem: uma nova avaliação exige autorização separada
e outro arquivo de saída, sem sobrescrever run-001 ou run-002.

## Documentação técnica canônica

- [README em inglês](README.md): contratos completos, execução e configuração.
- [Arquitetura](docs/architecture.md): componentes, responsabilidades e recuperação.
- [ADRs](docs/decisions/): decisões técnicas e seus adendos históricos.
- [Resumo da avaliação V1](evaluation/reports/retrieval_v1_summary.md).
- [Comparação run-001 × run-002](evaluation/reports/retrieval_v1_comparison.md).

## Licença

MIT, copyright 2026 Ramon Valgas Luz. Consulte [LICENSE](LICENSE).
