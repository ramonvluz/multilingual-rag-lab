# Golden Dataset V1 — resumo

Conjunto controlado de 48 perguntas para comparar posteriormente Dense (A), Dense+BM25+RRF (B) e a mesma combinação com reranker (C). Abrange pt-BR, en e es; 8 semantic, 6 exact, 6 mixed, 8 cross_lingual, 6 multi_context, 6 versioning, 4 ambiguous e 4 unanswerable.

O ground truth oficial é **document-level**, em `relevant_documents` com IDs DOC-001–DOC-024: 44 consultas respondíveis e 4 lacunas sem documentos positivos. A análise positiva de Recall@k, MRR e nDCG deve excluir as quatro lacunas; elas ficam para avaliação posterior de abstenção. O dataset permite cortes por tipo, idioma e direção cross-lingual.

Limitações: relevância binária por documento pode recompensar um trecho errado do documento certo; o conjunto é pequeno e sintético; perguntas ambíguas têm uma intenção documentada, mas outras leituras podem ser plausíveis; respostas de referência não constituem benchmark de geração. **Section-level** é evolução futura. Nenhuma variante ou métrica foi executada nesta entrega.
